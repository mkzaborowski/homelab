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
        # liczymy tickery, nie loty - inaczej jedna spółka w 13 transzach
        # raportuje "13 pozycji bez stopa" i ostrzeżenie przestaje cokolwiek znaczyć
        "pozycje_bez_stopa": len({p.get("symbol") for p in poz_akcji if not p.get("stop")}),
        "koncentracja_top5": koncentracja,
        "waluty": dict(waluty),
        "tickery": sorted(wg_symbolu.values(), key=lambda t: -t["wartosc"]),
        "rozklad": rozklad_wynikow(list(wg_symbolu.values())),
        "hhi": koncentracja_hhi(list(wg_symbolu.values()), podstawa),
        "wiek": wiek_pozycji(poz_akcji),
        "zyskownych": sum(1 for t in wg_symbolu.values() if t["zysk"] > 0),
        "stratnych": sum(1 for t in wg_symbolu.values() if t["zysk"] < 0),
        "pozycje": poz_akcji,
        "opcje": poz_opcji,
        "dywidendy_naliczone": dane.get("dywidendy_naliczone", 0.0),
    }


def okresy(hist: list[dict], nav_biezacy: float,
           przeplywy: dict[str, float] | None = None) -> dict:
    """Zmiana NAV za okresy kalendarzowe.

    Okres liczymy TYLKO wtedy, gdy historia faktycznie sięga jego początku.
    Wcześniej QTD, YTD i „od początku" liczyły się od tej samej, pierwszej
    zapisanej obserwacji i pokazywały trzy razy tę samą liczbę pod trzema
    nazwami - wyglądało to na trzy niezależne pomiary, a było jednym.
    Gdy historii brakuje, oddajemy `dostepny=False`, a panel pisze wprost,
    od kiedy dane w ogóle są.

    Uwaga: to nadal zwykła różnica NAV. Przy pierwszej wpłacie na rachunek
    pokaże ją jako zysk - od tego jest TWR w module `zwrot`.
    """
    if not hist:
        return {}
    dzis = _data(hist[-1]["data"]) or date.today()
    pierwszy = _data(hist[0]["data"]) or dzis
    progi = [
        ("MTD", date(dzis.year, dzis.month, 1)),
        ("QTD", date(dzis.year, 3 * ((dzis.month - 1) // 3) + 1, 1)),
        ("YTD", date(dzis.year, 1, 1)),
        ("1R", date(dzis.year - 1, dzis.month, min(dzis.day, 28))),
        ("Od początku", pierwszy),
    ]
    wynik = {}
    for etykieta, od in progi:
        if etykieta != "Od początku" and pierwszy > od:
            wynik[etykieta] = {"dostepny": False, "od": hist[0]["data"],
                               "proc": None, "kwota": None}
            continue
        baza = next((h for h in hist if (_data(h["data"]) or dzis) >= od), None) or hist[0]
        start = baza["nav"] or 0.0
        if start and baza["data"] != hist[-1]["data"]:
            # Zwrot za okres liczymy jak TWR, z korektą o wpłaty i wypłaty.
            # Sama różnica NAV dawała dla tego rachunku +3428% za rok, bo
            # w tym czasie wpłynęło 596 tys. Panel pokazywałby wtedy dwie
            # różne liczby dla tej samej wielkości: tutaj i w zakładce Wynik.
            wycinek = [h for h in hist if h["data"] >= baza["data"]]
            proc = None
            if przeplywy is not None:
                import zwrot as _zwrot
                t = _zwrot.twr(wycinek, przeplywy)
                proc = t * 100 if t is not None else None
            if proc is None:
                proc = (nav_biezacy - start) / start * 100
            wynik[etykieta] = {"dostepny": True, "proc": proc,
                               "kwota": nav_biezacy - start, "od": baza["data"]}
    return wynik


def rozklad_wynikow(tickery: list[dict]) -> list[dict]:
    """Histogram wyników procentowych - do wykresu słupkowego."""
    kubelki = [(-1e9, -20, "< -20%"), (-20, -10, "-20…-10%"), (-10, -5, "-10…-5%"),
               (-5, 0, "-5…0%"), (0, 5, "0…5%"), (5, 10, "5…10%"),
               (10, 20, "10…20%"), (20, 1e9, "> 20%")]
    wynik = []
    for lo, hi, etykieta in kubelki:
        w = [t for t in tickery if lo <= t["zysk_proc"] < hi]
        wynik.append({"etykieta": etykieta, "ile": len(w), "dodatni": lo >= 0,
                      "kwota": sum(t["zysk"] for t in w)})
    return wynik


def koncentracja_hhi(tickery: list[dict], podstawa: float) -> float:
    """Indeks Herfindahla-Hirschmana (0-10000). Powyżej ~2500 portfel jest skupiony."""
    if not podstawa:
        return 0.0
    return sum((t["wartosc"] / podstawa * 100) ** 2 for t in tickery)


def wiek_pozycji(pozycje: list[dict], dzis: date | None = None) -> list[dict]:
    """Rozkład kapitału wg długości trzymania - liczony na lotach."""
    dzis = dzis or date.today()
    progi = [(0, 30, "< 1 mies."), (30, 90, "1-3 mies."), (90, 365, "3-12 mies."),
             (365, 10 ** 6, "> rok")]
    wynik = [{"etykieta": e, "wartosc": 0.0, "ile": 0} for _, _, e in progi]
    for p in pozycje:
        d = _data(p.get("data_otwarcia", "")[:10])
        if not d:
            continue
        dni = (dzis - d).days
        for i, (lo, hi, _) in enumerate(progi):
            if lo <= dni < hi:
                wynik[i]["wartosc"] += p.get("wartosc", 0.0)
                wynik[i]["ile"] += 1
                break
    return wynik
