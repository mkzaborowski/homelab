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

# --------------------------------------------------------------------------- #
#  Europejskie odpowiedniki funduszy indeksowych
#
#  Amerykańskiego ETF-u z arkusza nie kupisz, ale fundusz UCITS śledzący TEN
#  SAM indeks - tak. Bez tej tabeli taki fundusz w portfelu był podwójnie
#  źle liczony: pozycja z arkusza znikała jako „fundusz", a Twój odpowiednik
#  wychodził jako „Not in model".
#
#  DOPASOWANIE PO ISIN, NIGDY PO TICKERZE. Tickery z LSE pokrywają się
#  z amerykańskimi, a znaczą co innego: „SLVP" w arkuszu to fundusz spółek
#  wydobywczych srebra, a „SLVP" na LSE to Invesco Physical Silver ETC -
#  fizyczny metal. Dopasowanie po nazwie symbolu połączyłoby je po cichu.
#
#  Tylko fundusze INDEKSOWE: odpowiednik ma śledzić ten sam indeks. Każdy
#  wpis sprawdzony w prospekcie/nocie funduszu (wrzesień 2026). Świadomie
#  pominięte:
#    SCHD  - żaden UCITS nie śledzi Dow Jones U.S. Dividend 100,
#    SLVP  - brak UCITS na MSCI ACWI Select Silver Miners,
#    SPXS, SQQQ, SDS - lewar -3x/-2x; europejskie produkty mają inny mnożnik,
#          więc to inna ekspozycja, nie odpowiednik.
#
#  `pokrewny` = inny, choć bliski indeks. Taki odpowiednik liczy się do
#  porównania, ale panel pisze wprost, że to nie jest ten sam indeks.
# --------------------------------------------------------------------------- #

ODPOWIEDNIKI: dict[str, dict] = {
    "XLE": {
        "indeks": "S&P Energy Select Sector",
        "isin": {
            "IE00BWBXM492": ("SXLE", "SPDR S&P U.S. Energy Select Sector UCITS", False),
            # wersja z limitem wagi 20% na spółkę - ten sam skład, inne wagi szczytowe
            "IE00B435CG94": ("XLES", "Invesco Energy S&P US Select Sector UCITS", False),
        },
    },
    "KWEB": {
        "indeks": "CSI Overseas China Internet",
        "isin": {"IE00BFXR7892": ("KWEB", "KraneShares CSI China Internet UCITS", False)},
    },
    "OIH": {
        "indeks": "MVIS US Listed Oil Services 25",
        # wersja z limitem 10% na spółkę
        "isin": {"IE000NXF88S1": ("OIHV", "VanEck Oil Services UCITS", False)},
    },
    "UFO": {
        "indeks": "S-Network Space",
        "isin": {"IE00BLH3CV30": ("YODA", "Procure Space UCITS", False)},
    },
    "NLR": {
        "indeks": "MVIS Global Uranium & Nuclear Energy",
        # MarketVector Global Uranium and Nuclear Energy INFRASTRUCTURE - bliski, nie ten sam
        "isin": {"IE000M7V94E1": ("NUCL", "VanEck Uranium and Nuclear Technologies UCITS", True)},
    },
}


def _reczne_odpowiedniki() -> dict[str, str]:
    """WZORZEC_ODPOWIEDNIKI="SCHD=IE00ABC,UFO=JEDG" - ISIN albo symbol z konta.

    Na wypadek funduszu, którego tabela nie zna. Decyzja człowieka wygrywa
    z tabelą, więc wpis tutaj może też odłączyć automatyczne dopasowanie
    (wtedy wystarczy wskazać inny ISIN)."""
    wynik: dict[str, str] = {}
    for para in os.environ.get("WZORZEC_ODPOWIEDNIKI", "").split(","):
        if "=" in para:
            k, v = para.split("=", 1)
            if k.strip() and v.strip():
                wynik[v.strip().upper()] = k.strip().upper()
    return wynik


def _europejski(isin: str) -> bool:
    """ISIN spoza USA = fundusz europejski, nawet jeśli ma amerykański ticker."""
    return bool(isin) and not isin.upper().startswith("US")


def dopasuj_odpowiedniki(symbole: list[str], instrumenty: dict[str, dict]) -> dict[str, dict]:
    """{symbol z konta: {"wzor": ticker z arkusza, "nazwa", "indeks", "pokrewny", "reczny"}}.

    Symbol z konta nieobecny w katalogu instrumentów (brak ISIN) nie jest
    dopasowywany - bez ISIN nie odróżnimy KWEB z Londynu od KWEB z Nowego Jorku.
    """
    po_isin = {isin: (tic, *dane) for tic, w in ODPOWIEDNIKI.items() for isin, dane in w["isin"].items()}
    reczne = _reczne_odpowiedniki()
    wynik: dict[str, dict] = {}
    for sym in symbole:
        info = instrumenty.get(sym) or instrumenty.get(sym.upper()) or {}
        isin = (info.get("isin") or "").upper()
        cel = reczne.get(isin) or reczne.get(sym.upper())
        if cel:
            wynik[sym] = {"wzor": cel, "nazwa": info.get("nazwa") or sym,
                          "indeks": ODPOWIEDNIKI.get(cel, {}).get("indeks", ""),
                          "pokrewny": False, "reczny": True, "isin": isin}
        elif isin in po_isin:
            tic, _skrot, nazwa, pokrewny = po_isin[isin]
            wynik[sym] = {"wzor": tic, "nazwa": nazwa, "indeks": ODPOWIEDNIKI[tic]["indeks"],
                          "pokrewny": pokrewny, "reczny": False, "isin": isin}
    return wynik


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


def porownaj(wzor: dict, pods: dict, instrumenty: dict[str, dict] | None = None) -> dict:
    """Zestawia udziały docelowe z faktycznymi. Podstawą procentów po naszej
    stronie jest suma aktywów, tak samo jak w reszcie panelu."""
    podstawa = pods.get("suma_aktywow") or 0.0
    faktyczne: dict[str, float] = {}
    wartosci: dict[str, float] = {}
    for t in pods.get("tickery", []):
        udzial = (t["wartosc"] / podstawa * 100) if podstawa else 0.0
        faktyczne[t["symbol"].upper()] = udzial
        wartosci[t["symbol"].upper()] = t["wartosc"]

    instrumenty = instrumenty or {}
    surowy_cel = wzor["tickery"]

    # Europejskie odpowiedniki: udział funduszu UCITS przechodzi na pozycję
    # z arkusza, której indeks śledzi. XLES liczy się jako XLE.
    odpowiedniki = {s: d for s, d in dopasuj_odpowiedniki(list(faktyczne), instrumenty).items()
                    if d["wzor"] in surowy_cel}
    dopasowane: dict[str, list[dict]] = defaultdict(list)
    for sym, d in odpowiedniki.items():
        u, w = faktyczne.pop(sym), wartosci.pop(sym, 0.0)
        faktyczne[d["wzor"]] = faktyczne.get(d["wzor"], 0.0) + u
        wartosci[d["wzor"]] = wartosci.get(d["wzor"], 0.0) + w
        dopasowane[d["wzor"]].append({"symbol": sym, **d})

    # Europejski fundusz BEZ odpowiednika w arkuszu, który przypadkiem ma ticker
    # z arkusza (SLVP z LSE to srebro fizyczne, a nie spółki wydobywcze
    # z arkusza), dostaje osobny klucz - inaczej wylądowałby w cudzym wierszu.
    for sym in list(faktyczne):
        isin = (instrumenty.get(sym) or {}).get("isin") or ""
        if sym in surowy_cel and sym not in dopasowane and _europejski(isin):
            nowy = f"{sym} (UCITS)"
            faktyczne[nowy] = faktyczne.pop(sym)
            wartosci[nowy] = wartosci.pop(sym, 0.0)

    # Wyrzucamy krypto i fundusze bez kupionego odpowiednika, a udziały reszty
    # skalujemy tak, żeby sumowały się do 100% tego, co realnie możesz kupić.
    pominiete = {t: p for t in surowy_cel if (p := poza_zasiegiem(t)) and t not in dopasowane}
    dostepne = {t: u for t, u in surowy_cel.items() if t not in pominiete}
    suma_dostepnych = sum(dostepne.values())
    skala = (100.0 / suma_dostepnych) if suma_dostepnych else 1.0
    cel = {t: u * skala for t, u in dostepne.items()}

    # z faktycznych też usuwamy to, czego nie porównujemy - ale tylko amerykańskie
    # fundusze; odpowiedniki już siedzą pod tickerem z arkusza
    faktyczne = {t: u for t, u in faktyczne.items()
                 if t in dopasowane or t.endswith(" (UCITS)")
                 or not poza_zasiegiem(t)
                 or _europejski((instrumenty.get(t) or {}).get("isin") or "")}
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
            # co z Twojego konta liczy się za ten ticker z arkusza
            "odpowiedniki": dopasowane.get(tic, []),
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
        # fundusze z arkusza, które da się kupić w UE, choć jeszcze ich nie masz
        "do_kupienia_w_ue": sorted(
            (t, [f"{sk} ({isin})" + (" – pokrewny indeks" if pk else "")
                 for isin, (sk, _n, pk) in ODPOWIEDNIKI[t]["isin"].items()])
            for t in pominiete if t in ODPOWIEDNIKI),
        "odpowiedniki": sorted(((sym, d) for sym, d in odpowiedniki.items()),
                               key=lambda x: x[1]["wzor"]),
        "skala": skala,
        "suma_dostepnych": round(suma_dostepnych, 2),
    }
