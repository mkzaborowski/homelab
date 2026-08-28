"""Przeglądarka wykresu spółki - parametry z adresu na gotowy rysunek.

Konfiguracja wykresu siedzi w ADRESIE, nie w stanie przeglądarki. Dzięki temu
konkretny układ (spółka, zakres, zestaw wskaźników) da się wysłać komuś linkiem
albo wrzucić do zakładek, a panel nie potrzebuje ani grama stanu po stronie
klienta poza tym, co i tak trzyma w formularzu.

Cały rysunek powstaje po stronie serwera, jak każdy inny wykres w tym panelu.
"""
from __future__ import annotations

import datetime as dt
import json
from html import escape as e

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
        # Okno wybrane myszą na wykresie. Daty, nie indeksy: indeks znaczy co
        # innego po każdej zmianie zakresu albo interwału, więc link z indeksami
        # pokazywałby po tygodniu inny fragment.
        "od": (p.get("od") or "").strip()[:10],
        "do": (p.get("do") or "").strip()[:10],
    }


def _okno(sesje: list[dict], od: str, do: str) -> tuple[int, int]:
    """Indeksy [pierwszy, ostatni+1] sesji mieszczących się w oknie dat."""
    if not od and not do:
        return 0, len(sesje)
    def dzien(x: dict) -> str:
        return dt.datetime.fromtimestamp(x["czas"], dt.timezone.utc).strftime("%Y-%m-%d")
    i = 0
    j = len(sesje)
    if od:
        while i < j and dzien(sesje[i]) < od:
            i += 1
    if do:
        while j > i and dzien(sesje[j - 1]) > do:
            j -= 1
    # Okno węższe niż dwie sesje nie jest wykresem - wracamy do całości
    # zamiast rysować jedną świecę na całą szerokość.
    return (0, len(sesje)) if j - i < 2 else (i, j)


def rysuj(symbol: str, ust: dict) -> str:
    """Gotowy SVG albo komunikat, gdy nie ma z czego rysować."""
    sesje = historia.pobierz(symbol, ust["zakres"])
    if not sesje:
        return '<p class="wyk-brak">Price history unavailable right now.</p>'

    # Wskaźniki liczymy z PEŁNEGO zakresu, a okno wycinamy dopiero na końcu.
    # Odwrotna kolejność znaczyłaby, że po przybliżeniu do miesiąca średnia
    # ze 100 sesji znika - bo w oknie nie ma stu sesji, choć w danych są.
    wyciete = _okno(sesje, ust["od"], ust["do"])

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

    a, b = wyciete
    if (a, b) != (0, len(sesje)):
        sesje = sesje[a:b]
        for nak in nakladki:
            nak["wartosci"] = nak["wartosci"][a:b]
        for o in oscylatory:
            for sr in o["serie"]:
                sr["wartosci"] = sr["wartosci"][a:b]
            if o.get("histogram"):
                o["histogram"] = o["histogram"][a:b]

    svg = wykresy.wykres_ceny(sesje, nakladki=nakladki, oscylatory=oscylatory,
                              wolumen=ust["wolumen"], symbol=symbol, typ=ust["typ"])

    # Dane jadą razem z rysunkiem, w <script type="application/json">.
    # Przeglądarka takiego bloku NIE wykonuje - to zwykły tekst do odczytania.
    # Bez tego odczyt pod kursorem wymagałby pytania serwera przy każdym ruchu
    # myszy, czyli byłby niemożliwy.
    serie = [{"n": n["nazwa"], "k": n["kolor"], "w": n["wartosci"]}
             for n in nakladki if n["nazwa"]]
    for o in oscylatory:
        for sr in o["serie"]:
            nazwa = f'{o["nazwa"]} {sr["nazwa"]}'.strip()
            serie.append({"n": nazwa, "k": sr["kolor"], "w": sr["wartosci"]})

    dane = {
        "symbol": symbol,
        "daty": [dt.datetime.fromtimestamp(x["czas"], dt.timezone.utc).strftime("%Y-%m-%d") for x in sesje],
        "o": [x["otwarcie"] for x in sesje], "h": [x["max"] for x in sesje],
        "l": [x["min"] for x in sesje], "c": [x["zamkniecie"] for x in sesje],
        "v": [x["wolumen"] for x in sesje],
        "serie": serie,
    }
    # separators bez spacji: przy 250 sesjach i ośmiu seriach to kilkanaście
    # kilobajtów różnicy na każdym przerysowaniu
    ladunek = json.dumps(dane, separators=(",", ":"), default=lambda v: None)
    return (f'{svg}<script type="application/json" class="wyk-dane">'
            f'{e(ladunek, quote=False)}</script>')
