"""Wypychanie danych do Google Sheets (opcjonalne).

Wymaga konta serwisowego Google i udostępnienia arkusza jego adresowi e-mail.
Bez konfiguracji moduł po prostu nic nie robi - Excel na serwerze działa dalej.
"""
from __future__ import annotations

import os
from pathlib import Path

PLIK_KONTA = os.environ.get("GOOGLE_SA_JSON", "/dane/google-sa.json")
ID_ARKUSZA = os.environ.get("GOOGLE_SHEET_ID", "")


def skonfigurowane() -> bool:
    return bool(ID_ARKUSZA) and Path(PLIK_KONTA).exists()


def _naglowki() -> list[str]:
    return ["% portfela", "Koszyk", "Spółka", "Ticker", "Ocena", "Akcje",
            "Pozycja startowa", "Pozycja bieżąca", "Cena wejścia", "Zmiana dzienna %",
            "Cena bieżąca", "Stop", "% zysk/strata", "Zysk/strata", "Do stopu %", "Covered call"]


def _wiersze(pods: dict) -> list[list]:
    from raport_excel import _opis_cc
    cc = pods["covered_calls"]
    w = [[f"Portfel — {pods['kwartal']}", f"stan na {pods['data']}", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
         [f"NAV: {pods['nav']:,.2f}", f"Gotówka: {pods['gotowka']:,.2f}",
          f"Wynik: {pods['zysk']:,.2f} ({pods['zysk_proc']:.2f}%)", "", "", "", "", "", "", "", "", "", "", "", "", ""],
         [], _naglowki()]

    for k in pods["koszyki"]:
        w.append([f"{k['udzial']:.2f}%", k["koszyk"], "", "", "", "", round(k["koszt"], 2),
                  round(k["wartosc"], 2), "", "", "", "", f"{k['zysk_proc']:.2f}%", round(k["zysk"], 2), "", ""])
        for t in k["tickery"]:
            w.append([f"{t['udzial']:.2f}%", "", (t["opis"] or t["symbol"]) + " *", t["symbol"], t["ocena"],
                      t["ilosc"], round(t["koszt"], 2), round(t["wartosc"], 2), round(t["cena_kosztu"], 2),
                      f"{t['zmiana_dzienna']:.2f}%" if t["zmiana_dzienna"] is not None else "",
                      round(t["cena"], 2), "", f"{t['zysk_proc']:.2f}%", round(t["zysk"], 2), "",
                      _opis_cc(t["symbol"], cc)])
            for lot in t["loty"]:
                w.append(["", "", "   " + (lot.get("opis") or ""), lot.get("symbol", ""), "",
                          lot.get("ilosc", 0), round(lot.get("koszt", 0), 2), round(lot.get("wartosc", 0), 2),
                          round(lot.get("cena_kosztu", 0), 2), "", round(lot.get("cena", 0), 2),
                          lot.get("stop") or "", f"{lot.get('zysk_proc', 0):.2f}%", round(lot.get("zysk", 0), 2),
                          f"{lot['do_stopu_proc']:.2f}%" if lot.get("do_stopu_proc") is not None else "", ""])
        w.append([])
    return w


def wypchnij(pods: dict) -> str:
    """Nadpisuje zakładkę bieżącego kwartału. Zwraca komunikat."""
    if not skonfigurowane():
        return "Google Sheets nieskonfigurowane - pominięto"
    import gspread
    from google.oauth2.service_account import Credentials

    cred = Credentials.from_service_account_file(
        PLIK_KONTA, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(cred)
    ark = gc.open_by_key(ID_ARKUSZA)

    tytul = pods["kwartal"]
    dane = _wiersze(pods)
    try:
        zakladka = ark.worksheet(tytul)
        zakladka.clear()
    except Exception:
        zakladka = ark.add_worksheet(title=tytul, rows=max(len(dane) + 20, 100), cols=len(_naglowki()) + 2)
    zakladka.update(values=dane, range_name="A1")
    return f"Zaktualizowano zakładkę „{tytul}” w Google Sheets"
