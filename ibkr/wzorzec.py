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

Kontrola poprawności: suma udziałów wychodzi ~98%, reszta to gotówka.
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

    cel = wzor["tickery"]
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
    koszyki = []
    for nazwa, c in sorted(wzor["koszyki"].items(), key=lambda x: -x[1]):
        f = fakt_kosz.get(nazwa, 0.0)
        koszyki.append({"koszyk": nazwa, "cel": c, "faktyczne": f, "roznica": f - c,
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
    }
