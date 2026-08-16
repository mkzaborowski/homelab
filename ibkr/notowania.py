"""Notowania na żywo z Tradiera - opcjonalne uzupełnienie danych z Flex.

Po co: Flex oddaje wyciąg z poprzedniej sesji, więc cena opcji aktualizuje się
raz na dobę. Do samego rozliczenia premii to wystarcza, ale próg odkupu trzeba
łapać w ciągu dnia - stąd osobne źródło kursów.

Darmowe konto deweloperskie Tradiera daje notowania opóźnione (piaskownica),
płatne - na żywo. Adres bazowy jest w zmiennej, więc jedno i drugie działa
bez zmiany kodu.

Bez TRADIER_TOKEN moduł milczy i zwraca pustkę, a cały panel liczy dalej na
cenach z Flex. Brak notowań nie może wyłączyć analizy.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

TOKEN = os.environ.get("TRADIER_TOKEN", "").strip()
# piaskownica: https://sandbox.tradier.com/v1 (dane opóźnione, konto darmowe)
# produkcja:   https://api.tradier.com/v1     (na żywo, konto płatne)
BAZA = os.environ.get("TRADIER_BAZA", "https://sandbox.tradier.com/v1").rstrip("/")
TIMEOUT = int(os.environ.get("TRADIER_TIMEOUT", "20"))
# ile symboli w jednym zapytaniu - Tradier przyjmuje listę po przecinku
PACZKA = 40


def skonfigurowane() -> bool:
    return bool(TOKEN)


def opis() -> str:
    if not TOKEN:
        return "no TRADIER_TOKEN - prices from the IBKR statement only"
    rodzaj = "delayed (sandbox)" if "sandbox" in BAZA else "live"
    return f"Tradier quotes, {rodzaj}"


def symbol_opcji(s: str) -> str:
    """Symbol OCC bez spacji. IBKR podaje „LUNR  260918C00021000",
    Tradier oczekuje „LUNR260918C00021000"."""
    return (s or "").replace(" ", "").upper()


def _zapytaj(sciezka: str, params: dict) -> dict:
    url = f"{BAZA}/{sciezka.lstrip('/')}?" + urllib.parse.urlencode(params)
    zad = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(zad, timeout=TIMEOUT) as o:
        return json.loads(o.read().decode("utf-8"))


def _cena_z_wiersza(w: dict) -> float | None:
    """Cena z notowania.

    Dla opcji świadomie preferujemy środek widełek zamiast ostatniej
    transakcji: przy niepłynnych seriach „last" bywa sprzed wielu godzin
    i potrafi być grubo obok rynku, a odkup i tak wykonuje się przy ask.
    """
    bid, ask = w.get("bid"), w.get("ask")
    try:
        if bid is not None and ask is not None and float(bid) > 0 and float(ask) > 0:
            return (float(bid) + float(ask)) / 2.0
    except (TypeError, ValueError):
        pass
    for pole in ("last", "close", "prevclose"):
        v = w.get(pole)
        try:
            if v is not None and float(v) > 0:
                return float(v)
        except (TypeError, ValueError):
            continue
    return None


def pobierz(symbole: list[str]) -> dict[str, dict]:
    """Notowania dla listy symboli (akcje i opcje razem).

    Klucze wyniku to symbole w postaci przekazanej na wejściu, żeby dzwoniący
    nie musiał pamiętać o normalizacji. Błąd sieci albo braku uprawnień nie
    rzuca wyjątkiem - zwracamy tyle, ile się udało."""
    if not TOKEN or not symbole:
        return {}
    # mapowanie znormalizowany -> oryginalny, bo Tradier odda swoją postać
    mapa = {symbol_opcji(s): s for s in symbole if s}
    wynik: dict[str, dict] = {}
    klucze = list(mapa)
    for i in range(0, len(klucze), PACZKA):
        paczka = klucze[i:i + PACZKA]
        try:
            dane = _zapytaj("markets/quotes", {"symbols": ",".join(paczka),
                                               "greeks": "false"})
        except Exception:                                       # noqa: BLE001
            continue
        q = ((dane or {}).get("quotes") or {}).get("quote")
        if q is None:
            continue
        if isinstance(q, dict):
            q = [q]
        for w in q:
            sym = symbol_opcji(str(w.get("symbol") or ""))
            cena = _cena_z_wiersza(w)
            if not sym or cena is None or sym not in mapa:
                continue
            wynik[mapa[sym]] = {
                "cena": cena,
                "bid": w.get("bid"), "ask": w.get("ask"), "last": w.get("last"),
                "zrodlo": "tradier",
            }
    return wynik


def symbole_ze_zrzutu(dane: dict) -> list[str]:
    """Wszystko, co warto odpytać: kontrakty opcyjne i ich instrumenty bazowe."""
    poz = dane.get("pozycje", [])
    opcje_ = [p.get("symbol") for p in poz
              if (p.get("klasa") or "").upper() in ("OPT", "FOP") and p.get("symbol")]
    bazowe = [p.get("bazowy") for p in poz
              if (p.get("klasa") or "").upper() in ("OPT", "FOP") and p.get("bazowy")]
    return sorted(set(opcje_) | set(bazowe))
