"""Pojedynczy przebieg: pobierz z IBKR -> zapisz -> zbuduj Excela -> wypchnij do Sheets."""
from __future__ import annotations

import os
from pathlib import Path

import flex
import raport_excel
import sheets
import statystyki
import store

PLIK_XLSX = store.KATALOG / "portfel.xlsx"


def _kwartaly_do_raportu() -> list[tuple[dict, list[dict]]]:
    """Bieżący zrzut per kwartał: dla każdego kwartału bierzemy jego ostatni dzień."""
    dni = store.wszystkie_dni()
    if not dni:
        return []
    ostatni_w_kwartale: dict[str, str] = {}
    for d in dni:                      # dni rosnąco -> nadpisujemy najnowszym
        ostatni_w_kwartale[statystyki.kwartal(d)] = d

    meta = store.meta()
    wynik = []
    for kw, dzien in ostatni_w_kwartale.items():
        z = store.zrzut(dzien)
        if not z:
            continue
        pods = statystyki.podsumowanie(z, meta, store.poprzedni_zrzut(dzien))
        transakcje = [t for t in z["dane"].get("transakcje", [])
                      if statystyki.kwartal(t.get("data", "")) == kw]
        wynik.append((pods, transakcje))
    return wynik


def uruchom(token: str | None = None, query_id: str | None = None) -> tuple[bool, str]:
    """Zwraca (czy_ok, komunikat). Nie rzuca wyjątkami - wszystko trafia do logu."""
    token = token or os.environ.get("IBKR_TOKEN", "")
    query_id = query_id or os.environ.get("IBKR_QUERY_ID", "")
    if not token or not query_id:
        kom = "Brak IBKR_TOKEN lub IBKR_QUERY_ID"
        store.zapisz_przebieg(False, kom)
        return False, kom

    try:
        xml = flex.pobierz_raport(token, query_id)
        rap = flex.parsuj(xml)
        dzien = store.zapisz_zrzut(rap)

        kwartaly = _kwartaly_do_raportu()
        if kwartaly:
            raport_excel.zbuduj(PLIK_XLSX, kwartaly)

        czesci = [f"zapisano {dzien}", f"{len(rap.pozycje)} pozycji"]
        if sheets.skonfigurowane() and kwartaly:
            try:
                czesci.append(sheets.wypchnij(kwartaly[-1][0]))
            except Exception as e:                          # noqa: BLE001
                czesci.append(f"Sheets nie zadziałało: {e}")

        kom = " · ".join(czesci)
        store.zapisz_przebieg(True, kom)
        return True, kom
    except Exception as e:                                  # noqa: BLE001
        kom = f"{type(e).__name__}: {e}"
        store.zapisz_przebieg(False, kom)
        return False, kom


if __name__ == "__main__":
    store.zainicjuj()
    ok, kom = uruchom()
    print(("OK  " if ok else "BŁĄD ") + kom)
    raise SystemExit(0 if ok else 1)
