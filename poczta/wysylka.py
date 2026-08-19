"""Warstwa dostarczania poczty.

ROZDZIELENIE NA INTERFEJS I IMPLEMENTACJĘ nie jest tu ozdobą architektoniczną,
tylko odpowiedzią na konkretną datę w kalendarzu. Microsoft wyłącza podstawowe
uwierzytelnianie SMTP w Exchange Online: do końca grudnia 2026 działa bez
zmian, potem jest domyślnie wyłączone (administrator może włączyć z powrotem),
a ostateczny termin usunięcia ma zostać ogłoszony w drugiej połowie 2027.
Kiedy ten dzień przyjdzie, wymiana hasła na OAuth ma być podmianą jednej
klasy, a nie przepisywaniem usługi.

TRWAŁY KONTRA CHWILOWY BŁĄD. Serwer SMTP odpowiada kodem z dwóch rodzin:
5xx znaczy „nie zadziała nigdy" (adres nie istnieje, skrzynka zamknięta),
4xx znaczy „nie teraz" (limit nadawcy, chwilowa niedostępność). Ponawianie
wysyłki na nieistniejący adres nie tylko nic nie daje, ale psuje reputację
nadawcy - dostawcy poczty liczą odboje. Dlatego rozróżniamy je u źródła.

HASŁO WCZYTUJEMY WYŁĄCZNIE ZE ZMIENNEJ ŚRODOWISKOWEJ. Nigdy nie trafia do
bazy, logów ani panelu.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
# Ile listów na minutę. Exchange Online przyjmuje 30/min i odcina powyżej,
# więc trzymamy się poniżej progu zamiast dowiadywać się o nim z odmowy.
NA_MINUTE = int(os.environ.get("SMTP_NA_MINUTE", "20") or "20")


class BladTrwaly(Exception):
    """Ponawianie nie ma sensu - adres jest zły albo list odrzucony."""


class BladChwilowy(Exception):
    """Warto spróbować później."""


def poprawny_adres(email: str) -> bool:
    """Minimalna, celowo niepełna walidacja adresu.

    ŚWIADOMIE NIE IMPLEMENTUJEMY RFC 5322. Pełna gramatyka adresu dopuszcza
    komentarze w nawiasach, cudzysłowy i adresy IP w nawiasach kwadratowych;
    wyrażenie regularne, które to obejmuje, ma kilkaset znaków i i tak nie
    odpowiada na jedyne interesujące pytanie - czy skrzynka istnieje. Tego nie
    da się sprawdzić inaczej niż wysyłką, więc odrzucamy tylko to, co jest
    bezspornie złe, a resztę weryfikuje serwer pocztowy odbojem.

    Sprawdzenie „czy jest małpa" nie wystarczyło: „@example.com" ma małpę
    i nie ma adresata."""
    e = (email or "").strip()
    if not e or len(e) > 254 or any(z.isspace() for z in e):
        return False
    if e.count("@") != 1:
        return False
    lokalna, _, domena = e.partition("@")
    if not lokalna or len(lokalna) > 64:
        return False
    if "." not in domena or domena.startswith(".") or domena.endswith("."):
        return False
    return all(czesc for czesc in domena.split("."))


def _adres(email: str, nazwa: str = "") -> str:
    """Nagłówek From z nazwą wyświetlaną, poprawnie zakodowany dla polskich
    znaków. Ręczne sklejanie 'Nazwa <adres>' psuje się przy diakrytykach."""
    email = (email or "").strip()
    if not nazwa:
        return email
    uzytkownik, _, domena = email.partition("@")
    if not domena:
        return email
    return str(Address(display_name=nazwa, username=uzytkownik, domain=domena))


# Limity załączników. Certyfikat EDU Plus waży ok. 220 kB, więc 8 MB na list
# to zapas rzędu wielkości. Powyżej tego i tak większość serwerów odrzuca
# wiadomość, a odrzucenie po stronie odbiorcy jest gorsze niż nasze własne:
# nie wiadomo wtedy, czy problem jest w rozmiarze, czy w treści.
MAKS_ZALACZNIK = 8 * 1024 * 1024
MAKS_ZALACZNIKOW = 5
# Nazwa pliku jedzie w nagłówku Content-Disposition. Znak nowej linii pozwala
# dopisać własne nagłówki, ukośnik sugeruje ścieżkę - jedno i drugie wycinamy
# u źródła, zamiast ufać, że biblioteka to zrobi.
_ZLE_W_NAZWIE = str.maketrans({"\r": None, "\n": None, "/": "-", "\\": "-", '"': "'"})


def czysta_nazwa_pliku(nazwa: str) -> str:
    nazwa = (nazwa or "").translate(_ZLE_W_NAZWIE).strip().lstrip(".")
    return (nazwa or "zalacznik")[:120]


def zbuduj(nadawca_email: str, nadawca_nazwa: str, do_email: str,
           temat: str, tresc: str, odpowiedz_do: str = "",
           naglowki: dict[str, str] | None = None,
           tresc_html: str | None = None,
           zalaczniki: list[dict] | None = None) -> EmailMessage:
    w = EmailMessage()
    w["Subject"] = temat
    w["From"] = _adres(nadawca_email, nadawca_nazwa)
    w["To"] = do_email
    if odpowiedz_do:
        w["Reply-To"] = odpowiedz_do
    # Własny Message-ID z domeny nadawcy. Bez niego serwer wstawia swój,
    # co przy wysyłce przez cudzy relay bywa czytane jako niespójność.
    _, adr = parseaddr(nadawca_email)
    domena = adr.partition("@")[2] or "localhost"
    w["Message-ID"] = make_msgid(domain=domena)
    for k, v in (naglowki or {}).items():
        w[k] = v

    # Wersja tekstowa ZAWSZE jako pierwsza, HTML jako alternatywa. Kolejność
    # nie jest kosmetyczna: czytnik pokazuje ostatnią część, którą umie
    # wyświetlić, więc odwrócenie jej daje surowy HTML w kliencie tekstowym.
    w.set_content(tresc)
    if tresc_html:
        w.add_alternative(tresc_html, subtype="html")

    for z in (zalaczniki or [])[:MAKS_ZALACZNIKOW]:
        dane = z.get("dane")
        if not isinstance(dane, (bytes, bytearray)) or not dane:
            continue
        if len(dane) > MAKS_ZALACZNIK:
            raise BladTrwaly(
                f"załącznik {czysta_nazwa_pliku(z.get('nazwa', ''))} ma "
                f"{len(dane) // 1024} kB, limit to {MAKS_ZALACZNIK // 1024} kB")
        typ = (z.get("typ") or "application/octet-stream").split("/", 1)
        w.add_attachment(bytes(dane), maintype=typ[0],
                         subtype=typ[1] if len(typ) > 1 else "octet-stream",
                         filename=czysta_nazwa_pliku(z.get("nazwa", "")))
    return w


class Dostawca:
    """Interfejs. Implementacja ma wysłać albo rzucić Blad{Trwaly,Chwilowy}."""

    nazwa = "abstrakcyjny"

    def skonfigurowany(self) -> tuple[bool, str]:
        raise NotImplementedError

    def wyslij(self, w: EmailMessage) -> str:
        raise NotImplementedError


class SmtpHaslem(Dostawca):
    """SMTP z loginem i hasłem, po STARTTLS na 587 albo SSL na 465."""

    nazwa = "SMTP"

    def skonfigurowany(self) -> tuple[bool, str]:
        brak = [n for n, v in (("SMTP_HOST", SMTP_HOST), ("SMTP_USER", SMTP_USER),
                               ("SMTP_PASS", SMTP_PASS)) if not v]
        if brak:
            return False, "brakuje: " + ", ".join(brak)
        return True, f"{SMTP_USER} przez {SMTP_HOST}:{SMTP_PORT}"

    def wyslij(self, w: EmailMessage) -> str:
        ok, opis = self.skonfigurowany()
        if not ok:
            raise BladTrwaly(f"nadawca nieskonfigurowany - {opis}")
        try:
            if SMTP_PORT == 465:
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30,
                                      context=ssl.create_default_context()) as s:
                    s.login(SMTP_USER, SMTP_PASS)
                    s.send_message(w)
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
                    s.starttls(context=ssl.create_default_context())
                    s.login(SMTP_USER, SMTP_PASS)
                    s.send_message(w)
            return f"{SMTP_HOST}:{SMTP_PORT}"
        except smtplib.SMTPAuthenticationError as e:
            # Osobno, bo to jedyny błąd, którego NIE naprawi ani ponowienie,
            # ani poprawienie adresu odbiorcy - i przy wyłączaniu Basic Auth
            # przez Microsoft to on pojawi się pierwszy.
            raise BladTrwaly(f"uwierzytelnienie odrzucone: {_krotko(e)}") from e
        except smtplib.SMTPRecipientsRefused as e:
            raise BladTrwaly(f"adresat odrzucony: {_krotko(e)}") from e
        except smtplib.SMTPSenderRefused as e:
            raise BladTrwaly(f"nadawca odrzucony: {_krotko(e)}") from e
        except smtplib.SMTPResponseException as e:
            tresc = f"{e.smtp_code} {_krotko(e)}"
            raise (BladTrwaly(tresc) if 500 <= e.smtp_code < 600
                   else BladChwilowy(tresc)) from e
        except (smtplib.SMTPException, OSError) as e:
            # Zerwane połączenie, DNS, timeout - wszystko chwilowe z definicji
            raise BladChwilowy(f"{type(e).__name__}: {e}") from e


def _krotko(e: Exception) -> str:
    t = str(e).replace("\n", " ")
    return t[:200]


def dostawca() -> Dostawca:
    """Punkt wymiany. Gdy Microsoft wyłączy hasła, dochodzi tu druga klasa
    (SmtpOAuth) i jeden warunek - reszta usługi nie wie o zmianie."""
    return SmtpHaslem()


def opis() -> str:
    d = dostawca()
    ok, szczegol = d.skonfigurowany()
    return f"{d.nazwa}: {szczegol}" if ok else f"{d.nazwa} nieskonfigurowany - {szczegol}"
