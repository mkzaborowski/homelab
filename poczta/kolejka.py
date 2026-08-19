"""Przebieg wysyłkowy: bierze listy z kolejki i próbuje je dostarczyć.

DLACZEGO KOLEJKA, A NIE WYSYŁKA W ŻĄDANIU. Trzy powody, każdy wystarczający
sam z siebie:

1. SMTP bywa niedostępny przez minutę. Wysyłka synchroniczna albo gubi list,
   albo blokuje żądanie aplikacji na czas timeoutu - a formularz na stronie
   nie ma prawa czekać trzydziestu sekund na cudzy serwer pocztowy.
2. Exchange Online przyjmuje 30 listów na minutę. Bez kolejki nie ma gdzie
   tego tempa pilnować.
3. Ponowienie wymaga pamięci o poprzedniej próbie, a żądanie HTTP jej nie ma.

TEMPO. Rozkładamy wysyłkę równo w minucie zamiast wystrzelić paczkę i czekać:
serwer pocztowy patrzy na chwilowe natężenie, nie na średnią.
"""
from __future__ import annotations

import base64
import json
import time

import store
import wysylka

PRZERWA = 60.0 / max(wysylka.NA_MINUTE, 1)


def _zalaczniki(x: dict) -> list[dict]:
    """Załączniki leżą w bazie jako base64 w JSON-ie i dopiero tutaj wracają
    do bajtów. Trzymanie ich w bazie, a nie na dysku, jest świadome: list
    w kolejce ma być samowystarczalny, żeby ponowienie po godzinie nie zależało
    od tego, czy plik nadal gdzieś leży."""
    if not x.get("zalaczniki"):
        return []
    try:
        surowe = json.loads(x["zalaczniki"])
    except (ValueError, TypeError):
        return []
    out = []
    for z in surowe if isinstance(surowe, list) else []:
        try:
            out.append({"nazwa": z.get("nazwa", ""), "typ": z.get("typ", ""),
                        "dane": base64.b64decode(z.get("dane_b64") or "", validate=True)})
        except (ValueError, TypeError):
            continue
    return out


def _list_do_wiadomosci(x: dict) -> "wysylka.EmailMessage":
    s = store.serwis(x["serwis_id"]) or {}
    return wysylka.zbuduj(
        nadawca_email=s.get("nadawca_email", ""),
        nadawca_nazwa=s.get("nadawca_nazwa", ""),
        do_email=x["do_email"],
        temat=x["temat"],
        tresc=x["tresc"],
        tresc_html=x.get("tresc_html"),
        zalaczniki=_zalaczniki(x),
        odpowiedz_do=s.get("odpowiedz_do") or "",
        # Nagłówek diagnostyczny: po nim widać w cudzej skrzynce, który serwis
        # wysłał list, bez zaglądania do naszej bazy.
        naglowki={"X-Poczta-Serwis": s.get("kod", "?")},
    )


def przebieg(ile: int = 20, dostawca: wysylka.Dostawca | None = None,
             spij=time.sleep) -> dict:
    """Jedna tura wysyłki. Zwraca podsumowanie do logu.

    Nie rzuca wyjątkami: nieudany list zapisuje błąd i idzie dalej. Jeden zły
    adres nie może zatrzymać kolejki dla wszystkich pozostałych."""
    d = dostawca or wysylka.dostawca()

    # BRAK KONFIGURACJI NADAWCY NIE JEST BŁĘDEM LISTU. Sprawdzamy to raz, przed
    # wzięciem czegokolwiek z kolejki, i wychodzimy bez dotykania wiadomości.
    #
    # Wcześniej każdy list zaliczał tu próbę i po piątej przepadał - a to jest
    # dokładnie odwrotność tego, po co jest kolejka. Nikt jeszcze nie próbował
    # niczego wysłać: nie było połączenia z serwerem, nie było odmowy, nie ma
    # czego liczyć jako nieudanej próby. Poczta ma poczekać, aż hasło trafi do
    # konfiguracji, i wyjść wtedy w komplecie.
    ok, czego_brak = d.skonfigurowany()
    if not ok:
        czeka = len(store.do_wyslania(1))
        return {"wziete": 0, "wyslane": 0, "chwilowe": 0, "trwale": 0,
                "pominiete": 0, "wstrzymane": czeka, "powod": czego_brak}

    listy = store.do_wyslania(ile)
    wynik = {"wziete": len(listy), "wyslane": 0, "chwilowe": 0, "trwale": 0,
             "pominiete": 0}

    for i, x in enumerate(listy):
        # Wykluczenie sprawdzamy TUTAJ, a nie tylko przy przyjmowaniu: adres
        # mógł się odbić między zakolejkowaniem a wysyłką i nie ma powodu
        # dokładać drugiego odboju.
        w = store.wykluczony(x["do_email"], x["serwis_id"])
        if w:
            store.oznacz_blad(x["id"], f"adres wykluczony ({w['powod']})", trwaly=True)
            wynik["pominiete"] += 1
            continue
        try:
            opis = d.wyslij(_list_do_wiadomosci(x))
            store.oznacz_wyslany(x["id"], opis)
            wynik["wyslane"] += 1
        except wysylka.BladTrwaly as e:
            store.oznacz_blad(x["id"], str(e), trwaly=True)
            wynik["trwale"] += 1
            # Odbój od nieistniejącej skrzynki obowiązuje wszędzie - to cecha
            # adresu, nie relacji z jednym serwisem.
            if "adresat odrzucony" in str(e):
                store.wyklucz(x["do_email"], "odbity")
        except wysylka.BladChwilowy as e:
            store.oznacz_blad(x["id"], str(e))
            wynik["chwilowe"] += 1
        except Exception as e:                                  # noqa: BLE001
            # Nieprzewidziany wyjątek traktujemy jak chwilowy: przy błędzie
            # w naszym kodzie lepiej ponowić po poprawce niż uznać list za
            # przepadły i stracić go bezpowrotnie.
            store.oznacz_blad(x["id"], f"{type(e).__name__}: {e}")
            wynik["chwilowe"] += 1

        if i + 1 < len(listy):
            spij(PRZERWA)
    return wynik


def opis_przebiegu(w: dict) -> str:
    if w.get("powod"):
        return (f"wstrzymane — {w['powod']}"
                + (f" ({w['wstrzymane']} w kolejce)" if w.get("wstrzymane") else ""))
    if not w["wziete"]:
        return "kolejka pusta"
    czesci = [f"wysłano {w['wyslane']}/{w['wziete']}"]
    for klucz, etykieta in (("chwilowe", "do ponowienia"), ("trwale", "przepadło"),
                            ("pominiete", "pominięto")):
        if w[klucz]:
            czesci.append(f"{etykieta} {w[klucz]}")
    return " · ".join(czesci)
