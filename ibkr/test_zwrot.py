"""Testy silnika zwrotu.

Najważniejszy jest test przepływów: to on pilnuje, żeby wpłata na rachunek
nigdy nie została policzona jako zysk. Reszta to znane przykłady liczbowe,
przy których wynik da się sprawdzić na kartce.
"""
import math

import zwrot


def _szereg(wartosci, od_dnia=1):
    return [{"data": f"2026-01-{od_dnia + i:02d}", "nav": v}
            for i, v in enumerate(wartosci)]


# --------------------------------------------------------------------------- #
#  przepływy - sedno sprawy
# --------------------------------------------------------------------------- #

def test_wplata_nie_jest_zyskiem():
    """Portfel stoi w miejscu, ale dochodzi 100 000 wpłaty. Zwrot ma być zerowy,
    a nie +10%. To jest błąd, przed którym cały ten moduł ma chronić."""
    szereg = _szereg([1_000_000.0, 1_100_000.0])
    bez_korekty = (1_100_000 - 1_000_000) / 1_000_000
    assert abs(bez_korekty - 0.10) < 1e-12          # tak liczył dawny panel

    r = zwrot.zwroty_dzienne(szereg, {"2026-01-02": 100_000.0})
    assert len(r) == 1
    assert abs(r[0][1]) < 1e-12                     # zero, nie dziesięć procent
    assert abs(zwrot.twr(szereg, {"2026-01-02": 100_000.0})) < 1e-12


def test_wyplata_nie_jest_strata():
    szereg = _szereg([1_000_000.0, 900_000.0])
    r = zwrot.zwroty_dzienne(szereg, {"2026-01-02": -100_000.0})
    assert abs(r[0][1]) < 1e-12


def test_wplata_i_zysk_rozdzielone():
    """NAV rośnie o 150 000: 100 000 to wpłata, reszta to zarobek.

    Przy konwencji uzgodnionej z IBKR wpłata pracuje od początku dnia, więc
    podstawą jest 1,1 mln, a nie 1 mln: 1 150 000 / 1 100 000 - 1."""
    szereg = _szereg([1_000_000.0, 1_150_000.0])
    r = zwrot.zwroty_dzienne(szereg, {"2026-01-02": 100_000.0})
    assert abs(r[0][1] - (1_150_000 / 1_100_000 - 1)) < 1e-12


# --------------------------------------------------------------------------- #
#  TWR
# --------------------------------------------------------------------------- #

def test_twr_to_iloczyn_stop_a_nie_suma():
    """+10% i -10% pod rząd daje -1%, nie zero. Klasyczna pułapka."""
    szereg = _szereg([100.0, 110.0, 99.0])
    t = zwrot.twr(szereg)
    assert abs(t - (-0.01)) < 1e-12


def test_twr_znany_przyklad():
    szereg = _szereg([100.0, 105.0, 110.25])          # dwa razy +5%
    assert abs(zwrot.twr(szereg) - 0.1025) < 1e-12


def test_twr_bez_historii():
    assert zwrot.twr([]) is None
    assert zwrot.twr(_szereg([100.0])) is None


# --------------------------------------------------------------------------- #
#  Modified Dietz
# --------------------------------------------------------------------------- #

def test_dietz_bez_przeplywow_to_zwykla_stopa():
    d = zwrot.modified_dietz(100.0, 110.0, [], "2026-01-01", "2026-01-31")
    assert abs(d - 0.10) < 1e-12


def test_dietz_wazy_przeplyw_czasem():
    """Wpłata w połowie okresu pracuje przez połowę czasu, więc wchodzi
    do mianownika z wagą 0,5."""
    d = zwrot.modified_dietz(1000.0, 1600.0, [("2026-01-16", 500.0)],
                             "2026-01-01", "2026-01-31")
    # (1600 - 1000 - 500) / (1000 + 0.5*500) = 100 / 1250
    assert abs(d - 0.08) < 1e-6


def test_dietz_przeplyw_na_starcie_wazy_pelnym_okresem():
    d = zwrot.modified_dietz(1000.0, 1600.0, [("2026-01-02", 500.0)],
                             "2026-01-01", "2026-01-31")
    waga = (30 - 1) / 30
    assert abs(d - (100.0 / (1000.0 + waga * 500.0))) < 1e-9


def test_dietz_odrzuca_bezsens():
    assert zwrot.modified_dietz(0.0, 100.0, [], "2026-01-01", "2026-01-31") is None
    assert zwrot.modified_dietz(100.0, 110.0, [], "2026-01-31", "2026-01-01") is None


# --------------------------------------------------------------------------- #
#  XIRR
# --------------------------------------------------------------------------- #

def test_xirr_prosty_rok():
    """-1000 na starcie, +1100 po roku to dokładnie 10%."""
    r = zwrot.xirr([("2026-01-01", -1000.0), ("2027-01-01", 1100.0)])
    assert r is not None and abs(r - 0.10) < 1e-4


def test_xirr_podwojenie_w_rok():
    r = zwrot.xirr([("2026-01-01", -1000.0), ("2027-01-01", 2000.0)])
    assert abs(r - 1.0) < 1e-4


def test_xirr_nieregularne_przeplywy():
    """Sprawdzenie przez podstawienie: przy znalezionej stopie NPV musi zerować."""
    pf = [("2026-01-01", -10_000.0), ("2026-04-01", -5_000.0),
          ("2026-09-15", 2_000.0), ("2027-01-01", 14_500.0)]
    r = zwrot.xirr(pf)
    assert r is not None
    from datetime import date
    d0 = date(2026, 1, 1)
    npv = sum(k / (1.0 + r) ** ((date.fromisoformat(d) - d0).days / 365.0) for d, k in pf)
    assert abs(npv) < 1e-4


def test_xirr_wymaga_obu_znakow():
    assert zwrot.xirr([("2026-01-01", -100.0), ("2027-01-01", -50.0)]) is None
    assert zwrot.xirr([("2026-01-01", 100.0)]) is None


def test_twr_i_mwr_to_rozne_liczby():
    """Sedno rozróżnienia: portfel zarabia równo, ale duża wpłata trafia
    tuż przed słabym okresem. TWR tego nie widzi, MWR owszem."""
    szereg = [{"data": "2026-01-01", "nav": 100_000.0},
              {"data": "2026-06-01", "nav": 120_000.0},
              {"data": "2026-06-02", "nav": 620_000.0},   # wpłata 500k
              {"data": "2026-12-31", "nav": 558_000.0}]
    pf = {"2026-06-02": 500_000.0}
    t = zwrot.twr(szereg, pf)
    m = zwrot.xirr([("2026-01-01", -100_000.0), ("2026-06-02", -500_000.0),
                    ("2026-12-31", 558_000.0)])
    assert t is not None and m is not None
    assert t > 0 > m          # zarządzanie na plusie, portfel inwestora na minusie


# --------------------------------------------------------------------------- #
#  obsunięcia
# --------------------------------------------------------------------------- #

def test_obsuniecie_liczy_sie_od_szczytu_kroczacego():
    szereg = _szereg([100.0, 120.0, 90.0, 110.0])
    o = zwrot.obsuniecia(szereg)
    assert abs(o["maks"] - (90.0 / 120.0 - 1.0)) < 1e-12      # -25%
    assert o["maks_od"] == "2026-01-02" and o["maks_dno"] == "2026-01-03"
    assert abs(o["biezace"] - (110.0 / 120.0 - 1.0)) < 1e-12


def test_nowy_szczyt_zeruje_obsuniecie():
    o = zwrot.obsuniecia(_szereg([100.0, 90.0, 130.0]))
    assert abs(o["biezace"]) < 1e-12
    assert o["dni_od_szczytu"] == 0


def test_obsuniecie_wymaga_dwoch_punktow():
    assert zwrot.obsuniecia(_szereg([100.0]))["dostepne"] is False


# --------------------------------------------------------------------------- #
#  wykrywanie skoków i annualizacja
# --------------------------------------------------------------------------- #

def test_skok_nav_zostaje_oznaczony():
    """Nie zgadujemy kwoty przelewu - oznaczamy dzień jako podejrzany."""
    s = zwrot.wykryj_skoki(_szereg([100.0, 101.0, 150.0, 151.0]))
    assert len(s) == 1 and s[0]["data"] == "2026-01-03"
    assert s[0]["roznica"] == 49.0


def test_spokojny_szereg_nie_ma_skokow():
    assert zwrot.wykryj_skoki(_szereg([100.0, 101.0, 102.0, 101.5])) == []


def test_annualizacja_odmawia_przy_krotkim_okresie():
    """Zwrot z dwóch tygodni pomnożony do roku byłby liczbą efektowną
    i pozbawioną treści."""
    assert zwrot.annualizuj(0.05, 14) is None
    r = zwrot.annualizuj(0.10, 365)
    assert abs(r - 0.10) < 1e-9
    r2 = zwrot.annualizuj(0.10, 182)
    assert r2 > 0.20                          # pół roku +10% to ponad 20% rocznie


def test_konwencja_zgodna_z_ibkr():
    """Uzgodnienie wobec rzeczywistego wyciągu rocznego IBKR.

    Prawdziwe dane z rachunku, 25.08.2025: NAV 22 972,56 dzień wcześniej,
    268 578,48 po wpłacie 245 403. Portfel zarobił tego dnia grosze — cała
    reszta przyrostu to przelew.

    Obie konwencje dają wynik dodatni, ale różnią się o rząd wielkości,
    a przez 27 dni z przelewami różnica narasta do 1,3 pp w skali roku.
    Wersja z przepływem w mianowniku trafia w TWR podane przez IBKR
    (40,479%) co do trzeciego miejsca po przecinku.
    """
    szereg = [{"data": "2025-08-22", "nav": 22_972.56},
              {"data": "2025-08-25", "nav": 268_578.48}]
    pf = {"2025-08-25": 245_403.00}
    r = zwrot.zwroty_dzienne(szereg, pf)[0][1]
    # przepływ w mianowniku: 268 578,48 / (22 972,56 + 245 403) - 1
    assert abs(r - (268_578.48 / 268_375.56 - 1.0)) < 1e-12
    assert 0.0 < r < 0.002                      # ułamek procenta, nie kilkaset

    # odejmowanie w liczniku zawyża dzień o ponad rząd wielkości
    zla = (268_578.48 - 245_403.00) / 22_972.56 - 1.0
    assert zla > 10 * r


def test_przeplywy_biora_tylko_przelewy():
    """Dywidenda i odsetki to wynik portfela, nie wpłata inwestora.
    Wrzucenie ich do przepływów zaniżyłoby zwrot o to, co portfel zarobił."""
    ops = [
        {"rodzaj": "Deposits/Withdrawals", "data": "2026-01-05", "kwota": 10_000.0},
        {"rodzaj": "Dividends", "data": "2026-01-06", "kwota": 500.0},
        {"rodzaj": "Broker Interest Received", "data": "2026-01-07", "kwota": 120.0},
        {"rodzaj": "Withholding Tax", "data": "2026-01-08", "kwota": -75.0},
    ]
    pf = zwrot.przeplywy_z_operacji(ops)
    assert pf == {"2026-01-05": 10_000.0}


def test_podsumowanie_mowi_ze_danych_za_malo():
    p = zwrot.podsumowanie(_szereg([100.0, 101.0, 102.0]))
    assert p["dostepne"] is True
    assert p["wystarczajaco"] is False        # 2 obserwacje przy wymaganych 20
    assert p["obserwacji"] == 2


def test_podsumowanie_na_dlugim_szeregu():
    import random
    random.seed(7)
    nav, seria = 100_000.0, []
    for i in range(120):
        nav *= (1.0 + random.gauss(0.0005, 0.01))
        seria.append({"data": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "nav": nav})
    p = zwrot.podsumowanie(seria)
    assert p["wystarczajaco"] is True
    assert p["twr"] is not None and p["obsuniecia"]["dostepne"] is True
    assert -1.0 < p["twr"] < 5.0


def test_krzywa_twr_konczy_sie_dokladnie_na_twr():
    """Najważniejszy test tej krzywej. Jest rysowana obok wykresu NAV i ma
    prawo istnieć tylko wtedy, gdy jej koniec zgadza się co do grosza
    z liczbą w kaflu - dwie różne odpowiedzi na to samo pytanie na jednym
    ekranie są gorsze niż jedna."""
    s = _szereg([100.0, 104.0, 101.0, 109.0, 112.0])
    k = zwrot.krzywa_twr(s)
    assert len(k) == len(s)
    assert abs(k[0][1] - 100.0) < 1e-12
    assert abs(k[-1][1] / 100.0 - 1.0 - zwrot.twr(s)) < 1e-12


def test_krzywa_twr_ignoruje_przelew_ktory_podnosi_nav():
    """Sedno tej krzywej: wpłata podnosi wartość konta i NIE MOŻE podnosić
    wyniku. Bez tego wykres pokazywałby zamożność, nie skuteczność."""
    s = _szereg([100.0, 100.0, 200.0, 200.0])
    przep = {s[2]["data"]: 100.0}
    k = zwrot.krzywa_twr(s, przep)
    assert all(abs(v - 100.0) < 1e-9 for _, v in k), k    # płasko mimo podwojenia NAV
    bez = zwrot.krzywa_twr(s)
    assert bez[-1][1] > 190.0                              # bez korekty: fałszywe +100%


def test_krzywa_twr_zaczyna_sie_od_daty_pierwszego_dnia():
    s = _szereg([100.0, 101.0, 102.0])
    k = zwrot.krzywa_twr(s)
    assert k[0][0] == s[0]["data"] and k[-1][0] == s[-1]["data"]


def test_krzywa_twr_bez_historii_jest_pusta():
    assert zwrot.krzywa_twr([]) == []
    assert zwrot.krzywa_twr(_szereg([100.0])) == []
