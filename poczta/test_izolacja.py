"""Testy izolacji serwisów - najważniejszy plik w tej usłudze.

Cała reszta to wygoda; TO jest wymaganie, dla którego usługa powstała:
poczta i kontakty z alphaolsztyn.pl, ochronazklasa.pl i panelu portfela mają
się nie mieszać. Izolacja ma być własnością konstrukcji, nie obietnicą - więc
testy próbują ją złamać, a nie tylko sprawdzają, że zwykłe użycie działa.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["POCZTA_DANE"] = tempfile.mkdtemp(prefix="poczta-test-")

import store                                                    # noqa: E402


def _czysto():
    """Każdy test dostaje pustą bazę. Współdzielona baza między testami
    ukrywa błędy izolacji, bo dane z poprzedniego testu wyglądają jak dane
    właściwego serwisu."""
    if store.PLIK.exists():
        store.PLIK.unlink()
    for pom in (".wal", ".shm"):
        p = Path(str(store.PLIK) + pom)
        if p.exists():
            p.unlink()
    store.zainicjuj()


def _dwa_serwisy():
    _czysto()
    a = store.dodaj_serwis("alpha", "Alpha Olsztyn", "kontakt@alphaolsztyn.pl")
    o = store.dodaj_serwis("ochrona", "Ochrona z klasą", "biuro@ochronazklasa.pl")
    return a, o


def test_ten_sam_adres_w_dwoch_serwisach_to_dwa_osobne_kontakty():
    """Ta sama osoba może być rodzicem z ochronazklasa i uczestnikiem alphy.
    To dwa niezależne wpisy: usunięcie z jednego nie rusza drugiego."""
    a, o = _dwa_serwisy()
    store.dodaj_kontakt(a, "jan@example.com", "Jan")
    store.dodaj_kontakt(o, "jan@example.com", "Jan Kowalski")

    assert [k["email"] for k in store.kontakty(a)] == ["jan@example.com"]
    assert [k["email"] for k in store.kontakty(o)] == ["jan@example.com"]
    assert store.kontakty(a)[0]["imie"] == "Jan"
    assert store.kontakty(o)[0]["imie"] == "Jan Kowalski"

    store.usun_kontakt(a, "jan@example.com")
    assert store.kontakty(a) == []
    assert len(store.kontakty(o)) == 1


def test_serwis_widzi_wylacznie_swoje_kontakty():
    a, o = _dwa_serwisy()
    store.dodaj_kontakt(a, "uczestnik@example.com")
    store.dodaj_kontakt(o, "rodzic@example.com")
    assert [k["email"] for k in store.kontakty(a)] == ["uczestnik@example.com"]
    assert [k["email"] for k in store.kontakty(o)] == ["rodzic@example.com"]


def test_szukanie_nie_przecieka_miedzy_serwisami():
    """Wyszukiwarka to najłatwiejsze miejsce na wyciek: łatwo zapomnieć
    o warunku serwisu, gdy dopisuje się filtr tekstowy."""
    a, o = _dwa_serwisy()
    store.dodaj_kontakt(a, "kowalski@example.com", "Kowalski")
    store.dodaj_kontakt(o, "kowalski@inne.pl", "Kowalski")
    assert [k["email"] for k in store.kontakty(a, "kowalski")] == ["kowalski@example.com"]
    assert [k["email"] for k in store.kontakty(o, "kowalski")] == ["kowalski@inne.pl"]


def test_szablony_o_tym_samym_kodzie_sa_niezalezne():
    """Oba serwisy mają szablon 'potwierdzenie' i to normalne - jeden pisze
    o ubezpieczeniu, drugi o spotkaniu."""
    a, o = _dwa_serwisy()
    store.zapisz_szablon(a, "potwierdzenie", "Zapisano na spotkanie", "Do zobaczenia")
    store.zapisz_szablon(o, "potwierdzenie", "Zgłoszenie przyjęte", "Polisa w drodze")
    assert store.szablon(a, "potwierdzenie")["temat"] == "Zapisano na spotkanie"
    assert store.szablon(o, "potwierdzenie")["temat"] == "Zgłoszenie przyjęte"

    store.usun_szablon(a, "potwierdzenie")
    assert store.szablon(a, "potwierdzenie") is None
    assert store.szablon(o, "potwierdzenie") is not None


def test_log_wysylek_jest_rozdzielony():
    a, o = _dwa_serwisy()
    store.zakolejkuj(a, "jeden@example.com", "A", "treść A")
    store.zakolejkuj(o, "dwa@example.com", "O", "treść O")
    assert [x["temat"] for x in store.historia(a)] == ["A"]
    assert [x["temat"] for x in store.historia(o)] == ["O"]
    assert len(store.historia()) == 2          # panel widzi całość, serwis nie


def test_klucz_api_rozpoznaje_wlasciwy_serwis():
    a, o = _dwa_serwisy()
    ka, ko = store.wydaj_klucz(a), store.wydaj_klucz(o)
    assert store.serwis_po_kluczu(ka)["id"] == a
    assert store.serwis_po_kluczu(ko)["id"] == o
    assert ka != ko


def test_klucza_nie_da_sie_odczytac_z_bazy():
    """Gdyby baza wyciekła, znajdujące się w niej skróty nie pozwalają wysłać
    ani jednego maila."""
    a, _ = _dwa_serwisy()
    klucz = store.wydaj_klucz(a)
    s = store.serwis(a)
    assert klucz not in str(dict(s))
    assert s["klucz_skrot"] != klucz and len(s["klucz_skrot"]) == 64
    assert s["klucz_koncowka"] == klucz[-4:]     # tyle, ile trzeba do rozpoznania


def test_nowy_klucz_uniewaznia_poprzedni():
    a, _ = _dwa_serwisy()
    stary = store.wydaj_klucz(a)
    nowy = store.wydaj_klucz(a)
    assert store.serwis_po_kluczu(stary) is None
    assert store.serwis_po_kluczu(nowy)["id"] == a


def test_wylaczony_serwis_traci_dostep_natychmiast():
    a, _ = _dwa_serwisy()
    klucz = store.wydaj_klucz(a)
    assert store.serwis_po_kluczu(klucz) is not None
    store.zmien_serwis(a, aktywny=0)
    assert store.serwis_po_kluczu(klucz) is None


def test_smiec_zamiast_klucza_nie_daje_dostepu():
    a, _ = _dwa_serwisy()
    store.wydaj_klucz(a)
    for zly in ("", "pk_", "pk_nieistniejacy", "Bearer pk_x", None,
                "' OR 1=1 --", "pk_" + "a" * 43):
        assert store.serwis_po_kluczu(zly) is None, zly


def test_wykluczenie_serwisowe_nie_ucisza_pozostalych():
    """Wypisanie się z powiadomień alphy nie może zablokować potwierdzenia
    zgłoszenia ubezpieczeniowego - to byłoby zaskakujące i szkodliwe."""
    a, o = _dwa_serwisy()
    store.wyklucz("jan@example.com", "wypisany", a)
    assert store.wykluczony("jan@example.com", a)["powod"] == "wypisany"
    assert store.wykluczony("jan@example.com", o) is None


def test_twardy_odboj_obowiazuje_wszedzie():
    """Nieistniejąca skrzynka to cecha adresu, nie relacji z jednym serwisem."""
    a, o = _dwa_serwisy()
    store.wyklucz("nieistnieje@example.com", "odbity")      # bez serwisu = globalnie
    assert store.wykluczony("nieistnieje@example.com", a) is not None
    assert store.wykluczony("nieistnieje@example.com", o) is not None


def test_globalne_wyklucznie_wygrywa_z_serwisowym():
    """Adres wykluczony i lokalnie, i globalnie ma pokazać powód globalny -
    ten jest mocniejszy i to on tłumaczy, dlaczego poczta nie dochodzi."""
    a, _ = _dwa_serwisy()
    store.wyklucz("jan@example.com", "wypisany", a)
    store.wyklucz("jan@example.com", "odbity")
    assert store.wykluczony("jan@example.com", a)["powod"] == "odbity"


def test_odwolanie_wykluczenia_dziala_w_swoim_zasiegu():
    a, _ = _dwa_serwisy()
    store.wyklucz("jan@example.com", "wypisany", a)
    store.wyklucz("jan@example.com", "odbity")
    store.odwolaj_wykluczenie("jan@example.com", None)          # tylko globalne
    assert store.wykluczony("jan@example.com", a)["powod"] == "wypisany"


def test_usuniecie_serwisu_zabiera_jego_dane_i_nie_rusza_cudzych():
    a, o = _dwa_serwisy()
    store.dodaj_kontakt(a, "jeden@example.com")
    store.dodaj_kontakt(o, "dwa@example.com")
    store.zakolejkuj(a, "jeden@example.com", "A", "x")
    with store.polacz() as con:
        con.execute("DELETE FROM serwisy WHERE id=?", (a,))
    assert store.kontakty(o) and len(store.kontakty(o)) == 1
    assert len(store.historia()) == 0                           # kaskada zadziałała


def test_idempotencja_nie_wysyla_drugi_raz():
    """Aplikacja, która dostała timeout, ponowi żądanie. Bez tego ta sama
    osoba dostałaby dwa identyczne potwierdzenia."""
    a, _ = _dwa_serwisy()
    id1, nowy1 = store.zakolejkuj(a, "jan@example.com", "T", "treść", klucz_idem="zg-42")
    id2, nowy2 = store.zakolejkuj(a, "jan@example.com", "T", "treść", klucz_idem="zg-42")
    assert nowy1 is True and nowy2 is False and id1 == id2
    assert len(store.historia(a)) == 1


def test_ten_sam_klucz_idempotencji_w_dwoch_serwisach_nie_koliduje():
    """Dwie aplikacje numerują zgłoszenia od jedynki. Gdyby klucz był globalny,
    zgłoszenie nr 1 w alphie zablokowałoby zgłoszenie nr 1 w ochronie."""
    a, o = _dwa_serwisy()
    store.zakolejkuj(a, "jan@example.com", "A", "x", klucz_idem="1")
    _, nowy = store.zakolejkuj(o, "jan@example.com", "O", "y", klucz_idem="1")
    assert nowy is True
    assert len(store.historia(a)) == 1 and len(store.historia(o)) == 1


def test_zapomnienie_czysci_wszystkie_serwisy_i_tresc():
    a, o = _dwa_serwisy()
    store.dodaj_kontakt(a, "jan@example.com")
    store.dodaj_kontakt(o, "jan@example.com")
    store.zakolejkuj(a, "jan@example.com", "Temat", "treść wrażliwa")
    n = store.zapomnij("jan@example.com")
    assert n == 2
    assert store.kontakty(a) == [] and store.kontakty(o) == []
    assert "wrażliwa" not in store.historia(a)[0]["tresc"]
    # wykluczenie zostaje, żeby adres nie wrócił przy kolejnym formularzu
    assert store.wykluczony("jan@example.com", a) is not None
