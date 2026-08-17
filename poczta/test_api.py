"""Testy API na granicy HTTP - tam, gdzie stykają się z nią pozostałe usługi.

Izolacja sprawdzona w test_izolacja.py jest własnością warstwy danych. Tutaj
sprawdzamy, że nie da się jej obejść od zewnątrz: podając cudzy identyfikator
w ciele żądania, zgadując numer listu albo wołając bez klucza.
"""
from __future__ import annotations

import os
import tempfile

os.environ["POCZTA_DANE"] = tempfile.mkdtemp(prefix="poczta-test-api-")
os.environ["PANEL_HASLO"] = "tajne-do-testow"
os.environ["HARMONOGRAM"] = "0"          # bez tła: testy sterują kolejką same
os.environ["COOKIE_SECURE"] = "0"

import app as aplikacja                                         # noqa: E402
import kolejka                                                  # noqa: E402
import store                                                    # noqa: E402
from test_izolacja import _czysto                               # noqa: E402
from test_wysylka import Udany                                  # noqa: E402


def _klient():
    aplikacja.app.config["TESTING"] = True
    return aplikacja.app.test_client()


def _dwa():
    _czysto()
    a = store.dodaj_serwis("alpha", "Alpha", "kontakt@alphaolsztyn.pl")
    o = store.dodaj_serwis("ochrona", "Ochrona", "biuro@ochronazklasa.pl")
    return (a, store.wydaj_klucz(a)), (o, store.wydaj_klucz(o))


def _naglowek(klucz):
    return {"Authorization": f"Bearer {klucz}"}


# --------------------------------------------------------------------------- #
#  dostęp
# --------------------------------------------------------------------------- #

def test_bez_klucza_api_odmawia():
    _dwa()
    k = _klient()
    for naglowki in ({}, {"Authorization": "Bearer"}, {"Authorization": "pk_cos"},
                     {"Authorization": "Bearer pk_zmyslony"}):
        o = k.post("/api/wyslij", json={"do": "jan@example.com", "temat": "T",
                                        "tresc": "C"}, headers=naglowki)
        assert o.status_code == 401, (naglowki, o.status_code)


def test_klucz_nie_jest_przyjmowany_z_adresu():
    """Adresy lądują w logach serwera pośredniczącego i w historii przeglądarki,
    więc klucz w query stringu wyciekłby w dwóch miejscach naraz."""
    (_, ka), _ = _dwa()
    o = _klient().post(f"/api/wyslij?klucz_api={ka}",
                       json={"do": "jan@example.com", "temat": "T", "tresc": "C"})
    assert o.status_code == 401


def test_panel_wymaga_zalogowania():
    _dwa()
    o = _klient().get("/", follow_redirects=False)
    assert o.status_code == 302 and "/login" in o.headers["Location"]


# --------------------------------------------------------------------------- #
#  izolacja na granicy HTTP
# --------------------------------------------------------------------------- #

def test_serwis_nie_podejrzy_listu_drugiego_serwisu():
    """Najbardziej prawdopodobna próba: zgadnąć numer listu i odczytać treść."""
    (a, ka), (o, ko) = _dwa()
    k = _klient()
    r = k.post("/api/wyslij", json={"do": "rodzic@example.com",
                                    "temat": "Polisa", "tresc": "wrażliwe"},
               headers=_naglowek(ko))
    list_id = r.get_json()["id"]

    swoj = k.get(f"/api/stan/{list_id}", headers=_naglowek(ko))
    assert swoj.status_code == 200 and swoj.get_json()["temat"] == "Polisa"

    cudzy = k.get(f"/api/stan/{list_id}", headers=_naglowek(ka))
    assert cudzy.status_code == 404
    assert "Polisa" not in cudzy.get_data(as_text=True)


def test_podanie_cudzego_serwisu_w_ciele_zadania_nic_nie_daje():
    """Tożsamość bierze się WYŁĄCZNIE z klucza. Gdyby dało się ją nadpisać
    polem w JSON-ie, cała izolacja byłaby dekoracją."""
    (a, ka), (o, _) = _dwa()
    r = _klient().post("/api/wyslij",
                       json={"do": "jan@example.com", "temat": "T", "tresc": "C",
                             "serwis_id": o, "serwis": "ochrona"},
                       headers=_naglowek(ka))
    assert r.status_code == 202
    assert len(store.historia(a)) == 1 and len(store.historia(o)) == 0


def test_kontakty_widac_tylko_swoje():
    (a, ka), (o, ko) = _dwa()
    k = _klient()
    k.post("/api/kontakt", json={"email": "uczestnik@example.com"}, headers=_naglowek(ka))
    k.post("/api/kontakt", json={"email": "rodzic@example.com"}, headers=_naglowek(ko))
    z_alphy = k.get("/api/kontakty", headers=_naglowek(ka)).get_json()
    assert [x["email"] for x in z_alphy["kontakty"]] == ["uczestnik@example.com"]
    assert z_alphy["serwis"] == "alpha"


def test_szablon_drugiego_serwisu_jest_niewidoczny():
    (a, ka), (o, _) = _dwa()
    store.zapisz_szablon(o, "polisa", "Polisa gotowa", "Treść")
    r = _klient().post("/api/wyslij",
                       json={"do": "jan@example.com", "szablon": "polisa"},
                       headers=_naglowek(ka))
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
#  zachowanie API
# --------------------------------------------------------------------------- #

def test_przyjecie_do_kolejki_odpowiada_202_a_nie_200():
    """W chwili odpowiedzi nic jeszcze nie zostało dostarczone."""
    (a, ka), _ = _dwa()
    r = _klient().post("/api/wyslij", json={"do": "jan@example.com", "temat": "T",
                                            "tresc": "C"}, headers=_naglowek(ka))
    assert r.status_code == 202
    assert r.get_json()["stan"] == "w kolejce"


def test_zly_adres_odrzucony_od_razu():
    (a, ka), _ = _dwa()
    k = _klient()
    for zly in ("", "jan", "@example.com", "a@b"):
        r = k.post("/api/wyslij", json={"do": zly, "temat": "T", "tresc": "C"},
                   headers=_naglowek(ka))
        assert r.status_code == 400, zly


def test_ponowione_zadanie_z_tym_samym_kluczem_nie_dubluje():
    (a, ka), _ = _dwa()
    k = _klient()
    ciało = {"do": "jan@example.com", "temat": "T", "tresc": "C", "klucz": "zg-7"}
    p = k.post("/api/wyslij", json=ciało, headers=_naglowek(ka)).get_json()
    d = k.post("/api/wyslij", json=ciało, headers=_naglowek(ka)).get_json()
    assert p["id"] == d["id"] and p["nowy"] is True and d["nowy"] is False
    assert len(store.historia(a)) == 1


def test_wykluczony_adres_konczy_sie_pominieciem_a_nie_bledem():
    """Z punktu widzenia aplikacji wołającej wszystko poszło zgodnie z regułami -
    to nie jest awaria, tylko decyzja."""
    (a, ka), _ = _dwa()
    store.wyklucz("jan@example.com", "wypisany", a)
    r = _klient().post("/api/wyslij", json={"do": "jan@example.com", "temat": "T",
                                            "tresc": "C"}, headers=_naglowek(ka))
    assert r.status_code == 200 and r.get_json()["stan"] == "pominiety"
    assert store.historia(a) == []


def test_szablon_bez_kompletu_zmiennych_odrzucony_z_wyjasnieniem():
    (a, ka), _ = _dwa()
    store.zapisz_szablon(a, "zapis", "Cześć {imie}", "Widzimy się {kiedy}")
    r = _klient().post("/api/wyslij",
                       json={"do": "jan@example.com", "szablon": "zapis",
                             "dane": {"imie": "Jan"}},
                       headers=_naglowek(ka))
    assert r.status_code == 400
    assert "kiedy" in r.get_json()["blad"]


def test_szablon_z_kompletem_zmiennych_trafia_do_kolejki_z_podstawieniem():
    (a, ka), _ = _dwa()
    store.zapisz_szablon(a, "zapis", "Cześć {imie}", "Widzimy się {kiedy}.")
    r = _klient().post("/api/wyslij",
                       json={"do": "jan@example.com", "szablon": "zapis",
                             "dane": {"imie": "Jan", "kiedy": "w piątek"},
                             "dodaj_kontakt": True},
                       headers=_naglowek(ka))
    assert r.status_code == 202
    x = store.historia(a)[0]
    assert x["temat"] == "Cześć Jan" and "w piątek" in x["tresc"]
    assert [c["email"] for c in store.kontakty(a)] == ["jan@example.com"]


def test_stan_listu_odzwierciedla_faktyczna_wysylke():
    (a, ka), _ = _dwa()
    k = _klient()
    list_id = k.post("/api/wyslij", json={"do": "jan@example.com", "temat": "T",
                                          "tresc": "C"},
                     headers=_naglowek(ka)).get_json()["id"]
    assert k.get(f"/api/stan/{list_id}", headers=_naglowek(ka)).get_json()["stan"] == "czeka"
    kolejka.przebieg(dostawca=Udany(), spij=lambda _: None)
    po = k.get(f"/api/stan/{list_id}", headers=_naglowek(ka)).get_json()
    assert po["stan"] == "wyslany" and po["wyslano"]


# --------------------------------------------------------------------------- #
#  wypisanie
# --------------------------------------------------------------------------- #

def test_odnosnik_wypisu_dziala_i_obejmuje_jeden_serwis():
    (a, _), (o, _) = _dwa()
    k = _klient()
    with aplikacja.app.test_request_context():
        podpis = aplikacja.podpis_wypisu("jan@example.com", a)
    r = k.get(f"/wypisz/{a}/jan@example.com/{podpis}")
    assert r.status_code == 200
    assert store.wykluczony("jan@example.com", a)["powod"] == "wypisany"
    assert store.wykluczony("jan@example.com", o) is None


def test_podrobiony_podpis_wypisu_nic_nie_zmienia():
    (a, _), _ = _dwa()
    r = _klient().get(f"/wypisz/{a}/jan@example.com/" + "0" * 32)
    assert r.status_code == 400
    assert store.wykluczony("jan@example.com", a) is None


def test_podpis_wypisu_jest_zwiazany_z_adresem_i_serwisem():
    """Podpis dla jednego adresu nie może wypisać innego ani działać w innym
    serwisie - inaczej jeden wyciekły odnośnik wypisałby wszystkich."""
    (a, _), (o, _) = _dwa()
    with aplikacja.app.test_request_context():
        p = aplikacja.podpis_wypisu("jan@example.com", a)
        assert aplikacja.podpis_wypisu("ktos@example.com", a) != p
        assert aplikacja.podpis_wypisu("jan@example.com", o) != p


# --------------------------------------------------------------------------- #
#  panel
# --------------------------------------------------------------------------- #

def _zalogowany():
    k = _klient()
    k.post("/login", data={"haslo": "tajne-do-testow"})
    return k


def test_panel_sklada_sie_z_danymi():
    (a, _), _ = _dwa()
    store.dodaj_kontakt(a, "jan@example.com", "Jan")
    store.zapisz_szablon(a, "zapis", "Cześć {imie}", "Treść")
    store.zakolejkuj(a, "jan@example.com", "T", "C")
    html = _zalogowany().get("/").get_data(as_text=True)
    assert html.rstrip().endswith("</html>")
    for panel in ("przeglad", "kontakty", "szablony", "log", "wykluczenia"):
        assert f'data-panel="{panel}"' in html, panel
    assert "jan@example.com" in html and "zapis" in html


def test_klucz_pokazuje_sie_raz_przy_utworzeniu_serwisu():
    _czysto()
    k = _zalogowany()
    html = k.post("/serwis", data={"kod": "nowy", "nazwa": "Nowy",
                                   "nadawca_email": "a@b.pl"}).get_data(as_text=True)
    assert "pk_" in html
    # kolejne wejście na panel już go nie pokazuje
    assert "pk_" not in k.get("/").get_data(as_text=True)


def test_panel_nie_pokazuje_kontaktow_innego_serwisu_niz_wybrany():
    (a, _), (o, _) = _dwa()
    store.dodaj_kontakt(a, "uczestnik@example.com")
    store.dodaj_kontakt(o, "rodzic@example.com")
    k = _zalogowany()
    html_a = k.get(f"/?serwis={a}").get_data(as_text=True)
    assert "uczestnik@example.com" in html_a
    assert "rodzic@example.com" not in html_a


def test_zly_kod_serwisu_nie_tworzy_duplikatu():
    _czysto()
    k = _zalogowany()
    k.post("/serwis", data={"kod": "alpha", "nazwa": "Alpha", "nadawca_email": "a@b.pl"})
    html = k.post("/serwis", data={"kod": "alpha", "nazwa": "Inna",
                                   "nadawca_email": "c@d.pl"}).get_data(as_text=True)
    assert "już istnieje" in html
    assert len(store.serwisy()) == 1


def test_healthz_dziala_bez_logowania():
    assert _klient().get("/healthz").get_json() == {"status": "ok"}


def test_karta_zbiorcza_pokazuje_poczte_ze_wszystkich_serwisow():
    """Nagłówek „Latest across all services" ma nie kłamać. Przy wspólnej
    zmiennej karta była filtrowana po wybranym serwisie i wyglądała na pustą,
    gdy poczta szła z innego."""
    (a, _), (o, _) = _dwa()
    store.zakolejkuj(o, "rodzic@example.com", "Z ochrony", "C")
    html = _zalogowany().get(f"/?serwis={a}").get_data(as_text=True)
    assert "Z ochrony" in html, "poczta z niewybranego serwisu zniknęła z karty zbiorczej"
