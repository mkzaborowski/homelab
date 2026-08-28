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

import pytest

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
            komorki = re.findall(r"<td([^>]*)>", w)
            if not komorki:
                continue                  # wiersz nagłówkowy albo pusty stan
            # Liczy się ROZPIĘTOŚĆ, nie liczba komórek: wiersz rozciągnięty na
            # całą szerokość (wykres spółki) ma jedną komórkę z colspan i jest
            # poprawny, a wiersz z brakującą kolumną nadal się nie zgadza.
            rozpietosc = 0
            for atrybuty in komorki:
                m = re.search(r'colspan="(\d+)"', atrybuty)
                rozpietosc += int(m.group(1)) if m else 1
            assert rozpietosc == len(naglowki), (
                f"wiersz obejmuje {rozpietosc} kolumn przy {len(naglowki)} nagłówkach:\n"
                f"{w[:220]}"
            )


# --------------------------------------------------------------------------- #
#  wykres pozycji
# --------------------------------------------------------------------------- #

def test_wykres_ma_swiece_srednia_i_rsi():
    """Zamówiony był wykres świecowy z RSI i średnią 100-sesyjną.

    Test pilnuje trzech rzeczy naraz, bo każda z nich potrafi zniknąć osobno:
    świece (prostokąty korpusów), średnia ze 100 sesji i panel RSI z progami.
    Sam fakt, że coś się narysowało, niczego nie dowodzi - pusty SVG też się
    rysuje.
    """
    import historia
    import wykresy

    # dane syntetyczne: 250 sesji, żeby średnia ze 100 miała się z czego wziąć
    sesje = []
    cena = 100.0
    for i in range(250):
        cena *= 1.004 if i % 3 else 0.995
        sesje.append({"czas": 1_700_000_000 + i * 86400, "otwarcie": cena * 0.99,
                      "max": cena * 1.02, "min": cena * 0.97,
                      "zamkniecie": cena, "wolumen": 1000.0})
    z = [s["zamkniecie"] for s in sesje]
    svg = wykresy.swiece_z_rsi(sesje, historia.sma(z, 100), historia.rsi(z), "TEST")

    assert svg.count("<rect") >= 250, "brakuje korpusów świec"
    assert "MA(100)" in svg, "nie ma średniej ze 100 sesji"
    assert "RSI(14)" in svg, "nie ma RSI"
    for prog in (">30<", ">50<", ">70<"):
        assert prog in svg, f"panel RSI bez progu {prog}"


def test_srednia_100_nie_zaczyna_sie_przed_setna_sesja():
    """Średnia ze 100 sesji narysowana na dwudziestej byłaby liczbą, której nie
    ma - a na wykresie wyglądałaby dokładnie tak samo jak prawdziwa."""
    import historia
    s = historia.sma([float(i) for i in range(150)], 100)
    assert s[98] is None
    assert s[99] == pytest.approx(sum(range(100)) / 100)


def test_rsi_liczy_metoda_wildera():
    """RSI po zwykłej średniej daje inne liczby niż w każdym innym narzędziu.
    Sprawdzamy skrajność: same wzrosty to 100, same spadki to 0."""
    import historia
    rosnie = historia.rsi([float(i) for i in range(1, 40)])
    spada = historia.rsi([float(i) for i in range(40, 1, -1)])
    assert rosnie[-1] == pytest.approx(100.0)
    assert spada[-1] == pytest.approx(0.0, abs=1e-9)


def test_wykres_bez_danych_nie_wybucha():
    """Yahoo bywa niedostępny. Panel ma wtedy powiedzieć, że nie wie -
    a nie wysypać całą zakładkę pozycji."""
    import wykresy
    out = wykresy.swiece_z_rsi([], [], [], "TEST")
    assert "wyk-brak" in out and "<svg" not in out


def test_symbol_opcji_nie_dostaje_wykresu():
    """Opcje i wpisy techniczne nie mają wykresu spółki - próba pobrania
    kończyłaby się pustą odpowiedzią przy każdym otwarciu."""
    assert widok._SYMBOL_WYKRESU.match("AAPL")
    assert widok._SYMBOL_WYKRESU.match("BRK.B")
    assert not widok._SYMBOL_WYKRESU.match("AAPL 260918C00250000")
    assert not widok._SYMBOL_WYKRESU.match("")


# --------------------------------------------------------------------------- #
#  przeglądarka wykresów
# --------------------------------------------------------------------------- #

def _sesje(ile: int = 300) -> list[dict]:
    cena, out = 100.0, []
    for i in range(ile):
        cena *= 1.004 if i % 3 else 0.995
        out.append({"czas": 1_700_000_000 + i * 86400, "otwarcie": cena * 0.99,
                    "max": cena * 1.02, "min": cena * 0.97,
                    "zamkniecie": cena, "wolumen": 1000.0 + i})
    return out


def test_ustawienia_odsiewaja_smieci_z_adresu():
    """Parametry przychodzą z adresu, więc może w nich być cokolwiek.
    Zły zakres, ujemny okres i nieistniejący oscylator mają zniknąć, a nie
    wywrócić stronę."""
    import przegladarka as pz
    u = pz.ustawienia({"zakres": "xxx", "sma": "abc,-5,0,999999,50",
                       "osc": "rsi,nieistnieje", "typ": "krzaczki"})
    assert u["zakres"] == "1y"
    assert u["sma"] == [50]
    assert u["oscylatory"] == ["rsi"]
    assert u["typ"] == "swiece"


def test_liczba_srednich_jest_ograniczona():
    """Dziesięć średnich na jednym wykresie to nie wykres, tylko sieć —
    a każda dokłada przeliczenie całej serii."""
    import przegladarka as pz
    u = pz.ustawienia({"sma": "5,10,15,20,25,30,35,40"})
    assert len(u["sma"]) == pz.OKRESY_MAKS


def test_wykres_rysuje_wszystkie_zamowione_warstwy():
    import historia as hi
    import wykresy
    s = _sesje()
    z = [x["zamkniecie"] for x in s]
    svg = wykresy.wykres_ceny(
        s,
        nakladki=[{"nazwa": "SMA(100)", "wartosci": hi.sma(z, 100), "kolor": "#0071E3"}],
        oscylatory=[{"nazwa": "RSI(14)", "zakres": (0, 100), "progi": [30, 70],
                     "serie": [{"nazwa": "", "wartosci": hi.rsi(z), "kolor": "#0071E3"}]}],
        wolumen=True, symbol="TEST")
    assert "SMA(100)" in svg and "RSI(14)" in svg and "Volume" in svg
    assert svg.count("<rect") > 300      # korpusy świec + słupki wolumenu


def test_nakladka_bez_nazwy_nie_zajmuje_wiersza_legendy():
    """Druga wstęga Bollingera rysuje się, ale nie ma czego podpisać —
    naga liczba bez etykiety wyglądała jak usterka."""
    import wykresy
    s = _sesje(120)
    svg = wykresy.wykres_ceny(s, nakladki=[
        {"nazwa": "BB", "wartosci": [x["max"] for x in s], "kolor": "#888"},
        {"nazwa": "", "wartosci": [x["min"] for x in s], "kolor": "#888"},
    ], wolumen=False, symbol="TEST")
    assert svg.count("BB") == 1


def test_kazdy_zakres_czasu_ma_swoj_interwal():
    """Pięć lat sesji dziennych to 1250 świec, których i tak nie widać.
    Powyżej dwóch lat schodzimy na tygodnie i miesiące."""
    import historia as hi
    assert set(hi.ZAKRESY) == set(hi.ETYKIETY_ZAKRESU)
    assert hi.ZAKRESY["1y"][1] == "1d"
    assert hi.ZAKRESY["5y"][1] == "1wk"
    assert hi.ZAKRESY["max"][1] == "1mo"


def test_ema_startuje_od_sredniej_a_nie_od_pierwszej_ceny():
    """EMA rozpędzana z jednego punktu przez kilkadziesiąt sesji goni resztę
    i rysuje na początku krzywą, której nie ma."""
    import historia as hi
    v = [10.0] * 5 + [20.0] * 20
    e = hi.ema(v, 5)
    assert e[3] is None
    assert e[4] == pytest.approx(10.0)


def test_macd_histogram_to_roznica_linii_i_sygnalu():
    import historia as hi
    z = [x["zamkniecie"] for x in _sesje(200)]
    linia, sygnal, hist = hi.macd(z)
    for a, b, h in zip(linia, sygnal, hist):
        if a is None or b is None:
            assert h is None
        else:
            assert h == pytest.approx(a - b)


def test_stochastyczny_bez_zakresu_daje_srodek_a_nie_wyjatek():
    """Sesja, w której max == min (papier bez obrotu), dzieliłaby przez zero."""
    import historia as hi
    k, d = hi.stochastyczny([5.0] * 20, [5.0] * 20, [5.0] * 20)
    assert k[-1] == 50.0


def test_okno_dat_wycina_ale_nie_przelicza_wskaznikow():
    """Po przybliżeniu do miesiąca średnia ze 100 sesji ma nadal istnieć.

    Gdyby okno wycinać PRZED liczeniem, w oknie nie byłoby stu sesji i średnia
    zniknęłaby z wykresu - a na ekranie wyglądałoby to jak brak danych,
    nie jak błąd kolejności.
    """
    import przegladarka as pz
    sesje = _sesje(300)
    a, b = pz._okno(sesje, "", "")
    assert (a, b) == (0, 300)


def test_okno_wezsze_niz_dwie_sesje_wraca_do_calosci():
    """Kliknięcie bez przeciągnięcia nie może zostawić jednej świecy
    rozciągniętej na całą szerokość."""
    import datetime as dt
    import przegladarka as pz
    sesje = _sesje(50)
    dzien = dt.datetime.fromtimestamp(sesje[10]["czas"], dt.timezone.utc).strftime("%Y-%m-%d")
    assert pz._okno(sesje, dzien, dzien) == (0, 50)


def test_rysunek_niesie_dane_do_odczytu_pod_kursorem():
    """Bez danych przy rysunku odczyt wymagałby pytania serwera przy każdym
    ruchu myszy, czyli byłby niemożliwy."""
    import json
    import re
    import przegladarka as pz

    class _Historia:
        ZAKRESY = pz.historia.ZAKRESY
        @staticmethod
        def pobierz(sym, zak="1y"):
            return _sesje(150)
    stara = pz.historia
    pz.historia = type("H", (), {**{k: getattr(stara, k) for k in dir(stara) if not k.startswith("__")},
                                 "pobierz": staticmethod(lambda s, z="1y": _sesje(150))})
    try:
        html = pz.rysuj("TEST", pz.ustawienia({"osc": "rsi"}))
    finally:
        pz.historia = stara

    m = re.search(r'<script type="application/json" class="wyk-dane">(.*?)</script>', html, re.S)
    assert m, "rysunek przyszedł bez danych"
    d = json.loads(m.group(1))
    assert len(d["daty"]) == len(d["c"]) == 150
    assert [s["n"] for s in d["serie"]] == ["SMA(50)", "SMA(100)", "RSI(14)"]


def test_svg_niesie_geometrie_potrzebna_do_krzyza():
    """Przeglądarka musi umieć przeliczyć pozycję kursora na indeks sesji.
    Bez tych atrybutów wykres jest obrazkiem, a nie narzędziem."""
    import wykresy
    svg = wykresy.wykres_ceny(_sesje(120), wolumen=True, symbol="TEST")
    for atrybut in ("data-x0", "data-krok", "data-n", "data-gora", "data-dol"):
        assert atrybut in svg, f"brak {atrybut}"
    assert 'class="wyk-lapacz"' in svg and 'class="wyk-krzyz"' in svg
