"""Testy warunków skrajnych: co się stanie z portfelem przy danym wstrząsie.

Metoda: liniowe przełożenie przez bety czynnikowe. Wstrząs czynnika mnożymy
przez betę portfela wobec tego czynnika i przez wartość portfela.

OGRANICZENIA, o których trzeba wiedzieć, bo inaczej te liczby wprowadzają
w błąd (§11 briefu wymaga oznaczenia ich jako szacunek, nie prognozę):

1. Beta jest liniowa, a rynki w krachu - nie. Przy spadku o 30% korelacje
   rosną, a bety rozjeżdżają się wobec tych z okresu spokojnego. Ten model
   zaniża straty w scenariuszach najgłębszych.
2. Bety liczymy z ostatniego roku. Portfel, którego skład się zmienił,
   niesie betę mieszaną - historyczną, nie bieżącą.
3. Opcje wchodzą przez deltę, więc dla dużych ruchów przybliżenie jest
   grube: gamma sprawia, że delta sama się zmienia po drodze. Dokładamy
   człon gamma, ale nadal jest to rozwinięcie drugiego rzędu, nie wycena.
4. Scenariusze łączone zakładają, że wstrząsy się sumują. To uproszczenie -
   w rzeczywistości oddziałują na siebie.

Mimo to odpowiada na pytanie, na które inaczej nie ma odpowiedzi wcale:
„jeśli Nasdaq spadnie o 20%, a złoto urośnie o 8%, co się dzieje z NAV".
"""
from __future__ import annotations

# Pojedyncze wstrząsy: czynnik → lista zmian do przetestowania.
WSTRZASY = {
    "SPY": [-0.30, -0.20, -0.10, -0.05, 0.05, 0.10],
    "QQQ": [-0.30, -0.20, -0.10, 0.10],
    "IWM": [-0.20, -0.10, 0.10],
    "GLD": [-0.20, -0.10, 0.10, 0.20],
    "SLV": [-0.30, -0.15, 0.15, 0.30],
    "XLE": [-0.25, -0.10, 0.20],
    "TLT": [-0.10, -0.05, 0.05, 0.10],
    "UUP": [-0.10, -0.05, 0.05, 0.10],
}

# Scenariusze łączone - nazwane sytuacje rynkowe, nie pojedyncze ruchy.
POLACZONE = {
    "Ucieczka od ryzyka": {
        "opis": "gwałtowna wyprzedaż akcji, kapitał ucieka w złoto i dolara",
        "wstrzasy": {"SPY": -0.15, "QQQ": -0.22, "GLD": 0.08, "UUP": 0.07, "XLE": -0.20},
    },
    "Wstrząs inflacyjny": {
        "opis": "stopy w górę, wyceny wzrostowe pod presją, surowce mocne",
        "wstrzasy": {"TLT": -0.12, "QQQ": -0.18, "GLD": 0.12, "XLE": 0.15},
    },
    "Pęknięcie bańki technologicznej": {
        "opis": "przecena spółek wzrostowych bez paniki na szerokim rynku",
        "wstrzasy": {"QQQ": -0.30, "SPY": -0.12, "IWM": -0.18},
    },
    "Załamanie metali": {
        "opis": "silny dolar zbija złoto i srebro, kopalnie mocniej niż kruszec",
        "wstrzasy": {"GLD": -0.15, "SLV": -0.25, "UUP": 0.08},
    },
    "Odbicie ryzyka": {
        "opis": "powrót apetytu na ryzyko, małe spółki i technologia w górę",
        "wstrzasy": {"SPY": 0.10, "QQQ": 0.15, "IWM": 0.14, "UUP": -0.05},
    },
}


def _beta_wg_symbolu(czynniki: list[dict]) -> dict[str, float]:
    return {c["symbol"]: c["beta"] for c in (czynniki or []) if c.get("beta") is not None}


def wplyw_opcji(pozycje_opcji: list[dict], czynnik: str, zmiana: float,
                bety_bazowych: dict[str, float] | None = None) -> float:
    """Wpływ wstrząsu na nogę opcyjną, przez deltę i gammę.

    Rozwinięcie do drugiego rzędu: dP ≈ delta·dS + ½·gamma·dS².
    Człon gamma jest tu istotny, bo przy krótkich callach jest ujemny -
    przy dużym ruchu w górę pozycja traci szybciej, niż sugeruje sama delta.
    Pominięcie go zaniżałoby stratę dokładnie w scenariuszu, który boli
    najbardziej."""
    bety = bety_bazowych or {}
    razem = 0.0
    for p in pozycje_opcji or []:
        spot = float(p.get("spot") or 0.0)
        if not spot:
            continue
        # ruch bazowego = wstrząs czynnika przeskalowany betą tej spółki;
        # bez znanej bety zakładamy jeden do jednego dla szerokiego rynku
        beta_spolki = bety.get(p.get("bazowy") or "", 1.0 if czynnik in ("SPY", "QQQ") else 0.0)
        dS = spot * zmiana * beta_spolki
        if not dS:
            continue
        razem += p.get("delta_akcji", 0.0) * dS
        razem += 0.5 * p.get("gamma", 0.0) * dS * dS
    return razem


def pojedyncze(nav: float, czynniki: list[dict],
               pozycje_opcji: list[dict] | None = None) -> list[dict]:
    """Wpływ pojedynczych wstrząsów, czynnik po czynniku."""
    bety = _beta_wg_symbolu(czynniki)
    opisy = {c["symbol"]: c["opis"] for c in (czynniki or [])}
    r2 = {c["symbol"]: c.get("r2") for c in (czynniki or [])}
    out = []
    for sym, zmiany in WSTRZASY.items():
        if sym not in bety:
            continue
        for z in zmiany:
            akcje = nav * bety[sym] * z
            opcje_ = wplyw_opcji(pozycje_opcji, sym, z)
            out.append({
                "czynnik": sym, "opis": opisy.get(sym, sym), "zmiana": z,
                "beta": bety[sym], "r2": r2.get(sym),
                "wplyw_akcji": akcje, "wplyw_opcji": opcje_,
                "wplyw": akcje + opcje_,
                "wplyw_proc": (akcje + opcje_) / nav if nav else 0.0,
            })
    return out


# Czynniki z tej samej grupy opisują TĘ SAMĄ ekspozycję z różnych stron.
# SPY, QQQ i IWM to w znacznej części te same spółki, więc dodanie ich bet
# liczyłoby jedną ekspozycję akcyjną trzy razy. Na prawdziwym portfelu dawało
# to -53% NAV przy scenariuszu technologicznym, mimo że roczna zmienność
# całego portfela wynosi 21% - liczba efektowna i nieprawdziwa.
GRUPY = {
    "SPY": "akcje", "QQQ": "akcje", "IWM": "akcje",
    "GLD": "metale", "SLV": "metale",
    "XLE": "energia",
    "TLT": "stopy",
    "UUP": "waluta",
}


def polaczone(nav: float, czynniki: list[dict],
              pozycje_opcji: list[dict] | None = None) -> list[dict]:
    """Nazwane sytuacje rynkowe - kilka wstrząsów naraz.

    W obrębie grupy skorelowanych czynników bierzemy NAJMOCNIEJSZY wpływ,
    a nie sumę: portfel ma jedną ekspozycję akcyjną i dostaje po niej raz.
    Sumujemy dopiero między grupami, bo akcje, złoto i dolar to naprawdę
    różne ekspozycje. Odrzucone składniki zostają widoczne z adnotacją,
    żeby było jasne, co model policzył, a czego nie."""
    bety = _beta_wg_symbolu(czynniki)
    out = []
    for nazwa, s in POLACZONE.items():
        wg_grup: dict[str, list[dict]] = {}
        for sym, z in s["wstrzasy"].items():
            if sym not in bety:
                continue
            w = nav * bety[sym] * z + wplyw_opcji(pozycje_opcji, sym, z)
            wpis = {"czynnik": sym, "zmiana": z, "beta": bety[sym], "wplyw": w,
                    "grupa": GRUPY.get(sym, sym), "liczony": True}
            wg_grup.setdefault(wpis["grupa"], []).append(wpis)
        if not wg_grup:
            continue

        razem, skladniki = 0.0, []
        for grupa, wpisy in wg_grup.items():
            wiodacy = max(wpisy, key=lambda x: abs(x["wplyw"]))
            razem += wiodacy["wplyw"]
            for w in wpisy:
                w["liczony"] = w is wiodacy
                skladniki.append(w)

        skladniki.sort(key=lambda x: (not x["liczony"], x["wplyw"]))
        out.append({
            "nazwa": nazwa, "opis": s["opis"],
            "wplyw": razem, "wplyw_proc": razem / nav if nav else 0.0,
            "nav_po": nav + razem,
            "skladniki": skladniki,
            "grup": len(wg_grup),
            "objete": len(skladniki), "wszystkich": len(s["wstrzasy"]),
        })
    return sorted(out, key=lambda x: x["wplyw"])


def podsumowanie(nav: float, czynniki: list[dict],
                 pozycje_opcji: list[dict] | None = None) -> dict:
    if not czynniki:
        return {"dostepne": False,
                "powod": "brak wyliczonych bet czynnikowych - potrzebna historia kursów"}
    poj = pojedyncze(nav, czynniki, pozycje_opcji)
    pol = polaczone(nav, czynniki, pozycje_opcji)
    return {
        "dostepne": True,
        "nav": nav,
        "pojedyncze": poj,
        "polaczone": pol,
        "najgorszy": pol[0] if pol else None,
        "czynnikow": len(czynniki),
    }
