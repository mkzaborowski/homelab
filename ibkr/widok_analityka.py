"""Zakładki „Wynik" i „Ryzyko".

Osobny plik, bo widok.py ma już 800 linii, a te dwie zakładki mają własny
zestaw kafli i wykresów, którego nie używa nic innego.

Reguła obowiązująca wszędzie niżej: metryka, której nie da się policzyć,
pokazuje kreskę i powód, a nie liczbę. Panel nie ma prawa wyglądać na pewny
tam, gdzie danych brakuje.
"""
from __future__ import annotations

from html import escape as e

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
  <polygon points="0,0 {pkt} {szer},0" fill="rgba(248,81,73,.18)"/>
  <polyline points="{pkt}" fill="none" stroke="#f85149" stroke-width="1.6"/>
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
  <div class="karta"><h2>Obsunięcie od szczytu<span class="obok">odległość od
      najwyższej dotąd wartości konta</span></h2>
    <div class="tresc">{wykres_obsuniecia(a["szereg"])}</div></div>
  <div class="karta"><h2>Zwroty miesiąc po miesiącu</h2>
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
  <div class="karta"><h2>Koncentracja kapitału</h2>
    <div class="kafle">{kafle_konc}</div>{komentarz_konc}
    <div class="tresc"><p class="uwaga">To koncentracja kapitału, nie ryzyka.
      Rozkład zmienności na pozycje wymaga historii kursów poszczególnych spółek
      i dojdzie razem z dostawcą danych rynkowych.</p></div>
  </div>
</div>'''
