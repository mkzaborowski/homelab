"""Panel portfela IBKR - statystyki, ręczne dane i harmonogram pobrań."""
from __future__ import annotations

import os
import secrets
from functools import wraps

from flask import (Flask, redirect, request, send_file, session, url_for)

import opcje
import sheets
import statystyki
import wzorzec
import store
import widok
import zadanie

HASLO = os.environ.get("PANEL_HASLO", "")
STREFA = os.environ.get("TZ", "Europe/Warsaw")
# Co ile minut odświeżamy dane. Arkusz wzorcowy zmienia się na bieżąco,
# więc częstotliwość ustawia właśnie on - Flex i tak generuje wyciąg raz
# na dobę, a powtórne pobranie nadpisuje zrzut tego samego dnia.
CO_MINUT = int(os.environ.get("CO_MINUT", "90"))

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
    pods = _dane_panelu()
    hist = store.historia()
    por = analiza_opcji = None
    if pods:
        try:
            por = wzorzec.porownaj(wzorzec.parsuj(wzorzec.pobierz()), pods)
        except Exception as e:                                  # noqa: BLE001
            # brak wzorca nie może wywalić całego panelu
            app.logger.warning("Nie udało się pobrać wzorca: %s", e)
        try:
            z = store.zrzut()
            analiza_opcji = opcje.analiza_do_panelu(
                z["dane"], store.transakcje(), store.zakres_rejestru())
        except Exception as e:                                  # noqa: BLE001
            app.logger.warning("Nie udało się policzyć opcji: %s", e)
    return widok.panel(pods, hist, store.koszyki(), store.ostatnie_przebiegi(),
                       komunikat=komunikat, blad=blad, sheets_ok=sheets.skonfigurowane(),
                       okresy=statystyki.okresy(hist, pods["nav"]) if pods else {},
                       harmonogram=opis_harmonogramu(), porownanie=por,
                       analiza_opcji=analiza_opcji)


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


def opis_harmonogramu() -> str:
    return f"pobranie co {CO_MINUT} min"


def _harmonogram():
    """Odświeżanie w stałym odstępie. Zrzut jest kluczowany datą raportu,
    więc powtórka tego samego dnia nadpisuje wpis, nie duplikuje go."""
    from apscheduler.schedulers.background import BackgroundScheduler
    s = BackgroundScheduler(timezone=STREFA)
    s.add_job(zadanie.uruchom, "interval", minutes=CO_MINUT, id="pobranie",
              misfire_grace_time=1800, coalesce=True, max_instances=1)
    s.start()
    return s


if os.environ.get("HARMONOGRAM", "1") == "1":
    _harmonogram()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8090")))
