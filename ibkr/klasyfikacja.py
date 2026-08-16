"""Przypisanie pozycji do sektorów, tematów i klas aktywów.

Flex nie podaje ani sektora, ani branży, ani kraju - stąd wzięło się 100%
portfela w koszyku „Nieprzypisane". Zamiast kupować dane klasyfikacyjne,
korzystamy z dwóch źródeł, które już mamy:

1. arkusz portfela wzorcowego - ma gotowe przypisanie ticker → koszyk
   i to jest przypisanie zrobione przez człowieka, więc lepsze niż
   jakikolwiek automat,
2. mapa sektorów i tematów w tym pliku - uzupełnia to, czego w arkuszu nie ma.

Zasada nadrzędna: automat NIGDY nie nadpisuje decyzji ręcznej. Za to
odpowiada flaga `recznie` w tabeli klasyfikacji.
"""
from __future__ import annotations

import store

# Wymiary klasyfikacji. Rozdzielone, bo pytanie „ile mam w półprzewodnikach"
# i „ile mam w USA" to dwa różne pytania do tych samych pozycji.
SEKTOR, TEMAT, KLASA, KRAJ = "sektor", "temat", "klasa", "kraj"

# Mapa utrzymywana ręcznie. Świadomie mała: obejmuje to, co faktycznie jest
# w portfelu, zamiast udawać kompletny słownik giełdy. Nowe spółki trafiają
# do „Nieprzypisane" i widać je w panelu jako zadanie do zrobienia.
MAPA: dict[str, dict[str, object]] = {
    # półprzewodniki i sprzęt
    "NVDA": {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"]},
    "AMD":  {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"]},
    "INTC": {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"]},
    "MU":   {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"]},
    "TSM":  {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"], KRAJ: "Taiwan"},
    "ASML": {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"], KRAJ: "Netherlands"},
    "AVGO": {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"]},
    "QCOM": {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"]},
    "ARM":  {SEKTOR: "Technology", TEMAT: ["AI / semiconductors"]},
    "MBLY": {SEKTOR: "Technology", TEMAT: ["AI / semiconductors", "Robotics"]},
    # oprogramowanie i platformy
    "MSFT": {SEKTOR: "Technology", TEMAT: ["Software", "AI / semiconductors"]},
    "GOOGL": {SEKTOR: "Technology", TEMAT: ["Software", "AI / semiconductors"]},
    "GOOG": {SEKTOR: "Technology", TEMAT: ["Software", "AI / semiconductors"]},
    "AMZN": {SEKTOR: "Consumer cyclical", TEMAT: ["Software"]},
    "META": {SEKTOR: "Technology", TEMAT: ["Software", "AI / semiconductors"]},
    "AAPL": {SEKTOR: "Technology", TEMAT: ["Software"]},
    "PLTR": {SEKTOR: "Technology", TEMAT: ["Software", "AI / semiconductors"]},
    "CRWD": {SEKTOR: "Technology", TEMAT: ["Software"]},
    "NOW":  {SEKTOR: "Technology", TEMAT: ["Software"]},
    # kosmos, obronność, robotyka
    "LUNR": {SEKTOR: "Industrials", TEMAT: ["Space", "Emerging tech"]},
    "RKLB": {SEKTOR: "Industrials", TEMAT: ["Space", "Emerging tech"]},
    "ASTS": {SEKTOR: "Telecom", TEMAT: ["Space", "Emerging tech"]},
    "ACHR": {SEKTOR: "Industrials", TEMAT: ["Emerging tech"]},
    "JOBY": {SEKTOR: "Industrials", TEMAT: ["Emerging tech"]},
    "TSLA": {SEKTOR: "Consumer cyclical", TEMAT: ["Robotics", "Emerging tech"]},
    # energia jądrowa i uran
    "OKLO": {SEKTOR: "Energy", TEMAT: ["Nuclear energy"]},
    "SMR":  {SEKTOR: "Energy", TEMAT: ["Nuclear energy"]},
    "LEU":  {SEKTOR: "Energy", TEMAT: ["Nuclear energy"]},
    "CCJ":  {SEKTOR: "Energy", TEMAT: ["Nuclear energy"], KRAJ: "Canada"},
    "NLR":  {SEKTOR: "Energy", TEMAT: ["Nuclear energy"], KLASA: "ETF"},
    "UEC":  {SEKTOR: "Energy", TEMAT: ["Nuclear energy"]},
    # metale szlachetne i kopalnie
    "GLD":  {SEKTOR: "Commodities", TEMAT: ["Gold"], KLASA: "ETF"},
    "SLV":  {SEKTOR: "Commodities", TEMAT: ["Silver"], KLASA: "ETF"},
    "SLVP": {SEKTOR: "Commodities", TEMAT: ["Silver", "Silver miners"], KLASA: "ETF"},
    "GDX":  {SEKTOR: "Commodities", TEMAT: ["Gold miners"], KLASA: "ETF"},
    "NEM":  {SEKTOR: "Commodities", TEMAT: ["Gold miners"]},
    "AEM":  {SEKTOR: "Commodities", TEMAT: ["Gold miners"], KRAJ: "Canada"},
    "PAAS": {SEKTOR: "Commodities", TEMAT: ["Silver miners"], KRAJ: "Canada"},
    "HL":   {SEKTOR: "Commodities", TEMAT: ["Silver miners"]},
    "AG":   {SEKTOR: "Commodities", TEMAT: ["Silver miners"], KRAJ: "Canada"},
    "WPM":  {SEKTOR: "Commodities", TEMAT: ["Gold miners", "Silver miners"], KRAJ: "Canada"},
    "ANGX": {SEKTOR: "Commodities", TEMAT: ["Gold miners"]},
    # energia konwencjonalna i przemysł
    "XLE":  {SEKTOR: "Energy", TEMAT: ["Energy"], KLASA: "ETF"},
    "OIH":  {SEKTOR: "Energy", TEMAT: ["Energy"], KLASA: "ETF"},
    "XOM":  {SEKTOR: "Energy", TEMAT: ["Energy"]},
    "CVX":  {SEKTOR: "Energy", TEMAT: ["Energy"]},
    "CAT":  {SEKTOR: "Industrials", TEMAT: ["Industrials"]},
    "DE":   {SEKTOR: "Industrials", TEMAT: ["Industrials"]},
    # szerokie i lewarowane fundusze
    "SPY":  {SEKTOR: "Broad market", TEMAT: ["Broad market"], KLASA: "ETF"},
    "QQQ":  {SEKTOR: "Broad market", TEMAT: ["Broad market"], KLASA: "ETF"},
    "SPXS": {SEKTOR: "Broad market", TEMAT: ["Hedge"], KLASA: "ETF"},
    "SQQQ": {SEKTOR: "Broad market", TEMAT: ["Hedge"], KLASA: "ETF"},
    "SDS":  {SEKTOR: "Broad market", TEMAT: ["Hedge"], KLASA: "ETF"},
    "SCHD": {SEKTOR: "Broad market", TEMAT: ["Dividend"], KLASA: "ETF"},
    "KWEB": {SEKTOR: "Technology", TEMAT: ["China"], KLASA: "ETF", KRAJ: "China"},
    "UFO":  {SEKTOR: "Industrials", TEMAT: ["Space"], KLASA: "ETF"},
    "SPCX": {SEKTOR: "Industrials", TEMAT: ["Space"], KLASA: "ETF"},
    "AVAV": {SEKTOR: "Industrials", TEMAT: ["Defence", "Emerging tech"]},
    "NNE":  {SEKTOR: "Energy", TEMAT: ["Nuclear energy"]},
    "MELI": {SEKTOR: "Consumer cyclical", TEMAT: ["Software"], KRAJ: "Argentina"},
    "ZETA": {SEKTOR: "Technology", TEMAT: ["Software"]},
    "RPD":  {SEKTOR: "Technology", TEMAT: ["Software"]},
}

# Koszyk z arkusza wzorcowego → temat u nas. Arkusz nazywa rzeczy po swojemu,
# a chcemy jednego słownika w całym panelu.
KOSZYK_NA_TEMAT = {
    "gold": "Gold", "silver": "Silver", "gold miners": "Gold miners",
    "silver miners": "Silver miners", "energy": "Energy",
    "nuclear": "Nuclear energy", "tech": "AI / semiconductors",
    "technology": "AI / semiconductors", "software": "Software",
    "space": "Space", "industrials": "Industrials", "materials": "Commodities",
    "crypto": "Crypto", "cash": "Cash", "defensive": "Defensive",
}


# Temat → sektor. Arkusz wzorcowy przypisuje tematy, nie sektory, więc bez
# tego przełożenia 48 spółek miałoby temat, a sektor „Nieprzypisane".
TEMAT_NA_SEKTOR = {
    "AI / semiconductors": "Technology", "Software": "Technology",
    "Robotics": "Technology", "China": "Technology",
    "Space": "Industrials", "Industrials": "Industrials", "Defence": "Industrials",
    "Emerging tech": "Industrials",
    "Nuclear energy": "Energy", "Energy": "Energy",
    "Gold": "Commodities", "Silver": "Commodities", "Gold miners": "Commodities",
    "Silver miners": "Commodities", "Commodities": "Commodities",
    "Crypto": "Digital assets",
    "Broad market": "Broad market", "Hedge": "Broad market",
    "Dividend": "Broad market", "Defensive": "Defensive",
    "Cash": "Cash",
}


def _temat_z_koszyka(nazwa: str) -> str:
    """Dopasowanie od najdłuższego wzorca: „gold miners" musi wygrać z „gold",
    inaczej kopalnie złota lądują w koszyku ze złotem fizycznym."""
    k = (nazwa or "").strip().lower()
    for wzor in sorted(KOSZYK_NA_TEMAT, key=len, reverse=True):
        if wzor in k:
            return KOSZYK_NA_TEMAT[wzor]
    return (nazwa or "").strip() or "Unassigned"


def klasa_instrumentu(p: dict) -> str:
    """Klasa aktywów z samego raportu - to jedyny wymiar, który Flex zna."""
    k = (p.get("klasa") or "").upper()
    if k in ("OPT", "FOP"):
        return "Options"
    if k == "STK":
        return "Equity"
    if k in ("CASH", "FX"):
        return "Cash"
    return k or "Inne"


def przypisz(pozycje: list[dict], przypisanie_wzorca: dict[str, str] | None = None) -> dict:
    """Nadaje klasyfikację wszystkim pozycjom. Zwraca licznik trafień i braków.

    Kolejność źródeł ma znaczenie: arkusz przed mapą, bo arkusz to decyzja
    człowieka podjęta dla tego konkretnego portfela."""
    wzorzec_map = {k.upper(): v for k, v in (przypisanie_wzorca or {}).items()}
    z_mapy = z_wzorca = bez = pominiete = 0
    braki: list[str] = []

    symbole = {p.get("symbol") for p in pozycje if p.get("symbol")}
    po_symbolu = {p["symbol"]: p for p in pozycje if p.get("symbol")}

    for s in sorted(symbole):
        p = po_symbolu[s]
        # opcje dziedziczą klasyfikację po instrumencie bazowym - inaczej
        # covered call na LUNR wyglądałby jak osobna, nieznana ekspozycja
        klucz = (p.get("bazowy") or s).upper()

        if not store.zapisz_klasyfikacje(s, KLASA, klasa_instrumentu(p),
                                         zrodlo="flex"):
            pominiete += 1

        wpis = MAPA.get(klucz)
        temat_wzorca = wzorzec_map.get(klucz)

        if temat_wzorca:
            store.zapisz_klasyfikacje(s, TEMAT, _temat_z_koszyka(temat_wzorca),
                                      zrodlo="model sheet")
            z_wzorca += 1
        elif wpis and wpis.get(TEMAT):
            tematy = wpis[TEMAT]
            if isinstance(tematy, str):
                tematy = [tematy]
            # ekspozycja dzieli się po równo; zapis jednym wywołaniem, bo
            # osobne kasowałyby się nawzajem
            store.zapisz_klasyfikacje(s, TEMAT, tematy, waga=1.0 / len(tematy),
                                      zrodlo="mapa")
            z_mapy += 1
        else:
            store.zapisz_klasyfikacje(s, TEMAT, "Unassigned", zrodlo="none")
            bez += 1
            if klucz not in braki:
                braki.append(klucz)

        if wpis and wpis.get(SEKTOR):
            store.zapisz_klasyfikacje(s, SEKTOR, str(wpis[SEKTOR]), zrodlo="mapa")
        else:
            # sektor z tematu - nie zgadujemy, tylko przekładamy znane przypisanie
            t = _temat_z_koszyka(temat_wzorca) if temat_wzorca else None
            sekt = TEMAT_NA_SEKTOR.get(t or "", "Unassigned")
            store.zapisz_klasyfikacje(s, SEKTOR, sekt,
                                      zrodlo="from theme" if sekt != "Unassigned" else "none")
        if wpis and wpis.get(KRAJ):
            store.zapisz_klasyfikacje(s, KRAJ, str(wpis[KRAJ]), zrodlo="mapa")
        else:
            store.zapisz_klasyfikacje(s, KRAJ, "USA", zrodlo="domyślnie")

    return {"z_arkusza": z_wzorca, "z_mapy": z_mapy, "bez_przypisania": bez,
            "pominiete_reczne": pominiete, "braki": sorted(braki)}


def udzialy(pozycje: list[dict], wymiar: str) -> list[dict]:
    """Wartość portfela w rozbiciu na wybrany wymiar, z uwzględnieniem wag.

    Pozycja w dwóch tematach po 50% wnosi do każdego połowę swojej wartości -
    inaczej suma ekspozycji przekraczałaby portfel."""
    klas = store.klasyfikacja(wymiar)
    suma: dict[str, float] = {}
    calosc = 0.0
    for p in pozycje:
        s, w = p.get("symbol"), float(p.get("wartosc") or 0.0)
        if not s:
            continue
        calosc += w
        wpisy = klas.get(s) or [{"wartosc": "Unassigned", "waga": 1.0}]
        for k in wpisy:
            suma[k["wartosc"]] = suma.get(k["wartosc"], 0.0) + w * float(k.get("waga") or 1.0)
    return sorted(
        ({"nazwa": n, "wartosc": v, "udzial": (v / calosc * 100.0) if calosc else 0.0}
         for n, v in suma.items()),
        key=lambda x: -x["wartosc"])
