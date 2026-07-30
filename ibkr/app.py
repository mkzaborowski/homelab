"""Panel portfela IBKR - statystyki, ręczne dane i harmonogram pobrań."""
from __future__ import annotations

import os
import secrets
from functools import wraps

from flask import (Flask, redirect, request, send_file, session, url_for)

import sheets
import statystyki
import store
import widok
import zadanie

HASLO = os.environ.get("PANEL_HASLO", "")
STREFA = os.environ.get("TZ", "Europe/Warsaw")
GODZINA = os.environ.get("GODZINA_POBRANIA", "23:10")   # po sesji w USA (22:00 CET zamknięcie)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1") == "1")

store.zainicjuj()


def chronione(f):
    @wraps(f)
    def opakowane(*a, **kw):
        if not session.get("ok"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return opakowane


@app.get("/login")
def login():
    return widok.logowanie()


@app.post("/login")
def login_post():
    if HASLO and secrets.compare_digest(request.form.get("haslo", ""), HASLO):
        session["ok"] = True
        session.permanent = True
        return redirect(url_for("glowna"))
    return widok.logowanie("Nieprawidłowe hasło"), 401


@app.get("/wyloguj")
def wyloguj():
    session.clear()
    return redirect(url_for("login"))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


def _dane_panelu():
    z = store.zrzut()
    if not z:
        return None
    return statystyki.podsumowanie(z, store.meta(), store.poprzedni_zrzut(z["data"]))


@app.get("/")
@chronione
def glowna(komunikat="", blad=False):
    return widok.panel(_dane_panelu(), store.historia_nav(), store.koszyki(),
                       store.ostatnie_przebiegi(), komunikat=komunikat, blad=blad,
                       sheets_ok=sheets.skonfigurowane())


@app.post("/odswiez")
@chronione
def odswiez():
    ok, kom = zadanie.uruchom()
    return glowna(komunikat=kom, blad=not ok)


@app.post("/meta")
@chronione
def meta():
    """Zapis całej tabeli naraz + opcjonalne masowe przypisanie koszyka."""
    masowy = (request.form.get("masowy_nowy") or request.form.get("masowy_koszyk") or "").strip()
    zaznaczone = {s.strip().upper() for s in request.form.getlist("zazn")}

    symbole = sorted({k.split("__", 1)[1] for k in request.form if k.startswith("koszyk__")})
    zle_liczby, zapisane = [], 0
    for s in symbole:
        stop = (request.form.get(f"stop__{s}") or "").strip().replace(",", ".").replace(" ", "")
        try:
            stop_f = float(stop) if stop else None
        except ValueError:
            zle_liczby.append(f"{s}: „{stop}”")
            continue
        koszyk = (request.form.get(f"koszyk__{s}") or "").strip()
        if masowy and s in zaznaczone:
            koszyk = masowy
        store.zapisz_meta(s, koszyk=koszyk or None,
                          ocena=(request.form.get(f"ocena__{s}") or "").strip(), stop=stop_f)
        zapisane += 1

    if zle_liczby:
        return glowna(komunikat="Pominięto - stop musi być liczbą: " + ", ".join(zle_liczby[:5]),
                      blad=True)
    dopisek = f", w tym {len(zaznaczone)} do „{masowy}”" if masowy and zaznaczone else ""
    return glowna(komunikat=f"Zapisano {zapisane} tickerów{dopisek}")


@app.get("/pobierz.xlsx")
@chronione
def pobierz():
    if not zadanie.PLIK_XLSX.exists():
        return glowna(komunikat="Brak pliku - najpierw pobierz dane", blad=True)
    return send_file(zadanie.PLIK_XLSX, as_attachment=True,
                     download_name="portfel.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _harmonogram():
    """Codzienne pobranie po zamknięciu sesji w USA (pon-pt)."""
    from apscheduler.schedulers.background import BackgroundScheduler
    godz, _, minuta = GODZINA.partition(":")
    s = BackgroundScheduler(timezone=STREFA)
    s.add_job(zadanie.uruchom, "cron", day_of_week="mon-fri",
              hour=int(godz), minute=int(minuta or 0), id="pobranie",
              misfire_grace_time=3600, coalesce=True)
    s.start()
    return s


if os.environ.get("HARMONOGRAM", "1") == "1":
    _harmonogram()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8090")))
