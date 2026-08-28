"""Przeglądarka wykresu spółki - parametry z adresu na gotowy rysunek.

Konfiguracja wykresu siedzi w ADRESIE, nie w stanie przeglądarki. Dzięki temu
konkretny układ (spółka, zakres, zestaw wskaźników) da się wysłać komuś linkiem
albo wrzucić do zakładek, a panel nie potrzebuje ani grama stanu po stronie
klienta poza tym, co i tak trzyma w formularzu.

Cały rysunek powstaje po stronie serwera, jak każdy inny wykres w tym panelu.
"""
from __future__ import annotations

import historia
import wykresy

# Barwy nakładek. Nie z palety kategorii, bo tam kolory mają odróżniać
# KATEGORIE między sobą; tutaj mają odróżniać średnie od świec i od siebie
# nawzajem, a przy tym nie udawać zieleni i czerwieni ze świec - te dwie
# znaczą już „wzrost" i „spadek".
BARWY_SREDNICH = ["#0071E3", "#FF9500", "#8E44AD", "#00A3A3", "#C2185B"]

OKRESY_MAKS = 5          # więcej średnich niż tyle to już nie wykres, tylko sieć
OKRES_MIN, OKRES_MAKS = 2, 400

OSCYLATORY = {"rsi": "RSI", "macd": "MACD", "stoch": "Stochastic"}


def _okresy(surowe: str) -> list[int]:
    """„50,100,200" → [50, 100, 200]. Odsiewa śmieci zamiast się wywracać:
    to jest parametr z adresu, więc może w nim być cokolwiek."""
    out: list[int] = []
    for kawalek in (surowe or "").split(","):
        kawalek = kawalek.strip()
        if not kawalek.isdigit():
            continue
        n = int(kawalek)
        if OKRES_MIN <= n <= OKRES_MAKS and n not in out:
            out.append(n)
        if len(out) >= OKRESY_MAKS:
            break
    return out


def _flaga(v: str | None, domyslnie: bool = False) -> bool:
    if v is None:
        return domyslnie
    return v.strip().lower() in ("1", "true", "tak", "on", "yes")


def ustawienia(p: dict) -> dict:
    """Sprowadza parametry zapytania do jednego, sprawdzonego słownika."""
    zakres = p.get("zakres", "1y")
    return {
        "zakres": zakres if zakres in historia.ZAKRESY else "1y",
        "typ": "linia" if p.get("typ") == "linia" else "swiece",
        "sma": _okresy(p.get("sma", "50,100")),
        "ema": _okresy(p.get("ema", "")),
        "bb": _flaga(p.get("bb")),
        "wolumen": _flaga(p.get("wol"), True),
        "oscylatory": [o for o in (p.get("osc", "rsi") or "").split(",")
                       if o.strip() in OSCYLATORY][:3],
    }


def rysuj(symbol: str, ust: dict) -> str:
    """Gotowy SVG albo komunikat, gdy nie ma z czego rysować."""
    sesje = historia.pobierz(symbol, ust["zakres"])
    if not sesje:
        return '<p class="wyk-brak">Price history unavailable right now.</p>'

    z = [s["zamkniecie"] for s in sesje]
    hi = [s["max"] for s in sesje]
    lo = [s["min"] for s in sesje]

    nakladki: list[dict] = []
    barwa = iter(BARWY_SREDNICH * 3)
    for okres in ust["sma"]:
        nakladki.append({"nazwa": f"SMA({okres})", "wartosci": historia.sma(z, okres),
                         "kolor": next(barwa)})
    for okres in ust["ema"]:
        nakladki.append({"nazwa": f"EMA({okres})", "wartosci": historia.ema(z, okres),
                         "kolor": next(barwa), "kreska": "5 3"})
    if ust["bb"]:
        g, s, d = historia.bollinger(z)
        # Wstęgi rysujemy cieniej i przerywanym: to jest tło dla ceny,
        # a nie kolejna średnia konkurująca z nią o uwagę.
        nakladki.append({"nazwa": "BB(20,2)", "wartosci": g, "kolor": "#8E8E93",
                         "grubosc": 1.0, "kreska": "4 3"})
        nakladki.append({"nazwa": "", "wartosci": d, "kolor": "#8E8E93",
                         "grubosc": 1.0, "kreska": "4 3"})

    oscylatory: list[dict] = []
    for o in ust["oscylatory"]:
        if o == "rsi":
            oscylatory.append({
                "nazwa": "RSI(14)", "zakres": (0, 100), "progi": [30, 50, 70],
                "serie": [{"nazwa": "", "wartosci": historia.rsi(z), "kolor": "#0071E3"}],
            })
        elif o == "macd":
            linia, sygnal, hist = historia.macd(z)
            oscylatory.append({
                "nazwa": "MACD(12,26,9)", "zakres": None, "progi": [0], "histogram": hist,
                "serie": [{"nazwa": "", "wartosci": linia, "kolor": "#0071E3"},
                          {"nazwa": "sig", "wartosci": sygnal, "kolor": "#FF9500"}],
            })
        elif o == "stoch":
            k, d = historia.stochastyczny(hi, lo, z)
            oscylatory.append({
                "nazwa": "Stoch(14,3)", "zakres": (0, 100), "progi": [20, 80],
                "serie": [{"nazwa": "%K", "wartosci": k, "kolor": "#0071E3"},
                          {"nazwa": "%D", "wartosci": d, "kolor": "#FF9500"}],
            })

    return wykresy.wykres_ceny(sesje, nakladki=nakladki, oscylatory=oscylatory,
                               wolumen=ust["wolumen"], symbol=symbol, typ=ust["typ"])
