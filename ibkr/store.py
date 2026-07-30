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
    return dzien


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


def zapisz_przebieg(ok: bool, komunikat: str) -> None:
    with polacz() as con:
        con.execute("INSERT INTO przebiegi (kiedy, ok, komunikat) VALUES (?,?,?)",
                    (datetime.now().isoformat(timespec="seconds"), 1 if ok else 0, komunikat[:500]))


def ostatnie_przebiegi(ile: int = 10) -> list[dict]:
    with polacz() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM przebiegi ORDER BY id DESC LIMIT ?", (ile,))]
