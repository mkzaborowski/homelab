"""Sprawdzenie matematyki opcyjnej.

Greki weryfikujemy różnicami skończonymi: liczymy pochodną numerycznie
z samej funkcji wyceny i porównujemy ze wzorem analitycznym. Jeśli wzór
jest przepisany z błędem, ta metoda to wychwyci - nie da się oszukać
obu dróg tym samym pomyłkowym znakiem.
"""
import math

import opcje

R, Q = 0.0425, 0.0
BLAD = 1e-6


def _pochodna(f, x, h):
    return (f(x + h) - f(x - h)) / (2.0 * h)


PRZYPADKI = [
    # S,     K,     T,      sigma, prawo
    (100.0, 100.0, 1.0, 0.20, "C"),
    (100.0, 100.0, 1.0, 0.20, "P"),
    (4.37, 5.00, 7 / 365, 0.85, "C"),      # ANGX, tydzień do wygaśnięcia
    (19.01, 21.00, 35 / 365, 0.95, "C"),   # LUNR
    (8.92, 10.00, 35 / 365, 0.50, "C"),    # MBLY
    (150.0, 120.0, 0.5, 0.35, "C"),        # głęboko w pieniądzu
    (50.0, 80.0, 0.25, 0.60, "P"),
]


def test_wycena_zgodna_z_tablica():
    """Klasyczny przykład podręcznikowy: S=K=100, T=1, r=0, sigma=0.20."""
    c = opcje.wycen(100, 100, 1.0, 0.0, 0.0, 0.20, "C")
    assert abs(c - 7.9656) < 1e-3, c
    p = opcje.wycen(100, 100, 1.0, 0.0, 0.0, 0.20, "P")
    assert abs(p - 7.9656) < 1e-3, p        # przy r=0 i S=K call i put są równe


def test_parytet_call_put():
    for S, K, T, sig, _ in PRZYPADKI:
        c = opcje.wycen(S, K, T, R, Q, sig, "C")
        p = opcje.wycen(S, K, T, R, Q, sig, "P")
        lewa = c - p
        prawa = S * math.exp(-Q * T) - K * math.exp(-R * T)
        assert abs(lewa - prawa) < 1e-9, (S, K, T, sig, lewa, prawa)


def test_delta_rowna_pochodnej_po_kursie():
    for S, K, T, sig, prawo in PRZYPADKI:
        g = opcje.greki(S, K, T, R, Q, sig, prawo)
        num = _pochodna(lambda x: opcje.wycen(x, K, T, R, Q, sig, prawo), S, S * 1e-5)
        assert abs(g["delta"] - num) < 1e-5, (S, K, prawo, g["delta"], num)


def test_gamma_rowna_drugiej_pochodnej():
    for S, K, T, sig, prawo in PRZYPADKI:
        g = opcje.greki(S, K, T, R, Q, sig, prawo)
        h = S * 1e-4
        num = (opcje.wycen(S + h, K, T, R, Q, sig, prawo)
               - 2 * opcje.wycen(S, K, T, R, Q, sig, prawo)
               + opcje.wycen(S - h, K, T, R, Q, sig, prawo)) / (h * h)
        assert abs(g["gamma"] - num) < 1e-4, (S, K, prawo, g["gamma"], num)


def test_vega_na_punkt_procentowy():
    for S, K, T, sig, prawo in PRZYPADKI:
        g = opcje.greki(S, K, T, R, Q, sig, prawo)
        num = _pochodna(lambda x: opcje.wycen(S, K, T, R, Q, x, prawo), sig, 1e-6)
        assert abs(g["vega"] - num / 100.0) < 1e-5, (S, K, prawo, g["vega"], num / 100)


def test_theta_na_dzien():
    """Theta to spadek wartości przy skracaniu czasu, więc pochodna po T ze znakiem minus."""
    for S, K, T, sig, prawo in PRZYPADKI:
        g = opcje.greki(S, K, T, R, Q, sig, prawo)
        num = -_pochodna(lambda x: opcje.wycen(S, K, x, R, Q, sig, prawo), T, 1e-6)
        assert abs(g["theta"] - num / 365.0) < 1e-5, (S, K, prawo, g["theta"], num / 365)


def test_rho_na_punkt_procentowy():
    for S, K, T, sig, prawo in PRZYPADKI:
        g = opcje.greki(S, K, T, R, Q, sig, prawo)
        num = _pochodna(lambda x: opcje.wycen(S, K, T, x, Q, sig, prawo), R, 1e-7)
        assert abs(g["rho"] - num / 100.0) < 1e-5, (S, K, prawo, g["rho"], num / 100)


def test_vanna_rowna_pochodnej_delty_po_zmiennosci():
    for S, K, T, sig, prawo in PRZYPADKI:
        g = opcje.greki(S, K, T, R, Q, sig, prawo)
        num = _pochodna(
            lambda x: opcje.greki(S, K, T, R, Q, x, prawo)["delta"], sig, 1e-6)
        assert abs(g["vanna"] - num) < 1e-4, (S, K, prawo, g["vanna"], num)


def test_zmiennosc_implikowana_wraca_do_ceny():
    """Najważniejszy test odwracania modelu: cena -> IV -> ta sama cena."""
    for S, K, T, sig, prawo in PRZYPADKI:
        cena = opcje.wycen(S, K, T, R, Q, sig, prawo)
        iv = opcje.zmiennosc_implikowana(cena, S, K, T, R, Q, prawo)
        assert iv is not None, (S, K, prawo)
        assert abs(iv - sig) < 1e-6, (S, K, prawo, iv, sig)


def test_iv_dla_skrajnych_zmiennosci():
    for sig in (0.05, 0.15, 1.5, 3.0, 6.0):
        S, K, T, prawo = 20.0, 22.0, 0.1, "C"
        cena = opcje.wycen(S, K, T, R, Q, sig, prawo)
        iv = opcje.zmiennosc_implikowana(cena, S, K, T, R, Q, prawo)
        assert iv is not None and abs(iv - sig) < 1e-5, (sig, iv)


def test_iv_odmawia_gdy_cena_bez_sensu():
    """Cena poniżej wartości wewnętrznej nie ma rozwiązania - ma być None,
    a nie wymyślona liczba."""
    assert opcje.zmiennosc_implikowana(0.01, 150.0, 100.0, 0.5, R, Q, "C") is None
    assert opcje.zmiennosc_implikowana(500.0, 100.0, 100.0, 0.5, R, Q, "C") is None
    assert opcje.zmiennosc_implikowana(1.0, 100.0, 100.0, 0.0, R, Q, "C") is None


def test_prawdopodobienstwo_itm_w_granicach():
    for S, K, T, sig, prawo in PRZYPADKI:
        p = opcje.prawd_w_pieniadzu(S, K, T, R, Q, sig, prawo)
        assert 0.0 <= p <= 1.0
    # głęboko w pieniądzu -> prawie pewne; głęboko poza -> prawie zero
    assert opcje.prawd_w_pieniadzu(200, 100, 0.1, R, Q, 0.2, "C") > 0.99
    assert opcje.prawd_w_pieniadzu(50, 100, 0.1, R, Q, 0.2, "C") < 0.01


def test_dotkniecie_zawsze_nie_mniejsze_niz_itm():
    """Dotknięcie bariery po drodze nie może być mniej prawdopodobne
    niż zakończenie powyżej niej - ale też nie może być pewne."""
    for S, K, T, sig in ((19.01, 21.0, 0.096, 0.95), (8.92, 10.0, 0.096, 0.5),
                         (4.37, 5.0, 0.019, 0.85), (100, 110, 1.0, 0.3)):
        itm = opcje.prawd_w_pieniadzu(S, K, T, R, Q, sig, "C")
        dot = opcje.prawd_dotkniecia(S, K, T, R, Q, sig)
        assert dot >= itm - 1e-9, (S, K, itm, dot)
        assert dot < 0.999, (S, K, dot)      # pewność zdradza zły wzór


def test_dotkniecie_bez_dryfu_to_podwojone_itm():
    """Sprawdzian zamknięty: gdy dryf znika (r - q = sigma^2/2), zasada
    odbicia daje dokładnie 2*N(-b/(sigma*sqrt(T))). Ten test wyłapuje błąd
    znaku, którego nierówność wobec P(ITM) nie widzi - zawyżone wartości
    ją spełniają."""
    for S, K, T, sig in ((100.0, 110.0, 1.0, 0.30), (19.01, 21.0, 0.096, 0.95),
                         (4.37, 5.0, 0.019, 0.85), (50.0, 51.0, 0.5, 0.25)):
        r0 = 0.5 * sig * sig                  # tak dobrane, by mu = 0
        licz = opcje.prawd_dotkniecia(S, K, T, r0, 0.0, sig)
        wzor = 2.0 * opcje.Fi(-math.log(K / S) / (sig * math.sqrt(T)))
        assert abs(licz - wzor) < 1e-12, (S, K, licz, wzor)


def test_dotkniecie_zgadza_sie_z_symulacja():
    """Kontrola niezależna od wzoru: symulujemy ścieżki i liczymy, jak często
    kurs dotyka strike'a.

    Symulacja sprawdza barierę skokowo, a wzór zakłada obserwację ciągłą -
    ścieżka potrafi przeskoczyć barierę między krokami i wrócić, więc surowa
    symulacja systematycznie zaniża trafienia. Porównujemy więc z poprawką
    ciągłości Broadiego-Glassermana-Kou: bariera dyskretna odpowiada ciągłej
    przesuniętej o exp(0.5826 * sigma * sqrt(dt)).
    """
    import random
    random.seed(20260814)
    S, K, T, sig, r = 19.01, 21.0, 35 / 365, 0.95, 0.0425
    krokow, sciezek = 400, 40000
    dt = T / krokow
    dryf = (r - 0.5 * sig * sig) * dt
    zmien = sig * math.sqrt(dt)
    prog = math.log(K / S)
    trafien = 0
    for _ in range(sciezek):
        x = 0.0
        for _ in range(krokow):
            x += dryf + zmien * random.gauss(0.0, 1.0)
            if x >= prog:
                trafien += 1
                break
    z_symulacji = trafien / sciezek
    blad = 2.0 * math.sqrt(z_symulacji * (1 - z_symulacji) / sciezek)   # 2 sigma
    K_popr = K * math.exp(0.5826 * sig * math.sqrt(dt))
    z_modelu = opcje.prawd_dotkniecia(S, K_popr, T, r, 0.0, sig)
    assert abs(z_modelu - z_symulacji) < max(blad, 0.005), (z_modelu, z_symulacji, blad)
    # wersja ciągła musi leżeć powyżej dyskretnej - inaczej znak jest zły
    assert opcje.prawd_dotkniecia(S, K, T, r, 0.0, sig) > z_symulacji


def test_wygasla_opcja_to_wartosc_wewnetrzna():
    assert opcje.wycen(120, 100, 0.0, R, Q, 0.3, "C") == 20.0
    assert opcje.wycen(80, 100, 0.0, R, Q, 0.3, "C") == 0.0
    assert opcje.wycen(80, 100, 0.0, R, Q, 0.3, "P") == 20.0
    g = opcje.greki(120, 100, 0.0, R, Q, 0.3, "C")
    assert g["delta"] == 1.0 and g["gamma"] == 0.0 and g["theta"] == 0.0


def test_analiza_covered_calla_na_prawdziwych_danych():
    """Dane odwzorowują rzeczywisty stan rachunku z 14.08.2026."""
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "LUNR", "ilosc": 220, "cena": 19.01, "koszt": 3133.9},
        {"klasa": "STK", "symbol": "LUNR", "ilosc": 250, "cena": 19.01, "koszt": 3563.75},
        {"klasa": "OPT", "symbol": "LUNR  260918C00021000", "bazowy": "LUNR",
         "prawo": "C", "strike": 21.0, "wygasa": "20260918", "ilosc": -4.0,
         "cena": 1.56, "wartosc": -624.0, "koszt": -693.239302, "zysk": 69.239302},
    ]}
    poz = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))
    assert len(poz) == 1
    p = poz[0]
    assert p.krotka and p.kontraktow == 4
    assert p.dni == 35
    assert abs(p.premia - 693.239302) < 1e-6
    assert abs(p.wartosc_biezaca - 624.0) < 1e-9
    assert p.akcje_pod == 470 and p.pokrycie > 1.0        # w pełni pokryty
    assert p.iv is not None and 0.1 < p.iv < 5.0
    # krótki call: delta pozycji ujemna, theta dodatnia (czas pracuje na nas)
    assert p.delta_akcji < 0
    assert p.theta_dzienna > 0
    assert p.vega_pozycji < 0                             # krótka zmienność
    # cena efektywna sprzedaży = strike + premia na akcję
    assert abs(p.cena_wykonania_efektywna - (21.0 + 693.239302 / 400)) < 1e-9
    assert not p.uwagi or all("Niepokryte" not in u for u in p.uwagi)


def test_pozycja_niepokryta_jest_oznaczona():
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "XYZ", "ilosc": 100, "cena": 10.0},
        {"klasa": "OPT", "symbol": "XYZ   260918C00012000", "bazowy": "XYZ",
         "prawo": "C", "strike": 12.0, "wygasa": "20260918", "ilosc": -3.0,
         "cena": 0.30, "wartosc": -90.0, "koszt": -95.0, "zysk": 5.0},
    ]}
    p = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))[0]
    assert abs(p.pokrycie - 100 / 300) < 1e-9
    assert any("Niepokryte" in u for u in p.uwagi)
    assert any("200" in u for u in p.uwagi)


def test_scalanie_lotow_tego_samego_kontraktu():
    """Dwa loty ANGX to jedna pozycja 21 kontraktów, nie dwie."""
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "ANGX", "ilosc": 2199, "cena": 4.37},
        {"klasa": "OPT", "symbol": "ANGX  260821C00005000", "bazowy": "ANGX",
         "prawo": "C", "strike": 5.0, "wygasa": "20260821", "ilosc": -5.0,
         "cena": 0.05, "wartosc": -25.0, "koszt": -27.281532, "zysk": 2.281532},
        {"klasa": "OPT", "symbol": "ANGX  260821C00005000", "bazowy": "ANGX",
         "prawo": "C", "strike": 5.0, "wygasa": "20260821", "ilosc": -16.0,
         "cena": 0.05, "wartosc": -80.0, "koszt": -87.300902, "zysk": 7.300902},
    ]}
    poz = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))
    assert len(poz) == 1
    assert poz[0].kontraktow == 21
    assert abs(poz[0].premia - (27.281532 + 87.300902)) < 1e-9
    assert poz[0].pokrycie >= 1.0                         # 2199 akcji na 2100


def test_podsumowanie_sumuje_sie():
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "LUNR", "ilosc": 470, "cena": 19.01},
        {"klasa": "STK", "symbol": "MBLY", "ilosc": 1317, "cena": 8.92},
        {"klasa": "OPT", "symbol": "LUNR  260918C00021000", "bazowy": "LUNR",
         "prawo": "C", "strike": 21.0, "wygasa": "20260918", "ilosc": -4.0,
         "cena": 1.56, "wartosc": -624.0, "koszt": -693.24, "zysk": 69.24},
        {"klasa": "OPT", "symbol": "MBLY  260918C00010000", "bazowy": "MBLY",
         "prawo": "C", "strike": 10.0, "wygasa": "20260918", "ilosc": -13.0,
         "cena": 0.25, "wartosc": -325.0, "koszt": -296.54, "zysk": -28.46},
    ]}
    poz = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))
    s = opcje.podsumuj(poz)
    assert s["pozycji"] == 2 and s["kontraktow"] == 17
    assert abs(s["premia"] - (693.24 + 296.54)) < 1e-6
    assert abs(s["do_zainkasowania"] - (624.0 + 325.0)) < 1e-6
    assert s["theta_dzienna"] > 0 and s["delta_akcji"] < 0
    assert s["bez_grekow"] == 0


def test_premia_rozdziela_brutto_netto_i_zrealizowany():
    """Dane 1:1 z rachunku: cztery sprzedaże calli 14.08.2026."""
    tr = [
        {"klasa": "OPT", "data": "2026-08-14", "ilosc": -5, "wartosc": 30.0,
         "prowizja": -2.72, "zysk_zrealizowany": 0.0},
        {"klasa": "OPT", "data": "2026-08-14", "ilosc": -16, "wartosc": 96.0,
         "prowizja": -8.70, "zysk_zrealizowany": 0.0},
        {"klasa": "OPT", "data": "2026-08-14", "ilosc": -4, "wartosc": 696.0,
         "prowizja": -2.76, "zysk_zrealizowany": 0.0},
        {"klasa": "OPT", "data": "2026-08-14", "ilosc": -13, "wartosc": 312.0,
         "prowizja": -15.46, "zysk_zrealizowany": 0.0},
        {"klasa": "STK", "data": "2026-08-14", "ilosc": 100, "wartosc": -900.0,
         "prowizja": -1.0, "zysk_zrealizowany": 0.0},        # akcje mają być pominięte
    ]
    w = opcje.premia_okresu(tr, "2026-08-01", "2026-08-31")
    assert w["transakcji"] == 4
    assert abs(w["brutto"] - 1134.0) < 1e-9
    assert abs(w["prowizje"] - 29.64) < 1e-9
    assert abs(w["netto"] - 1104.36) < 1e-9
    assert w["kontraktow_sprzedanych"] == 38
    assert w["zrealizowany"] == 0.0          # nic jeszcze nie domknięte


def test_premia_liczy_odkupienie_i_wynik():
    tr = [
        {"klasa": "OPT", "data": "2026-08-05", "ilosc": -10, "wartosc": 500.0,
         "prowizja": -5.0, "zysk_zrealizowany": 0.0},
        {"klasa": "OPT", "data": "2026-08-20", "ilosc": 10, "wartosc": -120.0,
         "prowizja": -5.0, "zysk_zrealizowany": 370.0},      # odkupione taniej
    ]
    w = opcje.premia_okresu(tr, "2026-08-01", "2026-08-31")
    assert abs(w["brutto"] - 500.0) < 1e-9
    assert abs(w["odkup"] - 120.0) < 1e-9
    assert abs(w["netto"] - 490.0) < 1e-9
    assert abs(w["zrealizowany"] - 370.0) < 1e-9
    assert w["kontraktow_odkupionych"] == 10


def test_premia_respektuje_granice_okresu():
    tr = [
        {"klasa": "OPT", "data": "2026-07-31", "ilosc": -1, "wartosc": 100.0,
         "prowizja": -1.0, "zysk_zrealizowany": 0.0},
        {"klasa": "OPT", "data": "2026-08-01", "ilosc": -1, "wartosc": 200.0,
         "prowizja": -1.0, "zysk_zrealizowany": 0.0},
        {"klasa": "OPT", "data": "2026-09-01", "ilosc": -1, "wartosc": 400.0,
         "prowizja": -1.0, "zysk_zrealizowany": 0.0},
    ]
    w = opcje.premia_okresu(tr, "2026-08-01", "2026-08-31")
    assert w["transakcji"] == 1 and abs(w["brutto"] - 200.0) < 1e-9


def _lunr():
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "LUNR", "ilosc": 470, "cena": 19.01},
        {"klasa": "OPT", "symbol": "LUNR  260918C00021000", "bazowy": "LUNR",
         "prawo": "C", "strike": 21.0, "wygasa": "20260918", "ilosc": -4.0,
         "cena": 1.56, "wartosc": -624.0, "koszt": -693.239302, "zysk": 69.239302},
    ]}
    return opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))[0]


def test_scenariusz_maksymalny_zysk_opcji_to_cala_premia():
    """Gdy kurs jest poniżej strike'a, krótki call oddaje pełną premię."""
    p = _lunr()
    sc = opcje.scenariusze(p)
    ponizej = [s for s in sc if s["kurs"] < p.strike]
    assert ponizej, "brak scenariusza poniżej strike'a"
    for s in ponizej:
        assert abs(s["opcja"] - p.premia) < 1e-9
        assert not s["przypisanie"]


def test_scenariusz_powyzej_strike_zysk_jest_zablokowany():
    """Istota covered calla: powyżej strike'a każdy dalszy wzrost akcji jest
    w całości oddawany na opcji, więc wynik łączny stoi w miejscu."""
    p = _lunr()
    sc = {round(s["zmiana"], 2): s for s in opcje.scenariusze(p)}
    # +10% to kurs 20,91 - wciąż PONIŻEJ strike'a 21,00, przypisania nie ma
    assert not sc[0.10]["przypisanie"]
    assert abs(sc[0.10]["opcja"] - p.premia) < 1e-9
    # +20% i +30% są już powyżej strike'a
    assert sc[0.20]["przypisanie"] and sc[0.30]["przypisanie"]
    assert sc[0.30]["akcje"] > sc[0.20]["akcje"]              # akcje dalej rosną
    assert abs(sc[0.30]["razem"] - sc[0.20]["razem"]) < 1e-6  # a wynik już nie
    # sufit zysku = premia + ruch do strike'a na pokrytych akcjach
    sufit = p.premia + (p.strike - p.kurs_bazowego) * min(p.akcje_pod, p.akcje_zaangazowane)
    assert abs(sc[0.30]["razem"] - sufit) < 1e-6


def test_scenariusz_pokryty_call_nie_traci_wiecej_niz_akcje():
    """Premia zawsze poprawia wynik względem samego trzymania akcji."""
    p = _lunr()
    for s in opcje.scenariusze(p):
        sama_akcja = s["akcje"]
        assert s["razem"] >= sama_akcja - 1e-9 or s["przypisanie"]


def test_scenariusz_bez_kursu_bazowego_jest_pusty():
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "OPT", "symbol": "ZZZ   260918C00010000", "bazowy": "ZZZ",
         "prawo": "C", "strike": 10.0, "wygasa": "20260918", "ilosc": -1.0,
         "cena": 0.5, "wartosc": -50.0, "koszt": -55.0, "zysk": 5.0},
    ]}
    p = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))[0]
    assert opcje.scenariusze(p) == []
    assert any("Brak kursu bazowego" in u for u in p.uwagi)


def test_prog_odkupu_zaostrza_sie_blisko_wygasniecia():
    """Im mniej czasu, tym mniej sensu płacić za zamknięcie - theta zrobi to
    za darmo. Próg zainkasowanej premii musi więc rosnąć."""
    assert opcje.udzial_docelowy(40) == 0.50
    assert opcje.udzial_docelowy(22) == 0.50
    assert opcje.udzial_docelowy(21) == 0.65
    assert opcje.udzial_docelowy(8) == 0.65
    assert opcje.udzial_docelowy(7) == 0.80
    assert opcje.udzial_docelowy(0) == 0.80


def test_odwrocenie_ceny_po_kursie_wraca_do_punktu_wyjscia():
    """Kluczowy test progu: cena -> kurs -> ta sama cena."""
    K, T, sig, prawo = 21.0, 35 / 365, 0.95, "C"
    for S in (14.0, 19.01, 25.0):
        cena = opcje.wycen(S, K, T, R, Q, sig, prawo)
        wstecz = opcje.kurs_dla_ceny_opcji(cena, K, T, R, Q, sig, prawo)
        assert wstecz is not None and abs(wstecz - S) < 1e-6, (S, wstecz)


def test_nizsza_cena_docelowa_to_nizszy_kurs():
    """Cena calla rośnie z kursem, więc tańszy odkup wymaga niższego kursu."""
    K, T, sig = 21.0, 35 / 365, 0.95
    poprzedni = None
    for cel in (2.0, 1.5, 1.0, 0.5, 0.2):
        k = opcje.kurs_dla_ceny_opcji(cel, K, T, R, Q, sig, "C")
        assert k is not None
        if poprzedni is not None:
            assert k < poprzedni, (cel, k, poprzedni)
        poprzedni = k


def test_prog_odkupu_na_realnej_pozycji():
    p = _lunr()
    o = opcje.prog_odkupu(p)
    assert o is not None
    # 35 dni -> próg 50%
    assert o["udzial_docelowy"] == 0.50
    na_akcje = p.premia / p.akcje_zaangazowane
    assert abs(o["cena_docelowa"] - na_akcje * 0.5) < 1e-9
    assert abs(o["zysk_docelowy"] - p.premia * 0.5) < 1e-6
    # cena dziś (1,56) jest wyżej niż próg, więc alert jeszcze nie działa
    assert not o["osiagniety"]
    # kurs, przy którym opcja spadłaby do progu, musi być poniżej dzisiejszego
    assert o["kurs_docelowy"] is not None
    assert o["kurs_docelowy"] < p.kurs_bazowego
    # poziomy są uporządkowane: więcej zainkasowane = taniej i niżej
    poz = o["poziomy"]
    assert [x["udzial"] for x in poz] == [0.50, 0.65, 0.80, 0.90]
    for a, b in zip(poz, poz[1:]):
        assert b["cena"] < a["cena"] and b["zysk"] > a["zysk"]
        assert b["kurs_bazowego"] < a["kurs_bazowego"]


def test_alert_wlacza_sie_gdy_cena_spadnie():
    """Ta sama pozycja, ale opcja potaniała z 1,56 do 0,60 - poniżej progu 50%
    (0,8666 na akcję). Alert ma się odezwać."""
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "LUNR", "ilosc": 470, "cena": 15.50},
        {"klasa": "OPT", "symbol": "LUNR  260918C00021000", "bazowy": "LUNR",
         "prawo": "C", "strike": 21.0, "wygasa": "20260918", "ilosc": -4.0,
         "cena": 0.60, "wartosc": -240.0, "koszt": -693.239302, "zysk": 453.24},
    ]}
    p = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))[0]
    o = opcje.prog_odkupu(p)
    assert o["osiagniety"]
    assert any("progu" in x for x in o["powody"])
    # zysk z odkupu to premia minus koszt zamknięcia
    assert abs((p.premia - p.wartosc_biezaca) - 453.239302) < 1e-6


def test_alert_gdy_zostalo_grosze_a_duzo_czasu():
    """Drugi powód: pozostała premia daje już znikomy zwrot w skali roku."""
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "MBLY", "ilosc": 1300, "cena": 8.92},
        {"klasa": "OPT", "symbol": "MBLY  260918C00010000", "bazowy": "MBLY",
         "prawo": "C", "strike": 10.0, "wygasa": "20260918", "ilosc": -13.0,
         "cena": 0.01, "wartosc": -13.0, "koszt": -296.54, "zysk": 283.54},
    ]}
    p = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))[0]
    o = opcje.prog_odkupu(p)
    assert o["osiagniety"]
    assert o["zwrot_pozostaly"] < opcje.MIN_ZWROT_POZOSTALY


def test_prog_odkupu_tylko_dla_krotkich():
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "AAA", "ilosc": 0, "cena": 10.0},
        {"klasa": "OPT", "symbol": "AAA   260918C00012000", "bazowy": "AAA",
         "prawo": "C", "strike": 12.0, "wygasa": "20260918", "ilosc": 2.0,
         "cena": 0.5, "wartosc": 100.0, "koszt": 110.0, "zysk": -10.0},
    ]}
    p = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))[0]
    assert not p.krotka
    assert opcje.prog_odkupu(p) is None


def test_zestawienie_miesieczne_grupuje_i_liczy():
    tr = [
        {"klasa": "OPT", "data": "2026-07-15", "bazowy": "LUNR", "ilosc": -2,
         "wartosc": 300.0, "prowizja": -2.0, "zysk_zrealizowany": 0.0},
        {"klasa": "OPT", "data": "2026-07-30", "bazowy": "LUNR", "ilosc": 2,
         "wartosc": -80.0, "prowizja": -2.0, "zysk_zrealizowany": 216.0},
        {"klasa": "OPT", "data": "2026-08-14", "bazowy": "MBLY", "ilosc": -13,
         "wartosc": 312.0, "prowizja": -15.46, "zysk_zrealizowany": 0.0},
        {"klasa": "OPT", "data": "2026-08-14", "bazowy": "LUNR", "ilosc": -4,
         "wartosc": 696.0, "prowizja": -2.76, "zysk_zrealizowany": 0.0},
        {"klasa": "STK", "data": "2026-08-14", "bazowy": "", "ilosc": 100,
         "wartosc": -900.0, "prowizja": -1.0, "zysk_zrealizowany": 0.0},
    ]
    m = opcje.miesiace(tr)
    assert [x["miesiac"] for x in m] == ["2026-08", "2026-07"]   # od najnowszego
    sierpien, lipiec = m
    assert sierpien["nazwa"] == "sierpień 2026"
    assert abs(sierpien["brutto"] - 1008.0) < 1e-9
    assert abs(sierpien["netto"] - (1008.0 - 18.22)) < 1e-9
    assert {s["bazowy"] for s in sierpien["spolki"]} == {"LUNR", "MBLY"}
    # LUNR wyżej, bo więcej netto
    assert sierpien["spolki"][0]["bazowy"] == "LUNR"
    assert abs(lipiec["zrealizowany"] - 216.0) < 1e-9
    assert abs(lipiec["odkup"] - 80.0) < 1e-9


def test_nazwa_miesiaca_po_polsku():
    assert opcje.nazwa_miesiaca("2026-08") == "sierpień 2026"
    assert opcje.nazwa_miesiaca("2026-01") == "styczeń 2026"
    assert opcje.nazwa_miesiaca("bzdura") == "bzdura"


def test_stan_alertu_odpala_sie_raz_i_odbezpiecza():
    """Alert ma odezwać się przy przekroczeniu progu, milczeć przy kolejnych
    pobraniach i móc odezwać się ponownie, gdy cena wróci i znów spadnie."""
    import os, tempfile, importlib
    kat = tempfile.mkdtemp()
    os.environ["IBKR_DANE"] = kat
    import store
    importlib.reload(store)
    store.zainicjuj()

    a = {"symbol": "LUNR  260918C00021000", "etykieta": "LUNR call 21",
         "powody": ["cena opcji spadła do progu"], "cena_teraz": 0.60,
         "cena_docelowa": 0.87, "kurs_bazowego": 15.5, "zysk": 453.24,
         "kontraktow": 4}

    assert len(store.przetworz_alerty([a])) == 1        # pierwsze przekroczenie
    assert len(store.przetworz_alerty([a])) == 0        # to samo -> cisza
    assert len(store.przetworz_alerty([a])) == 0
    assert len(store.stan_alertow()) == 1

    store.przetworz_alerty([])                          # cena wróciła powyżej progu
    assert len(store.stan_alertow()) == 0
    assert len(store.przetworz_alerty([a])) == 1        # znowu spadła -> alert wraca


def test_powiadomienie_bez_konfiguracji_nie_udaje_sukcesu():
    import powiadom
    ok, opis = powiadom.wyslij([{"etykieta": "X", "cena_teraz": 1.0,
                                 "cena_docelowa": 0.5, "kurs_bazowego": 10.0,
                                 "zysk": 100.0, "kontraktow": 1, "powody": ["test"]}])
    assert ok is False
    assert "kanał" in opis or "brakuje" in opis
    # brak alertów to poprawny wynik, nie błąd
    assert powiadom.wyslij([])[0] is True


def test_normalizacja_symbolu_opcji():
    import notowania
    assert notowania.symbol_opcji("LUNR  260918C00021000") == "LUNR260918C00021000"
    assert notowania.symbol_opcji("ANGX  260821C00005000") == "ANGX260821C00005000"
    assert notowania.symbol_opcji("lunr") == "LUNR"
    assert notowania.symbol_opcji("") == ""


def test_cena_z_notowania_woli_srodek_widelek():
    """Przy niepłynnej serii „last" bywa sprzed godzin — środek widełek
    jest bliżej tego, po czym faktycznie wykona się odkup."""
    import notowania
    assert notowania._cena_z_wiersza({"bid": 1.50, "ask": 1.62, "last": 9.99}) == 1.56
    # brak widełek -> schodzimy na last, potem close
    assert notowania._cena_z_wiersza({"bid": 0, "ask": 0, "last": 1.40}) == 1.40
    assert notowania._cena_z_wiersza({"last": 0, "close": 2.20}) == 2.20
    assert notowania._cena_z_wiersza({}) is None


def test_symbole_do_odpytania_obejmuja_bazowe():
    import notowania
    dane = {"pozycje": [
        {"klasa": "OPT", "symbol": "LUNR  260918C00021000", "bazowy": "LUNR"},
        {"klasa": "OPT", "symbol": "MBLY  260918C00010000", "bazowy": "MBLY"},
        {"klasa": "STK", "symbol": "AAPL", "bazowy": ""},
    ]}
    s = notowania.symbole_ze_zrzutu(dane)
    assert "LUNR  260918C00021000" in s and "LUNR" in s and "MBLY" in s
    assert "AAPL" not in s          # akcje bez opcji nas nie interesują


def test_notowania_nadpisuja_ceny_z_wyciagu():
    """Świeższa cena musi zmienić i wycenę pozycji, i próg odkupu."""
    from datetime import date
    dane = {"pozycje": [
        {"klasa": "STK", "symbol": "LUNR", "ilosc": 470, "cena": 19.01},
        {"klasa": "OPT", "symbol": "LUNR  260918C00021000", "bazowy": "LUNR",
         "prawo": "C", "strike": 21.0, "wygasa": "20260918", "ilosc": -4.0,
         "cena": 1.56, "wartosc": -624.0, "koszt": -693.239302, "zysk": 69.239302},
    ]}
    bez = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14))[0]
    assert bez.cena_opcji == 1.56 and bez.kurs_bazowego == 19.01
    assert bez.wartosc_biezaca == 624.0

    kursy = {"LUNR  260918C00021000": {"cena": 0.60}, "LUNR": {"cena": 15.50}}
    z = opcje.analizuj_pozycje(dane, dzis=date(2026, 8, 14), kursy=kursy)[0]
    assert z.cena_opcji == 0.60 and z.kurs_bazowego == 15.50
    # wartość bieżąca przeliczona z nowej ceny, nie wzięta z wyciągu
    assert abs(z.wartosc_biezaca - 0.60 * 4 * 100) < 1e-9
    # i to właśnie odpala próg odkupu
    assert opcje.prog_odkupu(z)["osiagniety"]
    assert not opcje.prog_odkupu(bez)["osiagniety"]


def test_brak_tokenu_nie_wywraca_pobierania():
    import notowania
    assert notowania.pobierz(["LUNR"]) == {}
    assert notowania.pobierz([]) == {}
    assert notowania.skonfigurowane() is False
