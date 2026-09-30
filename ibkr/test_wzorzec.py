"""Testy porównania z arkuszem wzorcowym - europejskie odpowiedniki funduszy.

Amerykańskiego ETF-u z arkusza nie da się kupić w UE, ale fundusz UCITS na ten
sam indeks - tak. Test pilnuje, żeby taki fundusz liczył się za pozycję
z arkusza, a przede wszystkim, żeby NIE łączyć instrumentów, które mają
wspólny tylko ticker (na koncie są dziś dwa takie: KWEB i SLVP z LSE).
"""
import wzorzec

# Wycinek arkusza w układzie z Dysku: nagłówek koszyka, potem transze.
ARKUSZ = (
    "The AWP,Oil/Energy,% of portfolio assets,Company,Ticker\n"
    ",,2.00%,Oil Majors ETF,XLE\n"
    ",,1.00%,Oil Services ETF,OIH\n"
    ",,5.00%,Exxon *,XOM\n"
    "The AWP,Diversified Technology,% of portfolio assets,Company,Ticker\n"
    ",,1.00%,China Internet ETF,KWEB\n"
    ",,4.00%,Nvidia,NVDA\n"
    "The AWP,GSMs,% of portfolio assets,Company,Ticker\n"
    ",,1.00%,Silver and Gold Miners ETF,SLVP\n"
    ",,1.00%,Nuclear ETF,NLR\n"
)

# Katalog instrumentów tak, jak leży w bazie panelu (symbol, ISIN, nazwa).
INSTRUMENTY = {
    "XLES": {"isin": "IE00B435CG94", "nazwa": "INVESCO US ENERGY S&P"},
    "KWEB": {"isin": "IE00BFXR7892", "nazwa": "KRANESHARES CSI CHINA INTRNT"},
    "SLVP": {"isin": "IE00B43VDT70", "nazwa": "INVESCO PHYSICAL SILVER ETC"},
    "NUCL": {"isin": "IE000M7V94E1", "nazwa": "VANECK URANIUM AND NUCLEAR"},
    "XOM": {"isin": "US30231G1022", "nazwa": "EXXON MOBIL CORP"},
    "NVDA": {"isin": "US67066G1040", "nazwa": "NVIDIA CORP"},
}


def _pods(**wartosci) -> dict:
    return {"suma_aktywow": 10_000.0,
            "tickery": [{"symbol": s, "wartosc": w} for s, w in wartosci.items()]}


def _por(pods, instrumenty=INSTRUMENTY):
    return wzorzec.porownaj(wzorzec.parsuj(ARKUSZ), pods, instrumenty)


def _wiersz(por, tic):
    return next((p for p in por["pozycje"] if p["ticker"] == tic), None)


def test_xles_liczy_sie_jako_xle():
    por = _por(_pods(XLES=200.0, XOM=500.0))
    xle = _wiersz(por, "XLE")
    assert xle is not None, "XLE powinno wrócić do porównania, skoro masz odpowiednik"
    assert abs(xle["faktyczne"] - 2.0) < 1e-9
    assert xle["odpowiedniki"][0]["symbol"] == "XLES"
    assert _wiersz(por, "XLES") is None, "XLES nie może jednocześnie wisieć jako 'Not in model'"
    assert "XLE" not in dict(por["pominiete"])


def test_ticker_taki_sam_jak_w_usa_dopasowany_po_isin():
    por = _por(_pods(KWEB=100.0))
    kweb = _wiersz(por, "KWEB")
    assert kweb is not None and abs(kweb["faktyczne"] - 1.0) < 1e-9
    assert kweb["odpowiedniki"][0]["isin"] == "IE00BFXR7892"


def test_bez_isin_nie_zgadujemy():
    # Bez katalogu nie wiadomo, czy KWEB to Londyn, czy Nowy Jork.
    por = _por(_pods(KWEB=100.0), instrumenty={})
    assert _wiersz(por, "KWEB") is None
    assert "KWEB" in dict(por["pominiete"])


def test_ten_sam_ticker_inny_instrument_nie_jest_laczony():
    # SLVP z LSE to fizyczne srebro, SLVP w arkuszu to spółki wydobywcze.
    por = _por(_pods(SLVP=100.0))
    assert _wiersz(por, "SLVP") is None, "srebro fizyczne nie może wejść w wiersz spółek wydobywczych"
    assert "SLVP" in dict(por["pominiete"])
    wlasny = _wiersz(por, "SLVP (UCITS)")
    assert wlasny is not None and wlasny["rodzaj"] == "nadmiarowa"


def test_amerykanski_fundusz_na_koncie_dalej_wykluczony():
    inne = dict(INSTRUMENTY, XLE={"isin": "US81369Y5069", "nazwa": "ENERGY SELECT SECTOR SPDR"})
    por = _por(_pods(XLE=200.0), inne)
    assert _wiersz(por, "XLE") is None
    assert "XLE" in dict(por["pominiete"])


def test_pokrewny_indeks_jest_oznaczony():
    por = _por(_pods(NUCL=100.0))
    nlr = _wiersz(por, "NLR")
    assert nlr is not None and nlr["odpowiedniki"][0]["pokrewny"] is True


def test_cel_przeliczany_z_odpowiednikiem_w_uniwersum():
    # Bez odpowiednika uniwersum to XOM + NVDA = 9%; z XLES dochodzi XLE = 11%.
    bez = _por(_pods(XOM=500.0))
    z = _por(_pods(XOM=500.0, XLES=200.0))
    assert abs(bez["suma_dostepnych"] - 9.0) < 1e-9
    assert abs(z["suma_dostepnych"] - 11.0) < 1e-9
    assert abs(_wiersz(z, "XOM")["cel"] - 5.0 * 100 / 11) < 1e-9


def test_podpowiedz_co_kupic_w_ue():
    por = _por(_pods(XOM=500.0))
    podp = dict(por["do_kupienia_w_ue"])
    assert any("OIHV" in x and "IE000NXF88S1" in x for x in podp["OIH"])
    assert "SLVP" not in podp, "dla spółek wydobywczych srebra nie ma odpowiednika UCITS"


def test_reczne_przypisanie(monkeypatch):
    monkeypatch.setenv("WZORZEC_ODPOWIEDNIKI", "OIH=GDX")
    inne = dict(INSTRUMENTY, GDX={"isin": "IE00BQQP9F84", "nazwa": "VANECK GOLD MINERS UCITS ETF"})
    por = _por(_pods(GDX=100.0), inne)
    oih = _wiersz(por, "OIH")
    assert oih is not None and oih["odpowiedniki"][0]["reczny"] is True


def test_bez_katalogu_zachowanie_jak_dawniej():
    stare = wzorzec.porownaj(wzorzec.parsuj(ARKUSZ), _pods(XOM=500.0, XLES=200.0))
    assert _wiersz(stare, "XLE") is None
    assert _wiersz(stare, "XLES")["rodzaj"] == "nadmiarowa"


def test_widok_pokazuje_odpowiednik():
    import widok
    por = _por(_pods(XOM=500.0, XLES=200.0, NUCL=100.0))
    html = widok._tabela_wzorca(por) + widok._odpowiedniki_ue(por)
    assert "held as XLES" in html
    assert "held as NUCL ≈" in html, "pokrewny indeks ma być oznaczony"
    assert "XLE ← XLES" in html
    assert "OIHV" in html, "podpowiedź, co kupić w UE zamiast OIH"
