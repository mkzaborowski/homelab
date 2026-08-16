"""Silnik ryzyka: zmienność, wskaźniki, VaR, beta i wkład do ryzyka.

Zasada nadrzędna: metryka statystycznie pusta nie ma prawa się pokazać.
Sharpe policzony z trzynastu obserwacji to nie oszacowanie, tylko liczba,
która wygląda jak oszacowanie — i to jest gorsze niż jej brak. Każda funkcja
zwraca None, gdy historii brakuje, a `podsumowanie` niesie jawne okno danych.

Wszystko na czystej bibliotece standardowej. Przy 250 dniach i 58 spółkach
macierz kowariancji to 58×58 — pure Python liczy to w ułamku sekundy, a brak
zależności trzyma obraz systemu prosty.
"""
from __future__ import annotations

import math

DNI_HANDLOWE = 252          # do annualizacji zmienności liczonej z dni sesyjnych
# Progi, poniżej których miara jest nie do obronienia. Dobrane tak, żeby
# błąd oszacowania zmienności nie przekraczał grubo kilkunastu procent.
MIN_ZMIENNOSC = 20
MIN_SHARPE = 60
MIN_VAR = 100               # kwantyl z ogona wymaga najwięcej obserwacji
MIN_BETA = 60


def _sr(x: list[float]) -> float:
    return sum(x) / len(x) if x else 0.0


def srednia(x: list[float]) -> float:
    return _sr(x)


def odchylenie(x: list[float], probka: bool = True) -> float | None:
    """Odchylenie standardowe. Dzielimy przez n-1, bo pracujemy na próbce
    z nieznanej populacji, a nie na całej populacji."""
    n = len(x)
    if n < 2:
        return None
    m = _sr(x)
    war = sum((v - m) ** 2 for v in x) / (n - 1 if probka else n)
    return math.sqrt(war)


def kowariancja(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 2:
        return None
    ma, mb = _sr(a[:n]), _sr(b[:n])
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (n - 1)


def korelacja(a: list[float], b: list[float]) -> float | None:
    sa, sb = odchylenie(a), odchylenie(b)
    kow = kowariancja(a, b)
    if kow is None or not sa or not sb:
        return None
    return kow / (sa * sb)


# --------------------------------------------------------------------------- #
#  zmienność i wskaźniki
# --------------------------------------------------------------------------- #

def zmiennosc(zwroty: list[float], roczna: bool = True) -> float | None:
    if len(zwroty) < MIN_ZMIENNOSC:
        return None
    s = odchylenie(zwroty)
    if s is None:
        return None
    return s * math.sqrt(DNI_HANDLOWE) if roczna else s


def zmiennosc_ujemna(zwroty: list[float], prog: float = 0.0) -> float | None:
    """Odchylenie liczone wyłącznie z dni poniżej progu.

    Uwaga na mianownik: dzielimy przez liczbę WSZYSTKICH obserwacji, nie tylko
    ujemnych. Inaczej portfel z rzadkimi, ale głębokimi spadkami wyglądałby
    na spokojniejszy niż jest."""
    if len(zwroty) < MIN_ZMIENNOSC:
        return None
    ponizej = [min(0.0, r - prog) for r in zwroty]
    war = sum(v * v for v in ponizej) / (len(zwroty) - 1)
    return math.sqrt(war) * math.sqrt(DNI_HANDLOWE)


def sharpe(zwroty: list[float], stopa_wolna: float = 0.0425) -> float | None:
    """Nadwyżka nad stopą wolną na jednostkę zmienności całkowitej."""
    if len(zwroty) < MIN_SHARPE:
        return None
    s = zmiennosc(zwroty)
    if not s:
        return None
    nadwyzka = _sr(zwroty) * DNI_HANDLOWE - stopa_wolna
    return nadwyzka / s


def sortino(zwroty: list[float], stopa_wolna: float = 0.0425) -> float | None:
    """Jak Sharpe, ale karze wyłącznie zmienność w dół. Dla portfela, który
    rośnie skokowo, jest uczciwszy niż Sharpe."""
    if len(zwroty) < MIN_SHARPE:
        return None
    s = zmiennosc_ujemna(zwroty)
    if not s:
        return None
    return (_sr(zwroty) * DNI_HANDLOWE - stopa_wolna) / s


def calmar(zwrot_roczny: float | None, maks_obsuniecie: float | None) -> float | None:
    """Zwrot roczny na jednostkę największego obsunięcia."""
    if zwrot_roczny is None or not maks_obsuniecie:
        return None
    return zwrot_roczny / abs(maks_obsuniecie)


# --------------------------------------------------------------------------- #
#  ryzyko ogona
# --------------------------------------------------------------------------- #

def var_historyczny(zwroty: list[float], poziom: float = 0.95) -> float | None:
    """Kwantyl empiryczny lewego ogona.

    Świadomie historyczny, a nie parametryczny: rozkład dziennych zwrotów
    ma grubsze ogony niż normalny, więc założenie normalności zaniżałoby
    stratę dokładnie tam, gdzie liczy się najbardziej."""
    if len(zwroty) < MIN_VAR:
        return None
    s = sorted(zwroty)
    i = int((1.0 - poziom) * len(s))
    return s[min(i, len(s) - 1)]


def cvar(zwroty: list[float], poziom: float = 0.95) -> float | None:
    """Średnia strata w dniach gorszych niż VaR — ile tracimy, GDY już jest źle.

    VaR mówi tylko, gdzie zaczyna się ogon; CVaR mówi, jak głęboki jest."""
    v = var_historyczny(zwroty, poziom)
    if v is None:
        return None
    ogon = [r for r in zwroty if r <= v]
    return _sr(ogon) if ogon else v


def rozklad(zwroty: list[float], kubelkow: int = 26) -> list[dict]:
    """Zwroty dzienne pogrupowane w kubełki równej szerokości.

    Równa szerokość, nie równa liczność: przy kwantylach ogon zlewa się
    z resztą i znika dokładnie ta informacja, po którą się tu przychodzi.
    Zakres domykamy symetrycznie wokół zera, żeby asymetria rozkładu była
    widoczna jako asymetria obrazka, a nie jako przesunięcie ramki."""
    if len(zwroty) < 10:
        return []
    kres = max(abs(min(zwroty)), abs(max(zwroty)))
    if kres <= 0:
        return []
    lo, hi = -kres, kres
    szer = (hi - lo) / kubelkow
    licznik = [0] * kubelkow
    for r in zwroty:
        i = int((r - lo) / szer)
        licznik[min(max(i, 0), kubelkow - 1)] += 1
    return [{"od": lo + i * szer, "do": lo + (i + 1) * szer, "ile": n}
            for i, n in enumerate(licznik)]


def zmiennosc_kroczaca(zwroty: list[tuple[str, float]], okno: int = 30) -> list[tuple[str, float]]:
    """Zmienność roczna liczona w oknie przesuwnym.

    Jedna liczba za cały okres uśrednia spokój z burzą i nie mówi, w którą
    stronę idzie ryzyko. Ta krzywa pokazuje, czy portfel się właśnie
    uspokaja, czy rozkręca - a to jest pytanie decyzyjne, w przeciwieństwie
    do średniej za rok.

    Okno 30 sesji to kompromis: krótsze skacze od pojedynczych dni,
    dłuższe reaguje z opóźnieniem, którego nie da się już użyć."""
    if len(zwroty) < okno + 5:
        return []
    out = []
    for i in range(okno, len(zwroty) + 1):
        wycinek = [x for _, x in zwroty[i - okno:i]]
        s = odchylenie(wycinek)
        if s is not None:
            out.append((zwroty[i - 1][0], s * math.sqrt(DNI_HANDLOWE)))
    return out


# --------------------------------------------------------------------------- #
#  beta i regresja
# --------------------------------------------------------------------------- #

def beta(portfel: list[float], wzorzec: list[float]) -> dict | None:
    """Regresja liniowa zwrotów portfela wobec wzorca.

    Zwraca betę, alfę w skali roku, R², błąd odwzorowania i wskaźnik
    informacyjny — czyli komplet potrzebny, żeby powiedzieć nie tylko
    „jak bardzo idziemy za rynkiem", ale też „ile z tego wyjaśnia rynek"."""
    n = min(len(portfel), len(wzorzec))
    if n < MIN_BETA:
        return None
    p, w = portfel[:n], wzorzec[:n]
    war_w = kowariancja(w, w)
    kow = kowariancja(p, w)
    if not war_w or kow is None:
        return None
    b = kow / war_w
    a = _sr(p) - b * _sr(w)
    kor = korelacja(p, w)
    roznice = [p[i] - w[i] for i in range(n)]
    te = odchylenie(roznice)
    # Uwaga na zero: błąd odwzorowania równy zeru to poprawny wynik (portfel
    # odwzorowuje wzorzec co do grosza), a nie brak danych. Warunek na samej
    # prawdziwości logicznej mylił jedno z drugim.
    te_roczny = te * math.sqrt(DNI_HANDLOWE) if te is not None else None
    aktywny = (_sr(p) - _sr(w)) * DNI_HANDLOWE
    return {
        "beta": b,
        "alfa_roczna": a * DNI_HANDLOWE,
        "r2": (kor ** 2) if kor is not None else None,
        "korelacja": kor,
        "blad_odwzorowania": te_roczny,
        "zwrot_aktywny": aktywny,
        # przy zerowym błędzie odwzorowania wskaźnik nie istnieje (dzielenie
        # przez zero), więc tu None jest właściwą odpowiedzią
        "wskaznik_informacyjny": (aktywny / te_roczny) if te_roczny else None,
        "obserwacji": n,
    }


# --------------------------------------------------------------------------- #
#  wkład do ryzyka
# --------------------------------------------------------------------------- #

def wklad_do_ryzyka(wagi: dict[str, float],
                    zwroty: dict[str, list[float]]) -> dict | None:
    """Rozkład zmienności portfela na pozycje.

    Sedno: udział w ryzyku to NIE to samo co udział w kapitale. Pozycja
    z wagą 5% i podwójną zmiennością wnosi znacznie więcej niż 5% ryzyka,
    a przy dodatniej korelacji z resztą portfela jeszcze więcej. Dopiero
    to zestawienie pokazuje, co naprawdę rządzi wynikiem.

    Wkład krańcowy to pochodna zmienności portfela po wadze pozycji;
    wkład składowy to waga razy wkład krańcowy i sumuje się do całości.
    """
    # Okno liczymy z MEDIANY długości szeregów, nie z minimum. Przy minimum
    # jedna świeżo notowana spółka obcinała wspólne okno wszystkim pozostałym:
    # 52 pozycje z rocznymi danymi liczyły się na 25 obserwacjach, bo jedna
    # miała 26 dni. Wynik wyglądał poprawnie i był statystycznie pusty.
    # Zamiast tego wykluczamy pozycje bez historii i mówimy o tym wprost.
    kandydaci = [s for s in wagi if s in zwroty and len(zwroty[s]) >= MIN_ZMIENNOSC]
    if len(kandydaci) < 2:
        return None
    dlugosci = sorted(len(zwroty[s]) for s in kandydaci)
    mediana = dlugosci[len(dlugosci) // 2]
    okno = max(MIN_ZMIENNOSC, int(mediana * 0.8))

    symbole = [s for s in kandydaci if len(zwroty[s]) >= okno]
    pominiete = [s for s in wagi if s not in symbole]
    if len(symbole) < 2:
        return None
    n = min(len(zwroty[s]) for s in symbole)
    serie = {s: zwroty[s][-n:] for s in symbole}
    w = {s: wagi[s] for s in symbole}
    suma_wag = sum(abs(v) for v in w.values())
    if suma_wag <= 0:
        return None
    w = {s: v / suma_wag for s, v in w.items()}

    kow = {a: {b: (kowariancja(serie[a], serie[b]) or 0.0) for b in symbole}
           for a in symbole}
    war_portfela = sum(w[a] * w[b] * kow[a][b] for a in symbole for b in symbole)
    if war_portfela <= 0:
        return None
    sigma = math.sqrt(war_portfela)

    pozycje = []
    for s in symbole:
        kranc = sum(w[b] * kow[s][b] for b in symbole) / sigma
        skladowy = w[s] * kranc
        wl = zmiennosc(serie[s])
        pozycje.append({
            "symbol": s,
            "waga": w[s],
            "zmiennosc": wl,
            "wklad_kranowy": kranc,
            "wklad_skladowy": skladowy,
            "udzial_w_ryzyku": skladowy / sigma if sigma else 0.0,
            # ile razy więcej ryzyka niż kapitału wnosi ta pozycja
            "krotnosc": (skladowy / sigma / w[s]) if w[s] else 0.0,
        })
    pozycje.sort(key=lambda x: -x["udzial_w_ryzyku"])
    return {
        "zmiennosc_portfela": sigma * math.sqrt(DNI_HANDLOWE),
        "pozycje": pozycje,
        "obserwacji": n,
        "instrumentow": len(symbole),
        # jawnie, bo wykluczona pozycja nadal zajmuje kapitał - tylko nie
        # da się rzetelnie powiedzieć, ile wnosi ryzyka
        "pominiete": sorted(pominiete),
        "udzial_objety": sum(abs(wagi[s]) for s in symbole)
                         / (sum(abs(v) for v in wagi.values()) or 1.0),
    }


# --------------------------------------------------------------------------- #
#  koncentracja
# --------------------------------------------------------------------------- #

def koncentracja(wartosci: dict[str, float]) -> dict:
    """Koncentracja kapitału. HHI i efektywna liczba pozycji mówią więcej
    niż sama liczba spółek: portfel z pięćdziesięcioma pozycjami, z których
    trzy to 70% wartości, nie jest zdywersyfikowany."""
    v = {k: abs(x) for k, x in wartosci.items() if x}
    suma = sum(v.values())
    if not suma:
        return {"dostepne": False}
    udzialy = sorted((x / suma for x in v.values()), reverse=True)
    hhi = sum(u * u for u in udzialy)
    return {
        "dostepne": True,
        "pozycji": len(udzialy),
        "top1": udzialy[0] * 100,
        "top3": sum(udzialy[:3]) * 100,
        "top5": sum(udzialy[:5]) * 100,
        "top10": sum(udzialy[:10]) * 100,
        "hhi": hhi * 10_000,
        "efektywna_liczba": 1.0 / hhi if hhi else 0.0,
    }


# --------------------------------------------------------------------------- #
#  zestawienie
# --------------------------------------------------------------------------- #

def podsumowanie(zwroty: list[float], obsuniecia: dict | None = None,
                 zwrot_roczny: float | None = None,
                 stopa_wolna: float = 0.0425) -> dict:
    """Komplet miar wraz z informacją, których jeszcze nie da się policzyć."""
    n = len(zwroty)
    maks_ob = (obsuniecia or {}).get("maks")
    braki = []
    if n < MIN_ZMIENNOSC:
        braki.append(f"zmienność wymaga {MIN_ZMIENNOSC} obserwacji")
    if n < MIN_SHARPE:
        braki.append(f"Sharpe i Sortino wymagają {MIN_SHARPE}")
    if n < MIN_VAR:
        braki.append(f"VaR i CVaR wymagają {MIN_VAR}")
    return {
        "obserwacji": n,
        "braki": braki,
        "zmiennosc": zmiennosc(zwroty),
        "zmiennosc_ujemna": zmiennosc_ujemna(zwroty),
        "sharpe": sharpe(zwroty, stopa_wolna),
        "sortino": sortino(zwroty, stopa_wolna),
        "calmar": calmar(zwrot_roczny, maks_ob),
        "var95": var_historyczny(zwroty, 0.95),
        "var99": var_historyczny(zwroty, 0.99),
        "cvar95": cvar(zwroty, 0.95),
        "maks_obsuniecie": maks_ob,
        "biezace_obsuniecie": (obsuniecia or {}).get("biezace"),
    }
