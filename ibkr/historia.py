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
    gotowe = _swieze(symbol)
    if gotowe is not None:
        return gotowe

    # requests, nie urllib: reszta projektu chodzi na requests i ma przez to
    # pakiet certyfikatów. Goły urllib bierze magazyn systemowy, którego
    # w obrazie kontenera po prostu nie ma.
    try:
        odp = requests.get(
            f"{BAZA}/{symbol}",
            params={"range": zakres, "interval": "1d"},
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
        _cache[symbol] = (time.time(), sesje)
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
