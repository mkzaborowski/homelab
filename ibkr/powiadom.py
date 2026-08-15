"""Wysyłka powiadomień o progu odkupu.

Dwa kanały, oba włączane zmienną środowiskową i oba opcjonalne:

  POWIADOMIENIA=email  + SMTP_HOST/PORT/USER/PASS + MAIL_DO
  POWIADOMIENIA=ntfy   + NTFY_TEMAT (darmowy push na telefon, bez konta)

Gdy nic nie jest ustawione, alerty i tak są liczone i widoczne w panelu -
brak kanału nie może wyłączyć samej analizy. Każda próba wysyłki ląduje
w tabeli alerty_log, więc widać, czy powiadomienie faktycznie wyszło.

Uwaga o UWIERZYTELNIANIU: hasło do SMTP wczytujemy WYŁĄCZNIE ze zmiennej
środowiskowej. Nigdy nie trafia do bazy, logów ani panelu.
"""
from __future__ import annotations

import os
import smtplib
import urllib.request
from email.message import EmailMessage

KANAL = os.environ.get("POWIADOMIENIA", "").strip().lower()

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_OD = os.environ.get("MAIL_FROM", SMTP_USER)
MAIL_DO = os.environ.get("MAIL_DO", "")

NTFY_SERWER = os.environ.get("NTFY_SERWER", "https://ntfy.sh")
NTFY_TEMAT = os.environ.get("NTFY_TEMAT", "")


def skonfigurowane() -> tuple[bool, str]:
    """Czy da się cokolwiek wysłać i co dokładnie jest ustawione."""
    if KANAL == "email":
        brak = [n for n, v in (("SMTP_HOST", SMTP_HOST), ("SMTP_USER", SMTP_USER),
                               ("SMTP_PASS", SMTP_PASS), ("MAIL_DO", MAIL_DO)) if not v]
        if brak:
            return False, "e-mail wybrany, ale brakuje: " + ", ".join(brak)
        return True, f"e-mail na {MAIL_DO}"
    if KANAL == "ntfy":
        if not NTFY_TEMAT:
            return False, "ntfy wybrane, ale brakuje NTFY_TEMAT"
        return True, f"ntfy, temat {NTFY_TEMAT}"
    return False, "kanał nieustawiony (POWIADOMIENIA=email albo ntfy)"


def _tresc(alerty: list[dict]) -> tuple[str, str]:
    tytul = (f"Odkup opcji: {alerty[0]['etykieta']}" if len(alerty) == 1
             else f"Odkup opcji: {len(alerty)} pozycje osiągnęły próg")
    linie = []
    for a in alerty:
        linie.append(
            f"{a['etykieta']}\n"
            f"  cena opcji {a['cena_teraz']:.2f} (próg {a['cena_docelowa']:.2f})\n"
            f"  kurs bazowego {a['kurs_bazowego']:.2f}\n"
            f"  zysk z odkupu teraz: {a['zysk']:.2f} USD na {a['kontraktow']:.0f} kontraktach\n"
            f"  powód: {' · '.join(a['powody'])}")
    linie.append("\nDane z wyciągu IBKR z poprzedniej sesji — przed złożeniem "
                 "zlecenia sprawdź bieżącą cenę w TWS.")
    return tytul, "\n\n".join(linie)


def _wyslij_email(tytul: str, tresc: str) -> None:
    w = EmailMessage()
    w["Subject"] = tytul
    w["From"] = MAIL_OD
    w["To"] = MAIL_DO
    w.set_content(tresc)
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(w)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(w)


def _wyslij_ntfy(tytul: str, tresc: str) -> None:
    zad = urllib.request.Request(
        f"{NTFY_SERWER.rstrip('/')}/{NTFY_TEMAT}",
        data=tresc.encode("utf-8"),
        headers={"Title": tytul.encode("utf-8").decode("latin-1", "ignore"),
                 "Priority": "high", "Tags": "chart_with_downwards_trend"},
        method="POST")
    with urllib.request.urlopen(zad, timeout=30) as o:
        o.read()


def wyslij(alerty: list[dict]) -> tuple[bool, str]:
    """Jedno powiadomienie zbiorcze o wszystkich nowych progach."""
    if not alerty:
        return True, "brak nowych alertów"
    ok, opis = skonfigurowane()
    if not ok:
        return False, opis
    tytul, tresc = _tresc(alerty)
    try:
        if KANAL == "email":
            _wyslij_email(tytul, tresc)
        else:
            _wyslij_ntfy(tytul, tresc)
        return True, f"wysłano ({opis})"
    except Exception as e:                                      # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
