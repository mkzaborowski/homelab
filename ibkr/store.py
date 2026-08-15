"""Przechowywanie zrzutów portfela i danych wprowadzanych ręcznie.

Historia dzienna daje: zmianę dzienną, wykres NAV i podział na kwartały.
Osobno trzymamy to, czego IBKR nie wie: koszyk, poziom stop-lossa i własną ocenę.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from flex import Raport

# w kontenerze montujemy /dane, lokalnie zapisujemy obok kodu
KATALOG = Path(os.environ.get("IBKR_DANE", Path(__file__).with_name("dane")))
SCIEZKA = KATALOG / "portfel.sqlite"


@contextmanager
def polacz():
    SCIEZKA.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(SCIEZKA)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def zainicjuj() -> None:
    with polacz() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS zrzuty (
            data TEXT PRIMARY KEY,          -- YYYY-MM-DD (data raportu IBKR)
            pobrano_o TEXT NOT NULL,
            konto TEXT,
            waluta TEXT,
            nav REAL,
            surowy_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meta_pozycji (   -- dane wprowadzane ręcznie
            symbol TEXT PRIMARY KEY,
            koszyk TEXT DEFAULT 'Nieprzypisane',
            ocena TEXT DEFAULT '',
            stop REAL,                      -- poziom stop-loss (zlecenie GTC w IBKR)
            notatka TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS przebiegi (      -- log uruchomień
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kiedy TEXT NOT NULL,
            ok INTEGER NOT NULL,
            komunikat TEXT
        );
        -- Flex oddaje transakcje tylko z ostatniej sesji, a zrzut dzienny je
        -- nadpisuje. Bez własnego rejestru nie da się policzyć premii za
        -- miesiąc - dlatego każde pobranie dokłada tu nowe wiersze i nic
        -- nie kasuje.
        CREATE TABLE IF NOT EXISTS transakcje (
            klucz TEXT PRIMARY KEY,         -- tradeID albo odcisk z pól transakcji
            data TEXT NOT NULL,             -- YYYY-MM-DD
            konto TEXT, symbol TEXT, opis TEXT, klasa TEXT, waluta TEXT,
            bazowy TEXT, prawo TEXT, strike REAL, wygasa TEXT,
            ilosc REAL, cena REAL, wartosc REAL, prowizja REAL,
            zysk_zrealizowany REAL, kod TEXT, otwarcie TEXT,
            dodano TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_transakcje_data ON transakcje(data);
        CREATE INDEX IF NOT EXISTS idx_transakcje_klasa ON transakcje(klasa);
        -- Alerty odkupu. Trzymamy stan, żeby nie powtarzać powiadomienia przy
        -- każdym pobraniu: alert odpala się raz, a odbezpiecza dopiero wtedy,
        -- gdy cena wróci powyżej progu.
        CREATE TABLE IF NOT EXISTS alerty (
            symbol TEXT PRIMARY KEY,
            aktywny INTEGER NOT NULL DEFAULT 0,
            pierwszy_raz TEXT,
            ostatni_raz TEXT,
            wyslano_o TEXT,
            cena REAL, cena_docelowa REAL, zysk REAL,
            powod TEXT
        );
        CREATE TABLE IF NOT EXISTS alerty_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kiedy TEXT NOT NULL,
            symbol TEXT NOT NULL,
            tresc TEXT,
            kanal TEXT,
            ok INTEGER
        );
        """)
        # agregaty trzymamy w kolumnach, żeby wykresy nie musiały parsować
        # JSON-a każdego dnia z osobna (przy 160 pozycjach robi się to kosztowne)
        kolumny = {w["name"] for w in con.execute("PRAGMA table_info(zrzuty)")}
        for nazwa in ("wartosc_pozycji", "gotowka", "koszt"):
            if nazwa not in kolumny:
                con.execute(f"ALTER TABLE zrzuty ADD COLUMN {nazwa} REAL")
        if kolumny and "wartosc_pozycji" not in kolumny:
            _uzupelnij_agregaty(con)


def _agregaty(dane: dict) -> tuple[float, float, float]:
    """Wartość pozycji, koszt i gotówka z surowego zrzutu (bez opcji)."""
    poz = [p for p in dane.get("pozycje", []) if (p.get("klasa") or "").upper() != "OPT"]
    wartosc = sum(p.get("wartosc", 0.0) for p in poz)
    koszt = sum(p.get("koszt", 0.0) for p in poz)
    gotowka = sum(g.get("konczy", 0.0) for g in dane.get("gotowka", []))
    return wartosc, koszt, gotowka


def _uzupelnij_agregaty(con) -> None:
    """Jednorazowe wyliczenie agregatów dla zrzutów zapisanych przed migracją."""
    for w in con.execute("SELECT data, surowy_json FROM zrzuty").fetchall():
        wartosc, koszt, gotowka = _agregaty(json.loads(w["surowy_json"]))
        con.execute("UPDATE zrzuty SET wartosc_pozycji=?, koszt=?, gotowka=? WHERE data=?",
                    (wartosc, koszt, gotowka, w["data"]))


def zapisz_zrzut(rap: Raport) -> str:
    """Zapisuje zrzut pod datą raportu. Ponowne pobranie tego samego dnia nadpisuje."""
    dzien = _normalizuj_date(rap.data) or date.today().isoformat()
    dane = rap.jako_slownik()
    wartosc, koszt, gotowka = _agregaty(dane)
    with polacz() as con:
        con.execute(
            "INSERT INTO zrzuty (data, pobrano_o, konto, waluta, nav, surowy_json,"
            " wartosc_pozycji, koszt, gotowka) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(data) DO UPDATE SET pobrano_o=excluded.pobrano_o, nav=excluded.nav,"
            " surowy_json=excluded.surowy_json, wartosc_pozycji=excluded.wartosc_pozycji,"
            " koszt=excluded.koszt, gotowka=excluded.gotowka",
            (dzien, datetime.now().isoformat(timespec="seconds"), rap.konto,
             rap.waluta_bazowa, rap.nav, json.dumps(dane, ensure_ascii=False),
             wartosc, koszt, gotowka),
        )
        # nowe symbole trafiają do koszyka "Nieprzypisane", żeby nie zniknęły z raportu
        for p in rap.pozycje:
            if p.symbol:
                con.execute("INSERT OR IGNORE INTO meta_pozycji (symbol) VALUES (?)", (p.symbol,))
        _zapisz_transakcje(con, dane.get("transakcje", []))
    return dzien


def _klucz_transakcji(t: dict) -> str:
    """Trwała tożsamość transakcji.

    Najlepszy jest tradeID od IBKR. Gdy go brak (starsze zrzuty albo raport
    bez tego pola), sklejamy odcisk z pól, które razem jednoznacznie opisują
    wykonanie. Musi być powtarzalny, bo przy każdym pobraniu ta sama
    transakcja ma trafić w ten sam wiersz zamiast się dublować."""
    tid = (t.get("id_transakcji") or "").strip()
    if tid:
        return f"id:{tid}"
    czesci = (t.get("konto"), t.get("symbol"), t.get("data"), t.get("ilosc"),
              t.get("cena"), t.get("wartosc"), t.get("prowizja"), t.get("poziom"))
    return "odcisk:" + "|".join(str(c) for c in czesci)


def _zapisz_transakcje(con, transakcje: list[dict]) -> int:
    """Dokłada nowe transakcje do rejestru. Zwraca liczbę faktycznie nowych."""
    nowe = 0
    teraz = datetime.now().isoformat(timespec="seconds")
    for t in transakcje:
        # ORDER i EXECUTION opisują to samo wykonanie na dwóch poziomach
        # szczegółowości - bierzemy jeden poziom, żeby nie liczyć premii dwa razy
        if (t.get("poziom") or "").upper() == "ORDER":
            continue
        k = con.execute(
            "INSERT OR IGNORE INTO transakcje (klucz, data, konto, symbol, opis, klasa,"
            " waluta, bazowy, prawo, strike, wygasa, ilosc, cena, wartosc, prowizja,"
            " zysk_zrealizowany, kod, otwarcie, dodano)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_klucz_transakcji(t), _normalizuj_date(t.get("data") or ""),
             t.get("konto"), t.get("symbol"), t.get("opis"), t.get("klasa"),
             t.get("waluta"), t.get("bazowy"), t.get("prawo"),
             t.get("strike") or 0.0, t.get("wygasa"), t.get("ilosc") or 0.0,
             t.get("cena") or 0.0, t.get("wartosc") or 0.0, t.get("prowizja") or 0.0,
             t.get("zysk_zrealizowany") or 0.0, t.get("kod"), t.get("otwarcie"), teraz))
        nowe += k.rowcount
    return nowe


def transakcje(klasa: str | None = None, od: str | None = None,
               do: str | None = None) -> list[dict]:
    """Transakcje z rejestru, rosnąco po dacie."""
    q, par = "SELECT * FROM transakcje", []
    war = []
    if klasa:
        war.append("klasa=?"); par.append(klasa)
    if od:
        war.append("data>=?"); par.append(od)
    if do:
        war.append("data<=?"); par.append(do)
    if war:
        q += " WHERE " + " AND ".join(war)
    q += " ORDER BY data, symbol"
    with polacz() as con:
        return [dict(r) for r in con.execute(q, par)]


def zakres_rejestru() -> tuple[str, str, int]:
    """Od kiedy do kiedy sięga rejestr i ile ma wierszy - potrzebne, żeby
    panel mógł uczciwie napisać, za jaki okres premia jest kompletna."""
    with polacz() as con:
        r = con.execute("SELECT MIN(data) a, MAX(data) b, COUNT(*) c FROM transakcje").fetchone()
    return (r["a"] or "", r["b"] or "", r["c"] or 0)


def _normalizuj_date(s: str) -> str:
    """IBKR podaje daty jako YYYYMMDD albo YYYY-MM-DD."""
    s = (s or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s[:10] if len(s) >= 10 else ""


def zrzut(dzien: str | None = None) -> dict | None:
    """Zrzut z podanego dnia albo najnowszy."""
    with polacz() as con:
        if dzien:
            w = con.execute("SELECT * FROM zrzuty WHERE data=?", (dzien,)).fetchone()
        else:
            w = con.execute("SELECT * FROM zrzuty ORDER BY data DESC LIMIT 1").fetchone()
        if not w:
            return None
        d = dict(w)
        d["dane"] = json.loads(d.pop("surowy_json"))
        return d


def poprzedni_zrzut(przed: str) -> dict | None:
    """Poprzedni dzień handlowy - do policzenia zmiany dziennej."""
    with polacz() as con:
        w = con.execute("SELECT * FROM zrzuty WHERE data < ? ORDER BY data DESC LIMIT 1",
                        (przed,)).fetchone()
        if not w:
            return None
        d = dict(w)
        d["dane"] = json.loads(d.pop("surowy_json"))
        return d


def historia_nav(limit: int = 400) -> list[tuple[str, float]]:
    with polacz() as con:
        w = con.execute("SELECT data, nav FROM zrzuty ORDER BY data DESC LIMIT ?",
                        (limit,)).fetchall()
    return [(r["data"], r["nav"] or 0.0) for r in reversed(w)]


def historia(limit: int = 800) -> list[dict]:
    """Szereg czasowy do wykresów - rosnąco po dacie."""
    with polacz() as con:
        w = con.execute("SELECT data, nav, wartosc_pozycji, koszt, gotowka FROM zrzuty "
                        "ORDER BY data DESC LIMIT ?", (limit,)).fetchall()
    return [{"data": r["data"], "nav": r["nav"] or 0.0,
             "wartosc": r["wartosc_pozycji"] or 0.0, "koszt": r["koszt"] or 0.0,
             "gotowka": r["gotowka"] or 0.0} for r in reversed(w)]


def wszystkie_dni() -> list[str]:
    with polacz() as con:
        return [r["data"] for r in con.execute("SELECT data FROM zrzuty ORDER BY data DESC")]


def meta() -> dict[str, dict]:
    with polacz() as con:
        return {r["symbol"]: dict(r) for r in con.execute("SELECT * FROM meta_pozycji")}


def zapisz_meta(symbol: str, *, koszyk=None, ocena=None, stop=None, notatka=None) -> None:
    with polacz() as con:
        con.execute("INSERT OR IGNORE INTO meta_pozycji (symbol) VALUES (?)", (symbol,))
        for kol, wart in (("koszyk", koszyk), ("ocena", ocena), ("stop", stop), ("notatka", notatka)):
            if wart is not None:
                con.execute(f"UPDATE meta_pozycji SET {kol}=? WHERE symbol=?", (wart, symbol))


def koszyki() -> list[str]:
    with polacz() as con:
        w = con.execute("SELECT DISTINCT koszyk FROM meta_pozycji ORDER BY koszyk").fetchall()
    return [r["koszyk"] for r in w if r["koszyk"]]


def przetworz_alerty(alerty: list[dict]) -> list[dict]:
    """Porównuje bieżące alerty z zapamiętanym stanem i zwraca te NOWE.

    Alert odpala się w chwili przekroczenia progu i milczy, dopóki cena nie
    wróci powyżej niego. Bez tego przy pobraniu co 90 minut ta sama informacja
    przychodziłaby kilkanaście razy dziennie i przestałaby cokolwiek znaczyć."""
    teraz = datetime.now().isoformat(timespec="seconds")
    biezace = {a["symbol"]: a for a in alerty}
    nowe = []
    with polacz() as con:
        stan = {r["symbol"]: dict(r) for r in con.execute("SELECT * FROM alerty")}
        for symbol, a in biezace.items():
            byl = stan.get(symbol, {}).get("aktywny", 0)
            powod = " · ".join(a["powody"])
            con.execute(
                "INSERT INTO alerty (symbol, aktywny, pierwszy_raz, ostatni_raz,"
                " cena, cena_docelowa, zysk, powod) VALUES (?,1,?,?,?,?,?,?)"
                " ON CONFLICT(symbol) DO UPDATE SET aktywny=1, ostatni_raz=excluded.ostatni_raz,"
                " cena=excluded.cena, cena_docelowa=excluded.cena_docelowa,"
                " zysk=excluded.zysk, powod=excluded.powod",
                (symbol, teraz, teraz, a["cena_teraz"], a["cena_docelowa"],
                 a["zysk"], powod))
            if not byl:
                nowe.append(a)
        # pozycje, które wyszły z progu albo zniknęły z portfela - odbezpieczamy,
        # żeby przy ponownym spadku alert mógł odezwać się jeszcze raz
        for symbol in stan:
            if symbol not in biezace:
                con.execute("UPDATE alerty SET aktywny=0 WHERE symbol=?", (symbol,))
    return nowe


def oznacz_wyslane(symbol: str, tresc: str, kanal: str, ok: bool) -> None:
    teraz = datetime.now().isoformat(timespec="seconds")
    with polacz() as con:
        con.execute("UPDATE alerty SET wyslano_o=? WHERE symbol=?", (teraz, symbol))
        con.execute("INSERT INTO alerty_log (kiedy, symbol, tresc, kanal, ok)"
                    " VALUES (?,?,?,?,?)", (teraz, symbol, tresc[:1000], kanal, 1 if ok else 0))


def stan_alertow() -> list[dict]:
    with polacz() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM alerty WHERE aktywny=1 ORDER BY ostatni_raz DESC")]


def historia_alertow(ile: int = 20) -> list[dict]:
    with polacz() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM alerty_log ORDER BY id DESC LIMIT ?", (ile,))]


def zapisz_przebieg(ok: bool, komunikat: str) -> None:
    with polacz() as con:
        con.execute("INSERT INTO przebiegi (kiedy, ok, komunikat) VALUES (?,?,?)",
                    (datetime.now().isoformat(timespec="seconds"), 1 if ok else 0, komunikat[:500]))


def ostatnie_przebiegi(ile: int = 10) -> list[dict]:
    with polacz() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM przebiegi ORDER BY id DESC LIMIT ?", (ile,))]
