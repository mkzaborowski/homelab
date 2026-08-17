"""Szablony listów: podstawianie zmiennych w temacie i treści.

ŚWIADOMIE BEZ SILNIKA SZABLONÓW. Jinja czy podobny dałby pętle, warunki
i dziedziczenie, ale wtedy treść maila staje się programem - a te szablony
edytuje się w panelu przez przeglądarkę. Program wpisywany w pole tekstowe
przez człowieka, który chce zmienić jedno zdanie, to proszenie się o awarię
w miejscu, gdzie awaria oznacza niewysłane potwierdzenie.

Zostaje podstawianie `{nazwa}` i nic więcej. Wszystko, co wymaga logiki,
robi aplikacja wołająca API i przysyła gotowy tekst.

BRAK ZMIENNEJ TO BŁĄD, NIE PUSTE MIEJSCE. Szablon z „Dzień dobry {imie}",
któremu nie podano imienia, wysłałby „Dzień dobry " - i nikt by tego nie
zauważył aż do reklamacji. Lepiej odmówić przyjęcia listu.
"""
from __future__ import annotations

import re

WZOR = re.compile(r"\{([a-z0-9_]+)\}", re.I)
# Ile znaków treści przyjmujemy. Powyżej tego rozmiaru to nie jest już mail
# transakcyjny, tylko załącznik przebrany za tekst.
MAKS_TRESC = 100_000
MAKS_TEMAT = 400


class BrakZmiennej(KeyError):
    pass


def zmienne(tekst: str) -> set[str]:
    return set(WZOR.findall(tekst or ""))


def podstaw(tekst: str, dane: dict) -> str:
    """Podstawia {zmienne}. Nieznana zmienna przerywa - patrz docstring."""
    braki = zmienne(tekst) - set(dane or {})
    if braki:
        raise BrakZmiennej(", ".join(sorted(braki)))
    return WZOR.sub(lambda m: str(dane[m.group(1)]), tekst or "")


def zloz(temat: str, tresc: str, dane: dict | None = None) -> tuple[str, str]:
    """Składa list i sprawdza rozmiary. Zwraca (temat, treść)."""
    dane = dane or {}
    t = podstaw(temat, dane).strip()
    c = podstaw(tresc, dane)
    if not t:
        raise ValueError("pusty temat")
    if not c.strip():
        raise ValueError("pusta treść")
    if len(t) > MAKS_TEMAT:
        raise ValueError(f"temat dłuższy niż {MAKS_TEMAT} znaków")
    if len(c) > MAKS_TRESC:
        raise ValueError(f"treść dłuższa niż {MAKS_TRESC} znaków")
    # Nagłówki rozdziela od treści pusta linia, więc znak nowej linii w temacie
    # pozwoliłby dopisać własne nagłówki. Python i tak by to odrzucił, ale
    # czytelny komunikat jest lepszy niż wyjątek z głębi biblioteki.
    if "\n" in t or "\r" in t:
        raise ValueError("temat nie może zawierać znaku nowej linii")
    return t, c
