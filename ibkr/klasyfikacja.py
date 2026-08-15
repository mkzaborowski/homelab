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
    "NVDA": {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"]},
    "AMD":  {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"]},
    "INTC": {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"]},
    "MU":   {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"]},
    "TSM":  {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"], KRAJ: "Tajwan"},
    "ASML": {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"], KRAJ: "Holandia"},
    "AVGO": {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"]},
    "QCOM": {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"]},
    "ARM":  {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki"]},
    "MBLY": {SEKTOR: "Technologia", TEMAT: ["AI / półprzewodniki", "Robotyka"]},
    # oprogramowanie i platformy
    "MSFT": {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie", "AI / półprzewodniki"]},
    "GOOGL": {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie", "AI / półprzewodniki"]},
    "GOOG": {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie", "AI / półprzewodniki"]},
    "AMZN": {SEKTOR: "Konsument cykliczny", TEMAT: ["Oprogramowanie"]},
    "META": {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie", "AI / półprzewodniki"]},
    "AAPL": {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie"]},
    "PLTR": {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie", "AI / półprzewodniki"]},
    "CRWD": {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie"]},
    "NOW":  {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie"]},
    # kosmos, obronność, robotyka
    "LUNR": {SEKTOR: "Przemysł", TEMAT: ["Kosmos", "Technologie wschodzące"]},
    "RKLB": {SEKTOR: "Przemysł", TEMAT: ["Kosmos", "Technologie wschodzące"]},
    "ASTS": {SEKTOR: "Telekomunikacja", TEMAT: ["Kosmos", "Technologie wschodzące"]},
    "ACHR": {SEKTOR: "Przemysł", TEMAT: ["Technologie wschodzące"]},
    "JOBY": {SEKTOR: "Przemysł", TEMAT: ["Technologie wschodzące"]},
    "TSLA": {SEKTOR: "Konsument cykliczny", TEMAT: ["Robotyka", "Technologie wschodzące"]},
    # energia jądrowa i uran
    "OKLO": {SEKTOR: "Energetyka", TEMAT: ["Energia jądrowa"]},
    "SMR":  {SEKTOR: "Energetyka", TEMAT: ["Energia jądrowa"]},
    "LEU":  {SEKTOR: "Energetyka", TEMAT: ["Energia jądrowa"]},
    "CCJ":  {SEKTOR: "Energetyka", TEMAT: ["Energia jądrowa"], KRAJ: "Kanada"},
    "NLR":  {SEKTOR: "Energetyka", TEMAT: ["Energia jądrowa"], KLASA: "ETF"},
    "UEC":  {SEKTOR: "Energetyka", TEMAT: ["Energia jądrowa"]},
    # metale szlachetne i kopalnie
    "GLD":  {SEKTOR: "Surowce", TEMAT: ["Złoto"], KLASA: "ETF"},
    "SLV":  {SEKTOR: "Surowce", TEMAT: ["Srebro"], KLASA: "ETF"},
    "SLVP": {SEKTOR: "Surowce", TEMAT: ["Srebro", "Kopalnie srebra"], KLASA: "ETF"},
    "GDX":  {SEKTOR: "Surowce", TEMAT: ["Kopalnie złota"], KLASA: "ETF"},
    "NEM":  {SEKTOR: "Surowce", TEMAT: ["Kopalnie złota"]},
    "AEM":  {SEKTOR: "Surowce", TEMAT: ["Kopalnie złota"], KRAJ: "Kanada"},
    "PAAS": {SEKTOR: "Surowce", TEMAT: ["Kopalnie srebra"], KRAJ: "Kanada"},
    "HL":   {SEKTOR: "Surowce", TEMAT: ["Kopalnie srebra"]},
    "AG":   {SEKTOR: "Surowce", TEMAT: ["Kopalnie srebra"], KRAJ: "Kanada"},
    "WPM":  {SEKTOR: "Surowce", TEMAT: ["Kopalnie złota", "Kopalnie srebra"], KRAJ: "Kanada"},
    "ANGX": {SEKTOR: "Surowce", TEMAT: ["Kopalnie złota"]},
    # energia konwencjonalna i przemysł
    "XLE":  {SEKTOR: "Energetyka", TEMAT: ["Energia"], KLASA: "ETF"},
    "OIH":  {SEKTOR: "Energetyka", TEMAT: ["Energia"], KLASA: "ETF"},
    "XOM":  {SEKTOR: "Energetyka", TEMAT: ["Energia"]},
    "CVX":  {SEKTOR: "Energetyka", TEMAT: ["Energia"]},
    "CAT":  {SEKTOR: "Przemysł", TEMAT: ["Przemysł"]},
    "DE":   {SEKTOR: "Przemysł", TEMAT: ["Przemysł"]},
    # szerokie i lewarowane fundusze
    "SPY":  {SEKTOR: "Szeroki rynek", TEMAT: ["Szeroki rynek"], KLASA: "ETF"},
    "QQQ":  {SEKTOR: "Szeroki rynek", TEMAT: ["Szeroki rynek"], KLASA: "ETF"},
    "SPXS": {SEKTOR: "Szeroki rynek", TEMAT: ["Zabezpieczenie"], KLASA: "ETF"},
    "SQQQ": {SEKTOR: "Szeroki rynek", TEMAT: ["Zabezpieczenie"], KLASA: "ETF"},
    "SDS":  {SEKTOR: "Szeroki rynek", TEMAT: ["Zabezpieczenie"], KLASA: "ETF"},
    "SCHD": {SEKTOR: "Szeroki rynek", TEMAT: ["Dywidenda"], KLASA: "ETF"},
    "KWEB": {SEKTOR: "Technologia", TEMAT: ["Chiny"], KLASA: "ETF", KRAJ: "Chiny"},
    "UFO":  {SEKTOR: "Przemysł", TEMAT: ["Kosmos"], KLASA: "ETF"},
    "SPCX": {SEKTOR: "Przemysł", TEMAT: ["Kosmos"], KLASA: "ETF"},
    "AVAV": {SEKTOR: "Przemysł", TEMAT: ["Obronność", "Technologie wschodzące"]},
    "NNE":  {SEKTOR: "Energetyka", TEMAT: ["Energia jądrowa"]},
    "MELI": {SEKTOR: "Konsument cykliczny", TEMAT: ["Oprogramowanie"], KRAJ: "Argentyna"},
    "ZETA": {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie"]},
    "RPD":  {SEKTOR: "Technologia", TEMAT: ["Oprogramowanie"]},
}

# Koszyk z arkusza wzorcowego → temat u nas. Arkusz nazywa rzeczy po swojemu,
# a chcemy jednego słownika w całym panelu.
KOSZYK_NA_TEMAT = {
    "gold": "Złoto", "silver": "Srebro", "gold miners": "Kopalnie złota",
    "silver miners": "Kopalnie srebra", "energy": "Energia",
    "nuclear": "Energia jądrowa", "tech": "AI / półprzewodniki",
    "technology": "AI / półprzewodniki", "software": "Oprogramowanie",
    "space": "Kosmos", "industrials": "Przemysł", "materials": "Surowce",
    "crypto": "Kryptowaluty", "cash": "Gotówka", "defensive": "Defensywne",
}


# Temat → sektor. Arkusz wzorcowy przypisuje tematy, nie sektory, więc bez
# tego przełożenia 48 spółek miałoby temat, a sektor „Nieprzypisane".
TEMAT_NA_SEKTOR = {
    "AI / półprzewodniki": "Technologia", "Oprogramowanie": "Technologia",
    "Robotyka": "Technologia", "Chiny": "Technologia",
    "Kosmos": "Przemysł", "Przemysł": "Przemysł", "Obronność": "Przemysł",
    "Technologie wschodzące": "Przemysł",
    "Energia jądrowa": "Energetyka", "Energia": "Energetyka",
    "Złoto": "Surowce", "Srebro": "Surowce", "Kopalnie złota": "Surowce",
    "Kopalnie srebra": "Surowce", "Surowce": "Surowce",
    "Kryptowaluty": "Aktywa cyfrowe",
    "Szeroki rynek": "Szeroki rynek", "Zabezpieczenie": "Szeroki rynek",
    "Dywidenda": "Szeroki rynek", "Defensywne": "Defensywne",
    "Gotówka": "Gotówka",
}


def _temat_z_koszyka(nazwa: str) -> str:
    """Dopasowanie od najdłuższego wzorca: „gold miners" musi wygrać z „gold",
    inaczej kopalnie złota lądują w koszyku ze złotem fizycznym."""
    k = (nazwa or "").strip().lower()
    for wzor in sorted(KOSZYK_NA_TEMAT, key=len, reverse=True):
        if wzor in k:
            return KOSZYK_NA_TEMAT[wzor]
    return (nazwa or "").strip() or "Nieprzypisane"


def klasa_instrumentu(p: dict) -> str:
    """Klasa aktywów z samego raportu - to jedyny wymiar, który Flex zna."""
    k = (p.get("klasa") or "").upper()
    if k in ("OPT", "FOP"):
        return "Opcje"
    if k == "STK":
        return "Akcje"
    if k in ("CASH", "FX"):
        return "Gotówka"
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
                                      zrodlo="arkusz wzorcowy")
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
            store.zapisz_klasyfikacje(s, TEMAT, "Nieprzypisane", zrodlo="brak")
            bez += 1
            if klucz not in braki:
                braki.append(klucz)

        if wpis and wpis.get(SEKTOR):
            store.zapisz_klasyfikacje(s, SEKTOR, str(wpis[SEKTOR]), zrodlo="mapa")
        else:
            # sektor z tematu - nie zgadujemy, tylko przekładamy znane przypisanie
            t = _temat_z_koszyka(temat_wzorca) if temat_wzorca else None
            sekt = TEMAT_NA_SEKTOR.get(t or "", "Nieprzypisane")
            store.zapisz_klasyfikacje(s, SEKTOR, sekt,
                                      zrodlo="z tematu" if sekt != "Nieprzypisane" else "brak")
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
        wpisy = klas.get(s) or [{"wartosc": "Nieprzypisane", "waga": 1.0}]
        for k in wpisy:
            suma[k["wartosc"]] = suma.get(k["wartosc"], 0.0) + w * float(k.get("waga") or 1.0)
    return sorted(
        ({"nazwa": n, "wartosc": v, "udzial": (v / calosc * 100.0) if calosc else 0.0}
         for n, v in suma.items()),
        key=lambda x: -x["wartosc"])
