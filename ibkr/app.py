"""Panel portfela IBKR - statystyki, ręczne dane i harmonogram pobrań."""
from __future__ import annotations

import os
import secrets
from functools import wraps

from flask import (Flask, redirect, request, send_file, session, url_for)

import notowania
import opcje
import klasyfikacja
import ryzyko
import rynek
import scenariusze as scen
import zwrot
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
# Osobny, częstszy przebieg wyłącznie dla progów odkupu. Nie rusza Flex,
# odpytuje tylko notowania - dlatego może chodzić dużo gęściej niż pobranie
# całego portfela. Bez skonfigurowanego Tradiera w ogóle nie startuje.
ALERTY_CO_MINUT = int(os.environ.get("ALERTY_CO_MINUT", "15"))

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


def _analityka(hist, pods) -> dict:
    """Zwrot, ryzyko i koncentracja - liczone raz na żądanie strony.

    Docelowo przeniesie się do dziennej migawki (§16 briefu), ale przy 262
    dniach i 58 spółkach liczy się w kilkadziesiąt milisekund, więc na razie
    nie ma czego optymalizować."""
    ops = store.operacje()
    z = zwrot.podsumowanie(hist, ops)
    if not z.get("dostepne"):
        return {"zwrot": z, "szereg": hist}
    dzienne = [x for _, x in z["zwroty"]]
    r = ryzyko.podsumowanie(dzienne, z["obsuniecia"], z["twr_roczny"])
    wartosci = {t["symbol"]: t["wartosc"] for t in (pods or {}).get("tickery", [])}

    # rozkład ryzyka i regresje czynnikowe - wymagają historii kursów
    ceny = store.ceny()
    wklad = czynniki = None
    if ceny:
        serie = {s: [x for _, x in rynek.zwroty_z_cen(sz)] for s, sz in ceny.items()}
        wagi = {s: v for s, v in wartosci.items() if s in serie and v > 0}
        wklad = ryzyko.wklad_do_ryzyka(wagi, serie)
        czynniki = _czynniki(dict(z["zwroty"]), ceny)

    poz = (pods or {}).get("pozycje", [])
    # Nogę opcyjną scenariusze biorą przez deltę i gammę, więc potrzebują
    # policzonych greków, a nie samych pozycji. Zera dawałyby wynik, w którym
    # opcje nie robią nic - a przy krótkich callach to one boleją najbardziej.
    opcje_do_scenariuszy = []
    try:
        zrz = store.zrzut()
        if zrz:
            for op in opcje.analizuj_pozycje(zrz["dane"]):
                if op.greki:
                    opcje_do_scenariuszy.append({
                        "bazowy": op.bazowy, "spot": op.kurs_bazowego,
                        "delta_akcji": op.delta_akcji, "gamma": op.gamma_pozycji})
    except Exception:                                           # noqa: BLE001
        opcje_do_scenariuszy = []
    return {
        "zwrot": z,
        "ryzyko": r,
        "koncentracja": ryzyko.koncentracja(wartosci),
        "miesiace": zwrot.zwroty_miesieczne(hist, zwrot.przeplywy_z_operacji(ops)),
        "szereg": hist,
        "uzgodnienie": {"ibkr": store.twr_ibkr()},
        "wklad": wklad,
        "czynniki": czynniki,
        "ekspozycje": {
            "temat": klasyfikacja.udzialy(poz, klasyfikacja.TEMAT),
            "sektor": klasyfikacja.udzialy(poz, klasyfikacja.SEKTOR),
            "kraj": klasyfikacja.udzialy(poz, klasyfikacja.KRAJ),
            "klasa": klasyfikacja.udzialy(poz, klasyfikacja.KLASA),
        },
        "zrodlo_cen": {"nazwa": rynek.dostawca().nazwa,
                       "zakres": store.zakres_cen()},
        "scenariusze": scen.podsumowanie(
            (pods or {}).get("nav", 0.0), czynniki or [], opcje_do_scenariuszy),
    }


def _czynniki(zwroty_portfela: dict, ceny: dict) -> list[dict]:
    """Regresja zwrotów portfela wobec każdego wzorca z osobna.

    Świadomie osobno, nie w jednej regresji wielorakiej: wzorce są ze sobą
    silnie skorelowane (QQQ z SPY), więc współczynniki z regresji wielorakiej
    byłyby niestabilne i trudne do obrony. Osobne bety odpowiadają na pytanie
    „jak bardzo portfel idzie za tym czynnikiem", i to jest pytanie użyteczne."""
    out = []
    for sym, opis in rynek.WZORCE.items():
        if sym not in ceny:
            continue
        wz = dict(rynek.zwroty_z_cen(ceny[sym]))
        wspolne = sorted(set(zwroty_portfela) & set(wz))
        b = ryzyko.beta([zwroty_portfela[d] for d in wspolne],
                        [wz[d] for d in wspolne]) if len(wspolne) >= 60 else None
        if b:
            out.append({"symbol": sym, "opis": opis, **b})
    return sorted(out, key=lambda x: -abs(x["r2"] or 0))


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
    por = analiza_opcji = analityka = None
    if pods:
        try:
            por = wzorzec.porownaj(wzorzec.parsuj(wzorzec.pobierz()), pods)
        except Exception as e:                                  # noqa: BLE001
            # brak wzorca nie może wywalić całego panelu
            app.logger.warning("Nie udało się pobrać wzorca: %s", e)
        try:
            z = store.zrzut()
            kursy = notowania.pobierz(notowania.symbole_ze_zrzutu(z["dane"]))
            analiza_opcji = opcje.analiza_do_panelu(
                z["dane"], store.transakcje(), store.zakres_rejestru(), kursy=kursy,
                zdarzenia=store.zdarzenia_opcji())
        except Exception as e:                                  # noqa: BLE001
            app.logger.warning("Nie udało się policzyć opcji: %s", e)
        try:
            analityka = _analityka(hist, pods)
        except Exception as e:                                  # noqa: BLE001
            app.logger.warning("Nie udało się policzyć analityki: %s", e)
    return widok.panel(pods, hist, store.koszyki(), store.ostatnie_przebiegi(),
                       komunikat=komunikat, blad=blad, sheets_ok=sheets.skonfigurowane(),
                       okresy=statystyki.okresy(hist, pods["nav"]) if pods else {},
                       harmonogram=opis_harmonogramu(), porownanie=por,
                       analiza_opcji=analiza_opcji, analityka=analityka)


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
    czesci = [f"pobranie co {CO_MINUT} min"]
    if notowania.skonfigurowane():
        czesci.append(f"progi odkupu co {ALERTY_CO_MINUT} min")
    czesci.append(notowania.opis())
    return " · ".join(czesci)


def _harmonogram():
    """Odświeżanie w stałym odstępie. Zrzut jest kluczowany datą raportu,
    więc powtórka tego samego dnia nadpisuje wpis, nie duplikuje go."""
    from apscheduler.schedulers.background import BackgroundScheduler
    s = BackgroundScheduler(timezone=STREFA)
    s.add_job(zadanie.uruchom, "interval", minutes=CO_MINUT, id="pobranie",
              misfire_grace_time=1800, coalesce=True, max_instances=1)
    if notowania.skonfigurowane():
        s.add_job(zadanie.sprawdz_same_alerty, "interval", minutes=ALERTY_CO_MINUT,
                  id="alerty", misfire_grace_time=600, coalesce=True, max_instances=1)
    s.start()
    return s


if os.environ.get("HARMONOGRAM", "1") == "1":
    _harmonogram()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8090")))
