"""Wyliczenia portfelowe: koszyki, zmiana dzienna, ryzyko stopów, covered calls."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime


def _data(s: str) -> date | None:
    s = (s or "").strip()[:10].replace("/", "-")
    if len(s) == 8 and s.isdigit():
        s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def kwartal(dzien: str) -> str:
    d = _data(dzien)
    if not d:
        return "?"
    return f"Q{(d.month - 1) // 3 + 1} {d.year}"


def akcje(pozycje: list[dict]) -> list[dict]:
    return [p for p in pozycje if p.get("klasa") not in ("OPT", "FOP") and p.get("ilosc")]


def opcje(pozycje: list[dict]) -> list[dict]:
    return [p for p in pozycje if p.get("klasa") in ("OPT", "FOP") and p.get("ilosc")]


def wzbogac(pozycje: list[dict], meta: dict, poprzednie: list[dict] | None) -> list[dict]:
    """Dokłada koszyk, stop, ocenę i zmianę dzienną liczoną z poprzedniego zrzutu."""
    ceny_wczoraj = {}
    for p in (poprzednie or []):
        if p.get("symbol") and p.get("cena"):
            ceny_wczoraj[p["symbol"]] = p["cena"]

    wynik = []
    for p in pozycje:
        m = meta.get(p.get("symbol", ""), {})
        q = dict(p)
        q["koszyk"] = m.get("koszyk") or "Nieprzypisane"
        q["ocena"] = m.get("ocena") or ""
        q["stop"] = m.get("stop")
        q["notatka"] = m.get("notatka") or ""

        wczoraj = ceny_wczoraj.get(q.get("symbol"))
        q["zmiana_dzienna"] = ((q["cena"] - wczoraj) / wczoraj * 100) if wczoraj else None

        koszt = q.get("koszt") or 0.0
        q["zysk_proc"] = (q.get("zysk", 0.0) / koszt * 100) if koszt else 0.0

        # dystans do stopa i kwota pod ryzykiem, jeśli stop jest ustawiony
        if q["stop"] and q.get("cena"):
            q["do_stopu_proc"] = (q["stop"] - q["cena"]) / q["cena"] * 100
            q["ryzyko"] = (q["stop"] - q["cena"]) * q.get("ilosc", 0.0)
        else:
            q["do_stopu_proc"] = None
            q["ryzyko"] = None
        wynik.append(q)
    return wynik


def wg_koszykow(pozycje: list[dict], nav: float) -> list[dict]:
    """Grupuje pozycje w koszyki i liczy udziały - układ jak w arkuszu AWP."""
    grupy: dict[str, list[dict]] = defaultdict(list)
    for p in pozycje:
        grupy[p["koszyk"]].append(p)

    wynik = []
    for nazwa, lista in sorted(grupy.items(),
                               key=lambda kv: -sum(x.get("wartosc", 0.0) for x in kv[1])):
        wartosc = sum(p.get("wartosc", 0.0) for p in lista)
        koszt = sum(p.get("koszt", 0.0) for p in lista)
        zysk = sum(p.get("zysk", 0.0) for p in lista)
        # w obrębie koszyka scalamy lot-y tego samego tickera w wiersz zbiorczy
        wg_symbolu: dict[str, list[dict]] = defaultdict(list)
        for p in lista:
            wg_symbolu[p.get("symbol", "")].append(p)
        tickery = []
        for sym, loty in sorted(wg_symbolu.items(),
                                key=lambda kv: -sum(x.get("wartosc", 0.0) for x in kv[1])):
            w = sum(x.get("wartosc", 0.0) for x in loty)
            k = sum(x.get("koszt", 0.0) for x in loty)
            il = sum(x.get("ilosc", 0.0) for x in loty)
            tickery.append({
                "symbol": sym,
                "opis": loty[0].get("opis", ""),
                "ocena": loty[0].get("ocena", ""),
                "ilosc": il,
                "koszt": k,
                "wartosc": w,
                "zysk": w - k,
                "zysk_proc": ((w - k) / k * 100) if k else 0.0,
                "cena": loty[0].get("cena", 0.0),
                "cena_kosztu": (k / il) if il else 0.0,
                "zmiana_dzienna": loty[0].get("zmiana_dzienna"),
                "udzial": (w / nav * 100) if nav else 0.0,
                "loty": sorted(loty, key=lambda x: x.get("data_otwarcia", "")),
            })
        wynik.append({
            "koszyk": nazwa,
            "wartosc": wartosc,
            "koszt": koszt,
            "zysk": zysk,
            "zysk_proc": (zysk / koszt * 100) if koszt else 0.0,
            "udzial": (wartosc / nav * 100) if nav else 0.0,
            "tickery": tickery,
        })
    return wynik


def covered_calls(poz_opcji: list[dict], poz_akcji: list[dict], dzis: date | None = None) -> list[dict]:
    """Krótkie calle pokryte akcjami + ryzyko przypisania."""
    dzis = dzis or date.today()
    ile_akcji: dict[str, float] = defaultdict(float)
    kurs: dict[str, float] = {}
    for a in poz_akcji:
        ile_akcji[a.get("symbol", "")] += a.get("ilosc", 0.0)
        kurs[a.get("symbol", "")] = a.get("cena", 0.0)

    wynik = []
    for o in poz_opcji:
        if o.get("prawo") != "C" or o.get("ilosc", 0) >= 0:
            continue  # interesują nas tylko wystawione calle
        bazowy = o.get("bazowy") or o.get("symbol", "").split()[0]
        kontrakty = abs(o.get("ilosc", 0.0))
        pokrycie = ile_akcji.get(bazowy, 0.0)
        spot = kurs.get(bazowy, 0.0)
        strike = o.get("strike", 0.0)
        wygasa = _data(o.get("wygasa", ""))
        dni = (wygasa - dzis).days if wygasa else None
        wynik.append({
            "symbol": o.get("symbol", ""),
            "bazowy": bazowy,
            "kontrakty": kontrakty,
            "strike": strike,
            "wygasa": wygasa.isoformat() if wygasa else "",
            "dni_do_wygasniecia": dni,
            "spot": spot,
            "w_pieniadzu": bool(strike and spot and spot > strike),
            "do_strike_proc": ((strike - spot) / spot * 100) if spot else None,
            "pokryte": pokrycie >= kontrakty * 100,
            "premia_biezaca": o.get("wartosc", 0.0),
            "wynik": o.get("zysk", 0.0),
        })
    return sorted(wynik, key=lambda x: (x["dni_do_wygasniecia"] is None, x["dni_do_wygasniecia"]))


def podsumowanie(zrzut: dict, meta: dict, poprzedni: dict | None) -> dict:
    """Komplet statystyk dla strony i nagłówka Excela."""
    dane = zrzut["dane"]
    nav = dane.get("nav") or 0.0
    poz_wszystkie = wzbogac(dane.get("pozycje", []), meta,
                            (poprzedni or {}).get("dane", {}).get("pozycje"))
    poz_akcji = akcje(poz_wszystkie)
    poz_opcji = opcje(poz_wszystkie)

    wartosc = sum(p.get("wartosc", 0.0) for p in poz_akcji)
    koszt = sum(p.get("koszt", 0.0) for p in poz_akcji)
    zysk = wartosc - koszt
    gotowka = sum(g.get("konczy", 0.0) for g in dane.get("gotowka", []))

    # Podstawa procentów: suma aktywów. Dzielenie przez NAV zawodzi, gdy raport
    # nie ma sekcji NAV albo gdy konto korzysta z dźwigni (pozycje > NAV).
    suma_aktywow = wartosc + gotowka
    if not nav:
        nav = suma_aktywow          # brak sekcji NAV - pokazujemy sumę aktywów
    podstawa = suma_aktywow or nav

    nav_poprz = (poprzedni or {}).get("nav") or 0.0
    zmiana_nav = ((nav - nav_poprz) / nav_poprz * 100) if nav_poprz else None

    koszyki = wg_koszykow(poz_akcji, podstawa)
    cc = covered_calls(poz_opcji, poz_akcji)

    # Ranking liczymy na tickerach, nie na lotach - inaczej ta sama spółka
    # kupiona w dwóch transzach pojawia się w zestawieniu dwa razy.
    wg_symbolu: dict[str, dict] = {}
    for p in poz_akcji:
        s = p.get("symbol", "")
        w = wg_symbolu.setdefault(s, {"symbol": s, "opis": p.get("opis", ""),
                                      "wartosc": 0.0, "koszt": 0.0})
        w["wartosc"] += p.get("wartosc", 0.0)
        w["koszt"] += p.get("koszt", 0.0)
    for w in wg_symbolu.values():
        w["zysk"] = w["wartosc"] - w["koszt"]
        w["zysk_proc"] = (w["zysk"] / w["koszt"] * 100) if w["koszt"] else 0.0

    posortowane = sorted(wg_symbolu.values(), key=lambda p: p["zysk_proc"])
    # przy małym portfelu skracamy listy, żeby te same spółki nie były
    # jednocześnie "najlepsze" i "najsłabsze"
    ile = min(5, max(1, len(posortowane) // 2))
    ryzyka = [p["ryzyko"] for p in poz_akcji if p.get("ryzyko") is not None]

    # koncentracja: udział 5 największych tickerów
    top = sorted(wg_symbolu.values(), key=lambda p: -p["wartosc"])[:5]
    koncentracja = sum(p["wartosc"] for p in top) / podstawa * 100 if podstawa else 0.0

    waluty: dict[str, float] = defaultdict(float)
    for p in poz_akcji:
        waluty[p.get("waluta", "?")] += p.get("wartosc", 0.0)

    return {
        "data": zrzut["data"],
        "kwartal": kwartal(zrzut["data"]),
        "konto": zrzut.get("konto", ""),
        "waluta": zrzut.get("waluta", "USD"),
        "nav": nav,
        "zmiana_nav_proc": zmiana_nav,
        "wartosc_pozycji": wartosc,
        "koszt": koszt,
        "zysk": zysk,
        "zysk_proc": (zysk / koszt * 100) if koszt else 0.0,
        "gotowka": gotowka,
        "suma_aktywow": suma_aktywow,
        "udzial_gotowki": (gotowka / podstawa * 100) if podstawa else 0.0,
        "liczba_pozycji": len(poz_akcji),
        "liczba_tickerow": len({p.get("symbol") for p in poz_akcji}),
        "koszyki": koszyki,
        "covered_calls": cc,
        "cc_w_pieniadzu": sum(1 for c in cc if c["w_pieniadzu"]),
        "cc_niepokryte": sum(1 for c in cc if not c["pokryte"]),
        "najlepsze": list(reversed(posortowane[-ile:])),
        "najgorsze": posortowane[:ile],
        "ryzyko_stopow": sum(ryzyka) if ryzyka else 0.0,
        "pozycje_bez_stopa": sum(1 for p in poz_akcji if not p.get("stop")),
        "koncentracja_top5": koncentracja,
        "waluty": dict(waluty),
        "pozycje": poz_akcji,
        "opcje": poz_opcji,
        "dywidendy_naliczone": dane.get("dywidendy_naliczone", 0.0),
    }
