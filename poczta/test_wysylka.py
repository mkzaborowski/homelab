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


# --------------------------------------------------------------------------- #
#  HTML i załączniki
# --------------------------------------------------------------------------- #

def test_list_z_html_ma_obie_wersje_we_wlasciwej_kolejnosci():
    """Czytnik pokazuje OSTATNIĄ część, którą umie wyświetlić. Odwrócona
    kolejność daje surowy HTML w kliencie tekstowym."""
    w = wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "wersja tekstowa",
                       tresc_html="<p>wersja HTML</p>")
    czesci = [c.get_content_type() for c in w.walk() if not c.is_multipart()]
    assert czesci == ["text/plain", "text/html"], czesci
    assert w.get_body(("plain",)).get_content().strip() == "wersja tekstowa"
    assert "wersja HTML" in w.get_body(("html",)).get_content()


def test_zalacznik_pdf_trafia_do_listu():
    pdf = b"%PDF-1.4 udawany certyfikat"
    w = wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C",
                       zalaczniki=[{"nazwa": "Certyfikat 123.pdf",
                                    "typ": "application/pdf", "dane": pdf}])
    zal = list(w.iter_attachments())
    assert len(zal) == 1
    assert zal[0].get_filename() == "Certyfikat 123.pdf"
    assert zal[0].get_content_type() == "application/pdf"
    assert zal[0].get_payload(decode=True) == pdf


def test_nazwa_zalacznika_nie_przemyci_naglowka():
    """Nazwa jedzie w Content-Disposition, więc znak nowej linii pozwoliłby
    dopisać własne nagłówki do listu."""
    for zla, czego_nie_ma in (("plik\r\nBcc: ktos@example.com.pdf", "\n"),
                              ("../../etc/passwd", "/"),
                              ("a\\b.pdf", "\\")):
        assert czego_nie_ma not in wysylka.czysta_nazwa_pliku(zla), zla
    assert wysylka.czysta_nazwa_pliku("") == "zalacznik"
    assert wysylka.czysta_nazwa_pliku("...") == "zalacznik"


def test_za_duzy_zalacznik_jest_bledem_trwalym():
    """Ponawianie nie zmniejszy pliku, więc to nie jest błąd chwilowy."""
    try:
        wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C",
                       zalaczniki=[{"nazwa": "duzy.pdf", "typ": "application/pdf",
                                    "dane": b"x" * (wysylka.MAKS_ZALACZNIK + 1)}])
    except wysylka.BladTrwaly as e:
        assert "limit" in str(e)
    else:
        raise AssertionError("za duży załącznik przeszedł")


def test_zalaczniki_przechodza_przez_kolejke_z_bazy():
    """Pełna droga: base64 w bazie → bajty → wiadomość."""
    import base64
    s = _serwis()
    pdf = b"%PDF-1.4 certyfikat z kolejki"
    store.zakolejkuj(s, "jan@example.com", "Certyfikat", "treść",
                     tresc_html="<b>treść</b>",
                     zalaczniki=[{"nazwa": "cert.pdf", "typ": "application/pdf",
                                  "dane_b64": base64.b64encode(pdf).decode()}])
    d = Udany()
    kolejka.przebieg(dostawca=d, spij=lambda _: None)
    assert len(d.wyslane) == 1
    zal = list(d.wyslane[0].iter_attachments())
    assert len(zal) == 1 and zal[0].get_payload(decode=True) == pdf
    assert d.wyslane[0].get_body(("html",)) is not None


def test_uszkodzony_zalacznik_w_bazie_nie_wywala_calego_listu():
    """Reszta listu jest w porządku - lepiej wysłać go bez załącznika niż
    nie wysłać wcale i zostawić rodzica bez informacji."""
    s = _serwis()
    store.zakolejkuj(s, "jan@example.com", "T", "treść",
                     zalaczniki=[{"nazwa": "zly.pdf", "typ": "application/pdf",
                                  "dane_b64": "to-nie-jest-base64!!!"}])
    d = Udany()
    w = kolejka.przebieg(dostawca=d, spij=lambda _: None)
    assert w["wyslane"] == 1
    assert list(d.wyslane[0].iter_attachments()) == []


# --------------------------------------------------------------------------- #
#  Microsoft Graph
# --------------------------------------------------------------------------- #

def test_graph_wygrywa_gdy_skonfigurowany():
    """Graph nie wymaga wyłączania zabezpieczeń dzierżawy i nie ma terminu
    ważności, więc gdy jest gotowy, SMTP nie ma po co startować."""
    import unittest.mock as mock
    with mock.patch.multiple(wysylka, GRAPH_KLIENT="k", GRAPH_SEKRET="s"):
        assert isinstance(wysylka.dostawca(), wysylka.GraphOAuth)
    with mock.patch.multiple(wysylka, GRAPH_KLIENT="", GRAPH_SEKRET=""):
        assert isinstance(wysylka.dostawca(), wysylka.SmtpHaslem)


def test_graph_mowi_czego_brakuje():
    import unittest.mock as mock
    with mock.patch.multiple(wysylka, GRAPH_DZIERZAWA="d", GRAPH_KLIENT="k",
                             GRAPH_SEKRET="s", GRAPH_SKRZYNKA=""):
        ok, opis = wysylka.GraphOAuth().skonfigurowany()
    assert ok is False and "GRAPH_SKRZYNKA" in opis


def test_graph_wysyla_wiadomosc_jako_mime_na_wlasciwy_adres():
    """MIME, nie JSON: dzięki temu ta sama zbudowana wiadomość - z HTML-em,
    załącznikami i nagłówkami - idzie oboma kanałami bez drugiego kodu."""
    import base64 as b64, io, unittest.mock as mock
    zapisane = {}

    class Odpowiedz(io.BytesIO):
        status = 202
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def udawaj(zad, timeout=None):
        if "login.microsoftonline.com" in zad.full_url:
            return Odpowiedz(b'{"access_token":"tok","expires_in":3600}')
        zapisane["url"] = zad.full_url
        zapisane["naglowki"] = {k.lower(): v for k, v in zad.header_items()}
        zapisane["mime"] = b64.b64decode(zad.data)
        return Odpowiedz(b"")

    w = wysylka.zbuduj("polisy@ochronazklasa.pl", "Ochrona z klasą",
                       "rodzic@example.com", "Certyfikat", "treść",
                       tresc_html="<p>treść</p>",
                       zalaczniki=[{"nazwa": "cert.pdf", "typ": "application/pdf",
                                    "dane": b"%PDF-1.4 xxx"}])
    with mock.patch.multiple(wysylka, GRAPH_DZIERZAWA="dz", GRAPH_KLIENT="k",
                             GRAPH_SEKRET="s", GRAPH_SKRZYNKA="polisy@ochronazklasa.pl"), \
         mock.patch.object(wysylka.urllib.request, "urlopen", udawaj):
        opis = wysylka.GraphOAuth().wyslij(w)

    assert "polisy%40ochronazklasa.pl/sendMail" in zapisane["url"]
    assert zapisane["naglowki"]["authorization"] == "Bearer tok"
    assert zapisane["naglowki"]["content-type"] == "text/plain"
    assert b"Certyfikat" in zapisane["mime"]
    assert b"cert.pdf" in zapisane["mime"]          # zalacznik jedzie z wiadomoscia
    assert b"text/html" in zapisane["mime"]         # i wersja HTML tez
    assert "polisy@ochronazklasa.pl" in opis


def test_graph_token_jest_pobierany_raz_na_serie():
    """Token żyje godzinę. Pobieranie go do każdego listu dokładałoby żądanie
    na każdą wiadomość i niepotrzebnie obciążało logowanie."""
    import io, unittest.mock as mock
    ile = {"token": 0}

    class Odpowiedz(io.BytesIO):
        status = 202
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def udawaj(zad, timeout=None):
        if "login.microsoftonline.com" in zad.full_url:
            ile["token"] += 1
            return Odpowiedz(b'{"access_token":"tok","expires_in":3600}')
        return Odpowiedz(b"")

    w = wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C")
    with mock.patch.multiple(wysylka, GRAPH_DZIERZAWA="dz", GRAPH_KLIENT="k",
                             GRAPH_SEKRET="s", GRAPH_SKRZYNKA="a@b.pl"), \
         mock.patch.object(wysylka.urllib.request, "urlopen", udawaj):
        d = wysylka.GraphOAuth()
        for _ in range(3):
            d.wyslij(w)
    assert ile["token"] == 1, ile


def test_graph_rozroznia_blad_trwaly_od_chwilowego():
    """429 i 5xx to przeciążenie po ich stronie - ponawiamy. 401 i 403 to brak
    uprawnienia albo zgody administratora; ponawianie tego w nieskończoność
    zamuli kolejkę zamiast pokazać przyczynę."""
    import io, unittest.mock as mock, urllib.error

    class Token(io.BytesIO):
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def dla_kodu(kod):
        def udawaj(zad, timeout=None):
            if "login.microsoftonline.com" in zad.full_url:
                return Token(b'{"access_token":"tok","expires_in":3600}')
            raise urllib.error.HTTPError(zad.full_url, kod, "nope", {},
                                         io.BytesIO(b'{"error":{"message":"x"}}'))
        return udawaj

    w = wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C")
    for kod, oczekiwany in ((429, wysylka.BladChwilowy), (503, wysylka.BladChwilowy),
                            (401, wysylka.BladTrwaly), (403, wysylka.BladTrwaly),
                            (400, wysylka.BladTrwaly)):
        with mock.patch.multiple(wysylka, GRAPH_DZIERZAWA="dz", GRAPH_KLIENT="k",
                                 GRAPH_SEKRET="s", GRAPH_SKRZYNKA="a@b.pl"), \
             mock.patch.object(wysylka.urllib.request, "urlopen", dla_kodu(kod)):
            try:
                wysylka.GraphOAuth().wyslij(w)
            except oczekiwany:
                pass
            except Exception as e:                              # noqa: BLE001
                raise AssertionError(f"kod {kod} dał {type(e).__name__}, "
                                     f"oczekiwano {oczekiwany.__name__}") from e
            else:
                raise AssertionError(f"kod {kod} nie rzucił niczego")


def test_graph_odrzuca_za_duza_wiadomosc_jako_blad_trwaly():
    """Ponawianie nie zmniejszy wiadomości."""
    import io, unittest.mock as mock

    class Token(io.BytesIO):
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    w = wysylka.zbuduj("a@b.pl", "", "c@d.pl", "T", "C",
                       zalaczniki=[{"nazwa": "duzy.pdf", "typ": "application/pdf",
                                    "dane": b"x" * 4_000_000}])
    with mock.patch.multiple(wysylka, GRAPH_DZIERZAWA="dz", GRAPH_KLIENT="k",
                             GRAPH_SEKRET="s", GRAPH_SKRZYNKA="a@b.pl"), \
         mock.patch.object(wysylka.urllib.request, "urlopen",
                           lambda *a, **k: Token(b'{"access_token":"t","expires_in":3600}')):
        try:
            wysylka.GraphOAuth().wyslij(w)
        except wysylka.BladTrwaly as e:
            assert "limit Graph" in str(e)
        else:
            raise AssertionError("za duża wiadomość przeszła")


def test_mime_dla_graph_ma_koncowki_crlf():
    """Błąd, który dotarł do skrzynki rodzica jako „Twoja po=isa jest gotowa".

    Domyślna polityka `email` składa wiadomość z samym LF - smtplib dokleja
    powrót karetki dopiero przy wysyłce. Graph dostaje surowy MIME, więc
    konwersji nie robi nikt. Quoted-printable zapisuje łamanie długiej linii
    jako „=" na jej końcu, a parser rozpoznaje to WYŁĄCZNIE jako „=CRLF";
    przy samym LF czyta znak równości dosłownie i zjada literę po nim."""
    import email as biblioteka_email
    w = wysylka.zbuduj("polisy@ochronazklasa.pl", "Ochrona z Klasą",
                       "rodzic@example.com", "Twoja polisa jest gotowa",
                       "Świadczenie za 1% uszczerbku na zdrowiu. Składka 135 zł. "
                       "Ogólne Warunki Ubezpieczenia znajdziesz w załączniku, "
                       "a szczegóły ochrony w certyfikacie dołączonym do tej wiadomości.",
                       tresc_html="<p>NNW <strong>InterRisk</strong> — "
                                  "certyfikat w załączniku tej wiadomości.</p>")
    surowe = w.as_bytes(policy=w.policy.clone(linesep="\r\n"))
    assert b"\r\n" in surowe
    # ani jednego LF bez poprzedzającego CR
    assert surowe.replace(b"\r\n", b"").count(b"\n") == 0

    # a po odkodowaniu treść jest nietknięta
    wiad = biblioteka_email.message_from_bytes(surowe, policy=biblioteka_email.policy.default)
    tekst = wiad.get_body(("plain",)).get_content()
    html = wiad.get_body(("html",)).get_content()
    assert "Świadczenie" in tekst and "Składka" in tekst and "Ogólne" in tekst
    assert "<strong>InterRisk</strong>" in html
    assert "=" not in tekst.replace("=", "", 0) or "po=isa" not in tekst
    for zepsute in ("=isa", "Sk=C5", "<=trong", "za=C4"):
        assert zepsute not in tekst and zepsute not in html, zepsute


def test_graph_wysyla_mime_ktory_da_sie_odczytac():
    """Sprawdzamy to, co faktycznie poleci do Microsoftu, a nie to, co
    zbudowaliśmy - między jednym a drugim był właśnie ten błąd."""
    import base64 as b64, email as be, io, unittest.mock as mock
    zapisane = {}

    class Odpowiedz(io.BytesIO):
        status = 202
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def udawaj(zad, timeout=None):
        if "login.microsoftonline.com" in zad.full_url:
            return Odpowiedz(b'{"access_token":"tok","expires_in":3600}')
        zapisane["mime"] = b64.b64decode(zad.data)
        return Odpowiedz(b"")

    w = wysylka.zbuduj("polisy@ochronazklasa.pl", "Ochrona z Klasą",
                       "rodzic@example.com", "Certyfikat gotowy",
                       "Składka 135 zł, świadczenie za 1% uszczerbku 750 zł.",
                       tresc_html="<p><strong>Ogólne</strong> warunki</p>")
    with mock.patch.multiple(wysylka, GRAPH_DZIERZAWA="dz", GRAPH_KLIENT="k",
                             GRAPH_SEKRET="s", GRAPH_SKRZYNKA="polisy@ochronazklasa.pl"), \
         mock.patch.object(wysylka.urllib.request, "urlopen", udawaj):
        wysylka.GraphOAuth().wyslij(w)

    wiad = be.message_from_bytes(zapisane["mime"], policy=be.policy.default)
    assert wiad["Subject"] == "Certyfikat gotowy"
    assert "Składka 135 zł" in wiad.get_body(("plain",)).get_content()
    assert "<strong>Ogólne</strong>" in wiad.get_body(("html",)).get_content()
