"""Baza usługi pocztowej.

ZASADA NADRZĘDNA TEGO PLIKU: izolacja serwisów jest wymuszona strukturalnie,
nie przez konwencję. Każda funkcja czytająca albo pisząca dane należące do
serwisu przyjmuje `serwis_id` i filtruje po nim w zapytaniu SQL. Nie ma
funkcji „pobierz wszystkie kontakty" bez tego argumentu, bo taka funkcja
prędzej czy później zostałaby użyta w miejscu, gdzie serwis powinien widzieć
tylko swoje. Kontakty z alphaolsztyn.pl i z ochronazklasa.pl mają się nie
mieszać nawet przez pomyłkę programisty.

KLUCZE API TRZYMAMY JAKO SKRÓTY, nigdy jawnie. Klucz pokazujemy raz, w chwili
utworzenia. Gdyby baza wyciekła, znajdujące się w niej skróty nie pozwalają
wysłać ani jednego maila. To ta sama zasada, co przy hasłach - z tą różnicą,
że tutaj sekret generuje maszyna, więc nie ma pokusy, żeby był słaby.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

KATALOG = Path(os.environ.get("POCZTA_DANE", "/dane"))
PLIK = KATALOG / "poczta.db"

# Ile razy próbujemy wysłać, zanim uznamy list za przepadły. Odstępy rosną
# wykładniczo, bo typowa awaria SMTP to albo chwilowy limit nadawcy, albo
# krótka niedostępność serwera - jedno i drugie mija w minutach.
PROBY = 5
ODSTEPY_MIN = (1, 5, 15, 60, 240)


def _teraz() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def polacz():
    KATALOG.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(PLIK, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def zainicjuj() -> None:
    with polacz() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS serwisy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT NOT NULL UNIQUE,          -- 'ochrona', 'alpha', 'portfel'
            nazwa TEXT NOT NULL,
            nadawca_email TEXT NOT NULL,       -- w polu From tego serwisu
            nadawca_nazwa TEXT NOT NULL DEFAULT '',
            odpowiedz_do TEXT,                 -- Reply-To, gdy inny niż nadawca
            klucz_skrot TEXT,                  -- skrót klucza API, nigdy jawny
            klucz_koncowka TEXT,               -- 4 znaki do rozpoznania w panelu
            klucz_wydany TEXT,
            aktywny INTEGER NOT NULL DEFAULT 1,
            utworzono TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kontakty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serwis_id INTEGER NOT NULL REFERENCES serwisy(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            imie TEXT DEFAULT '',
            tagi TEXT DEFAULT '',
            zrodlo TEXT DEFAULT '',            -- skąd się wziął: formularz, ręcznie, import
            dodano TEXT NOT NULL,
            ostatnia_wysylka TEXT,
            UNIQUE(serwis_id, email)           -- ten sam adres w dwóch serwisach to dwa wpisy
        );
        CREATE TABLE IF NOT EXISTS szablony (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serwis_id INTEGER NOT NULL REFERENCES serwisy(id) ON DELETE CASCADE,
            kod TEXT NOT NULL,                 -- 'potwierdzenie-zgloszenia'
            temat TEXT NOT NULL,
            tresc TEXT NOT NULL,
            zmieniono TEXT NOT NULL,
            UNIQUE(serwis_id, kod)
        );
        CREATE TABLE IF NOT EXISTS kolejka (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serwis_id INTEGER NOT NULL REFERENCES serwisy(id) ON DELETE CASCADE,
            do_email TEXT NOT NULL,
            temat TEXT NOT NULL,
            tresc TEXT NOT NULL,
            tresc_html TEXT,                   -- wersja HTML, gdy nadawca ją podał
            odpowiedz_do TEXT,                 -- Reply-To dla tej jednej wiadomości
            zalaczniki TEXT,                   -- JSON: [{nazwa, typ, dane_b64}]
            szablon TEXT,
            klucz_idem TEXT,                   -- ochrona przed podwójną wysyłką
            stan TEXT NOT NULL DEFAULT 'czeka',-- czeka | wyslany | przepadl
            prob INTEGER NOT NULL DEFAULT 0,
            nastepna_proba TEXT NOT NULL,
            ostatni_blad TEXT,
            przyjeto TEXT NOT NULL,
            wyslano TEXT,
            UNIQUE(serwis_id, klucz_idem)
        );
        CREATE TABLE IF NOT EXISTS proby (      -- pełny ślad, także nieudanych
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL REFERENCES kolejka(id) ON DELETE CASCADE,
            kiedy TEXT NOT NULL,
            ok INTEGER NOT NULL,
            opis TEXT
        );
        CREATE TABLE IF NOT EXISTS wykluczenia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            serwis_id INTEGER REFERENCES serwisy(id) ON DELETE CASCADE,
            powod TEXT NOT NULL,               -- 'odbity' | 'wypisany' | 'recznie'
            kiedy TEXT NOT NULL,
            UNIQUE(email, serwis_id)
        );
        CREATE INDEX IF NOT EXISTS idx_kolejka_stan ON kolejka(stan, nastepna_proba);
        CREATE INDEX IF NOT EXISTS idx_kolejka_serwis ON kolejka(serwis_id, przyjeto DESC);
        CREATE INDEX IF NOT EXISTS idx_kontakty_serwis ON kontakty(serwis_id, email);
        """)
        # CREATE TABLE IF NOT EXISTS obejmuje tylko NOWE bazy - działająca
        # produkcja ma tabelę bez tych kolumn i dostałaby „no such column"
        # przy pierwszej wysyłce z załącznikiem.
        kolumny = {w["name"] for w in con.execute("PRAGMA table_info(kolejka)")}
        for nazwa in ("tresc_html", "zalaczniki", "odpowiedz_do"):
            if nazwa not in kolumny:
                con.execute(f"ALTER TABLE kolejka ADD COLUMN {nazwa} TEXT")


# --------------------------------------------------------------------------- #
#  serwisy i klucze
# --------------------------------------------------------------------------- #

def _skrot(klucz: str) -> str:
    """SHA-256 wystarcza, bo klucz ma 32 bajty losowości z generatora
    kryptograficznego. Powolne funkcje haszujące chronią przed atakiem
    słownikowym na sekret WYBRANY PRZEZ CZŁOWIEKA - tutaj nie ma czego
    zgadywać."""
    return hashlib.sha256(klucz.encode()).hexdigest()


def dodaj_serwis(kod: str, nazwa: str, nadawca_email: str,
                 nadawca_nazwa: str = "", odpowiedz_do: str = "") -> int:
    with polacz() as con:
        kur = con.execute(
            "INSERT INTO serwisy (kod, nazwa, nadawca_email, nadawca_nazwa,"
            " odpowiedz_do, utworzono) VALUES (?,?,?,?,?,?)",
            (kod.strip().lower(), nazwa.strip(), nadawca_email.strip(),
             nadawca_nazwa.strip(), odpowiedz_do.strip() or None, _teraz()))
        return int(kur.lastrowid)


def wydaj_klucz(serwis_id: int) -> str:
    """Nowy klucz API. Zwracany RAZ - w bazie zostaje tylko skrót.

    Wydanie nowego unieważnia poprzedni, bo serwis ma dokładnie jeden klucz.
    Dwa równoległe klucze brzmią wygodnie przy rotacji, ale wtedy odebranie
    dostępu przestaje być jedną operacją i nigdy nie wiadomo, ile kluczy
    jeszcze żyje."""
    klucz = "pk_" + secrets.token_urlsafe(32)
    with polacz() as con:
        con.execute(
            "UPDATE serwisy SET klucz_skrot=?, klucz_koncowka=?, klucz_wydany=?"
            " WHERE id=?", (_skrot(klucz), klucz[-4:], _teraz(), serwis_id))
    return klucz


def serwis_po_kluczu(klucz: str) -> dict | None:
    """Rozpoznanie serwisu po kluczu API. To jest jedyne wejście do danych
    z zewnątrz i jedyne miejsce, gdzie ustala się, czyje one są."""
    if not klucz or not klucz.startswith("pk_"):
        return None
    with polacz() as con:
        w = con.execute(
            "SELECT * FROM serwisy WHERE klucz_skrot=? AND aktywny=1",
            (_skrot(klucz),)).fetchone()
        return dict(w) if w else None


def serwis(serwis_id: int) -> dict | None:
    with polacz() as con:
        w = con.execute("SELECT * FROM serwisy WHERE id=?", (serwis_id,)).fetchone()
        return dict(w) if w else None


def serwis_po_kodzie(kod: str) -> dict | None:
    with polacz() as con:
        w = con.execute("SELECT * FROM serwisy WHERE kod=?", (kod.strip().lower(),)).fetchone()
        return dict(w) if w else None


def serwisy() -> list[dict]:
    with polacz() as con:
        return [dict(w) for w in con.execute(
            "SELECT s.*,"
            " (SELECT COUNT(*) FROM kontakty k WHERE k.serwis_id=s.id) AS kontaktow,"
            " (SELECT COUNT(*) FROM kolejka q WHERE q.serwis_id=s.id"
            "    AND q.stan='wyslany') AS wyslanych,"
            " (SELECT COUNT(*) FROM kolejka q WHERE q.serwis_id=s.id"
            "    AND q.stan='przepadl') AS przepadlych"
            " FROM serwisy s ORDER BY s.nazwa")]


def zmien_serwis(serwis_id: int, **pola) -> None:
    dozwolone = {"nazwa", "nadawca_email", "nadawca_nazwa", "odpowiedz_do", "aktywny"}
    ustaw = {k: v for k, v in pola.items() if k in dozwolone}
    if not ustaw:
        return
    with polacz() as con:
        con.execute(f"UPDATE serwisy SET {', '.join(f'{k}=?' for k in ustaw)} WHERE id=?",
                    (*ustaw.values(), serwis_id))


# --------------------------------------------------------------------------- #
#  kontakty - zawsze w obrębie jednego serwisu
# --------------------------------------------------------------------------- #

def dodaj_kontakt(serwis_id: int, email: str, imie: str = "", tagi: str = "",
                  zrodlo: str = "ręcznie") -> None:
    """Ponowne dodanie tego samego adresu aktualizuje dane zamiast wybuchać:
    formularz przysyła kontakt przy każdym zgłoszeniu i to normalne."""
    email = (email or "").strip().lower()
    if not email:
        return
    with polacz() as con:
        con.execute(
            "INSERT INTO kontakty (serwis_id, email, imie, tagi, zrodlo, dodano)"
            " VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(serwis_id, email) DO UPDATE SET"
            "   imie=COALESCE(NULLIF(excluded.imie,''), kontakty.imie),"
            "   tagi=COALESCE(NULLIF(excluded.tagi,''), kontakty.tagi)",
            (serwis_id, email, imie.strip(), tagi.strip(), zrodlo, _teraz()))


def kontakty(serwis_id: int, szukaj: str = "", limit: int = 500) -> list[dict]:
    with polacz() as con:
        if szukaj:
            wz = f"%{szukaj.strip().lower()}%"
            w = con.execute(
                "SELECT * FROM kontakty WHERE serwis_id=?"
                " AND (LOWER(email) LIKE ? OR LOWER(imie) LIKE ? OR LOWER(tagi) LIKE ?)"
                " ORDER BY dodano DESC LIMIT ?", (serwis_id, wz, wz, wz, limit))
        else:
            w = con.execute(
                "SELECT * FROM kontakty WHERE serwis_id=? ORDER BY dodano DESC LIMIT ?",
                (serwis_id, limit))
        return [dict(x) for x in w]


def usun_kontakt(serwis_id: int, email: str) -> None:
    with polacz() as con:
        con.execute("DELETE FROM kontakty WHERE serwis_id=? AND email=?",
                    (serwis_id, (email or "").strip().lower()))


# --------------------------------------------------------------------------- #
#  wykluczenia
# --------------------------------------------------------------------------- #

def wyklucz(email: str, powod: str, serwis_id: int | None = None) -> None:
    """Wykluczenie ma ZASIĘG. Twardy odbój znaczy, że adres nie istnieje,
    więc obowiązuje wszędzie (serwis_id = NULL). Wypisanie się z powiadomień
    jednej usługi nie może uciszyć potwierdzeń z drugiej - to byłoby
    zaskakujące i w części przypadków szkodliwe."""
    with polacz() as con:
        con.execute(
            "INSERT INTO wykluczenia (email, serwis_id, powod, kiedy) VALUES (?,?,?,?)"
            " ON CONFLICT(email, serwis_id) DO UPDATE SET powod=excluded.powod,"
            " kiedy=excluded.kiedy",
            ((email or "").strip().lower(), serwis_id, powod, _teraz()))


def wykluczony(email: str, serwis_id: int) -> dict | None:
    with polacz() as con:
        w = con.execute(
            "SELECT * FROM wykluczenia WHERE email=? AND (serwis_id IS NULL OR serwis_id=?)"
            " ORDER BY serwis_id IS NOT NULL LIMIT 1",
            ((email or "").strip().lower(), serwis_id)).fetchone()
        return dict(w) if w else None


def wykluczenia(serwis_id: int | None = None) -> list[dict]:
    with polacz() as con:
        if serwis_id is None:
            w = con.execute("SELECT * FROM wykluczenia ORDER BY kiedy DESC LIMIT 500")
        else:
            w = con.execute(
                "SELECT * FROM wykluczenia WHERE serwis_id IS NULL OR serwis_id=?"
                " ORDER BY kiedy DESC LIMIT 500", (serwis_id,))
        return [dict(x) for x in w]


def odwolaj_wykluczenie(email: str, serwis_id: int | None) -> None:
    with polacz() as con:
        if serwis_id is None:
            con.execute("DELETE FROM wykluczenia WHERE email=? AND serwis_id IS NULL",
                        ((email or "").strip().lower(),))
        else:
            con.execute("DELETE FROM wykluczenia WHERE email=? AND serwis_id=?",
                        ((email or "").strip().lower(), serwis_id))


# --------------------------------------------------------------------------- #
#  szablony
# --------------------------------------------------------------------------- #

def zapisz_szablon(serwis_id: int, kod: str, temat: str, tresc: str) -> None:
    with polacz() as con:
        con.execute(
            "INSERT INTO szablony (serwis_id, kod, temat, tresc, zmieniono)"
            " VALUES (?,?,?,?,?)"
            " ON CONFLICT(serwis_id, kod) DO UPDATE SET temat=excluded.temat,"
            " tresc=excluded.tresc, zmieniono=excluded.zmieniono",
            (serwis_id, kod.strip().lower(), temat, tresc, _teraz()))


def szablon(serwis_id: int, kod: str) -> dict | None:
    with polacz() as con:
        w = con.execute("SELECT * FROM szablony WHERE serwis_id=? AND kod=?",
                        (serwis_id, (kod or "").strip().lower())).fetchone()
        return dict(w) if w else None


def szablony(serwis_id: int) -> list[dict]:
    with polacz() as con:
        return [dict(x) for x in con.execute(
            "SELECT * FROM szablony WHERE serwis_id=? ORDER BY kod", (serwis_id,))]


def usun_szablon(serwis_id: int, kod: str) -> None:
    with polacz() as con:
        con.execute("DELETE FROM szablony WHERE serwis_id=? AND kod=?",
                    (serwis_id, (kod or "").strip().lower()))


# --------------------------------------------------------------------------- #
#  kolejka
# --------------------------------------------------------------------------- #

def zakolejkuj(serwis_id: int, do_email: str, temat: str, tresc: str,
               szablon_kod: str | None = None,
               klucz_idem: str | None = None,
               tresc_html: str | None = None,
               zalaczniki: list[dict] | None = None,
               odpowiedz_do: str | None = None) -> tuple[int, bool]:
    """Wrzuca list do kolejki. Zwraca (id, czy_nowy).

    Idempotencja jest tu warunkiem bezpieczeństwa, nie wygodą: aplikacja,
    która dostała timeout, ponowi żądanie i bez tego wysłałaby drugie
    potwierdzenie tej samej osobie. Klucz jest w obrębie serwisu, więc dwie
    aplikacje nie zablokują się nawzajem przypadkową zbieżnością."""
    with polacz() as con:
        if klucz_idem:
            w = con.execute("SELECT id FROM kolejka WHERE serwis_id=? AND klucz_idem=?",
                            (serwis_id, klucz_idem)).fetchone()
            if w:
                return int(w["id"]), False
        kur = con.execute(
            "INSERT INTO kolejka (serwis_id, do_email, temat, tresc, tresc_html,"
            " zalaczniki, odpowiedz_do, szablon, klucz_idem, nastepna_proba, przyjeto)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (serwis_id, do_email.strip().lower(), temat, tresc, tresc_html or None,
             json.dumps(zalaczniki, ensure_ascii=False) if zalaczniki else None,
             odpowiedz_do or None, szablon_kod, klucz_idem, _teraz(), _teraz()))
        return int(kur.lastrowid), True


def do_wyslania(ile: int = 20) -> list[dict]:
    with polacz() as con:
        return [dict(x) for x in con.execute(
            "SELECT * FROM kolejka WHERE stan='czeka' AND nastepna_proba<=?"
            " ORDER BY przyjeto LIMIT ?", (_teraz(), ile))]


def oznacz_wyslany(list_id: int, opis: str = "") -> None:
    with polacz() as con:
        con.execute("UPDATE kolejka SET stan='wyslany', wyslano=?, prob=prob+1,"
                    " ostatni_blad=NULL WHERE id=?", (_teraz(), list_id))
        con.execute("INSERT INTO proby (list_id, kiedy, ok, opis) VALUES (?,?,1,?)",
                    (list_id, _teraz(), opis))
        con.execute(
            "UPDATE kontakty SET ostatnia_wysylka=? WHERE serwis_id="
            "(SELECT serwis_id FROM kolejka WHERE id=?) AND email="
            "(SELECT do_email FROM kolejka WHERE id=?)", (_teraz(), list_id, list_id))


def oznacz_blad(list_id: int, blad: str, trwaly: bool = False) -> None:
    """Błąd trwały (adres nie istnieje) nie ma sensu ponawiać - piąta próba
    dostarczenia na nieistniejącą skrzynkę psuje reputację nadawcy i nic
    nie daje. Błąd chwilowy ponawiamy z rosnącym odstępem."""
    with polacz() as con:
        w = con.execute("SELECT prob FROM kolejka WHERE id=?", (list_id,)).fetchone()
        prob = (w["prob"] if w else 0) + 1
        koniec = trwaly or prob >= PROBY
        odstep = ODSTEPY_MIN[min(prob, len(ODSTEPY_MIN)) - 1]
        nast = (datetime.now(timezone.utc) + timedelta(minutes=odstep)).isoformat(timespec="seconds")
        con.execute(
            "UPDATE kolejka SET stan=?, prob=?, ostatni_blad=?, nastepna_proba=? WHERE id=?",
            ("przepadl" if koniec else "czeka", prob, blad[:500], nast, list_id))
        con.execute("INSERT INTO proby (list_id, kiedy, ok, opis) VALUES (?,?,0,?)",
                    (list_id, _teraz(), blad[:500]))


def historia(serwis_id: int | None = None, stan: str = "", limit: int = 200) -> list[dict]:
    warunki, param = [], []
    if serwis_id is not None:
        warunki.append("k.serwis_id=?")
        param.append(serwis_id)
    if stan:
        warunki.append("k.stan=?")
        param.append(stan)
    gdzie = ("WHERE " + " AND ".join(warunki)) if warunki else ""
    with polacz() as con:
        return [dict(x) for x in con.execute(
            f"SELECT k.*, s.kod AS serwis_kod, s.nazwa AS serwis_nazwa"
            f" FROM kolejka k JOIN serwisy s ON s.id=k.serwis_id {gdzie}"
            f" ORDER BY k.przyjeto DESC LIMIT ?", (*param, limit))]


def list_szczegoly(list_id: int) -> dict | None:
    with polacz() as con:
        w = con.execute(
            "SELECT k.*, s.kod AS serwis_kod, s.nazwa AS serwis_nazwa,"
            " s.nadawca_email FROM kolejka k JOIN serwisy s ON s.id=k.serwis_id"
            " WHERE k.id=?", (list_id,)).fetchone()
        if not w:
            return None
        d = dict(w)
        d["proby"] = [dict(x) for x in con.execute(
            "SELECT * FROM proby WHERE list_id=? ORDER BY kiedy", (list_id,))]
        return d


def statystyki() -> dict:
    with polacz() as con:
        w = con.execute(
            "SELECT stan, COUNT(*) AS ile FROM kolejka GROUP BY stan").fetchall()
        wg = {x["stan"]: x["ile"] for x in w}
        doba = con.execute(
            "SELECT COUNT(*) AS ile FROM kolejka WHERE wyslano>=?",
            ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds"),)
        ).fetchone()["ile"]
        return {"czeka": wg.get("czeka", 0), "wyslany": wg.get("wyslany", 0),
                "przepadl": wg.get("przepadl", 0), "doba": doba}


def zapomnij(email: str) -> int:
    """Usuwa osobę ze WSZYSTKICH serwisów wraz z treścią listów.

    Potrzebne do realizacji prawa do bycia zapomnianym. Wykluczenie zostaje
    celowo: bez niego ten sam adres wróciłby do bazy przy pierwszym kolejnym
    zgłoszeniu formularza i żądanie usunięcia zostałoby cicho cofnięte."""
    email = (email or "").strip().lower()
    with polacz() as con:
        n = con.execute("DELETE FROM kontakty WHERE email=?", (email,)).rowcount
        con.execute("UPDATE kolejka SET tresc='[usunięto na żądanie]', temat='[usunięto]'"
                    " WHERE do_email=?", (email,))
    wyklucz(email, "zapomniany")
    return n
