"""Testy klasyfikacji i okresów.

Klasyfikacja wygląda niewinnie, ale steruje wszystkimi ekspozycjami: błąd tutaj
przechodzi wprost do wykresów sektorowych, tematycznych i do silnika ryzyka.
Najważniejszy jest test ochrony decyzji ręcznych - bez niego automat po cichu
kasowałby pracę człowieka przy każdym pobraniu.
"""
import os
import tempfile

os.environ.setdefault("IBKR_DANE", tempfile.mkdtemp())

import klasyfikacja  # noqa: E402
import statystyki  # noqa: E402
import store  # noqa: E402

store.zainicjuj()


def _czysto():
    with store.polacz() as con:
        con.execute("DELETE FROM klasyfikacja")


POZYCJE = [
    {"symbol": "NVDA", "klasa": "STK", "wartosc": 100_000.0},
    {"symbol": "GLD", "klasa": "STK", "wartosc": 50_000.0},
    {"symbol": "NIEZNANY", "klasa": "STK", "wartosc": 10_000.0},
    {"symbol": "LUNR  260918C00021000", "klasa": "OPT", "bazowy": "LUNR",
     "wartosc": -624.0},
]


def test_reczna_decyzja_nie_daje_sie_nadpisac():
    """Rdzeń ochrony pracy człowieka: automat nie tyka wiersza z flagą."""
    _czysto()
    assert store.zapisz_klasyfikacje("NVDA", klasyfikacja.TEMAT, "Mój własny temat",
                                     recznie=True, zrodlo="ja")
    # automat próbuje przypisać coś innego - ma zostać odrzucony
    assert store.zapisz_klasyfikacje("NVDA", klasyfikacja.TEMAT,
                                     "AI / semiconductors", zrodlo="mapa") is False
    wpisy = store.klasyfikacja(klasyfikacja.TEMAT)["NVDA"]
    assert [w["wartosc"] for w in wpisy] == ["Mój własny temat"]
    # pełny przebieg klasyfikacji też musi to uszanować
    wynik = klasyfikacja.przypisz(POZYCJE, {})
    assert wynik["pominiete_reczne"] >= 0
    assert [w["wartosc"] for w in store.klasyfikacja(klasyfikacja.TEMAT)["NVDA"]] \
        == ["Mój własny temat"]


def test_arkusz_wzorcowy_ma_pierwszenstwo_przed_mapa():
    """Przypisanie z arkusza to decyzja człowieka dla tego portfela."""
    _czysto()
    klasyfikacja.przypisz([POZYCJE[0]], {"NVDA": "Gold Miners"})
    wpisy = store.klasyfikacja(klasyfikacja.TEMAT)["NVDA"]
    assert [w["wartosc"] for w in wpisy] == ["Gold miners"]
    assert wpisy[0]["zrodlo"] == "model sheet"


def test_wielotematycznosc_dzieli_wage_po_rowno():
    """MBLY ma dwa tematy - każdy dostaje połowę, żeby suma ekspozycji
    nie przekroczyła wartości portfela."""
    _czysto()
    klasyfikacja.przypisz([{"symbol": "MBLY", "klasa": "STK", "wartosc": 1000.0}], {})
    wpisy = store.klasyfikacja(klasyfikacja.TEMAT)["MBLY"]
    assert len(wpisy) == 2
    assert all(abs(w["waga"] - 0.5) < 1e-9 for w in wpisy)
    u = klasyfikacja.udzialy([{"symbol": "MBLY", "klasa": "STK", "wartosc": 1000.0}],
                             klasyfikacja.TEMAT)
    assert abs(sum(x["wartosc"] for x in u) - 1000.0) < 1e-6


def test_opcja_dziedziczy_klasyfikacje_po_bazowym():
    """Covered call na LUNR nie może być osobną, nieznaną ekspozycją."""
    _czysto()
    klasyfikacja.przypisz([POZYCJE[3]], {"LUNR": "Space"})
    wpisy = store.klasyfikacja(klasyfikacja.TEMAT)["LUNR  260918C00021000"]
    assert [w["wartosc"] for w in wpisy] == ["Space"]
    klasy = store.klasyfikacja(klasyfikacja.KLASA)["LUNR  260918C00021000"]
    assert [k["wartosc"] for k in klasy] == ["Options"]


def test_nieznana_spolka_jest_jawnie_nieprzypisana():
    """Zgadywanie byłoby gorsze niż przyznanie się - brak ma być widoczny."""
    _czysto()
    w = klasyfikacja.przypisz([POZYCJE[2]], {})
    assert w["bez_przypisania"] == 1
    assert "NIEZNANY" in w["braki"]
    assert [x["wartosc"] for x in store.klasyfikacja(klasyfikacja.TEMAT)["NIEZNANY"]] \
        == ["Unassigned"]


def test_sektor_wyprowadzony_z_tematu():
    """Arkusz daje temat, nie sektor. Bez przełożenia 48 spółek miałoby
    temat i pusty sektor."""
    _czysto()
    klasyfikacja.przypisz([{"symbol": "XYZ", "klasa": "STK", "wartosc": 100.0}],
                          {"XYZ": "Nuclear"})
    assert [w["wartosc"] for w in store.klasyfikacja(klasyfikacja.TEMAT)["XYZ"]] \
        == ["Nuclear energy"]
    sekt = store.klasyfikacja(klasyfikacja.SEKTOR)["XYZ"]
    assert [w["wartosc"] for w in sekt] == ["Energy"]
    assert sekt[0]["zrodlo"] == "from theme"


def test_udzialy_sumuja_sie_do_portfela():
    _czysto()
    poz = [{"symbol": "NVDA", "klasa": "STK", "wartosc": 60_000.0},
           {"symbol": "GLD", "klasa": "STK", "wartosc": 40_000.0}]
    klasyfikacja.przypisz(poz, {})
    u = klasyfikacja.udzialy(poz, klasyfikacja.TEMAT)
    assert abs(sum(x["wartosc"] for x in u) - 100_000.0) < 1e-6
    assert abs(sum(x["udzial"] for x in u) - 100.0) < 1e-6


# --------------------------------------------------------------------------- #
#  okresy - naprawa fałszywej precyzji
# --------------------------------------------------------------------------- #

def _hist(od, do, nav_od=100.0, nav_do=110.0):
    from datetime import date, timedelta
    a = date.fromisoformat(od); b = date.fromisoformat(do)
    dni = (b - a).days
    return [{"data": (a + timedelta(days=i)).isoformat(),
             "nav": nav_od + (nav_do - nav_od) * i / max(dni, 1),
             "wartosc": 0.0, "koszt": 0.0, "gotowka": 0.0}
            for i in range(dni + 1)]


def test_krotka_historia_nie_udaje_pelnych_okresow():
    """To jest ten błąd: QTD, YTD i „od początku" pokazywały tę samą liczbę
    liczoną od tej samej obserwacji, sugerując trzy niezależne pomiary."""
    h = _hist("2026-07-29", "2026-08-14", 708_000.0, 803_907.0)
    o = statystyki.okresy(h, 803_907.0)
    for e in ("QTD", "YTD", "1R"):
        assert o[e]["dostepny"] is False, e
        assert o[e]["proc"] is None
        assert o[e]["od"] == "2026-07-29"
    assert o["Od początku"]["dostepny"] is True
    assert o["MTD"]["dostepny"] is True          # sierpień mieści się w historii


def test_dluga_historia_liczy_wszystkie_okresy():
    h = _hist("2024-01-01", "2026-08-14", 500_000.0, 803_907.0)
    o = statystyki.okresy(h, 803_907.0)
    for e in ("MTD", "QTD", "YTD", "1R", "Od początku"):
        assert o[e]["dostepny"] is True, e
        assert o[e]["proc"] is not None
    # okresy o różnej długości muszą dać różne wyniki
    assert o["YTD"]["proc"] != o["Od początku"]["proc"]
    assert o["MTD"]["proc"] != o["YTD"]["proc"]


def test_brak_historii_nie_wywala():
    assert statystyki.okresy([], 100.0) == {}
