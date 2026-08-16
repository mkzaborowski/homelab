"""Zakładki „Wynik" i „Ryzyko".

Osobny plik, bo widok.py ma już 800 linii, a te dwie zakładki mają własny
zestaw kafli i wykresów, którego nie używa nic innego.

Reguła obowiązująca wszędzie niżej: metryka, której nie da się policzyć,
pokazuje kreskę i powód, a nie liczbę. Panel nie ma prawa wyglądać na pewny
tam, gdzie danych brakuje.
"""
from __future__ import annotations

from html import escape as e

import wykresy

MIESIACE = ("sty", "lut", "mar", "kwi", "maj", "cze",
            "lip", "sie", "wrz", "paź", "lis", "gru")


def _pln(v, waluta="$"):
    if v is None:
        return "—"
    znak = "-" if v < 0 else ""
    return f"{znak}{waluta}{abs(v):,.2f}".replace(",", " ")


def _proc(v, znak=True, po=2):
    if v is None:
        return "—"
    return f"{v * 100:+.{po}f}%" if znak else f"{v * 100:.{po}f}%"


def _licz(v, po=2):
    return "—" if v is None else f"{v:,.{po}f}".replace(",", " ")


def _kl(v):
    return "mut" if v is None else ("up" if v >= 0 else "down")


def _kafel(et, w, kl="", pod=""):
    return (f'<div class="kafel"><div class="et">{e(et)}</div>'
            f'<div class="w num {kl}">{w}</div>'
            f'<div class="pod num">{pod}</div></div>')


# --------------------------------------------------------------------------- #
#  wykresy
# --------------------------------------------------------------------------- #

def wykres_obsuniecia(szereg: list[dict], wys: int = 150) -> str:
    """Obsunięcie od szczytu kroczącego. Zawsze poniżej zera, więc rysujemy
    w dół od górnej krawędzi - tak czyta się od razu, bez legendy."""
    if len(szereg) < 2:
        return '<div class="tresc uwaga">Za mało historii na wykres.</div>'
    szczyt, seria = 0.0, []
    for w in szereg:
        nav = w.get("nav") or 0.0
        szczyt = max(szczyt, nav)
        seria.append((nav / szczyt - 1.0) if szczyt else 0.0)
    naj = min(seria) or -0.01
    szer = 1000
    krok = szer / max(len(seria) - 1, 1)
    pkt = " ".join(f"{i * krok:.1f},{(r / naj) * wys:.1f}" for i, r in enumerate(seria))
    return f'''<svg viewBox="0 0 {szer} {wys}" preserveAspectRatio="none"
     style="width:100%;height:{wys}px;display:block" role="img"
     aria-label="Obsunięcie od szczytu, najgłębsze {naj * 100:.1f} procent">
  <polygon points="0,0 {pkt} {szer},0" fill="var(--spadek)" fill-opacity=".16"/>
  <polyline points="{pkt}" fill="none" stroke="var(--spadek)" stroke-width="1.6"/>
</svg>
<div class="mini" style="display:flex;justify-content:space-between;margin-top:6px">
  <span>{e(szereg[0]["data"])}</span>
  <span>najgłębsze {naj * 100:.2f}%</span>
  <span>{e(szereg[-1]["data"])}</span>
</div>'''


def siatka_miesiecy(miesiace: list[dict]) -> str:
    """Kalendarz zwrotów: wiersz na rok, kolumna na miesiąc.

    Nasycenie koloru skalowane do najmocniejszego miesiąca, żeby zwykłe
    wahania nie wyglądały jak katastrofa."""
    if not miesiace:
        return '<div class="tresc uwaga">Brak zamkniętych miesięcy.</div>'
    lata = sorted({m["miesiac"][:4] for m in miesiace})
    wg = {m["miesiac"]: m for m in miesiace}
    naj = max((abs(m["zwrot"]) for m in miesiace), default=0.01) or 0.01

    w = ['<div class="przewin"><table style="min-width:560px"><thead><tr><th></th>']
    w += [f'<th class="l">{m}</th>' for m in MIESIACE]
    w.append('<th class="l">rok</th></tr></thead><tbody>')
    for rok in lata:
        w.append(f'<tr><td class="tyk">{rok}</td>')
        il = 1.0
        for i in range(1, 13):
            m = wg.get(f"{rok}-{i:02d}")
            if not m:
                w.append('<td class="l num" style="color:var(--slaby)">·</td>')
                continue
            il *= (1.0 + m["zwrot"])
            moc = min(abs(m["zwrot"]) / naj, 1.0) * 0.42
            kolor = f"rgba(63,185,80,{moc:.2f})" if m["zwrot"] >= 0 else f"rgba(248,81,73,{moc:.2f})"
            gwiazdka = "" if m["pelny"] else "*"
            w.append(f'<td class="l num" style="background:{kolor}">'
                     f'{m["zwrot"] * 100:+.1f}{gwiazdka}</td>')
        w.append(f'<td class="l num"><b>{(il - 1.0) * 100:+.1f}</b></td></tr>')
    w.append('</tbody></table></div>'
             '<div class="mini" style="margin-top:8px">Wartości w procentach. '
             'Gwiazdka oznacza miesiąc niepełny — nie ma pełnego zestawu dni, '
             'więc nie jest porównywalny z zamkniętymi.</div>')
    return "".join(w)


# --------------------------------------------------------------------------- #
#  zakładki
# --------------------------------------------------------------------------- #

def tabela_wkladu(w: dict | None) -> str:
    """Rozkład zmienności na pozycje. Kluczowa jest kolumna „krotność":
    ile razy więcej ryzyka niż kapitału wnosi dana spółka."""
    if not w or not w.get("pozycje"):
        return ('<div class="tresc uwaga">Brak historii kursów — rozkładu ryzyka '
                'nie da się policzyć.</div>')
    wiersze = []
    for p in w["pozycje"][:18]:
        kr = p["krotnosc"]
        znak = ('<span class="plak zle">ryzyko ponad kapitał</span>' if kr >= 2.0
                else '<span class="plak uw">powyżej wagi</span>' if kr >= 1.3
                else '<span class="plak ok">dywersyfikuje</span>' if kr < 0.5 else '')
        wiersze.append(
            f'<tr><td class="tyk">{e(p["symbol"])}</td>'
            f'<td class="l num">{_proc(p["waga"], znak=False)}</td>'
            f'<td class="l num">{_proc(p["udzial_w_ryzyku"], znak=False)}</td>'
            f'<td class="l num"><b>{p["krotnosc"]:.2f}×</b></td>'
            f'<td class="l num">{_proc(p["zmiennosc"], znak=False)}</td>'
            f'<td>{znak}</td></tr>')
    pom = ""
    if w.get("pominiete"):
        pom = (f'<div class="tresc"><p class="uwaga">Pominięto '
               f'{len(w["pominiete"])} pozycji bez wystarczającej historii: '
               f'{e(", ".join(w["pominiete"][:8]))}. Zestawienie obejmuje '
               f'{_proc(w.get("udzial_objety", 0), znak=False)} kapitału — '
               f'wykluczona pozycja nadal zajmuje pieniądze, tylko nie da się '
               f'rzetelnie powiedzieć, ile wnosi ryzyka.</p></div>')
    return ('<div class="przewin"><table><thead><tr><th>Spółka</th>'
            '<th class="l">Kapitał</th><th class="l">Ryzyko</th>'
            '<th class="l">Krotność</th><th class="l">Zmienność</th><th></th>'
            f'</tr></thead><tbody>{"".join(wiersze)}</tbody></table></div>{pom}')


def tabela_czynnikow(cz: list[dict] | None) -> str:
    """Wrażliwość portfela na czynniki rynkowe."""
    if not cz:
        return '<div class="tresc uwaga">Brak historii kursów wzorców.</div>'
    wiersze = "".join(
        f'<tr><td class="tyk">{e(c["opis"])}</td>'
        f'<td class="l num"><b>{c["beta"]:+.2f}</b></td>'
        f'<td class="l num">{_proc(c["r2"], znak=False, po=0)}</td>'
        f'<td class="l num">{c["korelacja"]:+.2f}</td>'
        f'<td class="l num {_kl(c["alfa_roczna"])}">{_proc(c["alfa_roczna"])}</td></tr>'
        for c in cz)
    return ('<div class="przewin"><table><thead><tr><th>Czynnik</th>'
            '<th class="l">Beta</th><th class="l">R²</th>'
            '<th class="l">Korelacja</th><th class="l">Alfa roczna</th>'
            f'</tr></thead><tbody>{wiersze}</tbody></table></div>'
            '<div class="mini" style="margin-top:8px">Beta mówi, o ile porusza się '
            'portfel na każdy 1% ruchu czynnika. R² mówi, jaka część zmienności '
            'portfela jest tym czynnikiem wyjaśniona — niskie R² znaczy, że beta '
            'jest wprawdzie policzona, ale mało znacząca.</div>')


def pasek_udzialow(dane: list[dict], ile: int = 10) -> str:
    if not dane:
        return '<div class="tresc uwaga">Brak danych.</div>'
    naj = max(d["udzial"] for d in dane) or 1.0
    w = []
    for d in dane[:ile]:
        szer = d["udzial"] / naj * 100
        w.append(
            f'<div style="display:grid;grid-template-columns:150px 1fr 76px;'
            f'gap:12px;align-items:center;margin-bottom:7px">'
            f'<span class="mini" style="text-align:right">{e(d["nazwa"])}</span>'
            f'<span style="background:var(--linia);border-radius:4px;height:16px;'
            f'position:relative;overflow:hidden">'
            f'<i style="position:absolute;inset:0 auto 0 0;width:{szer:.1f}%;'
            f'background:linear-gradient(90deg,var(--akcent),var(--akcent-2));border-radius:4px;'
            f'display:block"></i></span>'
            f'<span class="num mini">{d["udzial"]:.1f}%</span></div>')
    return "".join(w)


def zakladka_ekspozycja(a: dict | None) -> str:
    if not a or not a.get("ekspozycje"):
        return ('<div data-panel="ekspozycja" class="panel-ukryty"><div class="karta">'
                '<div class="tresc uwaga">Brak klasyfikacji.</div></div></div>')
    ek = a["ekspozycje"]
    return f'''<div data-panel="ekspozycja" class="panel-ukryty">
  <div class="karta"><h2>Bety czynnikowe<span class="obok">ruch portfela na 1% ruchu
      czynnika</span></h2>
    <div class="tresc">{wykresy.tornado(
        [{"nazwa": f'{c["symbol"]} · {c["opis"]}'[:34], "wartosc": c["beta"]}
         for c in sorted(a.get("czynniki") or [], key=lambda c: c["beta"])],
        fmt=lambda v: f"{v:+.2f}")}</div>
    <div class="tresc"><p class="uwaga">Beta ujemna znaczy, że portfel idzie
      przeciwnie do czynnika. Sama wysokość słupka nie mówi jednak, czy zależność
      jest istotna — to pokazuje R² w tabeli niżej.</p></div>
  </div>
  <div class="karta" style="--op:60ms"><h2>Wrażliwość na czynniki rynkowe<span class="obok">regresja
      zwrotów dziennych</span></h2>{tabela_czynnikow(a.get("czynniki"))}</div>
  <div class="siatka dwie">
    <div class="karta" style="--op:80ms"><h2>Tematy<span class="obok">udział w wartości</span></h2>
      <div class="tresc">{wykresy.pierscien(
        [(x["nazwa"], x["wartosc"]) for x in (ek.get("temat") or [])],
        srodek_gora=f'{len(ek.get("temat") or [])}', srodek_dol="tematów")}</div></div>
    <div class="karta" style="--op:140ms"><h2>Sektory</h2><div class="tresc">
      {wykresy.slupki_poziome(ek.get("sektor") or [])}</div></div>
  </div>
  <div class="siatka dwie">
    <div class="karta" style="--op:200ms"><h2>Kraje</h2><div class="tresc">
      {wykresy.slupki_poziome(ek.get("kraj") or [], ile=6)}</div></div>
    <div class="karta" style="--op:260ms"><h2>Klasy aktywów</h2><div class="tresc">
      {wykresy.pierscien([(x["nazwa"], abs(x["wartosc"])) for x in (ek.get("klasa") or [])],
        rozmiar=150)}</div></div>
  </div>
</div>'''


def _skladniki(lista: list[dict]) -> str:
    """Skrót w rodzaju „QQQ −22% · SPY −15%" do kolumny opisowej."""
    return " · ".join(f'{k["czynnik"]} {k["zmiana"]:+.0%}' for k in lista)


def porownywalne_wstrzasy(pojedyncze: list[dict], cel: float = -0.10) -> list[dict]:
    """Po jednym wstrząsie na czynnik, o tej samej wielkości ruchu.

    Siatka wstrząsów jest różna dla różnych czynników - srebro testujemy przy
    30%, obligacje przy 5%, bo takie ruchy są dla nich realne. Do wykresu
    porównawczego trzeba jednak ruchu jednolitego: inaczej długość słupka
    miesza wrażliwość portfela z arbitralnym wyborem skali testu, a to jest
    dokładnie ten rodzaj wykresu, który wygląda na wniosek i nim nie jest."""
    wg_czynnika: dict[str, dict] = {}
    for x in pojedyncze:
        stary = wg_czynnika.get(x["czynnik"])
        if stary is None or abs(x["zmiana"] - cel) < abs(stary["zmiana"] - cel):
            wg_czynnika[x["czynnik"]] = x
    return sorted(
        ({"nazwa": f'{x["czynnik"]} · {x["opis"]}'[:34],
          "wartosc": x["wplyw_proc"] * 100} for x in wg_czynnika.values()),
        key=lambda d: d["wartosc"])


def zakladka_scenariusze(s: dict | None) -> str:
    if not s or not s.get("dostepne"):
        powod = (s or {}).get("powod", "brak danych")
        return (f'<div data-panel="scenariusze" class="panel-ukryty"><div class="karta">'
                f'<div class="tresc uwaga">{e(powod)}</div></div></div>')
    pol = "".join(
        f'<tr><td class="tyk">{e(x["nazwa"])}<div class="mini">{e(x["opis"])}</div></td>'
        f'<td class="l num {_kl(x["wplyw"])}"><b>{_pln(x["wplyw"])}</b></td>'
        f'<td class="l num {_kl(x["wplyw_proc"])}">{_proc(x["wplyw_proc"])}</td>'
        f'<td class="l num">{_pln(x["nav_po"])}</td>'
        f'<td class="mini">{e(_skladniki(x["skladniki"]))}</td></tr>'
        for x in s["polaczone"])
    poj = "".join(
        f'<tr><td class="tyk">{e(x["opis"])}</td>'
        f'<td class="l num">{x["zmiana"]:+.0%}</td>'
        f'<td class="l num">{x["beta"]:+.2f}</td>'
        f'<td class="l num {_kl(x["wplyw"])}">{_pln(x["wplyw"])}</td>'
        f'<td class="l num {_kl(x["wplyw_proc"])}">{_proc(x["wplyw_proc"])}</td></tr>'
        for x in s["pojedyncze"])
    return f'''<div data-panel="scenariusze" class="panel-ukryty">
  <div class="kom uw"><b>To są szacunki, nie prognozy.</b> Przełożenie jest liniowe
    przez bety z ostatniego roku. W prawdziwym krachu korelacje rosną, a bety się
    rozjeżdżają — model zaniża straty w scenariuszach najgłębszych. Opcje wchodzą
    przez deltę i gammę, co przy dużych ruchach też jest przybliżeniem.</div>
  <div class="karta"><h2>Wpływ scenariuszy na NAV<span class="obok">w procentach
      wartości konta</span></h2>
    <div class="tresc">{wykresy.tornado(
        [{"nazwa": x["nazwa"], "wartosc": x["wplyw_proc"] * 100} for x in s["polaczone"]])}</div>
  </div>
  <div class="karta" style="--op:60ms"><h2>Wrażliwość na pojedyncze czynniki<span
      class="obok">jednolity wstrząs −10%</span></h2>
    <div class="tresc">{wykresy.tornado(porownywalne_wstrzasy(s["pojedyncze"]))}</div>
    <div class="tresc"><p class="uwaga">Wszystkie czynniki przy tym samym ruchu
      −10%, żeby dało się je porównać między sobą. Pełną siatkę wstrząsów
      zawiera tabela niżej.</p></div>
  </div>
  <div class="karta" style="--op:120ms"><h2>Sytuacje rynkowe<span class="obok">kilka wstrząsów
      naraz</span></h2>
    <div class="przewin"><table><thead><tr><th>Scenariusz</th>
      <th class="l">Wpływ</th><th class="l">% NAV</th><th class="l">NAV po</th>
      <th>Składniki</th></tr></thead><tbody>{pol}</tbody></table></div>
  </div>
  <div class="karta"><h2>Pojedyncze wstrząsy</h2>
    <div class="przewin"><table><thead><tr><th>Czynnik</th><th class="l">Ruch</th>
      <th class="l">Beta</th><th class="l">Wpływ</th><th class="l">% NAV</th>
      </tr></thead><tbody>{poj}</tbody></table></div>
  </div>
</div>'''


def zakladka_wynik(a: dict | None) -> str:
    if not a or not a.get("zwrot", {}).get("dostepne"):
        return ('<div data-panel="wynik" class="panel-ukryty"><div class="karta">'
                '<div class="tresc uwaga">Brak historii do policzenia zwrotu.</div>'
                '</div></div>')
    z = a["zwrot"]
    o = z["obsuniecia"]
    uzg = a.get("uzgodnienie") or {}

    kafle = "".join([
        _kafel("TWR", _proc(z["twr"], po=2), _kl(z["twr"]),
               "ważony czasem · porównywalny z indeksem"),
        _kafel("TWR w skali roku", _proc(z["twr_roczny"]), _kl(z["twr_roczny"]),
               f'{z["dni"]} dni historii'),
        _kafel("MWR / XIRR", _proc(z["mwr"]), _kl(z["mwr"]),
               "Twój zwrot na wpłaconym kapitale"),
        _kafel("Modified Dietz", _proc(z["dietz"]), _kl(z["dietz"]),
               "przybliżenie przy nieznanej godzinie przelewu"),
        _kafel("Przelewy", f'{z["przeplywow"]}', "mut",
               "dni z wpłatą lub wypłatą"),
        _kafel("Maks. obsunięcie", _proc(o["maks"]), "down",
               f'{e(o["maks_od"])} → {e(o["maks_dno"])}'),
        _kafel("Bieżące obsunięcie", _proc(o["biezace"]), _kl(o["biezace"]),
               f'{o["dni_od_szczytu"]} dni od szczytu'),
        _kafel("Najdłuższe obsunięcie", f'{o["najdluzsze_dni"]} dni', "mut",
               "czas powrotu do szczytu"),
    ])

    wiersz_uzg = ""
    if uzg.get("ibkr") is not None:
        roz = abs((z["twr"] or 0) * 100 - uzg["ibkr"])
        stan = ('<span class="plak ok">zgodne</span>' if roz < 0.01
                else f'<span class="plak uw">różnica {roz:.3f} pp</span>')
        wiersz_uzg = (f'<div class="tresc"><p class="uwaga">Uzgodnienie: IBKR podaje '
                      f'w wyciągu TWR <b>{uzg["ibkr"]:.3f}%</b>, panel liczy '
                      f'<b>{(z["twr"] or 0) * 100:.3f}%</b>. {stan}</p></div>')

    ostrzezenie = ""
    if not z.get("wystarczajaco"):
        ostrzezenie = (f'<div class="kom uw">Tylko {z["obserwacji"]} obserwacji — '
                       f'część miar jest jeszcze niepewna (potrzeba '
                       f'{z["min_obserwacji"]}).</div>')

    naiwny = ""
    if z.get("prosty") is not None and z.get("twr") is not None \
            and abs(z["prosty"] - z["twr"]) > 0.05:
        naiwny = (f'<div class="tresc"><p class="uwaga">Sama różnica wartości konta '
                  f'to <b>{_proc(z["prosty"], po=1)}</b>, ale wpłaty i wypłaty '
                  f'nie są wynikiem inwestycyjnym. Po ich odjęciu zostaje '
                  f'<b>{_proc(z["twr"])}</b> — i to jest zwrot z portfela.</p></div>')

    return f'''<div data-panel="wynik" class="panel-ukryty">
  {ostrzezenie}
  <div class="karta"><h2>Wynik<span class="obok">{e(z["od"])} → {e(z["do"])}</span></h2>
    <div class="kafle">{kafle}</div>
    {naiwny}{wiersz_uzg}
  </div>
  <div class="karta" style="--op:60ms"><h2>Krzywa wyniku<span class="obok">indeks,
      start = 100</span></h2>
    <div class="tresc">{wykresy.obszar(a.get("krzywa") or [], jednostka="",
        odniesienie=100.0, zakresy=True, opis="Skumulowany zwrot ważony czasem")}</div>
    <div class="tresc"><p class="uwaga">Ta krzywa pokazuje sam wynik inwestycyjny:
      przelewy są z niej wyczyszczone, więc każdy jej ruch to rynek albo decyzja,
      nigdy wpłata. Kreska na wysokości 100 to punkt wyjścia — tylko tę krzywą
      wolno położyć obok indeksu.</p></div></div>
  <div class="karta" style="--op:120ms"><h2>Wartość konta<span class="obok">{len(a["szereg"])} dni ·
      z przelewami</span></h2>
    <div class="tresc">{wykresy.obszar([(w["data"], w["nav"]) for w in a["szereg"]],
        opis="Wartość konta", zakresy=True)}</div></div>
  <div class="karta" style="--op:180ms"><h2>Obsunięcie od szczytu<span class="obok">odległość od
      najwyższej dotąd wartości</span></h2>
    <div class="tresc">{wykres_obsuniecia(a["szereg"])}</div></div>
  <div class="karta" style="--op:240ms"><h2>Zwroty miesiąc po miesiącu</h2>
    <div class="tresc">{wykresy.slupki_pionowe(
        [(m["miesiac"], m["zwrot"] * 100) for m in (a.get("miesiace") or [])])}</div>
    {siatka_miesiecy(a.get("miesiace") or [])}</div>
</div>'''


def zakladka_ryzyko(a: dict | None) -> str:
    if not a or not a.get("ryzyko"):
        return ('<div data-panel="ryzyko" class="panel-ukryty"><div class="karta">'
                '<div class="tresc uwaga">Brak danych do analizy ryzyka.</div>'
                '</div></div>')
    r = a["ryzyko"]
    k = a.get("koncentracja") or {}

    kafle = "".join([
        _kafel("Zmienność roczna", _proc(r["zmiennosc"], znak=False), "mut",
               "odchylenie zwrotów w skali roku"),
        _kafel("Zmienność ujemna", _proc(r["zmiennosc_ujemna"], znak=False), "mut",
               "liczona tylko z dni spadkowych"),
        _kafel("Sharpe", _licz(r["sharpe"]), _kl(r["sharpe"]),
               "nadwyżka na jednostkę zmienności"),
        _kafel("Sortino", _licz(r["sortino"]), _kl(r["sortino"]),
               "karze wyłącznie spadki"),
        _kafel("Calmar", _licz(r["calmar"]), _kl(r["calmar"]),
               "zwrot na jednostkę obsunięcia"),
        _kafel("VaR 95% dzienny", _proc(r["var95"]), "down",
               "gorzej niż tyle w 1 dniu na 20"),
        _kafel("CVaR 95%", _proc(r["cvar95"]), "down",
               "średnia strata w tych złych dniach"),
        _kafel("VaR 99% dzienny", _proc(r["var99"]), "down",
               "gorzej niż tyle w 1 dniu na 100"),
    ])

    kafle_konc = "".join([
        _kafel("Największa pozycja", _proc(k.get("top1", 0) / 100, znak=False), "mut", ""),
        _kafel("Top 3", _proc(k.get("top3", 0) / 100, znak=False), "mut", ""),
        _kafel("Top 5", _proc(k.get("top5", 0) / 100, znak=False), "mut", ""),
        _kafel("Top 10", _proc(k.get("top10", 0) / 100, znak=False), "mut", ""),
        _kafel("HHI", _licz(k.get("hhi"), 0), "mut", "indeks koncentracji"),
        _kafel("Efektywna liczba pozycji", _licz(k.get("efektywna_liczba"), 1), "mut",
               f'z {k.get("pozycji", 0)} faktycznych'),
    ]) if k.get("dostepne") else ""

    braki = ""
    if r.get("braki"):
        braki = ('<div class="kom uw"><b>Nie wszystko da się jeszcze policzyć.</b><br>'
                 + "<br>".join(e(b) for b in r["braki"]) + '</div>')

    komentarz_konc = ""
    if k.get("dostepne") and k.get("efektywna_liczba"):
        komentarz_konc = (
            f'<div class="tresc"><p class="uwaga">Portfel ma {k["pozycji"]} pozycji, '
            f'ale zachowuje się jak <b>{k["efektywna_liczba"]:.1f}</b> — tyle wynosi '
            f'efektywna liczba po uwzględnieniu wag. Sama liczba spółek nie jest '
            f'miarą dywersyfikacji.</p></div>')

    return f'''<div data-panel="ryzyko" class="panel-ukryty">
  {braki}
  <div class="karta"><h2>Ryzyko<span class="obok">{r["obserwacji"]} obserwacji
      dziennych</span></h2>
    <div class="kafle">{kafle}</div>
    <div class="tresc"><p class="uwaga">VaR i CVaR liczone historycznie, z faktycznego
      rozkładu zwrotów, a nie z założenia normalności — rozkład dzienny ma grubsze
      ogony, więc normalność zaniżałaby stratę dokładnie tam, gdzie to najbardziej
      kosztuje.</p></div>
  </div>
  <div class="karta" style="--op:60ms"><h2>Rozkład zwrotów dziennych<span class="obok">{
      r["obserwacji"]} sesji</span></h2>
    <div class="tresc">{wykresy.histogram(a.get("rozklad_zwrotow") or [], znaczniki=[
        z for z in (
            {"wartosc": r.get("var95"), "etykieta": "VaR 95%", "kolor": "var(--uwaga)"},
            {"wartosc": r.get("cvar95"), "etykieta": "CVaR 95%", "kolor": "var(--spadek)"},
            {"wartosc": r.get("var99"), "etykieta": "VaR 99%", "kolor": "var(--spadek)"},
        ) if z["wartosc"] is not None], opis="Rozkład dziennych stóp zwrotu")}</div>
    <div class="tresc"><p class="uwaga">Każdy słupek to liczba sesji, które skończyły
      się zwrotem z danego przedziału. Ramka jest symetryczna wokół zera, więc
      przechył rozkładu widać jako przechył obrazka. Pionowe linie zaznaczają
      progi z kafli powyżej — dopiero z nimi ten wykres o czymś mówi.</p></div>
  </div>
  <div class="karta" style="--op:120ms"><h2>Zmienność w oknie 30 sesji<span class="obok">w skali
      roku</span></h2>
    <div class="tresc">{wykresy.obszar(
        [(d, v * 100) for d, v in (a.get("zmiennosc_kroczaca") or [])],
        wys=190, jednostka="", opis="Zmienność krocząca",
        odniesienie=(r["zmiennosc"] * 100) if r.get("zmiennosc") else None,
        zakresy=True)}</div>
    <div class="tresc"><p class="uwaga">Jedna liczba za cały okres uśrednia spokój
      z burzą. Ta krzywa mówi, w którą stronę ryzyko właśnie idzie; przerywana
      linia to średnia z całej historii.</p></div>
  </div>
  <div class="karta"><h2>Koncentracja kapitału</h2>
    <div class="kafle">{kafle_konc}</div>{komentarz_konc}
  </div>
  <div class="karta"><h2>Kapitał kontra ryzyko<span class="obok">pozycja po pozycji</span></h2>
    <div class="tresc">{wykresy.rozrzut(
        [{"x": p["waga"] * 100, "y": p["udzial_w_ryzyku"] * 100, "etykieta": p["symbol"]}
         for p in ((a.get("wklad") or {}).get("pozycje") or [])],
        os_x="udział w kapitale →", os_y="↑ udział w ryzyku",
        opis="Udział w kapitale wobec udziału w ryzyku")}</div>
    <div class="tresc"><p class="uwaga">Przekątna to równowaga: na niej pozycja
      wnosi tyle ryzyka, ile kapitału. Punkty nad nią pracują ciężej, niż ważą —
      i to one decydują o zmienności całości.</p></div>
  </div>
  <div class="karta"><h2>Wkład do ryzyka<span class="obok">udział w zmienności
      wobec udziału w kapitale</span></h2>{tabela_wkladu(a.get("wklad"))}
    <div class="tresc"><p class="uwaga">Krotność powyżej jedności znaczy, że pozycja
      wnosi więcej ryzyka, niż wynikałoby z jej wielkości. Poniżej jedności —
      że działa jak stabilizator. To jest inna informacja niż sama waga
      i zwykle ciekawsza.</p></div>
  </div>
</div>'''
