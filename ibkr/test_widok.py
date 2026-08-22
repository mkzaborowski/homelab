"""Test dymny warstwy widoku: czy panel w ogóle się składa.

Powstał po awarii, którą można było złapać w dwie sekundy lokalnie. Przejście
interfejsu na angielski zmieniło sygnaturę `_odm` w widok.py, ale ten sam
pomocnik istnieje w drugiej kopii w widok_opcje.py - i tamta została z trzema
argumentami. Panel wywalił się na produkcji z TypeError, bo test przed
wdrożeniem renderował `panel()` z `analiza_opcji=None` i po prostu nie wchodził
w ten plik.

Stąd zasada tego pliku: KAŻDA zakładka dostaje dane niepuste. Zakładka
renderowana z None sprawdza tylko gałąź „brak danych", czyli dokładnie tę,
w której nie ma czego zepsuć.

Test nie sprawdza wyglądu - od tego jest przeglądarka. Sprawdza trzy rzeczy,
których wygląd nie pokaże: że każda ścieżka się wykonuje, że w widocznej treści
nie został polski tekst i że żadna klamra f-stringa nie wyciekła do HTML-a.
"""
from __future__ import annotations

import re

import opcje
import ryzyko
import scenariusze as scen
import statystyki
import widok
import wzorzec
import zwrot

POLSKIE = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")


def _portfel() -> dict:
    """Kształt prawdziwego portfela: spółka w wielu transzach, spółka w jednej,
    krótki call w pieniądzu i bez pokrycia, pozycje bez stopa."""
    def akcja(sym, n, cena, koszt, data):
        return {"symbol": sym, "opis": f"{sym} INC", "klasa": "STK", "ilosc": n,
                "cena": cena, "wartosc": n * cena, "koszt": koszt,
                "zysk": n * cena - koszt, "data_otwarcia": data, "waluta": "USD"}

    poz = [akcja("TSLA", 21, 342.27, 8600.0, f"2026061{i}") for i in range(9)]
    poz.append(akcja("NEM", 214, 117.76, 22670.0, "20260805"))
    poz.append(akcja("GLD", 40, 310.00, 12000.0, "20260101"))
    poz.append({"symbol": "TSLA  260918C00350000", "opis": "TSLA CALL", "klasa": "OPT",
                "bazowy": "TSLA", "prawo": "C", "strike": 350.0, "wygasa": "20260918",
                "ilosc": -3, "cena": 12.4, "wartosc": -3720.0, "koszt": -5100.0,
                "zysk": 1380.0, "mnoznik": 100, "waluta": "USD"})
    return {"data": "2026-08-14", "nav": 803907.56,
            "dane": {"nav": 803907.56, "pozycje": poz,
                     "gotowka": [{"waluta": "USD", "konczy": 102312.59}]}}


def _historia(n: int = 200) -> list[dict]:
    import random
    random.seed(4)
    nav, out = 500_000.0, []
    for i in range(n):
        nav *= 1 + random.gauss(0.0012, 0.013)
        out.append({"data": f"2025-{i // 30 + 1:02d}-{i % 28 + 1:02d}", "nav": nav})
    return out


def _analityka(hist: list[dict], pods: dict) -> dict:
    z = zwrot.podsumowanie(hist)
    dzienne = [x for _, x in z["zwroty"]]
    czynniki = [
        {"symbol": "SPY", "opis": "US broad market", "beta": 1.25, "r2": 0.55,
         "korelacja": 0.74, "alfa_roczna": 0.08},
        {"symbol": "UUP", "opis": "US dollar", "beta": -1.04, "r2": 0.08,
         "korelacja": -0.28, "alfa_roczna": 0.19},
    ]
    import random
    random.seed(5)
    serie = {t["symbol"]: [random.gauss(0, 0.02) for _ in range(200)]
             for t in pods["tickery"]}
    wagi = {t["symbol"]: t["wartosc"] for t in pods["tickery"]}
    return {
        "zwrot": z,
        "ryzyko": ryzyko.podsumowanie(dzienne, z["obsuniecia"], z["twr_roczny"]),
        "koncentracja": ryzyko.koncentracja(wagi),
        "miesiace": zwrot.zwroty_miesieczne(hist),
        "szereg": hist,
        "krzywa": zwrot.krzywa_twr(hist),
        "rozklad_zwrotow": ryzyko.rozklad(dzienne),
        "zmiennosc_kroczaca": ryzyko.zmiennosc_kroczaca(z["zwroty"]),
        "uzgodnienie": {"ibkr": 40.479},
        "wklad": ryzyko.wklad_do_ryzyka(wagi, serie),
        "czynniki": czynniki,
        "ekspozycje": {
            "temat": [{"nazwa": "Gold miners", "wartosc": 25_200.0, "udzial": 22.0}],
            "sektor": [{"nazwa": "Commodities", "udzial": 30.0}],
            "kraj": [{"nazwa": "USA", "udzial": 88.0}],
            "klasa": [{"nazwa": "Equity", "wartosc": 700_000.0, "udzial": 90.0}],
        },
        "zrodlo_cen": {"nazwa": "Yahoo Finance", "zakres": {}},
        "scenariusze": scen.podsumowanie(pods["nav"], czynniki),
    }


# Wycinek arkusza wzorcowego w takim układzie, jaki naprawdę przychodzi
# z Dysku: wiersz nagłówkowy koszyka, potem transze, gwiazdka przy rdzeniu.
# Zakładka „Model" MUSI dostać prawdziwe dane - z porownanie=None renderuje się
# tylko komunikat „nie udało się pobrać" i cała tabela nigdy nie jest sprawdzana.
ARKUSZ_TESTOWY = (
    "The AWP,Diversified Technology,% of portfolio assets,Company,Ticker\n"
    ",% of total assets,6.05%,Tesla *,TSLA\n"
    ",23.60%,1.51%,Tesla,TSLA\n"
    ",,2.14%,ServiceNow *,NOW\n"
    ",,2.93%,Schwab Dividend ETF,SCHD\n"
    "The AWP,Hedging Vehicles,% of portfolio assets,Company,Ticker\n"
    ",5.08%,2.48%,Direxion Bear,SPXS\n"
    ",,2.60%,ProShares UltraShort,SQQQ\n"
)


def _porownanie(pods: dict) -> dict:
    return wzorzec.porownaj(wzorzec.parsuj(ARKUSZ_TESTOWY), pods)


def _strona() -> str:
    zrzut = _portfel()
    meta = {"TSLA": {"koszyk": "Emerging tech", "stop": 300.0},
            "NEM": {"koszyk": "Gold miners"}, "GLD": {}}
    pods = statystyki.podsumowanie(zrzut, meta, None)
    hist = _historia()
    return widok.panel(
        pods, hist, ["Emerging tech", "Gold miners"],
        [{"kiedy": "2026-08-14 20:00", "ok": True, "komunikat": "saved 2026-08-14"},
         {"kiedy": "2026-08-13 20:00", "ok": False, "komunikat": "prices failed"}],
        # Etykiety okresów BIERZEMY Z KODU, nie wpisujemy własnych: przy
        # własnych test przeoczył kafel „Od początku", który został po polsku
        # aż do zobaczenia go w przeglądarce.
        okresy=statystyki.okresy(hist, pods["nav"],
                                 zwrot.przeplywy_z_operacji([])),
        harmonogram="fetch every 90 min",
        analiza_opcji=opcje.analiza_do_panelu(
            zrzut["dane"],
            [{"symbol": "TSLA  260918C00350000", "bazowy": "TSLA", "data": "2026-08-04",
              "ilosc": -3, "cena": 17.0, "kwota": 5100.0, "prowizja": -3.9,
              "zysk_zrealizowany": 0.0, "klasa": "OPT"}],
            ("2026-08-01", "2026-08-14", 1)),
        analityka=_analityka(hist, pods),
        porownanie=_porownanie(pods))


def _widoczne(html: str) -> str:
    """HTML bez stylów, skryptów i komentarzy - czyli to, co czyta człowiek.
    Komentarze w CSS zostają po polsku świadomie i nie są treścią panelu."""
    return re.sub(r"<style>.*?</style>|<script>.*?</script>|<!--.*?-->", "",
                  html, flags=re.S)


def test_panel_sklada_sie_z_kompletem_danych():
    """Gdyby ten test istniał wcześniej, TypeError z `_odm` nie doszedłby na
    produkcję: wystarczyło podać niepustą analizę opcji."""
    html = _strona()
    assert len(html) > 40_000
    assert html.count('<html lang="en">') == 1
    assert html.rstrip().endswith("</html>")


def test_kazda_zakladka_ma_swoj_panel():
    html = _strona()
    for panel in ("przeglad", "pozycje", "analiza", "wynik", "ryzyko",
                  "ekspozycja", "scenariusze", "opcje", "wzorzec", "ustawienia"):
        assert f'data-panel="{panel}"' in html, panel


def test_zadna_zakladka_nie_jest_pusta():
    """Wykres bez danych rysuje „No data". Kilka takich naraz znaczy, że coś
    się nie policzyło, a panel udaje, że tak ma być."""
    html = _strona()
    assert html.count("pusto") <= 2, html.count("pusto")


def test_w_widocznej_tresci_nie_ma_polskiego_tekstu():
    braki = POLSKIE.findall(_widoczne(_strona()))
    assert not braki, f"{len(braki)} polskich znaków w treści panelu"


def test_zaden_f_string_nie_wyciekl_do_html():
    """Niedomknięta klamra w szablonie nie rzuca wyjątkiem - po prostu ląduje
    w HTML-u jako tekst i widać ją dopiero na ekranie.

    Szukamy sygnatury Pythona po klamrze, nie samej klamry: w atrybutach
    onclick siedzi prawdziwy JavaScript i on też ma nawiasy klamrowe."""
    w = _widoczne(_strona())
    wycieki = re.findall(r'\{[a-z_]+\[|\{e\(|\{_[a-z]+\(|\{len\(', w)
    assert not wycieki, wycieki[:5]


def test_transze_sa_schowane_a_spolki_widoczne():
    """Sedno przebudowy tabeli pozycji: domyślnie widać spółki, nie transze."""
    html = _strona()
    spolki = re.findall(r'<tr class="spolka"[^>]*>', html)
    loty = re.findall(r'<tr class="lot"[^>]*>', html)
    assert len(spolki) == 3, spolki
    assert len(loty) == 11, len(loty)
    assert all("hidden" in x for x in loty), "transza widoczna przy pierwszym wejściu"
    assert all("hidden" not in x for x in spolki), "spółka schowana"


def test_spolka_z_wieloma_transzami_ma_strzalke_i_licznik():
    html = _strona()
    assert "data-zwin-lot=" in html
    assert ">9 lots</span>" in html          # TSLA w dziewięciu transzach
    assert ">1 lot</span>" in html           # NEM w jednej


def test_stop_jest_widoczny_bez_rozwijania_transz():
    """Stop wpisuje się raz na ticker, więc musi stać przy spółce. Wcześniej
    stał tylko przy transzach i po ich schowaniu zniknąłby zupełnie."""
    html = _strona()
    wiersz = re.search(r'<tr class="spolka"[^>]*data-sym="TSLA">.*?</tr>', html, re.S)
    assert wiersz and "$300.00" in wiersz.group(0)


def test_kolor_nie_wraca_do_chromu():
    """Zabezpieczenie przed powrotem fioletu: chrom bierze --akcent, dane
    biorą --dane, i te dwie rodziny nie mają prawa się zamienić."""
    import style
    assert "--akcent:     #1D1D1F;" in style.STYL      # neutralny w jasnym
    assert "--akcent:     #F5F5F7;" in style.STYL      # neutralny w ciemnym
    for zmienna in ("--dane:", "--dane-2:", "--wzrost:", "--spadek:"):
        assert style.STYL.count(zmienna) == 2, zmienna  # komplet w obu motywach


def test_oba_motywy_maja_komplet_zmiennych():
    """Kolor zdefiniowany tylko w jednym motywie znika w drugim i zostawia
    tekst jednego motywu na tle drugiego - klasyczny błąd trybu ciemnego."""
    import style
    jasny, ciemny = style.STYL.split('html[data-motyw="ciemny"] {')
    nazwy = lambda blok: set(re.findall(r"(--[a-z0-9-]+):", blok.split("}")[0]))
    w_jasnym = nazwy(jasny.split(":root {")[1])
    w_ciemnym = nazwy(ciemny)
    brakuje = w_jasnym - w_ciemnym - {"--e", "--dotyk"}   # te dwa są wspólne
    assert not brakuje, f"w ciemnym motywie brakuje: {sorted(brakuje)}"


def test_data_transzy_traci_przyrostek_ibkr():
    """IBKR dokleja do daty otwarcia numer transzy („20260615;1"), przez co
    cała wartość nie przechodziła przez formatowanie i w tabeli stało surowe
    „20260615;1" zamiast daty."""
    assert widok._dzien("20260615;1") == "2026-06-15"
    assert widok._dzien("20260615") == "2026-06-15"
    assert widok._dzien("2026-06-15") == "2026-06-15"
    assert widok._dzien("") == ""


def test_transze_pokazuja_sformatowana_date():
    html = _strona()
    assert "Buy 1 · 2026-06-10" in html
    assert ";" not in re.search(r'<tr class="lot".*?</tr>', html, re.S).group(0)


def test_kazda_tabela_ma_tyle_komorek_ile_naglowkow():
    """Nagłówek obiecujący więcej kolumn niż wypisuje wiersz przesuwa CAŁĄ tabelę.

    Tak było w zestawieniu z portfelem wzorcowym: osiem nagłówków, siedem
    komórek. Pod „Sheet" stał przeskalowany cel, pod „Target" stan faktyczny,
    a wartość wprost z arkusza nie trafiała na ekran wcale - więc panelu nie
    dało się zestawić z arkuszem i wyglądało to na złe dane, a nie na zsunięte
    kolumny. Wygląd tego nie pokaże: tabela z przesunięciem rysuje się ładnie.
    """
    html = _strona()
    tabele = re.findall(r"<table[^>]*>.*?</table>", html, re.S)
    assert tabele, "na stronie nie ma ani jednej tabeli - test przestał cokolwiek sprawdzać"
    for tab in tabele:
        naglowki = re.findall(r"<th[ >]", tab)
        if not naglowki:
            continue                      # tabela układu, bez nagłówków
        wiersze = re.findall(r"<tr[^>]*>(?:(?!</tr>).)*?</tr>", tab, re.S)
        for w in wiersze:
            komorki = re.findall(r"<td[ >]", w)
            if not komorki:
                continue                  # wiersz nagłówkowy albo pusty stan
            assert len(komorki) == len(naglowki), (
                f"wiersz ma {len(komorki)} komórek przy {len(naglowki)} nagłówkach:\n"
                f"{w[:220]}"
            )
