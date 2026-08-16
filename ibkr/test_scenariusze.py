"""Testy silnika scenariuszy.

Scenariusze łatwo napisać tak, żeby dawały efektowne liczby bez treści.
Testy pilnują trzech rzeczy: że kierunek wstrząsu przekłada się poprawnie
przez betę, że krótkie opcje zachowują się jak krótkie opcje (gamma ujemna
pogłębia stratę przy ruchu w górę), i że brak danych daje uczciwą odmowę
zamiast zera.
"""
import scenariusze


CZYNNIKI = [
    {"symbol": "SPY", "opis": "US broad market", "beta": 1.25, "r2": 0.55},
    {"symbol": "QQQ", "opis": "Technology / growth", "beta": 0.79, "r2": 0.50},
    {"symbol": "GLD", "opis": "Gold", "beta": 0.25, "r2": 0.11},
    {"symbol": "UUP", "opis": "US dollar", "beta": -1.04, "r2": 0.08},
]
NAV = 800_000.0


def test_spadek_rynku_przy_becie_powyzej_jednosci_boli_mocniej():
    """Beta 1,25 znaczy, że spadek rynku o 10% to strata 12,5% portfela."""
    p = scenariusze.pojedyncze(NAV, CZYNNIKI)
    x = next(s for s in p if s["czynnik"] == "SPY" and abs(s["zmiana"] + 0.10) < 1e-9)
    assert abs(x["wplyw"] - (NAV * 1.25 * -0.10)) < 1e-6
    assert abs(x["wplyw_proc"] - (-0.125)) < 1e-9


def test_ujemna_beta_odwraca_kierunek():
    """Portfel z betą -1,04 do dolara ZYSKUJE, gdy dolar słabnie."""
    p = scenariusze.pojedyncze(NAV, CZYNNIKI)
    slabszy = next(s for s in p if s["czynnik"] == "UUP" and abs(s["zmiana"] + 0.10) < 1e-9)
    mocniejszy = next(s for s in p if s["czynnik"] == "UUP" and abs(s["zmiana"] - 0.10) < 1e-9)
    assert slabszy["wplyw"] > 0
    assert mocniejszy["wplyw"] < 0


def test_wstrzasy_skaluja_sie_liniowo():
    p = scenariusze.pojedyncze(NAV, CZYNNIKI)
    m10 = next(s for s in p if s["czynnik"] == "SPY" and abs(s["zmiana"] + 0.10) < 1e-9)
    m20 = next(s for s in p if s["czynnik"] == "SPY" and abs(s["zmiana"] + 0.20) < 1e-9)
    assert abs(m20["wplyw"] - 2 * m10["wplyw"]) < 1e-6


def test_gamma_krotkiego_calla_poglebia_strate_przy_wzroscie():
    """Krótki call ma gammę ujemną: przy ruchu w górę delta rośnie przeciwko
    nam, więc strata jest większa, niż wynikałoby z samej delty. Pominięcie
    członu gamma zaniżałoby ją dokładnie w scenariuszu, który boli."""
    opcje_ = [{"bazowy": "AAA", "spot": 100.0, "delta_akcji": -500.0, "gamma": -20.0}]
    tylko_delta = -500.0 * (100.0 * 0.10)
    z_gamma = scenariusze.wplyw_opcji(opcje_, "SPY", 0.10)
    assert z_gamma < tylko_delta                       # gorzej niż sama delta
    assert abs(z_gamma - (tylko_delta + 0.5 * (-20.0) * (10.0 ** 2))) < 1e-9


def test_gamma_dziala_tez_przy_spadku():
    """Przy ruchu w dół ujemna gamma też odejmuje - krótka opcja jest
    niekorzystna po obu stronach, tylko w różnym stopniu."""
    opcje_ = [{"bazowy": "AAA", "spot": 100.0, "delta_akcji": -500.0, "gamma": -20.0}]
    w = scenariusze.wplyw_opcji(opcje_, "SPY", -0.10)
    tylko_delta = -500.0 * (-10.0)
    assert w < tylko_delta


def test_skorelowane_czynniki_nie_licza_sie_dwa_razy():
    """Najważniejszy test tego modułu. SPY i QQQ to w dużej części te same
    spółki — portfel ma jedną ekspozycję akcyjną i dostaje po niej raz.

    Bez tego na prawdziwym portfelu scenariusz technologiczny dawał -53% NAV
    przy rocznej zmienności portfela 21%: liczba efektowna i nieprawdziwa."""
    p = scenariusze.polaczone(NAV, CZYNNIKI)
    s = next(x for x in p if x["nazwa"] == "Risk-off")
    akcyjne = [k for k in s["skladniki"] if k["grupa"] == "akcje"]
    assert len(akcyjne) >= 2                      # SPY i QQQ oba w scenariuszu
    liczone = [k for k in akcyjne if k["liczony"]]
    assert len(liczone) == 1                      # ale liczy się jeden
    # i to ten o najmocniejszym wpływie
    assert abs(liczone[0]["wplyw"]) == max(abs(k["wplyw"]) for k in akcyjne)
    # suma to wkłady wiodące z każdej grupy, nie wszystkie składniki
    assert abs(s["wplyw"] - sum(k["wplyw"] for k in s["skladniki"] if k["liczony"])) < 1e-6
    assert abs(s["nav_po"] - (NAV + s["wplyw"])) < 1e-6


def test_rozne_grupy_nadal_sie_sumuja():
    """Akcje, metale i dolar to naprawdę różne ekspozycje — te dodajemy."""
    p = scenariusze.polaczone(NAV, CZYNNIKI)
    s = next(x for x in p if x["nazwa"] == "Risk-off")
    grupy = {k["grupa"] for k in s["skladniki"] if k["liczony"]}
    assert len(grupy) >= 2 and s["grup"] == len(grupy)


def test_scenariusz_nie_przekracza_rozsadnej_skali():
    """Zabezpieczenie przed powrotem błędu: wstrząs akcyjny -22% przy becie
    poniżej 1,3 nie ma prawa zabrać ponad połowy portfela."""
    for x in scenariusze.polaczone(NAV, CZYNNIKI):
        assert abs(x["wplyw_proc"]) < 0.45, (x["nazwa"], x["wplyw_proc"])


def test_ucieczka_od_ryzyka_jest_ujemna_a_odbicie_dodatnie():
    p = {x["nazwa"]: x for x in scenariusze.polaczone(NAV, CZYNNIKI)}
    assert p["Risk-off"]["wplyw"] < 0
    assert p["Risk-on rebound"]["wplyw"] > 0


def test_najgorszy_scenariusz_jest_na_szczycie_listy():
    w = scenariusze.podsumowanie(NAV, CZYNNIKI)
    assert w["dostepne"] is True
    assert w["najgorszy"]["wplyw"] == min(x["wplyw"] for x in w["polaczone"])


def test_brak_bet_daje_uczciwa_odmowe():
    """Bez historii kursów nie ma bet, a bez bet scenariusz jest zgadywaniem.
    Zero byłoby gorsze niż przyznanie się."""
    w = scenariusze.podsumowanie(NAV, [])
    assert w["dostepne"] is False
    assert "price history" in w["powod"]


def test_czynnik_bez_bety_jest_pomijany_a_nie_zerowany():
    """SLV nie ma bety w zestawie - nie może pojawić się z wpływem zero,
    bo to sugerowałoby brak wrażliwości, a nie brak wiedzy."""
    p = scenariusze.pojedyncze(NAV, CZYNNIKI)
    assert all(s["czynnik"] != "SLV" for s in p)
