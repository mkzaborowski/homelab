#!/usr/bin/env python3
"""Diagnostyka wysyłki przez Microsoft Graph, krok po kroku.

PO CO TO ISTNIEJE. Rejestracja aplikacji w Entra ma cztery miejsca, w których
można się pomylić, a każde daje ten sam nieczytelny objaw: HTTP 401 albo 403
z kodem w rodzaju AADSTS7000215. Z samego kodu nie widać, czy zła jest
dzierżawa, klucz, sekret, czy po prostu nikt nie kliknął „Udziel zgody
administratora".

Ten skrypt przechodzi te kroki po kolei i mówi, który padł i co z tym zrobić.
Uruchamiany bez argumentów sprawdza konfigurację; z adresem e-mail wysyła
pod niego list próbny.

    python sprawdz_graph.py
    python sprawdz_graph.py ktos@example.com
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import store
import wysylka

# Kody z Entra tłumaczą się na konkretne kliknięcia w portalu. Bez tej mapy
# komunikat „AADSTS7000215" nie mówi nic nikomu poza autorem Azure.
PODPOWIEDZI = {
    "AADSTS90002": "zła DZIERŻAWA - sprawdź GRAPH_DZIERZAWA (Identyfikator katalogu)",
    "AADSTS700016": "aplikacja o tym identyfikatorze nie istnieje w tej dzierżawie "
                    "- sprawdź GRAPH_KLIENT (Identyfikator aplikacji)",
    "AADSTS7000215": "zły SEKRET - sprawdź GRAPH_SEKRET (wartość klucza tajnego, "
                     "nie jego identyfikator)",
    "AADSTS7000222": "sekret WYGASŁ - wygeneruj nowy w Certyfikaty i klucze tajne",
    "AADSTS500011": "nie ma takiej aplikacji w dzierżawie albo brak zgody administratora",
}


def _role_z_tokenu(token: str) -> list[str] | None:
    """Uprawnienia aplikacyjne z ładunku tokenu JWT.

    Bez weryfikacji podpisu i to jest w porządku: token dostaliśmy przed chwilą
    od Microsoftu po TLS, a odczyt służy diagnostyce, nie podejmowaniu decyzji
    o dostępie. Decyzję i tak podejmuje Graph przy wywołaniu."""
    try:
        ladunek = token.split(".")[1]
        ladunek += "=" * (-len(ladunek) % 4)          # base64url bez dopełnienia
        dane = json.loads(base64.urlsafe_b64decode(ladunek))
    except (ValueError, IndexError, TypeError):
        return None
    role = dane.get("roles")
    return list(role) if isinstance(role, list) else []


def _krok(nr: int, opis: str) -> None:
    print(f"\n[{nr}] {opis}")


def _ok(tekst: str) -> None:
    print(f"    OK   {tekst}")


def _zle(tekst: str) -> None:
    print(f"    BŁĄD {tekst}")


def _rada(tekst: str) -> None:
    print(f"    → {tekst}")


def sprawdz(adres_probny: str = "") -> int:
    print("Diagnostyka wysyłki przez Microsoft Graph")

    _krok(1, "Zmienne środowiskowe")
    braki = [n for n, v in (("GRAPH_DZIERZAWA", wysylka.GRAPH_DZIERZAWA),
                            ("GRAPH_KLIENT", wysylka.GRAPH_KLIENT),
                            ("GRAPH_SEKRET", wysylka.GRAPH_SEKRET),
                            ("GRAPH_SKRZYNKA", wysylka.GRAPH_SKRZYNKA)) if not v]
    if braki:
        _zle("brakuje: " + ", ".join(braki))
        _rada("uzupełnij /opt/poczta/.env i zrestartuj: docker compose up -d")
        return 1
    _ok(f"komplet, skrzynka {wysylka.GRAPH_SKRZYNKA}")

    _krok(2, "Token aplikacji (czy dzierżawa, klucz i sekret się zgadzają)")
    d = wysylka.GraphOAuth()
    try:
        token = d._pobierz_token()
        _ok(f"token wydany, {len(token)} znaków")
    except Exception as e:                                      # noqa: BLE001
        tresc = str(e)
        _zle(tresc[:220])
        for kod, rada in PODPOWIEDZI.items():
            if kod in tresc:
                _rada(rada)
                break
        else:
            _rada("sprawdź GRAPH_DZIERZAWA, GRAPH_KLIENT i GRAPH_SEKRET")
        return 1

    _krok(3, "Uprawnienie Mail.Send (czy administrator udzielił zgody)")
    # Czytamy uprawnienia PROSTO Z TOKENU, a nie próbnym wywołaniem Graph.
    #
    # Pierwsza wersja pytała o obiekt użytkownika (GET /users/...) i to był
    # błąd: odczyt katalogu wymaga User.Read.All, czyli zupełnie innego
    # uprawnienia niż Mail.Send. Diagnostyka pokazywałaby „brak zgody" nawet
    # przy poprawnie nadanym Mail.Send i wysyłałaby w pogoń za duchem.
    #
    # Token to JWT, a lista nadanych uprawnień aplikacyjnych siedzi w polu
    # `roles`. Nie weryfikujemy podpisu - to nie jest kontrola dostępu, tylko
    # odczyt tego, co Microsoft właśnie nam wydał.
    role = _role_z_tokenu(token)
    if role is None:
        _zle("nie udało się odczytać zawartości tokenu")
        return 1
    if "Mail.Send" in role:
        _ok("Mail.Send nadane i zatwierdzone" + (f" (razem z: {', '.join(sorted(set(role) - {'Mail.Send'}))})"
                                                 if len(set(role)) > 1 else ""))
    else:
        _zle("token nie zawiera uprawnienia Mail.Send"
             + (f" (ma: {', '.join(role)})" if role else " (nie ma żadnych uprawnień aplikacyjnych)"))
        _rada("Uprawnienia interfejsu API → Dodaj uprawnienie → Microsoft Graph")
        _rada("→ Uprawnienia APLIKACJI (nie delegowane) → Mail.Send → Dodaj")
        _rada("→ potem „Udziel zgody administratora dla <organizacja>”")
        _rada("gdyby przycisk był nieaktywny, otwórz jednorazowy adres zgody:")
        _rada(f"   https://login.microsoftonline.com/{wysylka.GRAPH_DZIERZAWA}"
              f"/adminconsent?client_id={wysylka.GRAPH_KLIENT}")
        return 1

    _krok(4, "Nadawcy serwisów (Graph odrzuci list z cudzego adresu)")
    skrzynka = wysylka.GRAPH_SKRZYNKA.strip().lower()
    niezgodni = [s for s in store.serwisy()
                 if (s["nadawca_email"] or "").strip().lower() != skrzynka]
    if niezgodni:
        for s in niezgodni:
            _zle(f'{s["kod"]}: nadawca {s["nadawca_email"]} ≠ {wysylka.GRAPH_SKRZYNKA}')
        _rada("popraw nadawcę w panelu albo dodaj te adresy jako aliasy skrzynki")
    else:
        _ok(f"wszystkie {len(store.serwisy())} serwisy wysyłają jako {wysylka.GRAPH_SKRZYNKA}")

    if not adres_probny:
        print("\nKonfiguracja wygląda poprawnie.")
        print("List próbny:  python sprawdz_graph.py twoj@adres.pl")
        return 0

    _krok(5, f"List próbny na {adres_probny}")
    w = wysylka.zbuduj(wysylka.GRAPH_SKRZYNKA, "Usługa pocztowa", adres_probny,
                       "Próba wysyłki przez Microsoft Graph",
                       "Jeśli to czytasz, wysyłka przez Graph działa.\n\n"
                       "Wiadomość wygenerowana przez sprawdz_graph.py.")
    try:
        opis = d.wyslij(w)
        _ok(f"przyjęte przez {opis}")
        print("\nSprawdź skrzynkę. Jeśli list doszedł, poczta jest gotowa.")
        return 0
    except Exception as e:                                      # noqa: BLE001
        _zle(str(e)[:300])
        return 1


if __name__ == "__main__":
    store.zainicjuj()
    raise SystemExit(sprawdz(sys.argv[1] if len(sys.argv) > 1 else ""))
