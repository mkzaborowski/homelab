"""Portfel wzorcowy (All-Weather Portfolio) i porównanie z faktycznym.

Arkusz jest opublikowany na Dysku Google i zmienia się na bieżąco, więc
pobieramy go przy każdym przebiegu, a nie raz na zawsze.

Układ arkusza, ustalony empirycznie:
  - wiersz nagłówkowy koszyka ma w kolumnie 2 tekst "% of portfolio assets",
    a nazwa koszyka siedzi w kolumnie 1,
  - każdy kolejny wiersz to jedna transza: kolumna 2 to udział w aktywach,
    kolumna 4 to ticker,
  - gwiazdka przy nazwie oznacza pozycję rdzeniową, NIE wiersz zbiorczy,
    więc sumujemy wszystkie wiersze tickera (arkusz sam to wyjaśnia).

Kontrola poprawności: suma udziałów wychodzi ~94%, reszta to gotówka.
"""
from __future__ import annotations

import csv
import io
import os
from collections import defaultdict

import requests

# opublikowany arkusz -> eksport CSV
KLUCZ = os.environ.get(
    "AWP_KLUCZ",
    "2PACX-1vQT7uecuE4ONP7z6L71E1y9F0mWp-Wbs6MrXpBtJ20toZwZhUuo0MVI36ahr1jpEqJJi1hXMKTnseRI",
)
URL = f"https://docs.google.com/spreadsheets/d/e/{KLUCZ}/pub?output=csv"

# Poniżej tego progu różnicę uznajemy za zgodność. Pół punktu procentowego
# to świadomy wybór użytkownika, nie przypadek.
PROG = 0.5

# --------------------------------------------------------------------------- #
#  Instrumenty poza zasięgiem
#
#  Kryptowaluty są z porównania wykluczone całkowicie. Fundusze ETF i ETN
#  notowane w USA są dla inwestora detalicznego z UE niedostępne (brak KID
#  wymaganego przez PRIIPs), a do tego część z nich to instrumenty lewarowane
#  i odwrotne. Takie pozycje nigdy się nie zgodzą, więc pokazywanie ich jako
#  "brakujących" byłoby wieczną fałszywą alarmówką.
#
#  Udziały docelowe pozostałych pozycji są przeliczane na nowo, tak by sumowały
#  się do 100% dostępnego uniwersum - inaczej cel byłby systematycznie zaniżony.
# --------------------------------------------------------------------------- #

# rozpoznawane po końcówce (BTCUSD, ETHUSD...) plus jawna lista
KRYPTO = {"BTCUSD", "ETHUSD", "LTCUSD", "BCHUSD", "SOLUSD", "DOGEUSD"}

# ETF-y, ETN-y i instrumenty lewarowane obecne w arkuszu
FUNDUSZE = {
    "SPXS", "SQQQ", "SDS",            # lewarowane odwrotne (Hedging Vehicles)
    "SCHD", "XLE", "KWEB", "OIH",     # zwykłe ETF-y sektorowe
    "GLD", "SLV", "SLVP", "NLR",      # metale i uran
    "UFO", "SPCX", "ANGX", "BXDC",    # tematyczne i fundusze zamknięte
    "SILVER",                          # pozycja towarowa, nie akcja
}

DODATKOWE = {x.strip().upper() for x in os.environ.get("WZORZEC_POMIN", "").split(",") if x.strip()}


def poza_zasiegiem(tic: str) -> str | None:
    """Zwraca powód wykluczenia albo None, gdy instrument jest dostępny."""
    t = tic.upper()
    if t in KRYPTO or t.endswith("USD"):
        return "krypto"
    if t in FUNDUSZE or t in DODATKOWE:
        return "fundusz"
    return None


def _procent(s: str) -> float | None:
    s = (s or "").strip().replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def pobierz(timeout: int = 30) -> str:
    r = requests.get(URL, timeout=timeout)
    r.raise_for_status()
    return r.text


def parsuj(tekst: str) -> dict:
    """Zwraca {tickery: {TIC: udzial}, koszyki: {nazwa: udzial}, przypisanie: {TIC: koszyk}}."""
    wiersze = list(csv.reader(io.StringIO(tekst)))
    koszyk = None
    tickery: dict[str, float] = defaultdict(float)
    koszyki: dict[str, float] = defaultdict(float)
    przypisanie: dict[str, str] = {}
    rdzenne: set[str] = set()

    for r in wiersze:
        if len(r) > 2 and "% of portfolio assets" in r[2]:
            koszyk = r[1].strip()
            continue
        if len(r) < 5:
            continue
        tic = r[4].strip().upper()
        udzial = _procent(r[2])
        if not tic or udzial is None or not tic.isalnum():
            continue
        tickery[tic] += udzial
        koszyki[koszyk or "Bez koszyka"] += udzial
        przypisanie.setdefault(tic, koszyk or "Bez koszyka")
        if r[3].strip().endswith("*"):
            rdzenne.add(tic)

    return {
        "tickery": dict(tickery),
        "koszyki": dict(koszyki),
        "przypisanie": przypisanie,
        "rdzenne": sorted(rdzenne),
        "suma": round(sum(tickery.values()), 2),
    }


def porownaj(wzor: dict, pods: dict) -> dict:
    """Zestawia udziały docelowe z faktycznymi. Podstawą procentów po naszej
    stronie jest suma aktywów, tak samo jak w reszcie panelu."""
    podstawa = pods.get("suma_aktywow") or 0.0
    faktyczne: dict[str, float] = {}
    wartosci: dict[str, float] = {}
    for t in pods.get("tickery", []):
        udzial = (t["wartosc"] / podstawa * 100) if podstawa else 0.0
        faktyczne[t["symbol"].upper()] = udzial
        wartosci[t["symbol"].upper()] = t["wartosc"]

    # Wyrzucamy krypto i fundusze, a udziały reszty skalujemy tak, żeby
    # sumowały się do 100% tego, co realnie możesz kupić.
    surowy_cel = wzor["tickery"]
    pominiete = {t: p for t in surowy_cel if (p := poza_zasiegiem(t))}
    dostepne = {t: u for t, u in surowy_cel.items() if t not in pominiete}
    suma_dostepnych = sum(dostepne.values())
    skala = (100.0 / suma_dostepnych) if suma_dostepnych else 1.0
    cel = {t: u * skala for t, u in dostepne.items()}

    # z faktycznych też usuwamy to, czego nie porównujemy
    faktyczne = {t: u for t, u in faktyczne.items() if not poza_zasiegiem(t)}
    wszystkie = sorted(set(cel) | set(faktyczne))

    pozycje = []
    for tic in wszystkie:
        c = cel.get(tic, 0.0)
        f = faktyczne.get(tic, 0.0)
        roznica = f - c
        if c and not f:
            rodzaj = "brakuje"
        elif f and not c:
            rodzaj = "nadmiarowa"
        elif abs(roznica) <= PROG:
            rodzaj = "zgodne"
        else:
            rodzaj = "dokup" if roznica < 0 else "sprzedaj"
        pozycje.append({
            "ticker": tic,
            "koszyk": wzor["przypisanie"].get(tic, "—"),
            "cel": c,
            # wartość wprost z arkusza, przed przeskalowaniem - żeby dało się
            # zestawić panel z arkuszem bez liczenia w pamięci
            "cel_arkusz": surowy_cel.get(tic, 0.0),
            "faktyczne": f,
            "roznica": roznica,
            "kwota": roznica / 100 * podstawa,   # ile dokupić (minus) lub sprzedać (plus)
            "rodzaj": rodzaj,
            "rdzenna": tic in wzor["rdzenne"],
            "wartosc": wartosci.get(tic, 0.0),
        })

    # koszyki liczymy po przypisaniu ze wzorca, żeby porównywać jabłka z jabłkami
    fakt_kosz: dict[str, float] = defaultdict(float)
    for p in pozycje:
        fakt_kosz[p["koszyk"]] += p["faktyczne"]
    # koszyki liczymy z przeskalowanych celów, żeby zgadzały się z pozycjami
    cel_kosz: dict[str, float] = defaultdict(float)
    for t, u in cel.items():
        cel_kosz[wzor["przypisanie"].get(t, "—")] += u
    # Koszyk, z którego NIC nie da się kupić (np. Hedging Vehicles to same
    # lewarowane ETF-y), nie trafiłby do cel_kosz i zniknąłby z panelu bez śladu.
    # Arkusz ma go jednak w spisie, więc pokazujemy go z celem zero - inaczej
    # zestawienie z arkuszem nie zgadza się co do liczby pozycji, a to wygląda
    # na zgubione dane.
    for nazwa in wzor["koszyki"]:
        cel_kosz.setdefault(nazwa, 0.0)

    koszyki = []
    for nazwa, c in sorted(cel_kosz.items(), key=lambda x: -x[1]):
        f = fakt_kosz.get(nazwa, 0.0)
        koszyki.append({"koszyk": nazwa, "cel": c, "faktyczne": f, "roznica": f - c,
                        # suma wprost z arkusza, razem z krypto i funduszami -
                        # ta liczba ma się zgadzać z arkuszem co do setnych
                        "cel_arkusz": wzor["koszyki"].get(nazwa, 0.0),
                        "zgodne": abs(f - c) <= PROG})

    licznik = defaultdict(int)
    for p in pozycje:
        licznik[p["rodzaj"]] += 1

    return {
        "pozycje": sorted(pozycje, key=lambda p: -abs(p["roznica"])),
        "koszyki": koszyki,
        "licznik": dict(licznik),
        "prog": PROG,
        "suma_wzorca": wzor["suma"],
        "podstawa": podstawa,
        # największa pojedyncza rozbieżność - najszybszy wskaźnik "jak bardzo odjechałem"
        "max_roznica": max((abs(p["roznica"]) for p in pozycje), default=0.0),
        "pominiete": sorted(pominiete.items()),
        "skala": skala,
        "suma_dostepnych": round(suma_dostepnych, 2),
    }
