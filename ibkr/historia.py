"""Roczna historia dzienna spółki - świece na wykres pozycji.

DLACZEGO NIE STOCKCHARTS. Ich obrazek wygląda dokładnie tak, jak trzeba,
ale nie da się go użyć w panelu z dwóch niezależnych powodów:

  * osadzony w stronie zwraca 403 - to ochrona przed hotlinkowaniem,
    a obchodzenie jej przez proxy na naszym serwerze byłoby omijaniem
    zabezpieczenia, które właściciel postawił świadomie,
  * średniej 100-dniowej nie da się zamówić parametrem adresu; `a=SMA(100)`
    i pokrewne kończą się po ich stronie błędem 500, bo własne nakładki
    wymagają zapisanego stylu na koncie StockCharts.

Rysujemy więc sami, z surowych notowań - tak jak każdy inny wykres w tym
panelu. Przy okazji wykres jest dokładnie taki, jak zamówiony: świece dzienne
z roku, RSI(14) i średnia ze 100 sesji, a nie 50 i 200 z cudzego domyślnego
układu.

Źródło: publiczny endpoint wykresów Yahoo Finance. Bez klucza, bez konta,
zwraca komplet OHLC. Gdyby przestał odpowiadać, panel pokazuje brak wykresu
i liczy dalej - to jest ozdoba pozycji, nie podstawa wyceny.
"""
from __future__ import annotations

import time

import requests

BAZA = "https://query1.finance.yahoo.com/v8/finance/chart"
TIMEOUT = 15

# Zakres → (parametr Yahoo, interwał). Powyżej dwóch lat schodzimy z dziennych
# świec na tygodniowe i miesięczne: pięć lat sesji dziennych to 1250 świec,
# których na wykresie o szerokości 760 punktów i tak nie da się rozróżnić,
# a rysunek robi się cztery razy cięższy.
ZAKRESY: dict[str, tuple[str, str]] = {
    "1mo": ("1mo", "1d"), "3mo": ("3mo", "1d"), "6mo": ("6mo", "1d"),
    "1y": ("1y", "1d"), "2y": ("2y", "1d"),
    "5y": ("5y", "1wk"), "max": ("max", "1mo"),
}
ETYKIETY_ZAKRESU = {"1mo": "1M", "3mo": "3M", "6mo": "6M", "1y": "1Y",
                    "2y": "2Y", "5y": "5Y", "max": "MAX"}

# Notowania dzienne zmieniają się raz na sesję, a panel odświeża się co
# kilkadziesiąt minut. Pobieranie przy każdym otwarciu wykresu biłoby w Yahoo
# bez powodu i spowalniało kliknięcie.
WAZNOSC_S = 6 * 3600
_cache: dict[str, tuple[float, list[dict]]] = {}


def _swieze(symbol: str) -> list[dict] | None:
    wpis = _cache.get(symbol)
    if not wpis:
        return None
    kiedy, dane = wpis
    return dane if time.time() - kiedy < WAZNOSC_S else None


def pobierz(symbol: str, zakres: str = "1y") -> list[dict]:
    """Lista sesji: {data, otwarcie, max, min, zamkniecie, wolumen}.

    Pusta lista znaczy „nie wiem" - nie „brak notowań". Wywołujący ma to
    potraktować jak brak wykresu, a nie jak spadek do zera.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return []
    zakres = zakres if zakres in ZAKRESY else "1y"
    klucz = f"{symbol}:{zakres}"
    gotowe = _swieze(klucz)
    if gotowe is not None:
        return gotowe
    rng, interwal = ZAKRESY[zakres]

    # requests, nie urllib: reszta projektu chodzi na requests i ma przez to
    # pakiet certyfikatów. Goły urllib bierze magazyn systemowy, którego
    # w obrazie kontenera po prostu nie ma.
    try:
        odp = requests.get(
            f"{BAZA}/{symbol}",
            params={"range": rng, "interval": interwal},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        odp.raise_for_status()
        surowe = odp.json()
    except (requests.RequestException, ValueError):
        return []

    wynik = (surowe.get("chart") or {}).get("result") or []
    if not wynik:
        return []
    r = wynik[0]
    czasy = r.get("timestamp") or []
    kw = ((r.get("indicators") or {}).get("quote") or [{}])[0]

    sesje: list[dict] = []
    for i, ts in enumerate(czasy):
        o, h, l, c = (kw.get(k) or [None] * len(czasy) for k in ("open", "high", "low", "close"))
        # Yahoo wstawia null dla sesji bez obrotu (święta na części giełd).
        # Świeca bez ceny nie ma czego rysować, a wciągnięta jako zero
        # zmiażdżyłaby całą skalę.
        if None in (o[i], h[i], l[i], c[i]):
            continue
        wol = (kw.get("volume") or [None] * len(czasy))[i]
        sesje.append({
            "czas": ts,
            "otwarcie": float(o[i]), "max": float(h[i]),
            "min": float(l[i]), "zamkniecie": float(c[i]),
            "wolumen": float(wol) if wol is not None else 0.0,
        })

    if sesje:
        _cache[klucz] = (time.time(), sesje)
    return sesje


def sma(wartosci: list[float], okno: int) -> list[float | None]:
    """Średnia krocząca. None do momentu, w którym okno się wypełni -
    dorysowanie średniej ze 100 sesji na dwudziestej sesji byłoby rysowaniem
    liczby, której nie ma."""
    out: list[float | None] = []
    suma = 0.0
    for i, v in enumerate(wartosci):
        suma += v
        if i >= okno:
            suma -= wartosci[i - okno]
        out.append(suma / okno if i >= okno - 1 else None)
    return out


def rsi(zamkniecia: list[float], okres: int = 14) -> list[float | None]:
    """RSI Wildera - ta sama metoda, którą liczy StockCharts.

    Wygładzanie jest wykładnicze, nie średnią prostą z ostatnich N zmian:
    zwykła średnia daje inne wartości i wykres rozjeżdżałby się z każdym
    innym narzędziem, w którym ktoś sprawdzi ten sam papier.
    """
    if len(zamkniecia) <= okres:
        return [None] * len(zamkniecia)
    out: list[float | None] = [None] * len(zamkniecia)
    zyski = straty = 0.0
    for i in range(1, okres + 1):
        d = zamkniecia[i] - zamkniecia[i - 1]
        zyski += max(d, 0.0)
        straty += max(-d, 0.0)
    sz, ss = zyski / okres, straty / okres
    out[okres] = 100.0 if ss == 0 else 100 - 100 / (1 + sz / ss)
    for i in range(okres + 1, len(zamkniecia)):
        d = zamkniecia[i] - zamkniecia[i - 1]
        sz = (sz * (okres - 1) + max(d, 0.0)) / okres
        ss = (ss * (okres - 1) + max(-d, 0.0)) / okres
        out[i] = 100.0 if ss == 0 else 100 - 100 / (1 + sz / ss)
    return out


def ema(wartosci: list[float], okno: int) -> list[float | None]:
    """Wykładnicza średnia krocząca.

    Rozbieg bierzemy ze średniej prostej z pierwszych `okno` wartości, a nie
    z pierwszej ceny: EMA startująca od jednego punktu przez kilkadziesiąt
    sesji goni resztę i na początku wykresu rysuje krzywą, której nie ma.
    """
    if len(wartosci) < okno or okno < 1:
        return [None] * len(wartosci)
    out: list[float | None] = [None] * (okno - 1)
    poprzednia = sum(wartosci[:okno]) / okno
    out.append(poprzednia)
    mnoznik = 2.0 / (okno + 1)
    for v in wartosci[okno:]:
        poprzednia = (v - poprzednia) * mnoznik + poprzednia
        out.append(poprzednia)
    return out


def macd(zamkniecia: list[float], szybka: int = 12, wolna: int = 26,
         sygnal: int = 9) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """MACD: linia, sygnał i histogram różnicy między nimi."""
    e_szybka, e_wolna = ema(zamkniecia, szybka), ema(zamkniecia, wolna)
    linia: list[float | None] = [
        (a - b) if a is not None and b is not None else None
        for a, b in zip(e_szybka, e_wolna)
    ]
    # Sygnał liczymy z linii MACD od miejsca, w którym ta w ogóle istnieje.
    gotowe = [v for v in linia if v is not None]
    przesuniecie = len(linia) - len(gotowe)
    sig_gotowe = ema(gotowe, sygnal)
    sygnalowa: list[float | None] = [None] * przesuniecie + sig_gotowe
    histogram: list[float | None] = [
        (a - b) if a is not None and b is not None else None
        for a, b in zip(linia, sygnalowa)
    ]
    return linia, sygnalowa, histogram


def stochastyczny(maksima: list[float], minima: list[float], zamkniecia: list[float],
                  okres: int = 14, wygladzenie: int = 3) -> tuple[list[float | None], list[float | None]]:
    """Oscylator stochastyczny %K i %D.

    %K mówi, gdzie zamknięcie leży w zakresie ostatnich `okres` sesji.
    Sesja bez zakresu (max == min) daje 50, a nie dzielenie przez zero:
    „w środku" jest tu uczciwszą odpowiedzią niż brak wartości.
    """
    k: list[float | None] = [None] * len(zamkniecia)
    for i in range(okres - 1, len(zamkniecia)):
        hh = max(maksima[i - okres + 1:i + 1])
        ll = min(minima[i - okres + 1:i + 1])
        k[i] = 50.0 if hh == ll else (zamkniecia[i] - ll) / (hh - ll) * 100.0
    gotowe = [v for v in k if v is not None]
    d_gotowe = sma(gotowe, wygladzenie) if gotowe else []
    d: list[float | None] = [None] * (len(k) - len(d_gotowe)) + d_gotowe
    return k, d


def bollinger(zamkniecia: list[float], okres: int = 20, odchylen: float = 2.0
              ) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Wstęgi Bollingera: środek (SMA) oraz górna i dolna o `odchylen` sigma."""
    srodek = sma(zamkniecia, okres)
    gora: list[float | None] = []
    dol: list[float | None] = []
    for i, s in enumerate(srodek):
        if s is None:
            gora.append(None)
            dol.append(None)
            continue
        okno = zamkniecia[i - okres + 1:i + 1]
        wariancja = sum((v - s) ** 2 for v in okno) / okres
        sigma = wariancja ** 0.5
        gora.append(s + odchylen * sigma)
        dol.append(s - odchylen * sigma)
    return gora, srodek, dol
