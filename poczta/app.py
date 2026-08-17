"""Usługa pocztowa: jedno API wysyłkowe i panel dla wszystkich moich serwisów.

IZOLACJA SERWISÓW JEST TU CELEM, NIE SKUTKIEM UBOCZNYM. Każdy serwis
(ochronazklasa, alpha, portfel) ma własny klucz API, własnego nadawcę, własną
książkę adresową i własny log. Klucz z jednego serwisu nie sięgnie do danych
drugiego, bo tożsamość serwisu ustala się raz - przy rozpoznaniu klucza -
i przechodzi do każdego zapytania w bazie.

Klucz API idzie w nagłówku Authorization, nigdy w adresie: adresy lądują
w logach serwera pośredniczącego i w historii przeglądarki.
"""
from __future__ import annotations

import hmac
import os
import secrets
from functools import wraps
from hashlib import sha256

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, request, session, url_for

import kolejka
import store
import szablony
import widok
import wysylka

HASLO = os.environ.get("PANEL_HASLO", "")
CO_SEKUND = int(os.environ.get("PRZEBIEG_CO_SEKUND", "60") or "60")
PACZKA = int(os.environ.get("PRZEBIEG_PACZKA", "20") or "20")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1") == "1",
                  MAX_CONTENT_LENGTH=2 * 1024 * 1024)

store.zainicjuj()


# --------------------------------------------------------------------------- #
#  dostęp
# --------------------------------------------------------------------------- #

def chronione(f):
    @wraps(f)
    def opakowane(*a, **kw):
        if not session.get("ok"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return opakowane


def z_kluczem(f):
    """Rozpoznaje serwis po kluczu API i podaje go dalej jako pierwszy argument.

    To jedyne miejsce, w którym żądanie z zewnątrz zdobywa tożsamość. Dalej
    już nic nie ma prawa jej zmienić - dlatego serwis jedzie argumentem,
    a nie jest odczytywany z ciała żądania, gdzie klient mógłby go podmienić."""
    @wraps(f)
    def opakowane(*a, **kw):
        naglowek = request.headers.get("Authorization", "")
        klucz = naglowek[7:].strip() if naglowek.lower().startswith("bearer ") else ""
        s = store.serwis_po_kluczu(klucz)
        if not s:
            return jsonify({"blad": "nieznany albo nieaktywny klucz API"}), 401
        return f(s, *a, **kw)
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
    return widok.logowanie("Wrong password"), 401


@app.get("/wyloguj")
def wyloguj():
    session.clear()
    return redirect(url_for("login"))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
#  API dla pozostałych usług
# --------------------------------------------------------------------------- #

@app.post("/api/wyslij")
@z_kluczem
def api_wyslij(s):
    """Przyjmuje list do kolejki. Odpowiada 202, nie 200 - w chwili odpowiedzi
    nic jeszcze nie zostało dostarczone i udawanie inaczej byłoby kłamstwem,
    na którym aplikacje budowałyby błędne założenia."""
    d = request.get_json(silent=True) or {}
    do = (d.get("do") or "").strip().lower()
    if not wysylka.poprawny_adres(do):
        return jsonify({"blad": "pole 'do' nie wygląda na adres e-mail"}), 400

    w = store.wykluczony(do, s["id"])
    if w:
        # 200, nie błąd: z punktu widzenia aplikacji wołającej wszystko poszło
        # zgodnie z regułami. To nie jest awaria, tylko decyzja.
        return jsonify({"stan": "pominiety", "powod": w["powod"]}), 200

    kod_szablonu = (d.get("szablon") or "").strip().lower()
    if kod_szablonu:
        sz = store.szablon(s["id"], kod_szablonu)
        if not sz:
            return jsonify({"blad": f"serwis nie ma szablonu '{kod_szablonu}'"}), 404
        temat_zr, tresc_zr = sz["temat"], sz["tresc"]
    else:
        temat_zr, tresc_zr = d.get("temat") or "", d.get("tresc") or ""

    try:
        temat, tresc = szablony.zloz(temat_zr, tresc_zr, d.get("dane") or {})
    except szablony.BrakZmiennej as e:
        return jsonify({"blad": f"szablon wymaga zmiennych, których nie podano: {e}"}), 400
    except ValueError as e:
        return jsonify({"blad": str(e)}), 400

    list_id, nowy = store.zakolejkuj(
        s["id"], do, temat, tresc, kod_szablonu or None,
        (d.get("klucz") or "").strip() or None)

    if d.get("dodaj_kontakt"):
        store.dodaj_kontakt(s["id"], do, (d.get("dane") or {}).get("imie", ""),
                            zrodlo=f"api/{kod_szablonu or 'wysylka'}")

    return jsonify({"id": list_id, "nowy": nowy, "stan": "w kolejce"}), 202


@app.get("/api/stan/<int:list_id>")
@z_kluczem
def api_stan(s, list_id):
    """Stan listu. Filtrowanie po serwisie jest tu istotne: bez niego można by
    poznać treść cudzego maila, zgadując numer."""
    x = store.list_szczegoly(list_id)
    if not x or x["serwis_id"] != s["id"]:
        return jsonify({"blad": "nie ma takiego listu"}), 404
    return jsonify({"id": x["id"], "stan": x["stan"], "do": x["do_email"],
                    "temat": x["temat"], "prob": x["prob"],
                    "przyjeto": x["przyjeto"], "wyslano": x["wyslano"],
                    "ostatni_blad": x["ostatni_blad"]})


@app.post("/api/kontakt")
@z_kluczem
def api_kontakt(s):
    """Dopisanie kontaktu bez wysyłki - do formularzy, które tylko zbierają."""
    d = request.get_json(silent=True) or {}
    do = (d.get("email") or "").strip().lower()
    if not wysylka.poprawny_adres(do):
        return jsonify({"blad": "pole 'email' nie wygląda na adres"}), 400
    store.dodaj_kontakt(s["id"], do, d.get("imie") or "", d.get("tagi") or "",
                        d.get("zrodlo") or "api")
    return jsonify({"stan": "zapisany"}), 201


@app.get("/api/kontakty")
@z_kluczem
def api_kontakty(s):
    return jsonify({"serwis": s["kod"],
                    "kontakty": store.kontakty(s["id"], request.args.get("szukaj", ""))})


# --------------------------------------------------------------------------- #
#  wypisanie - podpisany odnośnik, bez konta i bez logowania
# --------------------------------------------------------------------------- #

def podpis_wypisu(email: str, serwis_id: int) -> str:
    """HMAC zamiast losowego tokenu w bazie: nie ma czego przechowywać ani
    czyścić, a odnośnik i tak nie da się podrobić bez klucza serwera."""
    tresc = f"{serwis_id}:{email}".encode()
    return hmac.new(app.secret_key.encode() if isinstance(app.secret_key, str)
                    else app.secret_key, tresc, sha256).hexdigest()[:32]


@app.get("/wypisz/<int:serwis_id>/<email>/<podpis>")
def wypisz(serwis_id, email, podpis):
    email = email.strip().lower()
    if not hmac.compare_digest(podpis, podpis_wypisu(email, serwis_id)):
        return widok.wypisano("", blad=True), 400
    s = store.serwis(serwis_id)
    if not s:
        return widok.wypisano("", blad=True), 404
    store.wyklucz(email, "wypisany", serwis_id)
    return widok.wypisano(s["nazwa"])


# --------------------------------------------------------------------------- #
#  panel
# --------------------------------------------------------------------------- #

@app.get("/")
@chronione
def glowna(komunikat="", blad=False, klucz_jawny=""):
    wybrany = request.args.get("serwis", type=int)
    lista = store.serwisy()
    if wybrany is None and lista:
        wybrany = lista[0]["id"]
    return widok.panel(
        serwisy=lista, wybrany=wybrany,
        kontakty=store.kontakty(wybrany, request.args.get("szukaj", "")) if wybrany else [],
        szablony_=store.szablony(wybrany) if wybrany else [],
        historia=store.historia(wybrany, request.args.get("stan", "")),
        wykluczenia=store.wykluczenia(wybrany),
        stat=store.statystyki(), nadawca=wysylka.opis(),
        komunikat=komunikat, blad=blad, klucz_jawny=klucz_jawny,
        szukaj=request.args.get("szukaj", ""))


@app.post("/serwis")
@chronione
def serwis_nowy():
    kod = (request.form.get("kod") or "").strip().lower()
    nazwa = (request.form.get("nazwa") or "").strip()
    nadawca = (request.form.get("nadawca_email") or "").strip()
    if not kod or not nazwa or "@" not in nadawca:
        return glowna(komunikat="Podaj kod, nazwę i poprawny adres nadawcy", blad=True)
    if store.serwis_po_kodzie(kod):
        return glowna(komunikat=f"Serwis o kodzie '{kod}' już istnieje", blad=True)
    sid = store.dodaj_serwis(kod, nazwa, nadawca,
                             request.form.get("nadawca_nazwa") or "",
                             request.form.get("odpowiedz_do") or "")
    klucz = store.wydaj_klucz(sid)
    return glowna(komunikat=f"Dodano serwis „{nazwa}”. Zapisz klucz teraz — "
                            f"drugi raz go nie pokażę.", klucz_jawny=klucz)


@app.post("/serwis/<int:sid>/klucz")
@chronione
def serwis_klucz(sid):
    s = store.serwis(sid)
    if not s:
        return glowna(komunikat="Nie ma takiego serwisu", blad=True)
    klucz = store.wydaj_klucz(sid)
    return glowna(komunikat=f"Nowy klucz dla „{s['nazwa']}”. Poprzedni przestał "
                            f"działać w tej sekundzie.", klucz_jawny=klucz)


@app.post("/serwis/<int:sid>/zmien")
@chronione
def serwis_zmien(sid):
    store.zmien_serwis(
        sid, nazwa=(request.form.get("nazwa") or "").strip(),
        nadawca_email=(request.form.get("nadawca_email") or "").strip(),
        nadawca_nazwa=(request.form.get("nadawca_nazwa") or "").strip(),
        odpowiedz_do=(request.form.get("odpowiedz_do") or "").strip() or None,
        aktywny=1 if request.form.get("aktywny") else 0)
    return glowna(komunikat="Zapisano ustawienia serwisu")


@app.post("/serwis/<int:sid>/kontakt")
@chronione
def kontakt_nowy(sid):
    email = (request.form.get("email") or "").strip().lower()
    if not wysylka.poprawny_adres(email):
        return glowna(komunikat="To nie wygląda na adres e-mail", blad=True)
    store.dodaj_kontakt(sid, email, request.form.get("imie") or "",
                        request.form.get("tagi") or "", "ręcznie")
    return glowna(komunikat=f"Dodano {email}")


@app.post("/serwis/<int:sid>/kontakt/usun")
@chronione
def kontakt_usun(sid):
    store.usun_kontakt(sid, request.form.get("email") or "")
    return glowna(komunikat="Usunięto kontakt")


@app.post("/serwis/<int:sid>/szablon")
@chronione
def szablon_zapisz(sid):
    kod = (request.form.get("kod") or "").strip().lower()
    temat = request.form.get("temat") or ""
    tresc = request.form.get("tresc") or ""
    if not kod or not temat or not tresc:
        return glowna(komunikat="Szablon potrzebuje kodu, tematu i treści", blad=True)
    store.zapisz_szablon(sid, kod, temat, tresc)
    braki = sorted(szablony.zmienne(temat) | szablony.zmienne(tresc))
    dopisek = f" Zmienne do podania przy wysyłce: {', '.join(braki)}." if braki else ""
    return glowna(komunikat=f"Zapisano szablon „{kod}”.{dopisek}")


@app.post("/serwis/<int:sid>/szablon/usun")
@chronione
def szablon_usun(sid):
    store.usun_szablon(sid, request.form.get("kod") or "")
    return glowna(komunikat="Usunięto szablon")


@app.post("/wykluczenie")
@chronione
def wykluczenie_dodaj():
    email = (request.form.get("email") or "").strip().lower()
    sid = request.form.get("serwis_id", type=int)
    if not wysylka.poprawny_adres(email):
        return glowna(komunikat="To nie wygląda na adres e-mail", blad=True)
    store.wyklucz(email, request.form.get("powod") or "ręcznie", sid or None)
    zasieg = "wszystkich serwisów" if not sid else "tego serwisu"
    return glowna(komunikat=f"{email} nie dostanie już poczty z {zasieg}")


@app.post("/wykluczenie/usun")
@chronione
def wykluczenie_usun():
    store.odwolaj_wykluczenie(request.form.get("email") or "",
                              request.form.get("serwis_id", type=int) or None)
    return glowna(komunikat="Odwołano wykluczenie")


@app.post("/zapomnij")
@chronione
def zapomnij():
    email = (request.form.get("email") or "").strip().lower()
    if not wysylka.poprawny_adres(email):
        return glowna(komunikat="To nie wygląda na adres e-mail", blad=True)
    n = store.zapomnij(email)
    return glowna(komunikat=f"Usunięto {email} z {n} "
                            f"{'serwisu' if n == 1 else 'serwisów'} wraz z treścią "
                            f"listów. Wykluczenie zostaje, żeby adres nie wrócił "
                            f"przy kolejnym zgłoszeniu formularza.")


@app.post("/przebieg")
@chronione
def przebieg_recznie():
    w = kolejka.przebieg(PACZKA)
    return glowna(komunikat=f"Przebieg: {kolejka.opis_przebiegu(w)}")


@app.post("/ponow/<int:list_id>")
@chronione
def ponow(list_id):
    with store.polacz() as con:
        con.execute("UPDATE kolejka SET stan='czeka', prob=0, nastepna_proba=?"
                    " WHERE id=? AND stan='przepadl'", (store._teraz(), list_id))
    return glowna(komunikat=f"List #{list_id} wraca do kolejki")


# --------------------------------------------------------------------------- #
#  harmonogram
# --------------------------------------------------------------------------- #

def _harmonogram():
    h = BackgroundScheduler(timezone=os.environ.get("TZ", "Europe/Warsaw"))
    h.add_job(lambda: app.logger.info("przebieg: %s",
                                      kolejka.opis_przebiegu(kolejka.przebieg(PACZKA))),
              "interval", seconds=CO_SEKUND, id="wysylka",
              max_instances=1, coalesce=True)
    h.start()
    return h


if os.environ.get("HARMONOGRAM", "1") == "1":
    _harmonogram()
