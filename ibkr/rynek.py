"""Historia kursów: warstwa dostawcy danych rynkowych.

Silniki ryzyka mają dostawać znormalizowane szeregi i nie wiedzieć, skąd
pochodzą - stąd rozdział na interfejs i implementację (§33 briefu). Zamiana
źródła to podmiana jednej klasy, bez dotykania analityki.

OBECNE ŹRÓDŁO: Yahoo Finance, punkt końcowy wykresu. Działa, pokrywa 49 z 55
spółek portfela i wszystkie wzorce, kosztuje zero. Jest to jednak endpoint
NIEOFICJALNY: regulamin Yahoo ogranicza użycie automatyczne, a punkt końcowy
może zniknąć bez zapowiedzi. Decyzja świadoma, podjęta przez właściciela
panelu na własne ryzyko, przy użyciu prywatnym i bez redystrybucji danych.
Dlatego właśnie warstwa jest wymienialna.

Ceny bierzemy skorygowane o splity i dywidendy (adjclose). Bez tej korekty
podział akcji wygląda w szeregu jak spadek o połowę i zatruwa zmienność,
betę oraz wszystkie korelacje.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Wzorce do regresji czynnikowych. Dobrane pod ten konkretny portfel: szeroki
# rynek, technologia, małe spółki, metale, energia, obligacje i dolar.
WZORCE = {
    "SPY": "US broad market",
    "QQQ": "Technology / growth",
    "IWM": "Small caps",
    "GLD": "Gold",
    "SLV": "Silver",
    "XLE": "Energy",
    "TLT": "Treasuries",
    "UUP": "US dollar",
}

ODSTEP = float(os.environ.get("RYNEK_ODSTEP", "0.15"))
TIMEOUT = int(os.environ.get("RYNEK_TIMEOUT", "20"))


class BladRynku(Exception):
    pass


class DostawcaCen:
    """Interfejs. Implementacja ma zwracać [(data ISO, cena skorygowana)]."""

    nazwa = "abstrakcyjny"
    opoznienie = "nieznane"

    def dzienne(self, symbol: str, zakres: str = "1y") -> list[tuple[str, float]]:
        raise NotImplementedError


class Yahoo(DostawcaCen):
    nazwa = "Yahoo Finance"
    opoznienie = "koniec dnia"
    BAZA = "https://query1.finance.yahoo.com/v8/finance/chart/"

    def dzienne(self, symbol: str, zakres: str = "1y") -> list[tuple[str, float]]:
        url = f"{self.BAZA}{urllib.parse.quote(symbol)}?range={zakres}&interval=1d"
        zad = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(zad, timeout=TIMEOUT) as o:
                dane = json.loads(o.read())
        except urllib.error.HTTPError as e:
            raise BladRynku(f"{symbol}: HTTP {e.code}") from e
        except Exception as e:                                  # noqa: BLE001
            raise BladRynku(f"{symbol}: {type(e).__name__}") from e

        wyniki = (dane.get("chart") or {}).get("result") or []
        if not wyniki:
            raise BladRynku(f"{symbol}: pusta odpowiedź")
        w = wyniki[0]
        znaczniki = w.get("timestamp") or []
        wsk = w.get("indicators") or {}
        # adjclose koryguje splity i dywidendy - bez tego podział akcji
        # wygląda jak spadek o połowę i psuje całą statystykę
        skor = (wsk.get("adjclose") or [{}])[0].get("adjclose")
        if not skor:
            skor = (wsk.get("quote") or [{}])[0].get("close")
        if not znaczniki or not skor:
            raise BladRynku(f"{symbol}: brak szeregu cen")

        out = []
        for t, c in zip(znaczniki, skor):
            if c is None:
                continue
            d = datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat()
            out.append((d, float(c)))
        return out



def dostawca() -> DostawcaCen:
    """Punkt wymiany dostawcy. Docelowo wybierany zmienną środowiskową."""
    return Yahoo()


def pobierz_wiele(symbole: list[str], zakres: str = "1y",
                  d: DostawcaCen | None = None) -> tuple[dict[str, list], list[str]]:
    """Szeregi dla listy symboli. Zwraca (dane, lista_niepowodzeń).

    Pojedyncze niepowodzenie nie przerywa całości: spółka świeżo notowana albo
    wycofana z obrotu po prostu nie ma historii i tak trzeba to potraktować."""
    d = d or dostawca()
    out, bledy = {}, []
    for s in symbole:
        try:
            szereg = d.dzienne(s, zakres)
            if szereg:
                out[s] = szereg
            else:
                bledy.append(s)
        except BladRynku:
            bledy.append(s)
        time.sleep(ODSTEP)
    return out, bledy


def zwroty_z_cen(szereg: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Dzienne stopy z szeregu cen. Ceny są już skorygowane, więc zwykły
    iloraz wystarcza."""
    out = []
    for (d0, c0), (d1, c1) in zip(szereg, szereg[1:]):
        if c0 > 0:
            out.append((d1, c1 / c0 - 1.0))
    return out


def dopasuj_daty(serie: dict[str, list[tuple[str, float]]]) -> tuple[list[str], dict[str, list[float]]]:
    """Sprowadza szeregi do wspólnych dni.

    Bez tego macierz kowariancji liczyłaby się na przesuniętych względem
    siebie datach, a wynik wyglądałby poprawnie i byłby fałszywy - to jeden
    z najłatwiejszych do przeoczenia błędów w analizie portfela."""
    if not serie:
        return [], {}
    wspolne = None
    mapy = {}
    for s, szereg in serie.items():
        m = dict(szereg)
        mapy[s] = m
        wspolne = set(m) if wspolne is None else (wspolne & set(m))
    dni = sorted(wspolne or [])
    return dni, {s: [mapy[s][d] for d in dni] for s in mapy}
