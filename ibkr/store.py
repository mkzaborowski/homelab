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
        -- Dzienna historia wartości konta prosto z raportu Flex. Osobno od
        -- tabeli `zrzuty`, bo tamta ma tyle dni, ile sami zdążyliśmy pobrać
        -- (13), a ta tyle, ile obejmuje okres zapytania Flex - przy ustawieniu
        -- rocznym od razu około 250. To ona jest podstawą liczenia zmienności,
        -- obsunięcia i zwrotów za dłuższe okresy.
        -- Katalog instrumentów. Symbol nie jest stabilnym kluczem: spółki zmieniają
        -- tickery, a ten sam ticker bywa później czymś innym. conid od IBKR jest
        -- trwały, więc gdy raport go poda, staje się kluczem kanonicznym.
        CREATE TABLE IF NOT EXISTS instrumenty (
            symbol TEXT PRIMARY KEY,
            conid TEXT, isin TEXT,
            nazwa TEXT, klasa TEXT, waluta TEXT, gielda TEXT,
            mnoznik REAL DEFAULT 1,
            bazowy TEXT, strike REAL, wygasa TEXT, prawo TEXT,
            pierwszy_raz TEXT, ostatni_raz TEXT
        );
        -- Klasyfikacja rozdzielona od instrumentu, bo jedna pozycja może należeć
        -- do kilku tematów naraz z różnymi wagami. `recznie` chroni decyzje
        -- człowieka: automat nigdy nie nadpisuje wiersza z tą flagą.
        CREATE TABLE IF NOT EXISTS klasyfikacja (
            symbol TEXT NOT NULL,
            wymiar TEXT NOT NULL,        -- sektor | temat | kraj | klasa | strategia
            wartosc TEXT NOT NULL,
            waga REAL DEFAULT 1.0,
            recznie INTEGER DEFAULT 0,
            zrodlo TEXT DEFAULT '',
            zmieniono TEXT,
            PRIMARY KEY (symbol, wymiar, wartosc)
        );
        CREATE INDEX IF NOT EXISTS idx_klas_wymiar ON klasyfikacja(wymiar);
        -- Operacje gotówkowe: przelewy, dywidendy, odsetki, podatki. Przelewy
        -- są potrzebne silnikowi zwrotu (bez nich wpłata liczy się jako zysk),
        -- reszta zasila atrybucję dochodu.
        -- Liczby podane przez IBKR, trzymane wyłącznie do uzgadniania
        -- z własnymi wyliczeniami. Nigdy nie zastępują naszych metryk.
        -- Wygaśnięcia, wykonania i przypisania opcji. Domykają rozliczenie
        -- premii: kontrakt wygasły bez wartości oddaje ją w całości.
        CREATE TABLE IF NOT EXISTS zdarzenia_opcji (
            klucz TEXT PRIMARY KEY,
            symbol TEXT, bazowy TEXT, data TEXT, rodzaj TEXT, klasa TEXT,
            ilosc REAL, cena REAL, zysk_zrealizowany REAL, koszt_nabycia REAL,
            dodano TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_zdarzenia_data ON zdarzenia_opcji(data);
        -- Historia kursów instrumentów i wzorców. Ceny SKORYGOWANE o splity
        -- i dywidendy - bez tego podział akcji wygląda jak spadek o połowę
        -- i zatruwa zmienność, betę oraz wszystkie korelacje.
        CREATE TABLE IF NOT EXISTS ceny_dzienne (
            symbol TEXT NOT NULL,
            data TEXT NOT NULL,
            cena REAL NOT NULL,
            zrodlo TEXT DEFAULT '',
            PRIMARY KEY (symbol, data)
        );
        CREATE INDEX IF NOT EXISTS idx_ceny_data ON ceny_dzienne(data);
        CREATE TABLE IF NOT EXISTS uzgodnienie (
            klucz TEXT PRIMARY KEY, wartosc REAL, kiedy TEXT
        );
        CREATE TABLE IF NOT EXISTS operacje (
            klucz TEXT PRIMARY KEY,
            data TEXT NOT NULL, rodzaj TEXT NOT NULL,
            kwota REAL, waluta TEXT, symbol TEXT, opis TEXT,
            dodano TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_operacje_rodzaj ON operacje(rodzaj, data);
        CREATE TABLE IF NOT EXISTS nav_dzienny (
            data TEXT PRIMARY KEY,          -- YYYY-MM-DD
            nav REAL NOT NULL,
            gotowka REAL, akcje REAL, opcje REAL, fundusze REAL, obligacje REAL,
            dywidendy_naliczone REAL, odsetki_naliczone REAL,
            zrodlo TEXT DEFAULT 'flex',
            dodano TEXT NOT NULL
        );
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
        _zapisz_nav_dzienny(con, dane.get("historia_nav", []))
        _zapisz_operacje(con, dane.get("operacje", []))
        _zapisz_zdarzenia(con, dane.get("zdarzenia_opcji", []))
        if rap.twr_ibkr is not None:
            con.execute("INSERT INTO uzgodnienie (klucz, wartosc, kiedy) VALUES ('twr',?,?)"
                        " ON CONFLICT(klucz) DO UPDATE SET wartosc=excluded.wartosc,"
                        " kiedy=excluded.kiedy",
                        (rap.twr_ibkr, datetime.now().isoformat(timespec="seconds")))
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


def _zapisz_nav_dzienny(con, dni: list[dict]) -> int:
    """Dokłada dni z raportu. Istniejące nadpisujemy - IBKR potrafi skorygować
    wycenę wstecz, a wtedy nowsza wersja jest tą prawdziwą."""
    teraz = datetime.now().isoformat(timespec="seconds")
    ile = 0
    for d in dni:
        data = _normalizuj_date(d.get("data") or "")
        if not data or not d.get("nav"):
            continue
        con.execute(
            "INSERT INTO nav_dzienny (data, nav, gotowka, akcje, opcje, fundusze,"
            " obligacje, dywidendy_naliczone, odsetki_naliczone, dodano)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(data) DO UPDATE SET nav=excluded.nav, gotowka=excluded.gotowka,"
            " akcje=excluded.akcje, opcje=excluded.opcje, fundusze=excluded.fundusze,"
            " obligacje=excluded.obligacje, dywidendy_naliczone=excluded.dywidendy_naliczone,"
            " odsetki_naliczone=excluded.odsetki_naliczone, dodano=excluded.dodano",
            (data, d.get("nav"), d.get("gotowka"), d.get("akcje"), d.get("opcje"),
             d.get("fundusze"), d.get("obligacje"), d.get("dywidendy_naliczone"),
             d.get("odsetki_naliczone"), teraz))
        ile += 1
    return ile


def zapisz_instrumenty(pozycje: list[dict]) -> int:
    """Katalog uzupełniany przy każdym pobraniu. Pola techniczne (mnożnik, strike,
    wygaśnięcie) biorą się z raportu; klasyfikacja siedzi osobno."""
    teraz = datetime.now().isoformat(timespec="seconds")
    ile = 0
    with polacz() as con:
        for p in pozycje:
            s = p.get("symbol")
            if not s:
                continue
            klasa = (p.get("klasa") or "").upper()
            con.execute(
                "INSERT INTO instrumenty (symbol, conid, isin, nazwa, klasa, waluta,"
                " mnoznik, bazowy, strike, wygasa, prawo, pierwszy_raz, ostatni_raz)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(symbol) DO UPDATE SET"
                "  conid=COALESCE(NULLIF(excluded.conid,''), instrumenty.conid),"
                "  isin=COALESCE(NULLIF(excluded.isin,''), instrumenty.isin),"
                "  nazwa=COALESCE(NULLIF(excluded.nazwa,''), instrumenty.nazwa),"
                "  klasa=excluded.klasa, waluta=excluded.waluta,"
                "  mnoznik=excluded.mnoznik, bazowy=excluded.bazowy,"
                "  strike=excluded.strike, wygasa=excluded.wygasa,"
                "  prawo=excluded.prawo, ostatni_raz=excluded.ostatni_raz",
                (s, p.get("conid") or "", p.get("isin") or "", p.get("opis") or "",
                 klasa, p.get("waluta") or "",
                 100.0 if klasa in ("OPT", "FOP") else 1.0,
                 p.get("bazowy") or "", p.get("strike") or 0.0,
                 p.get("wygasa") or "", p.get("prawo") or "", teraz, teraz))
            ile += 1
    return ile


def instrumenty() -> dict[str, dict]:
    with polacz() as con:
        return {r["symbol"]: dict(r) for r in con.execute("SELECT * FROM instrumenty")}


def zapisz_klasyfikacje(symbol: str, wymiar: str, wartosci, waga: float = 1.0,
                        recznie: bool = False, zrodlo: str = "") -> bool:
    """Ustawia CAŁY wymiar dla symbolu naraz. Zwraca False, gdy pominięto,
    bo istnieje decyzja ręczna.

    Podmiana obejmuje cały wymiar, nie pojedynczą wartość - inaczej przy
    pozycji wielotematycznej drugi zapis kasowałby pierwszy i zostawałby
    jeden temat zamiast dwóch.

    To także cała ochrona pracy człowieka: automat nie dotknie wiersza
    z flagą `recznie`."""
    lista = [wartosci] if isinstance(wartosci, str) else list(wartosci)
    if not lista:
        return True
    teraz = datetime.now().isoformat(timespec="seconds")
    with polacz() as con:
        if not recznie:
            r = con.execute("SELECT recznie FROM klasyfikacja WHERE symbol=? AND wymiar=?",
                            (symbol, wymiar)).fetchone()
            if r and r["recznie"]:
                return False
            con.execute("DELETE FROM klasyfikacja WHERE symbol=? AND wymiar=? AND recznie=0",
                        (symbol, wymiar))
        for w in lista:
            con.execute(
                "INSERT INTO klasyfikacja (symbol, wymiar, wartosc, waga, recznie, zrodlo, zmieniono)"
                " VALUES (?,?,?,?,?,?,?)"
                " ON CONFLICT(symbol, wymiar, wartosc) DO UPDATE SET waga=excluded.waga,"
                " recznie=excluded.recznie, zrodlo=excluded.zrodlo, zmieniono=excluded.zmieniono",
                (symbol, wymiar, w, waga, 1 if recznie else 0, zrodlo, teraz))
    return True


def klasyfikacja(wymiar: str | None = None) -> dict[str, list[dict]]:
    q = "SELECT * FROM klasyfikacja"
    par = []
    if wymiar:
        q += " WHERE wymiar=?"; par.append(wymiar)
    out: dict[str, list[dict]] = {}
    with polacz() as con:
        for r in con.execute(q, par):
            out.setdefault(r["symbol"], []).append(dict(r))
    return out


def _zapisz_operacje(con, operacje: list[dict]) -> int:
    teraz = datetime.now().isoformat(timespec="seconds")
    ile = 0
    for o in operacje:
        data = _normalizuj_date(o.get("data") or "")
        if not data:
            continue
        # transactionID od IBKR jest unikalny. Odcisk z samych wartości NIE
        # wystarcza: trzy przelewy po 300 000 tego samego dnia mają identyczne
        # wszystkie pola poza identyfikatorem i zlewały się w jeden wiersz.
        tid = (o.get("id_operacji") or "").strip()
        klucz = f"id:{tid}" if tid else "odcisk:" + "|".join(
            str(o.get(k) or "") for k in ("data", "rodzaj", "kwota", "waluta", "symbol", "opis"))
        ile += con.execute(
            "INSERT OR IGNORE INTO operacje (klucz, data, rodzaj, kwota, waluta,"
            " symbol, opis, dodano) VALUES (?,?,?,?,?,?,?,?)",
            (klucz, data, o.get("rodzaj"), o.get("kwota") or 0.0, o.get("waluta"),
             o.get("symbol"), o.get("opis"), teraz)).rowcount
    return ile


def _zapisz_zdarzenia(con, zdarzenia: list[dict]) -> int:
    teraz = datetime.now().isoformat(timespec="seconds")
    ile = 0
    for z in zdarzenia:
        klucz = "|".join(str(z.get(k) or "") for k in
                         ("symbol", "data", "rodzaj", "ilosc", "cena", "zysk_zrealizowany"))
        ile += con.execute(
            "INSERT OR IGNORE INTO zdarzenia_opcji (klucz, symbol, bazowy, data, rodzaj,"
            " klasa, ilosc, cena, zysk_zrealizowany, koszt_nabycia, dodano)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (klucz, z.get("symbol"), z.get("bazowy"), _normalizuj_date(z.get("data") or ""),
             z.get("rodzaj"), z.get("klasa"), z.get("ilosc") or 0.0, z.get("cena") or 0.0,
             z.get("zysk_zrealizowany") or 0.0, z.get("koszt_nabycia") or 0.0, teraz)).rowcount
    return ile


def zdarzenia_opcji() -> list[dict]:
    with polacz() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM zdarzenia_opcji ORDER BY data")]


def zapisz_ceny(serie: dict[str, list], zrodlo: str = "") -> int:
    """Dokłada notowania. Istniejące dni nadpisujemy, bo dostawca potrafi
    skorygować kurs wstecz po splicie albo dywidendzie."""
    ile = 0
    with polacz() as con:
        for symbol, szereg in serie.items():
            for data, cena in szereg:
                con.execute(
                    "INSERT INTO ceny_dzienne (symbol, data, cena, zrodlo)"
                    " VALUES (?,?,?,?) ON CONFLICT(symbol, data) DO UPDATE SET"
                    " cena=excluded.cena, zrodlo=excluded.zrodlo",
                    (symbol, data, float(cena), zrodlo))
                ile += 1
    return ile


def ceny(symbole: list[str] | None = None, od: str | None = None) -> dict[str, list]:
    q = "SELECT symbol, data, cena FROM ceny_dzienne"
    war, par = [], []
    if symbole:
        war.append(f"symbol IN ({','.join('?' * len(symbole))})"); par += symbole
    if od:
        war.append("data >= ?"); par.append(od)
    if war:
        q += " WHERE " + " AND ".join(war)
    q += " ORDER BY symbol, data"
    out: dict[str, list] = {}
    with polacz() as con:
        for r in con.execute(q, par):
            out.setdefault(r["symbol"], []).append((r["data"], r["cena"]))
    return out


def zakres_cen() -> tuple[str, str, int, int]:
    with polacz() as con:
        r = con.execute("SELECT MIN(data) a, MAX(data) b, COUNT(*) c,"
                        " COUNT(DISTINCT symbol) s FROM ceny_dzienne").fetchone()
    return (r["a"] or "", r["b"] or "", r["c"] or 0, r["s"] or 0)


def zapisz_uzgodnienie(klucz: str, wartosc) -> None:
    if wartosc is None:
        return
    with polacz() as con:
        con.execute("INSERT INTO uzgodnienie (klucz, wartosc, kiedy) VALUES (?,?,?)"
                    " ON CONFLICT(klucz) DO UPDATE SET wartosc=excluded.wartosc,"
                    " kiedy=excluded.kiedy",
                    (klucz, float(wartosc), datetime.now().isoformat(timespec="seconds")))


def twr_ibkr() -> float | None:
    """TWR policzone przez IBKR - punkt odniesienia dla naszego silnika."""
    with polacz() as con:
        r = con.execute("SELECT wartosc FROM uzgodnienie WHERE klucz='twr'").fetchone()
    return r["wartosc"] if r else None


def operacje(rodzaj: str | None = None) -> list[dict]:
    q, par = "SELECT * FROM operacje", []
    if rodzaj:
        q += " WHERE rodzaj=?"; par.append(rodzaj)
    q += " ORDER BY data"
    with polacz() as con:
        return [dict(r) for r in con.execute(q, par)]


def wzbogac_instrumenty(lista: list[dict]) -> int:
    """Dane z SecurityInfo: conid, giełda, kraj emitenta, podkategoria."""
    ile = 0
    with polacz() as con:
        for i in lista:
            s = i.get("symbol")
            if not s:
                continue
            ile += con.execute(
                "UPDATE instrumenty SET conid=COALESCE(NULLIF(?,''), conid),"
                " isin=COALESCE(NULLIF(?,''), isin), nazwa=COALESCE(NULLIF(?,''), nazwa),"
                " gielda=COALESCE(NULLIF(?,''), gielda), mnoznik=?"
                " WHERE symbol=?",
                (i.get("conid") or "", i.get("isin") or "", i.get("nazwa") or "",
                 i.get("gielda") or "", i.get("mnoznik") or 1.0, s)).rowcount
    return ile


def nav_dzienny(limit: int = 3000) -> list[dict]:
    """Pełna dzienna historia konta, rosnąco po dacie."""
    with polacz() as con:
        w = con.execute("SELECT * FROM nav_dzienny ORDER BY data DESC LIMIT ?",
                        (limit,)).fetchall()
    return [dict(r) for r in reversed(w)]


def zakres_nav() -> tuple[str, str, int]:
    with polacz() as con:
        r = con.execute("SELECT MIN(data) a, MAX(data) b, COUNT(*) c FROM nav_dzienny").fetchone()
    return (r["a"] or "", r["b"] or "", r["c"] or 0)


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


def historia(limit: int = 3000) -> list[dict]:
    """Szereg czasowy do wykresów i statystyk okresowych - rosnąco po dacie.

    Scalamy dwa źródła. Zrzuty mają komplet (wartość, koszt, gotówka), ale tylko
    tyle dni, ile sami zdążyliśmy pobrać. `nav_dzienny` przychodzi gotowy z Flexa
    i sięga tak daleko, jak sięga okres zapytania - to on wyznacza kręgosłup
    szeregu. Gdzie mamy zrzut, dokładamy z niego koszt, bo tego Flex nie podaje."""
    with polacz() as con:
        zrzuty = {r["data"]: dict(r) for r in con.execute(
            "SELECT data, nav, wartosc_pozycji, koszt, gotowka FROM zrzuty")}
        dni = [dict(r) for r in con.execute("SELECT * FROM nav_dzienny ORDER BY data")]

    szereg: dict[str, dict] = {}
    for r in dni:
        szereg[r["data"]] = {
            "data": r["data"], "nav": r["nav"] or 0.0,
            "wartosc": (r["akcje"] or 0.0) + (r["opcje"] or 0.0),
            "koszt": 0.0, "gotowka": r["gotowka"] or 0.0,
        }
    for data, r in zrzuty.items():
        w = szereg.setdefault(data, {"data": data, "nav": 0.0, "wartosc": 0.0,
                                     "koszt": 0.0, "gotowka": 0.0})
        w["nav"] = w["nav"] or (r["nav"] or 0.0)
        w["koszt"] = r["koszt"] or 0.0
        w["wartosc"] = w["wartosc"] or (r["wartosc_pozycji"] or 0.0)
        w["gotowka"] = w["gotowka"] or (r["gotowka"] or 0.0)

    return [szereg[d] for d in sorted(szereg)][-limit:]


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
