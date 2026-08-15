"""Testy silnika ryzyka.

Statystyka jest wdzięcznym miejscem na cichy błąd: wynik zawsze wygląda
sensownie. Dlatego wszędzie, gdzie się da, sprawdzamy wobec wartości
policzalnej na kartce albo wobec wzoru zamkniętego, a nie „czy wyszło
mniej więcej tyle".
"""
import math

import ryzyko


def _staly(n, r=0.001):
    return [r] * n


def _naprzemienny(n, a=0.02, b=-0.01):
    return [a if i % 2 == 0 else b for i in range(n)]


# --------------------------------------------------------------------------- #
#  podstawy statystyczne
# --------------------------------------------------------------------------- #

def test_odchylenie_na_znanym_przykladzie():
    """Próbka 2,4,4,4,5,5,7,9: odchylenie populacyjne 2, próbkowe sqrt(32/7)."""
    x = [2, 4, 4, 4, 5, 5, 7, 9]
    assert abs(ryzyko.odchylenie(x, probka=False) - 2.0) < 1e-12
    assert abs(ryzyko.odchylenie(x) - math.sqrt(32 / 7)) < 1e-12


def test_odchylenie_wymaga_dwoch_punktow():
    assert ryzyko.odchylenie([1.0]) is None
    assert ryzyko.odchylenie([]) is None


def test_korelacja_idealna_i_odwrotna():
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert abs(ryzyko.korelacja(a, a) - 1.0) < 1e-12
    assert abs(ryzyko.korelacja(a, [-x for x in a]) + 1.0) < 1e-12


def test_kowariancja_ze_soba_to_wariancja():
    a = [0.01, -0.02, 0.03, 0.005, -0.01]
    s = ryzyko.odchylenie(a)
    assert abs(ryzyko.kowariancja(a, a) - s * s) < 1e-15


# --------------------------------------------------------------------------- #
#  progi — metryka pusta nie ma prawa się pokazać
# --------------------------------------------------------------------------- #

def test_krotka_historia_nie_daje_zadnej_metryki():
    """To jest sedno: 13 dni historii nie może wyprodukować Sharpe'a."""
    krotkie = _staly(13)
    assert ryzyko.zmiennosc(krotkie) is None
    assert ryzyko.sharpe(krotkie) is None
    assert ryzyko.sortino(krotkie) is None
    assert ryzyko.var_historyczny(krotkie) is None
    assert ryzyko.cvar(krotkie) is None
    p = ryzyko.podsumowanie(krotkie)
    assert len(p["braki"]) == 3
    assert all(p[k] is None for k in ("zmiennosc", "sharpe", "sortino", "var95"))


def test_progi_wlaczaja_sie_dokladnie_na_granicy():
    assert ryzyko.zmiennosc(_naprzemienny(19)) is None
    assert ryzyko.zmiennosc(_naprzemienny(20)) is not None
    assert ryzyko.sharpe(_naprzemienny(59)) is None
    assert ryzyko.sharpe(_naprzemienny(60)) is not None
    assert ryzyko.var_historyczny(_naprzemienny(99)) is None
    assert ryzyko.var_historyczny(_naprzemienny(100)) is not None


def test_beta_wymaga_wspolnej_historii():
    assert ryzyko.beta(_staly(30), _staly(30)) is None
    assert ryzyko.beta(_naprzemienny(60), _naprzemienny(60)) is not None


# --------------------------------------------------------------------------- #
#  annualizacja
# --------------------------------------------------------------------------- #

def test_zmiennosc_annualizuje_pierwiastkiem_czasu():
    z = _naprzemienny(120)
    dzienna = ryzyko.zmiennosc(z, roczna=False)
    roczna = ryzyko.zmiennosc(z, roczna=True)
    assert abs(roczna - dzienna * math.sqrt(252)) < 1e-12


def test_zmiennosc_ujemna_dzieli_przez_wszystkie_obserwacje():
    """Portfel z rzadkimi, głębokimi spadkami nie może wyglądać spokojniej
    niż jest — mianownik obejmuje wszystkie dni, nie tylko ujemne."""
    z = [0.01] * 90 + [-0.10] * 10
    du = ryzyko.zmiennosc_ujemna(z)
    reczne = math.sqrt(sum(min(0.0, r) ** 2 for r in z) / (len(z) - 1)) * math.sqrt(252)
    assert abs(du - reczne) < 1e-12
    # gdyby dzielić przez 10 zamiast 99, wynik byłby ponad trzykrotnie większy
    zle = math.sqrt(sum(min(0.0, r) ** 2 for r in z) / 10) * math.sqrt(252)
    assert zle > du * 3


def test_sam_wzrost_daje_zerowa_zmiennosc_ujemna():
    assert abs(ryzyko.zmiennosc_ujemna([0.01] * 60)) < 1e-15


# --------------------------------------------------------------------------- #
#  ryzyko ogona
# --------------------------------------------------------------------------- #

def test_var_to_kwantyl_empiryczny():
    """Sto obserwacji od -0,50 do 0,49 — 5% kwantyl to piąta od dołu."""
    z = [(i - 50) / 100 for i in range(100)]
    v = ryzyko.var_historyczny(z, 0.95)
    assert abs(v - (-0.45)) < 1e-12


def test_cvar_jest_glebszy_niz_var():
    """VaR mówi gdzie zaczyna się ogon, CVaR jak głęboki jest."""
    z = [(i - 50) / 100 for i in range(100)]
    v, c = ryzyko.var_historyczny(z, 0.95), ryzyko.cvar(z, 0.95)
    assert c < v
    assert abs(c - sum(x for x in z if x <= v) / len([x for x in z if x <= v])) < 1e-12


def test_var99_jest_gorszy_niz_var95():
    z = [(i - 50) / 100 for i in range(200)]
    assert ryzyko.var_historyczny(z, 0.99) < ryzyko.var_historyczny(z, 0.95)


# --------------------------------------------------------------------------- #
#  beta
# --------------------------------------------------------------------------- #

def test_beta_wobec_samego_siebie_to_jeden():
    w = _naprzemienny(120)
    b = ryzyko.beta(w, w)
    assert abs(b["beta"] - 1.0) < 1e-12
    assert abs(b["r2"] - 1.0) < 1e-12
    assert abs(b["blad_odwzorowania"]) < 1e-12


def test_beta_dwukrotnie_lewarowana():
    w = _naprzemienny(120)
    p = [2 * x for x in w]
    b = ryzyko.beta(p, w)
    assert abs(b["beta"] - 2.0) < 1e-12
    assert abs(b["r2"] - 1.0) < 1e-12


def test_beta_odwrotna_dla_pozycji_zabezpieczajacej():
    """Fundusz odwrotny musi mieć betę ujemną — inaczej zabezpieczenie
    wyglądałoby jak zwykła ekspozycja."""
    w = _naprzemienny(120)
    b = ryzyko.beta([-x for x in w], w)
    assert abs(b["beta"] + 1.0) < 1e-12
    assert b["korelacja"] < 0


def test_alfa_wychodzi_gdy_portfel_dokłada_stala_nadwyzke():
    w = _naprzemienny(120)
    p = [x + 0.001 for x in w]              # +0,1 pp dziennie ponad wzorzec
    b = ryzyko.beta(p, w)
    assert abs(b["beta"] - 1.0) < 1e-9
    assert abs(b["alfa_roczna"] - 0.001 * 252) < 1e-9


# --------------------------------------------------------------------------- #
#  wkład do ryzyka
# --------------------------------------------------------------------------- #

def test_wklady_skladowe_sumuja_sie_do_calosci():
    """Własność definicyjna: suma wkładów składowych równa się zmienności
    portfela. Jeśli to nie wychodzi, wzór jest zły."""
    import random
    random.seed(11)
    zwroty = {s: [random.gauss(0, 0.01 * (i + 1)) for _ in range(150)]
              for i, s in enumerate(["A", "B", "C"])}
    wagi = {"A": 0.5, "B": 0.3, "C": 0.2}
    w = ryzyko.wklad_do_ryzyka(wagi, zwroty)
    assert w is not None
    suma = sum(p["udzial_w_ryzyku"] for p in w["pozycje"])
    assert abs(suma - 1.0) < 1e-9


def test_pozycja_zmienna_wnosi_wiecej_ryzyka_niz_kapitalu():
    """Sedno całego modułu: udział w ryzyku to nie udział w kapitale."""
    import random
    random.seed(3)
    spokojna = [random.gauss(0, 0.004) for _ in range(200)]
    dzika = [random.gauss(0, 0.040) for _ in range(200)]
    w = ryzyko.wklad_do_ryzyka({"SPOKOJNA": 0.8, "DZIKA": 0.2},
                               {"SPOKOJNA": spokojna, "DZIKA": dzika})
    poz = {p["symbol"]: p for p in w["pozycje"]}
    assert poz["DZIKA"]["udzial_w_ryzyku"] > poz["DZIKA"]["waga"]
    assert poz["SPOKOJNA"]["udzial_w_ryzyku"] < poz["SPOKOJNA"]["waga"]
    assert poz["DZIKA"]["krotnosc"] > 2.0        # wnosi ponad dwa razy więcej


def test_wklad_wymaga_dwoch_instrumentow():
    assert ryzyko.wklad_do_ryzyka({"A": 1.0}, {"A": [0.01] * 100}) is None


# --------------------------------------------------------------------------- #
#  koncentracja
# --------------------------------------------------------------------------- #

def test_koncentracja_rownych_pozycji():
    """Dziesięć równych pozycji: HHI = 1000, efektywna liczba = 10."""
    k = ryzyko.koncentracja({f"S{i}": 100.0 for i in range(10)})
    assert abs(k["hhi"] - 1000.0) < 1e-9
    assert abs(k["efektywna_liczba"] - 10.0) < 1e-9
    assert abs(k["top5"] - 50.0) < 1e-9


def test_liczba_pozycji_to_nie_dywersyfikacja():
    """Pięćdziesiąt pozycji, ale trzy to 90% wartości. Efektywna liczba
    musi to obnażyć."""
    w = {"A": 300.0, "B": 300.0, "C": 300.0}
    w.update({f"D{i}": 100.0 / 47 for i in range(47)})
    k = ryzyko.koncentracja(w)
    assert k["pozycji"] == 50
    assert k["top3"] > 89.0
    assert k["efektywna_liczba"] < 4.0        # zachowuje się jak niecałe 4 pozycje


def test_koncentracja_pustego_portfela():
    assert ryzyko.koncentracja({})["dostepne"] is False


def test_calmar():
    assert abs(ryzyko.calmar(0.20, -0.10) - 2.0) < 1e-12
    assert ryzyko.calmar(0.20, None) is None
    assert ryzyko.calmar(None, -0.10) is None
    assert ryzyko.calmar(0.20, 0.0) is None
