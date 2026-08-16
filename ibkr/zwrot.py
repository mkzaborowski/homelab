"""Silnik zwrotu: TWR, MWR/XIRR, Modified Dietz, obsunięcia.

Po co to w ogóle istnieje: dotąd „zwrot" był zwykłą różnicą NAV. Dopóki na
rachunek nic nie wpływa, wynik wychodzi przypadkiem poprawny. Pierwsza wpłata
zostanie policzona jako zysk, a pierwsza wypłata jako strata. To najgroźniejszy
błąd w całym panelu, bo jest niewidoczny do chwili, w której zaczyna kłamać.

Trzy miary i różne pytania, na które odpowiadają:

  TWR  - jak radził sobie portfel, niezależnie od tego, kiedy dokładałeś
         pieniądze. Tym porównuje się z indeksem.
  MWR  - ile zarobiłeś Ty, z uwzględnieniem terminów wpłat. To XIRR.
  Dietz- przybliżenie TWR, gdy nie znamy dokładnej godziny przepływu.

Wszystko liczone na czystej bibliotece standardowej: przy 250 dniach i 58
spółkach nie ma czego przyspieszać, a brak zależności upraszcza obraz.
"""
from __future__ import annotations

import math
from datetime import date, datetime

DNI_W_ROKU = 365.0
# Minimalna liczba obserwacji, poniżej której miara jest statystycznie pusta.
# Sharpe z trzynastu dni to nie jest oszacowanie, to przypadek.
MIN_OBSERWACJI = 20


def _na_date(s) -> date | None:
    if isinstance(s, date):
        return s
    s = (s or "").strip()
    for wzor in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s[:10] if "-" in s else s[:8], wzor).date()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
#  przepływy zewnętrzne
# --------------------------------------------------------------------------- #

RODZAJ_PRZELEWU = "Deposits/Withdrawals"


def przeplywy_z_operacji(operacje: list[dict]) -> dict[str, float]:
    """Wpłaty i wypłaty w rozbiciu na dni, z sekcji CashTransaction.

    Bierzemy WYŁĄCZNIE rodzaj „Deposits/Withdrawals". Dywidendy, odsetki
    i podatki są wynikiem portfela, nie przepływem od inwestora - wrzucenie
    ich tutaj zaniżyłoby zwrot o kwotę, którą portfel faktycznie zarobił.
    """
    out: dict[str, float] = {}
    for o in operacje:
        if (o.get("rodzaj") or "") != RODZAJ_PRZELEWU:
            continue
        d = _na_date(o.get("data"))
        if d:
            out[d.isoformat()] = out.get(d.isoformat(), 0.0) + float(o.get("kwota") or 0.0)
    return out


def wykryj_skoki(szereg: list[dict], prog: float = 0.08) -> list[dict]:
    """Dni, w których NAV skoczył tak, że wygląda to na przelew, nie na rynek.

    Nie zgadujemy kwoty przelewu - tylko oznaczamy dzień jako podejrzany,
    żeby nie policzyć go po cichu jako wynik inwestycyjny. §17 briefu."""
    podejrzane = []
    for a, b in zip(szereg, szereg[1:]):
        n0, n1 = a.get("nav") or 0.0, b.get("nav") or 0.0
        if n0 <= 0:
            continue
        zmiana = (n1 - n0) / n0
        if abs(zmiana) >= prog:
            podejrzane.append({"data": b["data"], "zmiana": zmiana,
                               "nav_przed": n0, "nav_po": n1,
                               "roznica": n1 - n0})
    return podejrzane


# --------------------------------------------------------------------------- #
#  stopy zwrotu
# --------------------------------------------------------------------------- #

def zwroty_dzienne(szereg: list[dict],
                   przeplywy: dict[str, float] | None = None) -> list[tuple[str, float]]:
    """Dzienne stopy zwrotu z korektą o przepływy zewnętrzne.

    Wzór na dzień t:  r = NAV_t / (NAV_(t-1) + przepływ_t) - 1

    Przepływ wchodzi do MIANOWNIKA, czyli traktujemy go jako dostępny od
    początku dnia. Nie jest to wybór teoretyczny - wynika z uzgodnienia
    z rocznym wyciągiem IBKR, który sam podaje TWR w sekcji ChangeInNAV.
    Przy tej konwencji trafiamy w jego liczbę co do trzeciego miejsca po
    przecinku (40,479%), a przy przepływie na koniec dnia rozjeżdżamy się
    o 1,3 pp. Wersja z odejmowaniem w liczniku jest równie „logiczna",
    ale opisuje inne księgowanie niż to, które stosuje IBKR.
    """
    przeplywy = przeplywy or {}
    out = []
    for a, b in zip(szereg, szereg[1:]):
        n0, n1 = a.get("nav") or 0.0, b.get("nav") or 0.0
        if n0 <= 0:
            continue
        podstawa = n0 + przeplywy.get(b["data"], 0.0)
        if podstawa <= 0:
            continue
        out.append((b["data"], n1 / podstawa - 1.0))
    return out


def twr(szereg: list[dict], przeplywy: dict[str, float] | None = None) -> float | None:
    """Zwrot ważony czasem - iloczyn dziennych stóp.

    To jest miara jakości zarządzania: nie zależy od tego, kiedy dokładałeś
    kapitał, więc tylko ją wolno porównywać z indeksem."""
    r = zwroty_dzienne(szereg, przeplywy)
    if not r:
        return None
    iloczyn = 1.0
    for _, x in r:
        iloczyn *= (1.0 + x)
    return iloczyn - 1.0


def krzywa_twr(szereg: list[dict], przeplywy: dict[str, float] | None = None,
               baza: float = 100.0) -> list[tuple[str, float]]:
    """Skumulowany TWR jako indeks od wspólnej bazy.

    To jest krzywa, którą wolno położyć obok indeksu giełdowego - w
    przeciwieństwie do samego NAV, który rośnie także od wpłat. Przy tym
    portfelu różnica jest drastyczna: wartość konta urosła o kilkadziesiąt
    razy, ale prawie wszystko to przelewy, a wynik inwestycyjny to 40%.
    Wykres NAV odpowiada na pytanie „ile mam", ten na pytanie „ile zarobiłem".
    """
    r = zwroty_dzienne(szereg, przeplywy)
    if not r:
        return []
    poziom = baza
    out = [(szereg[0]["data"], baza)]
    for data, x in r:
        poziom *= (1.0 + x)
        out.append((data, poziom))
    return out


def modified_dietz(nav_poczatek: float, nav_koniec: float,
                   przeplywy: list[tuple[str, float]], od: str, do: str) -> float | None:
    """Przybliżenie TWR, gdy nie znamy godziny przepływu.

    Każdy przepływ ważony jest częścią okresu, przez którą pracował. Metoda
    jest defensywna i standardowa - GIPS dopuszcza ją tam, gdzie brakuje
    wyceny śróddziennej. §5 briefu wprost o nią prosi."""
    d0, d1 = _na_date(od), _na_date(do)
    if not d0 or not d1 or nav_poczatek <= 0:
        return None
    dni = (d1 - d0).days
    if dni <= 0:
        return None
    suma_pf = 0.0
    wazone = 0.0
    for data, kwota in przeplywy:
        d = _na_date(data)
        if not d or not (d0 < d <= d1):
            continue
        waga = (dni - (d - d0).days) / dni
        suma_pf += kwota
        wazone += waga * kwota
    mianownik = nav_poczatek + wazone
    if abs(mianownik) < 1e-9:
        return None
    return (nav_koniec - nav_poczatek - suma_pf) / mianownik


def xirr(przeplywy: list[tuple[str, float]], prob: int = 200) -> float | None:
    """Wewnętrzna stopa zwrotu przy nieregularnych datach (MWR).

    Rozwiązujemy NPV(r) = 0 bisekcją zamiast Newtonem: przy przepływach
    zmieniających znak Newton potrafi uciec, a bisekcja zawsze zbiega, o ile
    rozwiązanie leży w przedziale. Wymaga co najmniej jednego przepływu
    dodatniego i jednego ujemnego - inaczej stopa nie istnieje."""
    poz = [(d, k) for d, k in przeplywy if k > 0]
    neg = [(d, k) for d, k in przeplywy if k < 0]
    if not poz or not neg:
        return None
    daty = [_na_date(d) for d, _ in przeplywy]
    if any(d is None for d in daty):
        return None
    d0 = min(daty)

    def npv(r: float) -> float:
        s = 0.0
        for (d, k) in zip(daty, [k for _, k in przeplywy]):
            lata = (d - d0).days / DNI_W_ROKU
            s += k / ((1.0 + r) ** lata)
        return s

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(prob):
        sr = 0.5 * (lo + hi)
        f = npv(sr)
        if abs(f) < 1e-9:
            return sr
        if f_lo * f < 0:
            hi, f_hi = sr, f
        else:
            lo, f_lo = sr, f
        if hi - lo < 1e-12:
            break
    return 0.5 * (lo + hi)


def annualizuj(zwrot: float, dni: int) -> float | None:
    """Skala roczna. Poniżej miesiąca nie annualizujemy - wynik byłby
    liczbą efektowną i bez treści."""
    if dni < 30 or zwrot <= -1.0:
        return None
    return (1.0 + zwrot) ** (DNI_W_ROKU / dni) - 1.0


# --------------------------------------------------------------------------- #
#  obsunięcia
# --------------------------------------------------------------------------- #

def obsuniecia(szereg: list[dict]) -> dict:
    """Maksymalne i bieżące obsunięcie wraz z czasem trwania.

    Liczone na szczycie kroczącym: obsunięcie to odległość od najwyższej
    dotąd wartości, nie od początku okresu."""
    if len(szereg) < 2:
        return {"maks": None, "biezace": None, "dostepne": False}
    szczyt = szereg[0].get("nav") or 0.0
    data_szczytu = szereg[0]["data"]
    maks, maks_od, maks_do, maks_dno = 0.0, "", "", ""
    najdluzsze = 0
    dni_w_obsunieciu = 0
    for w in szereg:
        nav = w.get("nav") or 0.0
        if nav >= szczyt:
            szczyt, data_szczytu = nav, w["data"]
            najdluzsze = max(najdluzsze, dni_w_obsunieciu)
            dni_w_obsunieciu = 0
            continue
        dni_w_obsunieciu += 1
        if szczyt > 0:
            ob = nav / szczyt - 1.0
            if ob < maks:
                maks, maks_od, maks_dno = ob, data_szczytu, w["data"]
    najdluzsze = max(najdluzsze, dni_w_obsunieciu)

    ostatni = szereg[-1].get("nav") or 0.0
    biezace = (ostatni / szczyt - 1.0) if szczyt > 0 else 0.0
    return {
        "maks": maks, "maks_od": maks_od, "maks_dno": maks_dno,
        "biezace": biezace, "szczyt": szczyt, "szczyt_data": data_szczytu,
        "dni_od_szczytu": dni_w_obsunieciu,
        "najdluzsze_dni": najdluzsze,
        "dostepne": True,
    }


# --------------------------------------------------------------------------- #
#  zestawienie
# --------------------------------------------------------------------------- #

def zwroty_miesieczne(szereg: list[dict],
                      przeplywy: dict[str, float] | None = None) -> list[dict]:
    """Stopy miesięczne złożone z dziennych.

    Składamy iloczynem, nie sumujemy: miesiąc +10% i -10% to -1%, nie zero.
    Miesiąc niepełny (bieżący) jest oznaczony, żeby nie porównywać go
    z zamkniętymi tak, jakby był kompletny."""
    dzienne = zwroty_dzienne(szereg, przeplywy)
    if not dzienne:
        return []
    wg: dict[str, list[float]] = {}
    for data, r in dzienne:
        wg.setdefault(data[:7], []).append(r)
    # ostatni miesiąc szeregu jest z definicji niepełny - dane kończą się
    # w połowie. Pierwszy też, bo zaczynamy od dowolnego dnia.
    pierwszy, ostatni = dzienne[0][0][:7], dzienne[-1][0][:7]
    out = []
    for ym in sorted(wg):
        il = 1.0
        for r in wg[ym]:
            il *= (1.0 + r)
        out.append({"miesiac": ym, "zwrot": il - 1.0, "dni": len(wg[ym]),
                    "pelny": ym not in (pierwszy, ostatni)})
    return out


def podsumowanie(szereg: list[dict], operacje: list[dict] | None = None) -> dict:
    """Komplet miar zwrotu wraz z informacją, czy w ogóle są policzalne.

    Każda miara niesie `dostepne` i `obserwacji`, żeby panel nigdy nie
    pokazał liczby, której nie ma na czym oprzeć. §4 i §7 briefu."""
    if len(szereg) < 2:
        return {"dostepne": False, "obserwacji": len(szereg), "powod": "brak historii"}

    przeplywy = przeplywy_z_operacji(operacje or [])
    r = zwroty_dzienne(szereg, przeplywy)
    n = len(r)
    od, do = szereg[0]["data"], szereg[-1]["data"]
    d0, d1 = _na_date(od), _na_date(do)
    dni = (d1 - d0).days if d0 and d1 else 0

    calkowity = twr(szereg, przeplywy)
    nav0, nav1 = szereg[0].get("nav") or 0.0, szereg[-1].get("nav") or 0.0

    # MWR liczymy z perspektywy INWESTORA, nie rachunku: wartość początkowa
    # i każda wpłata to jego wydatek (znak ujemny), a wartość końcowa to
    # wpływ. W danych z Flexa wpłata ma znak dodatni, bo tam patrzymy od
    # strony konta - stąd odwrócenie znaku.
    pf = [(od, -nav0)] + [(d, -k) for d, k in sorted(przeplywy.items())] + [(do, nav1)]

    return {
        "dostepne": True,
        "obserwacji": n,
        "wystarczajaco": n >= MIN_OBSERWACJI,
        "min_obserwacji": MIN_OBSERWACJI,
        "od": od, "do": do, "dni": dni,
        "twr": calkowity,
        "twr_roczny": annualizuj(calkowity, dni) if calkowity is not None else None,
        "mwr": xirr(pf),
        "dietz": modified_dietz(nav0, nav1, sorted(przeplywy.items()), od, do),
        "prosty": (nav1 - nav0) / nav0 if nav0 > 0 else None,
        "przeplywow": len(przeplywy),
        "skoki": wykryj_skoki(szereg),
        "obsuniecia": obsuniecia(szereg),
        "zwroty": r,
    }
