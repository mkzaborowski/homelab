"""Testy składania listu, szablonów i kolejki z ponawianiem.

Sedno: rozróżnienie błędu trwałego od chwilowego. Ponawianie wysyłki na
nieistniejący adres nie tylko nic nie daje, ale psuje reputację nadawcy -
dostawcy poczty liczą odboje. Odwrotny błąd jest równie kosztowny: uznanie
chwilowej niedostępności za trwałą gubi list bezpowrotnie.
"""
from __future__ import annotations

import os
import smtplib
import tempfile

os.environ["POCZTA_DANE"] = tempfile.mkdtemp(prefix="poczta-test-w-")

import kolejka                                                  # noqa: E402
import store                                                    # noqa: E402
import szablony                                                 # noqa: E402
import wysylka                                                  # noqa: E402
from test_izolacja import _czysto                               # noqa: E402


class Udany(wysylka.Dostawca):
    nazwa = "test"

    def __init__(self):
        self.wyslane = []

    def skonfigurowany(self):
        return True, "test"

    def wyslij(self, w):
        self.wyslane.append(w)
        return "test"


class Padajacy(wysylka.Dostawca):
    def __init__(self, wyjatek, ile=999):
        self.wyjatek, self.ile, self.prob = wyjatek, ile, 0

    def skonfigurowany(self):
        return True, "test"

    def wyslij(self, w):
        self.prob += 1
        if self.prob <= self.ile:
            raise self.wyjatek
        return "test"


def _serwis():
    _czysto()
    return store.dodaj_serwis("alpha", "Alpha", "kontakt@alphaolsztyn.pl", "Alpha Olsztyn")


# --------------------------------------------------------------------------- #
#  szablony
# --------------------------------------------------------------------------- #

def test_podstawianie_zmiennych():
    t, c = szablony.zloz("Cześć {imie}", "Widzimy się {kiedy}.",
                         {"imie": "Jan", "kiedy": "w piątek"})
    assert t == "Cześć Jan" and c == "Widzimy się w piątek."


def test_brak_zmiennej_przerywa_zamiast_zostawiac_pustke():
    """Szablon „Dzień dobry {imie}" bez imienia wysłałby „Dzień dobry "
    i nikt by tego nie zauważył aż do reklamacji."""
    try:
        szablony.zloz("Dzień dobry {imie}", "treść", {})
    except szablony.BrakZmiennej as e:
        assert "imie" in str(e)
    else:
        raise AssertionError("brak zmiennej przeszedł bez szemrania")


def test_odmowa_przy_pustym_temacie_i_tresci():
    for temat, tresc in (("", "treść"), ("Temat", "   ")):
        try:
            szablony.zloz(temat, tresc)
        except ValueError:
            pass
        else:
            raise AssertionError(f"puste przeszło: {temat!r}/{tresc!r}")


def test_nowa_linia_w_temacie_jest_odrzucana():
    """Nagłówki od treści oddziela pusta linia, więc znak nowej linii w temacie
    pozwoliłby dopisać własne nagłówki do listu."""
    try:
        szablony.zloz("Temat\nBcc: ktos@example.com", "treść")
    except ValueError as e:
        assert "nowej linii" in str(e)
    else:
        raise AssertionError("wstrzyknięcie nagłówka przeszło")


def test_zmienne_sa_wykrywane_do_podpowiedzi_w_panelu():
    assert szablony.zmienne("Cześć {imie}, {kiedy} o {godzina}") == {"imie", "kiedy", "godzina"}


# --------------------------------------------------------------------------- #
#  budowa listu
# --------------------------------------------------------------------------- #

def test_nazwa_nadawcy_z_polskimi_znakami_jest_kodowana():
    """Ręczne sklejanie 'Nazwa <adres>' psuje się przy diakrytykach."""
    w = wysylka.zbuduj("biuro@ochronazklasa.pl", "Ochrona z klasą",
                       "jan@example.com", "Temat", "Treść")
    naglowek = str(w["From"])
    assert "ochronazklasa.pl" in naglowek
    assert w["To"] == "jan@example.com"
    assert w.get_content().strip() == "Treść"


def test_list_ma_message_id_z_domeny_nadawcy():
    w = wysylka.zbuduj("biuro@ochronazklasa.pl", "", "jan@example.com", "T", "C")
    assert w["Message-ID"].endswith("@ochronazklasa.pl>")


def test_reply_to_wchodzi_tylko_gdy_podany():
    bez = wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C")
    z = wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C", odpowiedz_do="x@y.pl")
    assert bez["Reply-To"] is None and z["Reply-To"] == "x@y.pl"


# --------------------------------------------------------------------------- #
#  kolejka
# --------------------------------------------------------------------------- #

def test_udana_wysylka_zdejmuje_list_z_kolejki():
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "Temat", "Treść")
    d = Udany()
    w = kolejka.przebieg(dostawca=d, spij=lambda _: None)
    assert w == {"wziete": 1, "wyslane": 1, "chwilowe": 0, "trwale": 0, "pominiete": 0}
    assert store.historia(s)[0]["stan"] == "wyslany"
    assert store.do_wyslania() == []
    assert d.wyslane[0]["To"] == "jan@example.com"


def test_udana_wysylka_odnotowuje_kontakt():
    s = _serwis()
    store.dodaj_kontakt(s, "jan@example.com")
    store.zakolejkuj(s, "jan@example.com", "T", "C")
    kolejka.przebieg(dostawca=Udany(), spij=lambda _: None)
    assert store.kontakty(s)[0]["ostatnia_wysylka"] is not None


def test_blad_chwilowy_zostawia_list_do_ponowienia():
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "T", "C")
    w = kolejka.przebieg(dostawca=Padajacy(wysylka.BladChwilowy("SMTP padł")),
                         spij=lambda _: None)
    assert w["chwilowe"] == 1
    x = store.historia(s)[0]
    assert x["stan"] == "czeka" and x["prob"] == 1
    assert "SMTP padł" in x["ostatni_blad"]


def test_blad_trwaly_nie_jest_ponawiany():
    s = _serwis()
    store.zakolejkuj(s, "nieistnieje@example.com", "T", "C")
    w = kolejka.przebieg(dostawca=Padajacy(wysylka.BladTrwaly("adresat odrzucony: 550")),
                         spij=lambda _: None)
    assert w["trwale"] == 1
    assert store.historia(s)[0]["stan"] == "przepadl"
    # i adres wchodzi na listę wykluczeń, żeby nie dokładać kolejnych odbojów
    assert store.wykluczony("nieistnieje@example.com", s)["powod"] == "odbity"


def test_list_przepada_dopiero_po_wyczerpaniu_prob():
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "T", "C")
    d = Padajacy(wysylka.BladChwilowy("chwilowo"))
    for i in range(store.PROBY):
        with store.polacz() as con:            # udajemy, że nadszedł czas próby
            con.execute("UPDATE kolejka SET nastepna_proba='2000-01-01T00:00:00+00:00'")
        kolejka.przebieg(dostawca=d, spij=lambda _: None)
    x = store.historia(s)[0]
    assert x["prob"] == store.PROBY
    assert x["stan"] == "przepadl"


def test_odstepy_miedzy_probami_rosna():
    """Pierwsza próba za minutę, ostatnia za cztery godziny. Stały odstęp albo
    zasypuje serwer przy dłuższej awarii, albo za długo zwleka z pierwszym
    ponowieniem po chwilowej czkawce."""
    assert list(store.ODSTEPY_MIN) == sorted(store.ODSTEPY_MIN)
    assert store.ODSTEPY_MIN[0] <= 5 and store.ODSTEPY_MIN[-1] >= 60
    assert len(store.ODSTEPY_MIN) == store.PROBY


def test_list_nie_wychodzi_przed_czasem_kolejnej_proby():
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "T", "C")
    kolejka.przebieg(dostawca=Padajacy(wysylka.BladChwilowy("x")), spij=lambda _: None)
    assert store.do_wyslania() == []            # czas następnej próby jeszcze nie nadszedł


def test_wykluczony_adres_nie_dostaje_listu_nawet_z_kolejki():
    """Adres mógł się odbić między zakolejkowaniem a wysyłką."""
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "T", "C")
    store.wyklucz("jan@example.com", "odbity")
    d = Udany()
    w = kolejka.przebieg(dostawca=d, spij=lambda _: None)
    assert w["pominiete"] == 1 and d.wyslane == []
    assert store.historia(s)[0]["stan"] == "przepadl"


def test_jeden_zly_list_nie_zatrzymuje_pozostalych():
    """Kolejka ma iść dalej mimo błędu - inaczej jeden zły adres blokuje
    korespondencję wszystkich."""
    s = _serwis()
    for i in range(3):
        store.zakolejkuj(s, f"jan{i}@example.com", "T", "C")

    class TylkoDrugiPada(Udany):
        def wyslij(self, w):
            if w["To"] == "jan1@example.com":
                raise wysylka.BladTrwaly("adresat odrzucony")
            return super().wyslij(w)

    d = TylkoDrugiPada()
    w = kolejka.przebieg(dostawca=d, spij=lambda _: None)
    assert w["wyslane"] == 2 and w["trwale"] == 1
    assert {x["To"] for x in d.wyslane} == {"jan0@example.com", "jan2@example.com"}


def test_nieprzewidziany_wyjatek_traktujemy_jak_chwilowy():
    """Przy błędzie w NASZYM kodzie lepiej ponowić po poprawce niż uznać list
    za przepadły i stracić go bezpowrotnie."""
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "T", "C")
    w = kolejka.przebieg(dostawca=Padajacy(RuntimeError("literówka w kodzie")),
                         spij=lambda _: None)
    assert w["chwilowe"] == 1
    assert store.historia(s)[0]["stan"] == "czeka"


def test_kolejka_zachowuje_kolejnosc_przyjecia():
    s = _serwis()
    for i in range(3):
        store.zakolejkuj(s, f"jan{i}@example.com", f"Temat {i}", "C")
    d = Udany()
    kolejka.przebieg(dostawca=d, spij=lambda _: None)
    assert [w["Subject"] for w in d.wyslane] == ["Temat 0", "Temat 1", "Temat 2"]


def test_tempo_wysylki_trzyma_sie_ponizej_limitu_nadawcy():
    """Exchange Online przyjmuje 30 listów na minutę i odcina powyżej."""
    assert wysylka.NA_MINUTE <= 30
    assert kolejka.PRZERWA >= 2.0


def test_przerwa_jest_robiona_miedzy_listami_a_nie_po_ostatnim():
    s = _serwis()
    for i in range(3):
        store.zakolejkuj(s, f"jan{i}@example.com", "T", "C")
    spania = []
    kolejka.przebieg(dostawca=Udany(), spij=spania.append)
    assert len(spania) == 2                     # trzy listy, dwie przerwy


def test_kod_5xx_jest_trwaly_a_4xx_chwilowy():
    """To rozróżnienie robi cała reszta zachowania kolejki, więc sprawdzamy
    je na prawdziwych wyjątkach smtplib, nie na atrapach."""
    d = wysylka.SmtpHaslem()
    os.environ["SMTP_USER"] = "x"                # tylko po to, by przejść walidację
    wysylka.SMTP_USER = wysylka.SMTP_PASS = wysylka.SMTP_HOST = "x"

    class Podmiana:
        def __init__(self, wyj): self.wyj = wyj
        def __enter__(self): raise self.wyj
        def __exit__(self, *a): return False

    import unittest.mock as mock
    for kod, oczekiwany in ((550, wysylka.BladTrwaly), (451, wysylka.BladChwilowy)):
        with mock.patch.object(wysylka.smtplib, "SMTP",
                               lambda *a, **k: Podmiana(
                                   wysylka.smtplib.SMTPResponseException(kod, b"nope"))):
            try:
                d.wyslij(wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C"))
            except oczekiwany:
                pass
            except Exception as e:                              # noqa: BLE001
                raise AssertionError(f"kod {kod} dał {type(e).__name__}, "
                                     f"oczekiwano {oczekiwany.__name__}") from e
            else:
                raise AssertionError(f"kod {kod} nie rzucił niczego")


def test_odrzucone_uwierzytelnienie_jest_trwale():
    """Przy wyłączaniu podstawowego uwierzytelniania przez Microsoft to ten
    błąd pojawi się pierwszy - i ponawianie go w nieskończoność zamuliłoby
    kolejkę zamiast pokazać przyczynę."""
    import unittest.mock as mock
    wysylka.SMTP_USER = wysylka.SMTP_PASS = wysylka.SMTP_HOST = "x"

    class Podmiana:
        def __enter__(self):
            raise smtplib.SMTPAuthenticationError(535, b"5.7.139 Basic auth disabled")
        def __exit__(self, *a): return False

    with mock.patch.object(wysylka.smtplib, "SMTP", lambda *a, **k: Podmiana()):
        try:
            wysylka.SmtpHaslem().wyslij(wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C"))
        except wysylka.BladTrwaly as e:
            assert "uwierzytelnienie" in str(e)
        else:
            raise AssertionError("odrzucone hasło nie zostało uznane za trwałe")


def test_walidacja_adresu_odrzuca_bezsporne_bzdury():
    """„@example.com" ma małpę i nie ma adresata - sprawdzanie samej małpy
    to za mało."""
    for zly in ("", "   ", "jan", "@example.com", "jan@", "a@b", "jan@.pl",
                "jan@pl.", "jan kowalski@example.com", "jan@@example.com",
                "a" * 65 + "@example.com", "jan@example..pl"):
        assert not wysylka.poprawny_adres(zly), zly


def test_walidacja_adresu_przepuszcza_normalne():
    for dobry in ("jan@example.com", "jan.kowalski+tag@sub.example.co.uk",
                  "biuro@ochronazklasa.pl", "k@a.pl"):
        assert wysylka.poprawny_adres(dobry), dobry


class Nieskonfigurowany(wysylka.Dostawca):
    nazwa = "test"

    def skonfigurowany(self):
        return False, "brakuje: SMTP_USER, SMTP_PASS"

    def wyslij(self, w):
        raise AssertionError("nie wolno próbować bez konfiguracji nadawcy")


def test_brak_konfiguracji_nadawcy_nie_zuzywa_prob():
    """Znalezione testem przelotowym na serwerze: przed poprawką każdy list
    zaliczał tu próbę i po piątej przepadał — czyli odwrotność tego, po co
    jest kolejka. Nikt niczego nie próbował wysłać: nie było połączenia,
    nie było odmowy, nie ma czego liczyć jako nieudanej próby."""
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "T", "C")
    for _ in range(store.PROBY + 2):
        w = kolejka.przebieg(dostawca=Nieskonfigurowany(), spij=lambda _: None)
    x = store.historia(s)[0]
    assert x["stan"] == "czeka", "list przepadł, choć nigdy nie próbowano go wysłać"
    assert x["prob"] == 0
    assert w["wstrzymane"] == 1 and "SMTP_USER" in w["powod"]


def test_poczta_wychodzi_w_komplecie_gdy_haslo_wreszcie_trafi_do_konfiguracji():
    """Sedno poprzedniego testu: listy mają poczekać i wyjść, a nie przepaść."""
    s = _serwis()
    for i in range(3):
        store.zakolejkuj(s, f"jan{i}@example.com", f"T{i}", "C")
    for _ in range(4):
        kolejka.przebieg(dostawca=Nieskonfigurowany(), spij=lambda _: None)

    d = Udany()
    w = kolejka.przebieg(dostawca=d, spij=lambda _: None)
    assert w["wyslane"] == 3 and len(d.wyslane) == 3
    assert all(x["stan"] == "wyslany" for x in store.historia(s))


def test_opis_wstrzymania_mowi_czego_brakuje():
    """W logu przebiegów ma stać przyczyna, nie „kolejka pusta" — inaczej
    wygląda to na brak poczty, a nie na brak hasła."""
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "T", "C")
    w = kolejka.przebieg(dostawca=Nieskonfigurowany(), spij=lambda _: None)
    opis = kolejka.opis_przebiegu(w)
    assert "wstrzymane" in opis and "SMTP_USER" in opis
