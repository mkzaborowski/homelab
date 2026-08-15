"""Klient Flex Web Service IBKR + parser raportu XML.

Flex to zwykłe HTTPS: /SendRequest zwraca ReferenceCode, potem /GetStatement
oddaje gotowy raport. Nie wymaga TWS ani IB Gateway.
Dane Activity Statement odświeżają się raz dziennie po zamknięciu sesji.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict

import requests

BAZA = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
WERSJA = "3"


class BladFlex(Exception):
    """Błąd komunikacji z Flex Web Service (z komunikatem od IBKR)."""


@dataclass
class Pozycja:
    """Pojedyncza pozycja albo lot (gdy raport ma poziom LOT)."""
    konto: str = ""
    symbol: str = ""
    opis: str = ""
    klasa: str = ""            # STK / OPT / FUT / CASH ...
    waluta: str = ""
    isin: str = ""
    ilosc: float = 0.0
    cena_kosztu: float = 0.0   # cena wejścia (na akcję)
    koszt: float = 0.0         # wartość kosztowa
    cena: float = 0.0          # kurs zamknięcia
    wartosc: float = 0.0       # wartość rynkowa
    zysk: float = 0.0          # niezrealizowany wynik
    data_otwarcia: str = ""
    lot_id: str = ""
    poziom: str = ""           # SUMMARY / LOT - patrz uwaga przy parsowaniu
    # pola opcji - potrzebne do covered calls
    bazowy: str = ""
    strike: float = 0.0
    wygasa: str = ""
    prawo: str = ""            # C / P

    @property
    def zysk_proc(self) -> float:
        return (self.zysk / self.koszt * 100) if self.koszt else 0.0


@dataclass
class Transakcja:
    konto: str = ""
    symbol: str = ""
    opis: str = ""
    klasa: str = ""
    waluta: str = ""
    data: str = ""
    ilosc: float = 0.0
    cena: float = 0.0
    wartosc: float = 0.0
    prowizja: float = 0.0
    zysk_zrealizowany: float = 0.0
    kod: str = ""              # kody IBKR, np. "O" otwarcie, "C" zamknięcie, "A" assignment
    poziom: str = ""           # ORDER / EXECUTION
    bazowy: str = ""
    strike: float = 0.0
    wygasa: str = ""
    prawo: str = ""
    # Rejestr premii zbiera transakcje z wielu pobrań, więc potrzebuje trwałego
    # identyfikatora. `kod` do tego nie służy: bierze najpierw `notes`, przez co
    # część transakcji ma tam "P" (wykonanie częściowe) zamiast znacznika O/C.
    id_transakcji: str = ""
    otwarcie: str = ""         # wyłącznie openCloseIndicator: O / C

    @property
    def kupno(self) -> bool:
        return self.ilosc > 0

    @property
    def assignment(self) -> bool:
        # Ex/As/Ep = exercise / assignment / expiration
        return any(k in self.kod for k in ("A", "Ex", "Ep"))


@dataclass
class Gotowka:
    waluta: str = ""
    konczy: float = 0.0
    odsetki: float = 0.0
    dywidendy: float = 0.0


@dataclass
class DzienNAV:
    """Jeden dzień z sekcji EquitySummaryByReportDateInBase.

    To jedyne miejsce w raporcie Flex z DZIENNĄ historią wartości konta.
    Ile dni tu przyjdzie, zależy wyłącznie od okresu ustawionego w zapytaniu
    Flex: przy „Last Business Day" są dwa, przy „Last 365 Calendar Days"
    około 250. Bez tej historii nie da się policzyć ani zmienności, ani
    obsunięcia, ani zwrotu za cokolwiek dłuższego niż zebrane zrzuty."""
    data: str = ""
    nav: float = 0.0
    gotowka: float = 0.0
    akcje: float = 0.0
    opcje: float = 0.0
    fundusze: float = 0.0
    obligacje: float = 0.0
    dywidendy_naliczone: float = 0.0
    odsetki_naliczone: float = 0.0


@dataclass
class Operacja:
    """Wiersz z sekcji CashTransaction: przelew, dywidenda, odsetki, podatek."""
    # transactionID jest jedynym polem odróżniającym dwa identyczne przelewy
    # tego samego dnia. Bez niego trzy wpłaty po 300 000 z 25.08.2025 zlewały
    # się w jedną i zaniżały przepływy o dwie trzecie.
    id_operacji: str = ""
    data: str = ""
    rodzaj: str = ""           # Deposits/Withdrawals | Dividends | ...
    kwota: float = 0.0         # już przeliczona na walutę bazową
    waluta: str = ""
    symbol: str = ""
    opis: str = ""


@dataclass
class Instrument:
    """Wiersz z SecurityInfo - kanoniczne dane instrumentu."""
    symbol: str = ""
    conid: str = ""
    isin: str = ""
    nazwa: str = ""
    klasa: str = ""
    podkategoria: str = ""
    gielda: str = ""
    kraj: str = ""
    mnoznik: float = 1.0


@dataclass
class ZdarzenieOpcji:
    """Wiersz z OptionEAE: wygaśnięcie, wykonanie albo przypisanie.

    Przypisanie przychodzi w PARZE: wiersz opcji (zysk zero, bo premia była
    zainkasowana wcześniej) oraz wiersz sprzedaży akcji po cenie wykonania,
    i to na nim siedzi faktyczny wynik. Pokazanie samej nogi opcyjnej
    sugerowałoby, że przypisanie jest darmowe."""
    symbol: str = ""
    bazowy: str = ""
    data: str = ""
    rodzaj: str = ""           # Expiration | Assignment | Exercise | Sell | Buy
    ilosc: float = 0.0
    cena: float = 0.0
    zysk_zrealizowany: float = 0.0
    koszt_nabycia: float = 0.0
    klasa: str = ""


@dataclass
class Raport:
    """Znormalizowany zrzut stanu konta z jednego raportu Flex."""
    konto: str = ""
    data: str = ""
    waluta_bazowa: str = "USD"
    nav: float = 0.0
    nav_poprzedni: float = 0.0
    pozycje: list[Pozycja] = field(default_factory=list)
    transakcje: list[Transakcja] = field(default_factory=list)
    gotowka: list[Gotowka] = field(default_factory=list)
    dywidendy_naliczone: float = 0.0
    historia_nav: list[DzienNAV] = field(default_factory=list)
    operacje: list[Operacja] = field(default_factory=list)
    instrumenty: list[Instrument] = field(default_factory=list)
    # TWR policzone przez samo IBKR. Trzymamy je po to, żeby móc porównać
    # z własnym wyliczeniem - to jedyny niezależny punkt odniesienia, jaki
    # w ogóle mamy dla poprawności silnika zwrotu.
    twr_ibkr: float | None = None
    zdarzenia_opcji: list[ZdarzenieOpcji] = field(default_factory=list)

    def jako_slownik(self) -> dict:
        d = asdict(self)
        return d


def _f(el: ET.Element, nazwa: str, domyslnie: float = 0.0) -> float:
    """Liczba z atrybutu - Flex potrafi zwrócić pusty string albo brak pola."""
    v = el.get(nazwa)
    if v is None or v == "":
        return domyslnie
    try:
        return float(v)
    except ValueError:
        return domyslnie


def _s(el: ET.Element, *nazwy: str) -> str:
    """Pierwszy niepusty atrybut z listy (Flex bywa niekonsekwentny w nazwach)."""
    for n in nazwy:
        v = el.get(n)
        if v:
            return v
    return ""


def pobierz_raport(token: str, query_id: str, *, czekaj: int = 20,
                   prob: int = 20, timeout: int = 120) -> str:
    """Pobiera raport i czeka, aż IBKR go wygeneruje.

    Budżet ponawiania jest hojny celowo: wyciąg roczny buduje się u IBKR
    znacznie dłużej niż jednodniowy, a wcześniejsze ~70 sekund kończyłoby się
    błędem „raport nie był gotowy" przy każdym pobraniu. Kod 1019 znaczy
    „jeszcze generuję" i nie jest błędem - czekamy dalej.

    Zwraca surowy XML. Rzuca BladFlex z komunikatem od IBKR.
    """
    r = requests.get(f"{BAZA}/SendRequest",
                     params={"t": token, "q": query_id, "v": WERSJA},
                     timeout=timeout)
    r.raise_for_status()
    root = ET.fromstring(r.text)

    status = (root.findtext("Status") or "").strip()
    if status != "Success":
        kod = (root.findtext("ErrorCode") or "?").strip()
        msg = (root.findtext("ErrorMessage") or "brak szczegółów").strip()
        raise BladFlex(f"SendRequest odrzucony przez IBKR (kod {kod}): {msg}")

    ref = (root.findtext("ReferenceCode") or "").strip()
    if not ref:
        raise BladFlex("IBKR nie zwrócił ReferenceCode")

    # raport bywa jeszcze generowany - IBKR prosi o cierpliwość i ponowienie
    for proba in range(prob):
        time.sleep(czekaj if proba == 0 else 10)
        g = requests.get(f"{BAZA}/GetStatement",
                         params={"t": token, "q": ref, "v": WERSJA},
                         timeout=timeout)
        g.raise_for_status()
        tresc = g.text
        if "<FlexQueryResponse" in tresc:
            return tresc
        if "<FlexStatementResponse" in tresc:
            root2 = ET.fromstring(tresc)
            kod = (root2.findtext("ErrorCode") or "").strip()
            msg = (root2.findtext("ErrorMessage") or "").strip()
            # 1019 = w trakcie generowania, próbujemy dalej
            if kod == "1019":
                continue
            raise BladFlex(f"GetStatement (kod {kod}): {msg}")
    raise BladFlex("Raport nie był gotowy mimo kilku prób - spróbuj za chwilę")


def parsuj(xml_tekst: str) -> Raport:
    """Zamienia XML Flex na znormalizowany Raport."""
    root = ET.fromstring(xml_tekst)
    stmt = root.find(".//FlexStatement")
    if stmt is None:
        raise BladFlex("W odpowiedzi nie ma sekcji FlexStatement")

    rap = Raport(konto=stmt.get("accountId", ""), data=stmt.get("toDate", ""))

    info = stmt.find(".//AccountInformation")
    if info is not None:
        rap.waluta_bazowa = info.get("currency", "USD")

    # NAV: gdy raport zawiera też poprzedni dzień, bierzemy wiersz o najpóźniejszej
    # dacie, a nie ostatni w pliku - kolejność w XML nie jest gwarantowana.
    nav_wiersze = stmt.findall(".//EquitySummaryByReportDateInBase")
    if nav_wiersze:
        biezacy = max(nav_wiersze, key=lambda n: _s(n, "reportDate"))
        rap.nav = _f(biezacy, "total")
        poprzednie = [n for n in nav_wiersze if n is not biezacy]
        if poprzednie:
            rap.nav_poprzedni = _f(max(poprzednie, key=lambda n: _s(n, "reportDate")), "total")

        # Cała zawartość tej sekcji, dzień po dniu. Przy okresie zapytania
        # ustawionym na rok dostajemy tu gotową historię konta - jedyne
        # darmowe źródło, z którego da się policzyć zmienność, obsunięcie
        # i zwroty za okresy dłuższe niż zebrane przez nas zrzuty.
        for n in nav_wiersze:
            rap.historia_nav.append(DzienNAV(
                data=_s(n, "reportDate"),
                nav=_f(n, "total"),
                gotowka=_f(n, "cash"),
                akcje=_f(n, "stock"),
                opcje=_f(n, "options"),
                fundusze=_f(n, "funds"),
                obligacje=_f(n, "bonds"),
                dywidendy_naliczone=_f(n, "dividendAccruals"),
                odsetki_naliczone=_f(n, "interestAccruals"),
            ))
        rap.historia_nav.sort(key=lambda d: d.data)

    for p in stmt.findall(".//OpenPosition"):
        rap.pozycje.append(Pozycja(
            poziom=_s(p, "levelOfDetail").upper(),
            konto=p.get("accountId", ""),
            symbol=_s(p, "symbol"),
            opis=_s(p, "description"),
            klasa=_s(p, "assetCategory"),
            waluta=_s(p, "currency"),
            isin=_s(p, "isin"),
            ilosc=_f(p, "position"),
            cena_kosztu=_f(p, "costBasisPrice"),
            koszt=_f(p, "costBasisMoney"),
            cena=_f(p, "markPrice"),
            wartosc=_f(p, "positionValue"),
            zysk=_f(p, "fifoPnlUnrealized"),
            data_otwarcia=_s(p, "openDateTime", "holdingPeriodDateTime"),
            lot_id=_s(p, "originatingTransactionID"),
            bazowy=_s(p, "underlyingSymbol"),
            strike=_f(p, "strike"),
            wygasa=_s(p, "expiry"),
            prawo=_s(p, "putCall"),
        ))

    for t in stmt.findall(".//Trade"):
        rap.transakcje.append(Transakcja(
            poziom=_s(t, "levelOfDetail").upper(),
            konto=t.get("accountId", ""),
            symbol=_s(t, "symbol"),
            opis=_s(t, "description"),
            klasa=_s(t, "assetCategory"),
            waluta=_s(t, "currency"),
            data=_s(t, "tradeDate", "dateTime"),
            ilosc=_f(t, "quantity"),
            cena=_f(t, "tradePrice"),
            wartosc=_f(t, "proceeds"),
            prowizja=_f(t, "ibCommission"),
            zysk_zrealizowany=_f(t, "fifoPnlRealized"),
            kod=_s(t, "notes", "code", "openCloseIndicator"),
            bazowy=_s(t, "underlyingSymbol"),
            strike=_f(t, "strike"),
            wygasa=_s(t, "expiry"),
            prawo=_s(t, "putCall"),
            id_transakcji=_s(t, "tradeID", "transactionID", "ibOrderID"),
            otwarcie=_s(t, "openCloseIndicator"),
        ))

    # Operacje gotówkowe. Ta sama pułapka co przy pozycjach i transakcjach:
    # raport zawiera wiersz SUMMARY i DETAIL dla tej samej operacji. Zsumowanie
    # obu podwoiło przelewy (1 192 059 zamiast 596 029) i wywracało cały zwrot.
    kasa = stmt.findall(".//CashTransaction")
    if kasa:
        poziomy = {_s(c, "levelOfDetail") for c in kasa}
        wybrany = "DETAIL" if "DETAIL" in poziomy else (poziomy.pop() if poziomy else "")
        for c in kasa:
            if wybrany and _s(c, "levelOfDetail") != wybrany:
                continue
            rap.operacje.append(Operacja(
                id_operacji=_s(c, "transactionID", "actionID"),
                data=_s(c, "reportDate", "dateTime", "settleDate"),
                rodzaj=_s(c, "type"),
                # kwota przeliczona na walutę bazową - konto ma GBP i USD
                kwota=_f(c, "amount") * (_f(c, "fxRateToBase", 1.0) or 1.0),
                waluta=_s(c, "currency"),
                symbol=_s(c, "symbol"),
                opis=_s(c, "description"),
            ))

    for z in stmt.findall(".//OptionEAE"):
        if not _s(z, "symbol"):
            continue
        rap.zdarzenia_opcji.append(ZdarzenieOpcji(
            symbol=_s(z, "symbol"),
            bazowy=_s(z, "underlyingSymbol") or _s(z, "symbol").split()[0],
            data=_s(z, "date", "reportDate"),
            rodzaj=_s(z, "transactionType"),
            ilosc=_f(z, "quantity"),
            cena=_f(z, "tradePrice"),
            zysk_zrealizowany=_f(z, "realizedPnl"),
            koszt_nabycia=_f(z, "costBasis"),
            klasa=_s(z, "assetCategory"),
        ))

    zmiana = stmt.find(".//ChangeInNAV")
    if zmiana is not None and zmiana.get("twr") not in (None, ""):
        rap.twr_ibkr = _f(zmiana, "twr")

    for si in stmt.findall(".//SecurityInfo"):
        rap.instrumenty.append(Instrument(
            symbol=_s(si, "symbol"),
            conid=_s(si, "conid"),
            isin=_s(si, "isin"),
            nazwa=_s(si, "description"),
            klasa=_s(si, "assetCategory"),
            podkategoria=_s(si, "subCategory"),
            gielda=_s(si, "listingExchange"),
            kraj=_s(si, "issuerCountryCode"),
            mnoznik=_f(si, "multiplier", 1.0) or 1.0,
        ))

    # Gotówka: raport potrafi zawierać jednocześnie wiersze per waluta i wiersz
    # zbiorczy BASE_SUMMARY. Zsumowanie wszystkiego dałoby podwójną gotówkę,
    # więc gdy jest podsumowanie w walucie bazowej, bierzemy wyłącznie je.
    kasa = stmt.findall(".//CashReportCurrency")
    zbiorcze = [c for c in kasa if _s(c, "currency").upper() in ("BASE_SUMMARY", "BASE SUMMARY")]
    for c in (zbiorcze or kasa):
        rap.gotowka.append(Gotowka(
            waluta=_s(c, "currency"),
            konczy=_f(c, "endingCash"),
            odsetki=_f(c, "interest"),
            dywidendy=_f(c, "dividends"),
        ))

    for d in stmt.findall(".//ChangeInDividendAccrual"):
        rap.dywidendy_naliczone += _f(d, "netAmount")

    _bez_duplikatow(rap)
    return rap


def _bez_duplikatow(rap: Raport) -> None:
    """Usuwa wiersze zbiorcze, gdy w raporcie są też szczegółowe.

    Flex potrafi zwrócić pozycje jednocześnie na poziomie SUMMARY i LOT, a
    transakcje na poziomie ORDER i EXECUTION. Zsumowanie obu poziomów zawyżyłoby
    portfel dwukrotnie, dlatego zostawiamy wyłącznie poziom szczegółowy.
    """
    if any(p.poziom == "LOT" for p in rap.pozycje):
        rap.pozycje = [p for p in rap.pozycje if p.poziom != "SUMMARY"]

    poziomy = {t.poziom for t in rap.transakcje}
    if "EXECUTION" in poziomy and "ORDER" in poziomy:
        rap.transakcje = [t for t in rap.transakcje if t.poziom != "ORDER"]
