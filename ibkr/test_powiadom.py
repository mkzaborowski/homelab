"""Testy wyboru kanału powiadomień i wysyłki przez usługę pocztową.

Ten moduł miał dotąd zero testów i to on jest przyczyną, dla której alerty
o progu odkupu liczyły się tygodniami, nie wychodząc nigdzie: nikt nie
sprawdził, że kanał w ogóle jest skonfigurowany.
"""
from __future__ import annotations

import io
import json
import unittest.mock as mock
import urllib.error

import powiadom

ALERTY = [{"symbol": "LUNR  260918C00021000", "etykieta": "LUNR 21C 18.09",
           "cena_teraz": 0.42, "cena_docelowa": 0.45, "kurs_bazowego": 17.8,
           "zysk": 258.0, "kontraktow": 6, "powody": ["cena spadła do progu"]}]


def _ustaw(**kw):
    """Zmienne modułu czytane są przy imporcie, więc w teście podmieniamy je
    wprost - inaczej trzeba by przeładowywać moduł przy każdym przypadku."""
    return mock.patch.multiple(powiadom, **kw)


def test_bez_kanalu_odmawia_i_mowi_dlaczego():
    with _ustaw(KANAL=""):
        ok, opis = powiadom.skonfigurowane()
    assert ok is False and "nieustawiony" in opis


def test_usluga_bez_klucza_wskazuje_brakujaca_zmienna():
    with _ustaw(KANAL="poczta", POCZTA_KLUCZ="", MAIL_DO="ja@example.com"):
        ok, opis = powiadom.skonfigurowane()
    assert ok is False and "POCZTA_KLUCZ" in opis


def test_usluga_z_kompletem_jest_skonfigurowana():
    with _ustaw(KANAL="poczta", POCZTA_KLUCZ="pk_x", MAIL_DO="ja@example.com"):
        ok, opis = powiadom.skonfigurowane()
    assert ok is True and "ja@example.com" in opis


def test_wysylka_idzie_na_wlasciwy_adres_z_kluczem_w_naglowku():
    wyslane = {}

    def udawaj(zad, timeout=None):
        wyslane["url"] = zad.full_url
        wyslane["naglowki"] = dict(zad.header_items())
        wyslane["ciało"] = json.loads(zad.data)
        return io.BytesIO(json.dumps({"id": 1, "stan": "w kolejce"}).encode())

    with _ustaw(KANAL="poczta", POCZTA_KLUCZ="pk_tajny", MAIL_DO="ja@example.com",
                POCZTA_URL="http://poczta:8091"), \
         mock.patch.object(powiadom.urllib.request, "urlopen", udawaj):
        ok, opis = powiadom.wyslij(ALERTY)

    assert ok is True, opis
    assert wyslane["url"] == "http://poczta:8091/api/wyslij"
    assert wyslane["naglowki"]["Authorization"] == "Bearer pk_tajny"
    assert wyslane["ciało"]["do"] == "ja@example.com"
    assert "LUNR" in wyslane["ciało"]["temat"]
    assert "0.42" in wyslane["ciało"]["tresc"]


def test_ten_sam_alert_tego_samego_dnia_ma_ten_sam_klucz_idempotencji():
    """Ponowiony przebieg nie może wysłać drugiego powiadomienia o tych samych
    pozycjach - alert przychodzący dwa razy przestaje być brany poważnie."""
    a = powiadom._klucz_idempotencji(ALERTY)
    b = powiadom._klucz_idempotencji(ALERTY)
    assert a == b
    inne = powiadom._klucz_idempotencji(
        ALERTY + [{**ALERTY[0], "symbol": "OKLO  261120C00090000"}])
    assert inne != a


def test_kolejnosc_alertow_nie_zmienia_klucza():
    dwa = ALERTY + [{**ALERTY[0], "symbol": "AAA"}]
    assert (powiadom._klucz_idempotencji(dwa)
            == powiadom._klucz_idempotencji(list(reversed(dwa))))


def test_blad_uslugi_wraca_z_trescia_a_nie_golym_kodem():
    def padnij(zad, timeout=None):
        raise urllib.error.HTTPError(zad.full_url, 401, "Unauthorized", {},
                                     io.BytesIO(b'{"blad": "nieznany klucz API"}'))

    with _ustaw(KANAL="poczta", POCZTA_KLUCZ="pk_zly", MAIL_DO="ja@example.com"), \
         mock.patch.object(powiadom.urllib.request, "urlopen", padnij):
        ok, opis = powiadom.wyslij(ALERTY)

    assert ok is False
    assert "401" in opis and "nieznany klucz API" in opis


def test_wykluczony_adres_konczy_sie_niepowodzeniem_z_powodem():
    """Usługa odpowiada 200, ale list nie poszedł. Gdyby przebieg uznał to za
    sukces, log twierdziłby, że powiadomienie wyszło."""
    def udawaj(zad, timeout=None):
        return io.BytesIO(json.dumps({"stan": "pominiety", "powod": "odbity"}).encode())

    with _ustaw(KANAL="poczta", POCZTA_KLUCZ="pk_x", MAIL_DO="ja@example.com"), \
         mock.patch.object(powiadom.urllib.request, "urlopen", udawaj):
        ok, opis = powiadom.wyslij(ALERTY)

    assert ok is False and "odbity" in opis


def test_brak_alertow_nie_wysyla_niczego():
    def nie_wolno(*a, **k):
        raise AssertionError("wysyłka przy pustej liście alertów")

    with _ustaw(KANAL="poczta", POCZTA_KLUCZ="pk_x", MAIL_DO="ja@example.com"), \
         mock.patch.object(powiadom.urllib.request, "urlopen", nie_wolno):
        ok, opis = powiadom.wyslij([])
    assert ok is True and "brak" in opis
