"""Wycena opcji, greki i analiza pozycji opcyjnych.

Flex nie podaje ani zmienności implikowanej, ani greków - daje tylko cenę
rynkową opcji i cenę instrumentu bazowego. To jednak wystarcza: z ceny
rynkowej odwracamy model Blacka-Scholesa i wyliczamy zmienność implikowaną,
a z niej wszystkie greki. Dzięki temu nie potrzeba żadnego zewnętrznego
dostawcy danych i liczby są spójne z tym, co faktycznie widać na rachunku.

Model: Black-Scholes-Merton z ciągłą stopą dywidendy. Opcje na akcje w USA
są amerykańskie, więc dla krótkich calli na spółkach bez dywidendy wycena
europejska jest równa amerykańskiej (wcześniejsze wykonanie się nie opłaca).
Przy spółkach z dywidendą to przybliżenie zaniża wartość - dlatego ryzyko
wcześniejszego przypisania liczymy osobno, na podstawie wartości czasowej.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime

# Mnożnik kontraktu na akcje w USA: jeden kontrakt to 100 akcji.
MNOZNIK = 100.0
# Stopa wolna od ryzyka do dyskontowania. Przy terminach liczonych w tygodniach
# jej wpływ jest marginalny, ale trzymamy ją jawnie zamiast zakładać zero.
STOPA_WOLNA = float(os.environ.get("STOPA_WOLNA", "0.0425"))
DNI_W_ROKU = 365.0
# Granice poszukiwania zmienności implikowanej. Górna jest wysoka celowo -
# tygodniowe opcje na rozchwianych spółkach potrafią mieć IV grubo ponad 200%.
SIGMA_MIN, SIGMA_MAX = 1e-4, 8.0


# --------------------------------------------------------------------------- #
#  rozkład normalny (bez scipy - potrzebne są tylko erf i exp)
# --------------------------------------------------------------------------- #

def fi(x: float) -> float:
    """Gęstość standardowego rozkładu normalnego."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def Fi(x: float) -> float:
    """Dystrybuanta standardowego rozkładu normalnego."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --------------------------------------------------------------------------- #
#  Black-Scholes-Merton
# --------------------------------------------------------------------------- #

def _d1_d2(S: float, K: float, T: float, r: float, q: float, sigma: float):
    v = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / v
    return d1, d1 - v


def wycen(S: float, K: float, T: float, r: float, q: float, sigma: float,
          prawo: str) -> float:
    """Wartość teoretyczna opcji. Po wygaśnięciu zwraca wartość wewnętrzną."""
    call = prawo.upper().startswith("C")
    if T <= 0 or sigma <= 0:
        return max(0.0, (S - K) if call else (K - S))
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    dysk_r, dysk_q = math.exp(-r * T), math.exp(-q * T)
    if call:
        return S * dysk_q * Fi(d1) - K * dysk_r * Fi(d2)
    return K * dysk_r * Fi(-d2) - S * dysk_q * Fi(-d1)


def greki(S: float, K: float, T: float, r: float, q: float, sigma: float,
          prawo: str) -> dict:
    """Komplet greków dla JEDNEJ opcji (na akcję, nie na kontrakt).

    Konwencje przyjęte tak, jak podaje je większość platform:
      delta  - zmiana ceny opcji na 1 USD ruchu bazowego,
      gamma  - zmiana delty na 1 USD ruchu bazowego,
      vega   - zmiana ceny na 1 punkt procentowy zmienności,
      theta  - zmiana ceny na jeden dzień kalendarzowy,
      rho    - zmiana ceny na 1 punkt procentowy stopy.
    Drugiego rzędu (vanna, volga, charm) w ujęciu surowym, bez skalowania.
    """
    call = prawo.upper().startswith("C")
    if T <= 0 or sigma <= 0:
        wewn = max(0.0, (S - K) if call else (K - S))
        d = (1.0 if S > K else 0.0) if call else (-1.0 if S < K else 0.0)
        return {"delta": d, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0,
                "vanna": 0.0, "volga": 0.0, "charm": 0.0, "wartosc": wewn}

    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    pier_T = math.sqrt(T)
    dysk_r, dysk_q = math.exp(-r * T), math.exp(-q * T)
    gest = fi(d1)

    delta = dysk_q * (Fi(d1) if call else Fi(d1) - 1.0)
    gamma = dysk_q * gest / (S * sigma * pier_T)
    vega = S * dysk_q * gest * pier_T                      # na 1.00 zmienności

    czlon_czasu = -(S * dysk_q * gest * sigma) / (2.0 * pier_T)
    if call:
        theta_rok = czlon_czasu - r * K * dysk_r * Fi(d2) + q * S * dysk_q * Fi(d1)
        rho_rok = K * T * dysk_r * Fi(d2)
    else:
        theta_rok = czlon_czasu + r * K * dysk_r * Fi(-d2) - q * S * dysk_q * Fi(-d1)
        rho_rok = -K * T * dysk_r * Fi(-d2)

    vanna = -dysk_q * gest * d2 / sigma                    # d delta / d sigma
    volga = vega * d1 * d2 / sigma                         # d vega  / d sigma
    charm_rok = (dysk_q * gest * (2.0 * (r - q) * T - d2 * sigma * pier_T)
                 / (2.0 * T * sigma * pier_T))
    if not call:
        charm_rok -= q * dysk_q * Fi(-d1) * 0.0            # człon q pomijalny przy q=0

    return {
        "delta": delta,
        "gamma": gamma,
        "vega": vega / 100.0,                              # na 1 punkt proc.
        "theta": theta_rok / DNI_W_ROKU,                   # na dzień
        "rho": rho_rok / 100.0,                            # na 1 punkt proc.
        "vanna": vanna,
        "volga": volga,
        "charm": charm_rok / DNI_W_ROKU,
        "wartosc": wycen(S, K, T, r, q, sigma, prawo),
    }


def zmiennosc_implikowana(cena: float, S: float, K: float, T: float, r: float,
                          q: float, prawo: str) -> float | None:
    """Zmienność wynikająca z ceny rynkowej. Newton z zabezpieczeniem bisekcją.

    Zwraca None, gdy zadanie nie ma rozwiązania: cena poniżej wartości
    wewnętrznej (nieaktualny kurs albo szeroki spread) albo opcja już wygasła.
    Zgadywanie liczby w takiej sytuacji byłoby gorsze niż przyznanie się,
    że jej nie znamy - dlatego panel pokazuje wtedy wprost brak danych.
    """
    call = prawo.upper().startswith("C")
    if T <= 0 or cena <= 0 or S <= 0 or K <= 0:
        return None
    dolna = max(0.0, (S * math.exp(-q * T) - K * math.exp(-r * T)) if call
                else (K * math.exp(-r * T) - S * math.exp(-q * T)))
    gorna = (S * math.exp(-q * T)) if call else (K * math.exp(-r * T))
    if cena < dolna - 1e-9 or cena > gorna + 1e-9:
        return None

    # start z przybliżenia Brennera-Subrahmanyama, dobrego blisko ATM
    sigma = max(SIGMA_MIN, math.sqrt(2.0 * math.pi / T) * cena / S)
    sigma = min(sigma, SIGMA_MAX)
    for _ in range(60):
        roznica = wycen(S, K, T, r, q, sigma, prawo) - cena
        if abs(roznica) < 1e-10:
            return sigma
        d1, _ = _d1_d2(S, K, T, r, q, sigma)
        v = S * math.exp(-q * T) * fi(d1) * math.sqrt(T)   # vega na 1.00
        if v < 1e-12:
            break
        krok = roznica / v
        nowa = sigma - krok
        if not (SIGMA_MIN < nowa < SIGMA_MAX) or math.isnan(nowa):
            break
        if abs(krok) < 1e-12:
            return nowa
        sigma = nowa
    else:
        return sigma

    # Newton uciekł poza przedział - dobijamy bisekcją, która zawsze zbiega
    lo, hi = SIGMA_MIN, SIGMA_MAX
    if wycen(S, K, T, r, q, hi, prawo) < cena:
        return None
    for _ in range(200):
        sr = 0.5 * (lo + hi)
        if wycen(S, K, T, r, q, sr, prawo) < cena:
            lo = sr
        else:
            hi = sr
        if hi - lo < 1e-10:
            break
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------- #
#  prawdopodobieństwa
# --------------------------------------------------------------------------- #

def prawd_w_pieniadzu(S: float, K: float, T: float, r: float, q: float,
                      sigma: float, prawo: str) -> float:
    """P(opcja wygaśnie w pieniądzu) w mierze martyngałowej. Dla calla to N(d2).

    Uwaga na interpretację: to prawdopodobieństwo ryzykownie neutralne, nie
    prognoza rynkowa. Dla krótkiej opcji jest to zarazem ryzyko przypisania
    w dniu wygaśnięcia."""
    if T <= 0:
        wewn = (S > K) if prawo.upper().startswith("C") else (S < K)
        return 1.0 if wewn else 0.0
    if sigma <= 0:
        return 0.0
    _, d2 = _d1_d2(S, K, T, r, q, sigma)
    return Fi(d2) if prawo.upper().startswith("C") else Fi(-d2)


def prawd_dotkniecia(S: float, K: float, T: float, r: float, q: float,
                     sigma: float) -> float:
    """P(kurs dotknie strike'a choć raz przed wygaśnięciem).

    Zagadnienie pierwszego przejścia dla geometrycznego ruchu Browna. Zawsze
    wyraźnie wyższe niż P(w pieniądzu) na koniec - i to ono odpowiada realnemu
    ryzyku, że pozycję trzeba będzie rolować przed terminem."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 1.0 if S >= K else 0.0
    # Zasada odbicia dla ruchu Browna z dryfem. Dla bariery b = ln(K/S) > 0:
    #   P = Fi((mu*T - b)/v) + exp(2*mu*b/sigma^2) * Fi((-b - mu*T)/v)
    # Oba człony mają w argumencie MINUS b - przy plusie w drugim wzór daje
    # dla zerowego dryfu Fi(-x)+Fi(x) = 1, czyli stałą jedynkę niezależnie
    # od danych. Sprawdzian: przy mu = 0 całość musi wyjść 2*Fi(-b/v).
    mu = r - q - 0.5 * sigma * sigma
    v = sigma * math.sqrt(T)
    if K > S:                                       # bariera w górę
        b = math.log(K / S)
        pierwszy = Fi((mu * T - b) / v)
        try:
            czynnik = math.exp(2.0 * mu * b / (sigma * sigma))
        except OverflowError:
            czynnik = float("inf")
        drugi = czynnik * Fi((-b - mu * T) / v)
        return max(0.0, min(1.0, pierwszy + drugi))
    return 1.0                                      # już jest przy barierze


# --------------------------------------------------------------------------- #
#  analiza pozycji
# --------------------------------------------------------------------------- #

def _na_date(s: str) -> date | None:
    s = (s or "").strip()
    for wzor in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10] if "-" in s else s[:8], wzor).date()
        except ValueError:
            continue
    return None


def dni_do_wygasniecia(wygasa: str, dzis: date | None = None) -> int:
    d = _na_date(wygasa)
    if not d:
        return 0
    return max(0, (d - (dzis or date.today())).days)


@dataclass
class Pozycja:
    """Jedna pozycja opcyjna razem z całą policzoną statystyką."""
    symbol: str = ""
    bazowy: str = ""
    prawo: str = ""
    strike: float = 0.0
    wygasa: str = ""
    ilosc: float = 0.0                 # ujemna = wystawione
    kurs_bazowego: float = 0.0
    cena_opcji: float = 0.0
    premia: float = 0.0                # zainkasowana netto (dodatnia dla krótkich)
    wartosc_biezaca: float = 0.0       # ile kosztowałoby odkupienie
    zysk_otwarty: float = 0.0
    dni: int = 0
    iv: float | None = None
    greki: dict = field(default_factory=dict)
    prawd_itm: float | None = None
    prawd_dot: float | None = None
    akcje_pod: float = 0.0             # ile akcji bazowego mamy
    pokrycie: float = 0.0              # udział pokrycia (1.0 = w pełni)
    uwagi: list[str] = field(default_factory=list)

    @property
    def krotka(self) -> bool:
        return self.ilosc < 0

    @property
    def kontraktow(self) -> float:
        return abs(self.ilosc)

    @property
    def akcje_zaangazowane(self) -> float:
        return self.kontraktow * MNOZNIK

    @property
    def zrealizowany_udzial(self) -> float:
        """Jaka część maksymalnego zysku jest już zainkasowana."""
        return (self.zysk_otwarty / self.premia) if self.premia else 0.0

    @property
    def do_zainkasowania(self) -> float:
        """Ile jeszcze zostało do wzięcia, gdy opcja wygaśnie bez wartości."""
        return self.wartosc_biezaca

    @property
    def cena_wykonania_efektywna(self) -> float:
        """Faktyczna cena sprzedaży akcji przy przypisaniu: strike + premia."""
        if not self.akcje_zaangazowane:
            return self.strike
        return self.strike + self.premia / self.akcje_zaangazowane

    @property
    def zapas_do_strike(self) -> float:
        """O ile procent bazowy musi urosnąć, żeby dotknąć strike'a."""
        if not self.kurs_bazowego:
            return 0.0
        return (self.strike - self.kurs_bazowego) / self.kurs_bazowego

    @property
    def wartosc_czasowa(self) -> float:
        wewn = max(0.0, self.kurs_bazowego - self.strike) if self.prawo.upper().startswith("C") \
            else max(0.0, self.strike - self.kurs_bazowego)
        return self.cena_opcji - wewn

    @property
    def zwrot_roczny(self) -> float:
        """Premia odniesiona do zaangażowanego kapitału, w skali roku.

        Kapitał to akcje pod calla wycenione rynkowo - tyle realnie jest
        zamrożone pod tę pozycję."""
        kapital = self.akcje_zaangazowane * self.kurs_bazowego
        if kapital <= 0 or self.dni <= 0:
            return 0.0
        return (self.premia / kapital) * (DNI_W_ROKU / self.dni)

    @property
    def zwrot_przy_przypisaniu(self) -> float:
        """Zwrot, gdy akcje zostaną odebrane po strike'u - premia plus ruch kursu."""
        kapital = self.akcje_zaangazowane * self.kurs_bazowego
        if kapital <= 0:
            return 0.0
        ruch = (self.strike - self.kurs_bazowego) * self.akcje_zaangazowane
        return (self.premia + ruch) / kapital

    @property
    def delta_akcji(self) -> float:
        """Ekspozycja w akcjach bazowego, ze znakiem pozycji."""
        return self.greki.get("delta", 0.0) * self.ilosc * MNOZNIK

    @property
    def delta_dolarowa(self) -> float:
        return self.delta_akcji * self.kurs_bazowego

    @property
    def theta_dzienna(self) -> float:
        """Ile pozycja zarabia (dodatnie) lub traci na dobę z upływu czasu."""
        return self.greki.get("theta", 0.0) * self.ilosc * MNOZNIK

    @property
    def vega_pozycji(self) -> float:
        return self.greki.get("vega", 0.0) * self.ilosc * MNOZNIK

    @property
    def gamma_pozycji(self) -> float:
        return self.greki.get("gamma", 0.0) * self.ilosc * MNOZNIK

    @property
    def ryzyko_wczesniejszego(self) -> bool:
        """Wartość czasowa bliska zeru przy opcji w pieniądzu = realne ryzyko,
        że ktoś wykona kontrakt przed terminem."""
        w_pieniadzu = self.kurs_bazowego > self.strike \
            if self.prawo.upper().startswith("C") else self.kurs_bazowego < self.strike
        return w_pieniadzu and self.wartosc_czasowa < 0.05


def _kurs_bazowego(pozycje: list[dict], bazowy: str) -> float:
    """Kurs instrumentu bazowego z pozycji akcyjnych (wszystkie loty mają ten sam)."""
    for p in pozycje:
        if (p.get("klasa") or "").upper() == "STK" and p.get("symbol") == bazowy:
            if p.get("cena"):
                return float(p["cena"])
    return 0.0


def _akcje_bazowego(pozycje: list[dict], bazowy: str) -> float:
    return sum(float(p.get("ilosc") or 0.0) for p in pozycje
               if (p.get("klasa") or "").upper() == "STK" and p.get("symbol") == bazowy)


def analizuj_pozycje(dane: dict, dzis: date | None = None,
                     stopa: float = STOPA_WOLNA,
                     kursy: dict[str, dict] | None = None) -> list[Pozycja]:
    """Pełna analiza otwartych pozycji opcyjnych ze zrzutu portfela.

    `kursy` pozwala nadpisać ceny świeższymi notowaniami (patrz notowania.py).
    Bez nich liczymy na cenach z wyciągu, czyli z zamknięcia poprzedniej sesji."""
    dzis = dzis or date.today()
    kursy = kursy or {}
    pozycje = dane.get("pozycje", [])
    surowe = [p for p in pozycje if (p.get("klasa") or "").upper() in ("OPT", "FOP")]

    # Ten sam kontrakt bywa rozbity na kilka lotów - scalamy, bo ryzyko
    # i greki dotyczą sumy, a nie poszczególnych partii zakupu.
    scalone: dict[str, dict] = {}
    for p in surowe:
        k = p.get("symbol") or ""
        w = scalone.setdefault(k, {**p, "ilosc": 0.0, "koszt": 0.0, "wartosc": 0.0})
        w["ilosc"] += float(p.get("ilosc") or 0.0)
        w["koszt"] += float(p.get("koszt") or 0.0)
        w["wartosc"] += float(p.get("wartosc") or 0.0)

    wynik: list[Pozycja] = []
    for p in scalone.values():
        bazowy = p.get("bazowy") or ""
        S = (kursy.get(bazowy, {}).get("cena")
             or _kurs_bazowego(pozycje, bazowy))
        K = float(p.get("strike") or 0.0)
        prawo = (p.get("prawo") or "C").upper()
        dni = dni_do_wygasniecia(p.get("wygasa") or "", dzis)
        T = dni / DNI_W_ROKU
        cena = float(kursy.get(p.get("symbol") or "", {}).get("cena")
                     or p.get("cena") or 0.0)

        poz = Pozycja(
            symbol=p.get("symbol") or "", bazowy=bazowy, prawo=prawo, strike=K,
            wygasa=p.get("wygasa") or "", ilosc=float(p.get("ilosc") or 0.0),
            kurs_bazowego=S, cena_opcji=cena,
            # koszt krótkiej opcji jest ujemny (uznanie) - premia to jego moduł
            premia=abs(float(p.get("koszt") or 0.0)),
            # wartość bieżąca musi pochodzić z tego samego źródła co cena,
            # inaczej próg odkupu mieszałby notowanie z wczorajszym wyciągiem
            wartosc_biezaca=(cena * abs(float(p.get("ilosc") or 0.0)) * MNOZNIK
                             if kursy.get(p.get("symbol") or "")
                             else abs(float(p.get("wartosc") or 0.0))),
            zysk_otwarty=float(p.get("zysk") or 0.0),
            dni=dni,
        )
        poz.akcje_pod = _akcje_bazowego(pozycje, bazowy)
        if poz.akcje_zaangazowane:
            poz.pokrycie = poz.akcje_pod / poz.akcje_zaangazowane

        if not S:
            poz.uwagi.append("Brak kursu bazowego w zrzucie - greków nie liczę")
        elif dni == 0:
            poz.uwagi.append("Wygasa dziś - greki nie mają już zastosowania")
        else:
            iv = zmiennosc_implikowana(cena, S, K, T, stopa, 0.0, prawo)
            poz.iv = iv
            if iv is None:
                poz.uwagi.append("Cena opcji poza widełkami modelu - IV nie do wyliczenia")
            else:
                poz.greki = greki(S, K, T, stopa, 0.0, iv, prawo)
                poz.prawd_itm = prawd_w_pieniadzu(S, K, T, stopa, 0.0, iv, prawo)
                poz.prawd_dot = prawd_dotkniecia(S, K, T, stopa, 0.0, iv)

        if poz.krotka and poz.pokrycie < 1.0:
            brak = poz.akcje_zaangazowane - poz.akcje_pod
            poz.uwagi.append(f"Niepokryte: brakuje {brak:,.0f} akcji".replace(",", " "))
        if poz.ryzyko_wczesniejszego:
            poz.uwagi.append("Wartość czasowa bliska zeru - możliwe wcześniejsze przypisanie")

        wynik.append(poz)

    wynik.sort(key=lambda x: (x.dni, -abs(x.premia)))
    return wynik


# --------------------------------------------------------------------------- #
#  próg odkupu
# --------------------------------------------------------------------------- #

# Ile premii warto zainkasować, zanim domkniemy pozycję. Im bliżej wygaśnięcia,
# tym mniej sensu ma płacić za zamknięcie: theta i tak dokończy robotę, a każdy
# odkup kosztuje prowizję i spread. Dlatego próg rośnie wraz z upływem czasu.
PROGI_ODKUPU = (
    (22, 0.50),      # powyżej 21 dni: bierz 50% i wystawiaj nowy kontrakt
    (8, 0.65),       # 8-21 dni: 65%
    (0, 0.80),       # ostatni tydzień: tylko gdy zostało naprawdę tanio
)
# Poniżej tego zwrotu w skali roku dalsze trzymanie pozycji przestaje się
# opłacać - kapitał lepiej pracuje pod nowym kontraktem.
MIN_ZWROT_POZOSTALY = float(os.environ.get("MIN_ZWROT_POZOSTALY", "0.15"))


def udzial_docelowy(dni: int) -> float:
    for prog_dni, udzial in PROGI_ODKUPU:
        if dni >= prog_dni:
            return udzial
    return PROGI_ODKUPU[-1][1]


def kurs_dla_ceny_opcji(cena_docelowa: float, K: float, T: float, r: float,
                        q: float, sigma: float, prawo: str,
                        S_max_mnoznik: float = 5.0) -> float | None:
    """Przy jakim kursie bazowego opcja byłaby warta zadaną cenę.

    Cena calla rośnie monotonicznie wraz z kursem, więc bisekcja zbiega zawsze.
    Zakładamy niezmienioną zmienność i termin - to pokazuje sam wpływ kursu,
    a nie mieszankę kursu, czasu i zmienności naraz."""
    if T <= 0 or sigma <= 0 or cena_docelowa < 0:
        return None
    lo, hi = 1e-6, max(K, 1.0) * S_max_mnoznik
    if wycen(hi, K, T, r, q, sigma, prawo) < cena_docelowa:
        return None                      # nieosiągalne w rozsądnym zakresie
    if wycen(lo, K, T, r, q, sigma, prawo) > cena_docelowa:
        return None
    for _ in range(200):
        sr = 0.5 * (lo + hi)
        if wycen(sr, K, T, r, q, sigma, prawo) < cena_docelowa:
            lo = sr
        else:
            hi = sr
        if hi - lo < 1e-9:
            break
    return 0.5 * (lo + hi)


def prog_odkupu(p: Pozycja) -> dict | None:
    """Sugerowana cena odkupu wraz z kursem bazowego, który by ją wywołał.

    Liczymy wyłącznie dla pozycji krótkich - to je się odkupuje, żeby zamknąć
    zysk. Dla długich taki próg nie ma sensu."""
    if not p.krotka or not p.akcje_zaangazowane:
        return None
    premia_na_akcje = p.premia / p.akcje_zaangazowane
    udzial = udzial_docelowy(p.dni)
    cena_cel = premia_na_akcje * (1.0 - udzial)

    poziomy = []
    for u in (0.50, 0.65, 0.80, 0.90):
        c = premia_na_akcje * (1.0 - u)
        kurs = (kurs_dla_ceny_opcji(c, p.strike, p.dni / DNI_W_ROKU, STOPA_WOLNA,
                                    0.0, p.iv, p.prawo) if p.iv and p.dni > 0 else None)
        poziomy.append({
            "udzial": u,
            "cena": c,
            "koszt": c * p.akcje_zaangazowane,
            "zysk": p.premia - c * p.akcje_zaangazowane,
            "kurs_bazowego": kurs,
            "osiagniete": p.cena_opcji <= c + 1e-9,
        })

    kapital = p.akcje_zaangazowane * p.kurs_bazowego
    zwrot_pozostaly = ((p.wartosc_biezaca / kapital) * (DNI_W_ROKU / p.dni)
                       if kapital > 0 and p.dni > 0 else 0.0)

    powody = []
    if p.cena_opcji <= cena_cel + 1e-9:
        powody.append(f"cena opcji spadła do progu {udzial:.0%} zainkasowanej premii")
    if 0 < zwrot_pozostaly < MIN_ZWROT_POZOSTALY and p.dni > 0:
        powody.append(f"z pozostałej premii zostało tylko {zwrot_pozostaly:.1%} w skali roku")

    return {
        "udzial_docelowy": udzial,
        "cena_docelowa": cena_cel,
        "koszt_docelowy": cena_cel * p.akcje_zaangazowane,
        "zysk_docelowy": p.premia - cena_cel * p.akcje_zaangazowane,
        "kurs_docelowy": (kurs_dla_ceny_opcji(cena_cel, p.strike, p.dni / DNI_W_ROKU,
                                              STOPA_WOLNA, 0.0, p.iv, p.prawo)
                          if p.iv and p.dni > 0 else None),
        "cena_teraz": p.cena_opcji,
        "zwrot_pozostaly": zwrot_pozostaly,
        "poziomy": poziomy,
        "osiagniety": bool(powody),
        "powody": powody,
    }


def scenariusze(p: Pozycja, kroki=(-0.30, -0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20, 0.30)) -> list[dict]:
    """Wynik pozycji w dniu wygaśnięcia przy różnych kursach bazowego.

    Liczymy osobno nogę opcyjną i akcyjną, bo dopiero razem pokazują, co
    naprawdę robi covered call: premia łagodzi spadek, ale obcina wzrost
    powyżej strike'a. Noga akcyjna liczona jest od dzisiejszego kursu, więc
    to wynik przyszły, a nie licząc od ceny zakupu."""
    if not p.kurs_bazowego:
        return []
    call = p.prawo.upper().startswith("C")
    akcje_pod_calla = min(p.akcje_pod, p.akcje_zaangazowane)
    out = []
    for k in kroki:
        S_T = p.kurs_bazowego * (1.0 + k)
        wewn = max(0.0, (S_T - p.strike) if call else (p.strike - S_T))
        # krótka opcja: oddajemy wartość wewnętrzną, zatrzymujemy premię
        wynik_opcji = p.premia - wewn * p.akcje_zaangazowane * (1 if p.krotka else -1)
        if not p.krotka:
            wynik_opcji = wewn * p.akcje_zaangazowane - p.premia
        wynik_akcji = (S_T - p.kurs_bazowego) * akcje_pod_calla
        out.append({
            "zmiana": k,
            "kurs": S_T,
            "opcja": wynik_opcji,
            "akcje": wynik_akcji,
            "razem": wynik_opcji + wynik_akcji,
            "przypisanie": (S_T > p.strike) if call else (S_T < p.strike),
        })
    return out


def premia_okresu(transakcje: list[dict], od: str, do: str) -> dict:
    """Rozliczenie premii opcyjnej za okres, wyłącznie z faktycznych transakcji.

    Rozdzielamy trzy różne liczby, bo potocznie myli się je ze sobą:

      brutto      - ile wpłynęło ze sprzedaży kontraktów (sama premia),
      netto       - to samo po odjęciu prowizji, czyli realny wpływ na rachunek,
      zrealizowany- wynik domkniętych pozycji: premia minus koszt odkupienia.
                    Kontrakt, który wygasł bez wartości, oddaje tu całą premię.

    Premia z pozycji wciąż otwartych NIE jest zyskiem - dopóki kontrakt żyje,
    trzeba go móc odkupić. Ta część siedzi w `otwarte_brutto` i zamienia się
    w zysk dopiero przy wygaśnięciu albo zamknięciu.
    """
    opcyjne = [t for t in transakcje
               if (t.get("klasa") or "").upper() in ("OPT", "FOP")
               and od <= (t.get("data") or "") <= do]

    brutto = prowizje = odkup = zrealizowany = 0.0
    sprzedanych = odkupionych = 0.0
    for t in opcyjne:
        ilosc = float(t.get("ilosc") or 0.0)
        wartosc = float(t.get("wartosc") or 0.0)
        prowizje += abs(float(t.get("prowizja") or 0.0))
        zrealizowany += float(t.get("zysk_zrealizowany") or 0.0)
        if ilosc < 0:                       # sprzedaż kontraktu = inkaso premii
            brutto += wartosc
            sprzedanych += abs(ilosc)
        elif ilosc > 0:                     # odkupienie = wydatek
            odkup += abs(wartosc)
            odkupionych += ilosc

    return {
        "od": od, "do": do,
        "transakcji": len(opcyjne),
        "kontraktow_sprzedanych": sprzedanych,
        "kontraktow_odkupionych": odkupionych,
        "brutto": brutto,
        "prowizje": prowizje,
        "netto": brutto - prowizje,
        "odkup": odkup,
        "zrealizowany": zrealizowany,
    }


def zakres_miesiaca(dzis: date | None = None) -> tuple[str, str]:
    d = dzis or date.today()
    return d.replace(day=1).isoformat(), d.isoformat()


MIESIACE_PL = ("styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec",
               "sierpień", "wrzesień", "październik", "listopad", "grudzień")


def nazwa_miesiaca(ym: str) -> str:
    try:
        rok, mies = ym.split("-")
        return f"{MIESIACE_PL[int(mies) - 1]} {rok}"
    except (ValueError, IndexError):
        return ym


def miesiace(transakcje: list[dict]) -> list[dict]:
    """Rozliczenie premii miesiąc po miesiącu, od najnowszego.

    Wygaśnięcie bez wartości IBKR księguje jako transakcję po cenie zero -
    wtedy `zysk_zrealizowany` oddaje całą premię i miesiąc domyka się sam.
    Rozbicie na spółki pokazuje, która pozycja faktycznie zarobiła.
    """
    opcyjne = [t for t in transakcje
               if (t.get("klasa") or "").upper() in ("OPT", "FOP") and t.get("data")]
    wg: dict[str, list[dict]] = {}
    for t in opcyjne:
        wg.setdefault((t["data"] or "")[:7], []).append(t)

    out = []
    for ym in sorted(wg, reverse=True):
        grupa = wg[ym]
        w = premia_okresu(grupa, f"{ym}-01", f"{ym}-31")
        spolki: dict[str, dict] = {}
        for t in grupa:
            baz = t.get("bazowy") or t.get("symbol") or "?"
            s = spolki.setdefault(baz, {"bazowy": baz, "brutto": 0.0, "prowizje": 0.0,
                                        "odkup": 0.0, "zrealizowany": 0.0, "kontraktow": 0.0})
            ilosc, wartosc = float(t.get("ilosc") or 0.0), float(t.get("wartosc") or 0.0)
            s["prowizje"] += abs(float(t.get("prowizja") or 0.0))
            s["zrealizowany"] += float(t.get("zysk_zrealizowany") or 0.0)
            if ilosc < 0:
                s["brutto"] += wartosc
                s["kontraktow"] += abs(ilosc)
            else:
                s["odkup"] += abs(wartosc)
        for s in spolki.values():
            s["netto"] = s["brutto"] - s["prowizje"]
        w["miesiac"] = ym
        w["nazwa"] = nazwa_miesiaca(ym)
        w["spolki"] = sorted(spolki.values(), key=lambda x: -x["netto"])
        out.append(w)
    return out


def _etykieta(p: Pozycja) -> str:
    """Czytelna nazwa kontraktu zamiast symbolu OCC („LUNR  260918C00021000")."""
    d = _na_date(p.wygasa)
    kiedy = d.strftime("%d.%m.%Y") if d else p.wygasa
    rodzaj = "call" if p.prawo.upper().startswith("C") else "put"
    return f"{p.bazowy} {kiedy} {rodzaj} {p.strike:g}"


def analiza_do_panelu(dane: dict, transakcje: list[dict], rejestr: tuple[str, str, int],
                      dzis: date | None = None, stopa: float = STOPA_WOLNA,
                      kursy: dict[str, dict] | None = None) -> dict:
    """Wszystko, czego potrzebuje zakładka opcji, w jednym słowniku."""
    dzis = dzis or date.today()
    pozycje = analizuj_pozycje(dane, dzis=dzis, stopa=stopa, kursy=kursy)
    od, do = zakres_miesiaca(dzis)
    call = lambda p: p.prawo.upper().startswith("C")   # noqa: E731
    progi = {p.symbol: prog_odkupu(p) for p in pozycje}

    return {
        "data": dzis.isoformat(),
        "stopa": stopa,
        "kursy_zywe": bool(kursy),
        "miesiac": premia_okresu(transakcje, od, do),
        "podsumowanie": podsumuj(pozycje) or {
            "pozycji": 0, "kontraktow": 0, "premia": 0.0, "wartosc_biezaca": 0.0,
            "zysk_otwarty": 0.0, "do_zainkasowania": 0.0, "delta_akcji": 0.0,
            "delta_dolarowa": 0.0, "theta_dzienna": 0.0, "vega": 0.0, "gamma": 0.0,
            "notional": 0.0, "najblizsze_dni": 0, "bez_grekow": 0, "iv_srednia": None},
        "rejestr": {"od": rejestr[0], "do": rejestr[1], "wierszy": rejestr[2]},
        "pozycje": [{
            "etykieta": _etykieta(p),
            "symbol": p.symbol, "bazowy": p.bazowy, "wygasa": _etykieta(p).split()[1],
            "ilosc": p.ilosc, "dni": p.dni,
            "spot": p.kurs_bazowego, "strike": p.strike,
            "zapas_proc": p.zapas_do_strike * 100.0,
            "iv": p.iv, "greki": p.greki,
            "delta_akcji": p.delta_akcji, "theta": p.theta_dzienna,
            "vega": p.vega_pozycji, "gamma": p.gamma_pozycji,
            "p_itm": p.prawd_itm, "p_dot": p.prawd_dot,
            "premia": p.premia, "teraz": p.wartosc_biezaca, "wynik": p.zysk_otwarty,
            "zrealizowany_udzial": p.zrealizowany_udzial,
            "zwrot_roczny": p.zwrot_roczny,
            "zwrot_przypisanie": p.zwrot_przy_przypisaniu,
            "cena_efektywna": p.cena_wykonania_efektywna,
            "wartosc_czasowa": p.wartosc_czasowa,
            "akcje_pod": p.akcje_pod, "akcje_zaang": p.akcje_zaangazowane,
            "pokrycie": p.pokrycie,
            "w_pieniadzu": (p.kurs_bazowego > p.strike) if call(p)
                           else (p.kurs_bazowego < p.strike),
            "ryzyko_wczesniejszego": p.ryzyko_wczesniejszego,
            "scenariusze": scenariusze(p),
            "odkup": progi.get(p.symbol),
            "uwagi": p.uwagi,
        } for p in pozycje],
        "miesiace": miesiace(transakcje),
        "alerty": [{
            "symbol": p.symbol,
            "etykieta": _etykieta(p),
            "powody": progi[p.symbol]["powody"],
            "cena_teraz": p.cena_opcji,
            "cena_docelowa": progi[p.symbol]["cena_docelowa"],
            "kurs_bazowego": p.kurs_bazowego,
            "zysk": p.premia - p.wartosc_biezaca,
            "kontraktow": p.kontraktow,
        } for p in pozycje if progi.get(p.symbol) and progi[p.symbol]["osiagniety"]],
    }


def podsumuj(pozycje: list[Pozycja]) -> dict:
    """Agregaty portfela opcyjnego."""
    if not pozycje:
        return {}
    ma_greki = [p for p in pozycje if p.greki]
    return {
        "pozycji": len(pozycje),
        "kontraktow": sum(p.kontraktow for p in pozycje),
        "premia": sum(p.premia for p in pozycje),
        "wartosc_biezaca": sum(p.wartosc_biezaca for p in pozycje),
        "zysk_otwarty": sum(p.zysk_otwarty for p in pozycje),
        "do_zainkasowania": sum(p.do_zainkasowania for p in pozycje),
        "delta_akcji": sum(p.delta_akcji for p in ma_greki),
        "delta_dolarowa": sum(p.delta_dolarowa for p in ma_greki),
        "theta_dzienna": sum(p.theta_dzienna for p in ma_greki),
        "vega": sum(p.vega_pozycji for p in ma_greki),
        "gamma": sum(p.gamma_pozycji for p in ma_greki),
        "notional": sum(p.akcje_zaangazowane * p.strike for p in pozycje),
        "najblizsze_dni": min((p.dni for p in pozycje), default=0),
        "bez_grekow": len(pozycje) - len(ma_greki),
        # średnia IV ważona liczbą kontraktów - pojedyncza pozycja z ekstremalną
        # zmiennością nie powinna przesuwać obrazu całości
        "iv_srednia": (sum(p.iv * p.kontraktow for p in ma_greki if p.iv)
                       / sum(p.kontraktow for p in ma_greki if p.iv))
        if any(p.iv for p in ma_greki) else None,
    }
