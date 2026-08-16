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

MIESIACE = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


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
        return '<div class="tresc uwaga">Not enough history to plot.</div>'
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
     aria-label="Drawdown from peak, deepest {naj * 100:.1f} percent">
  <polygon points="0,0 {pkt} {szer},0" fill="var(--spadek)" fill-opacity=".16"/>
  <polyline points="{pkt}" fill="none" stroke="var(--spadek)" stroke-width="1.6"/>
</svg>
<div class="mini" style="display:flex;justify-content:space-between;margin-top:6px">
  <span>{e(szereg[0]["data"])}</span>
  <span>deepest {naj * 100:.2f}%</span>
  <span>{e(szereg[-1]["data"])}</span>
</div>'''


def siatka_miesiecy(miesiace: list[dict]) -> str:
    """Kalendarz zwrotów: wiersz na rok, kolumna na miesiąc.

    Nasycenie koloru skalowane do najmocniejszego miesiąca, żeby zwykłe
    wahania nie wyglądały jak katastrofa."""
    if not miesiace:
        return '<div class="tresc uwaga">No completed months yet.</div>'
    lata = sorted({m["miesiac"][:4] for m in miesiace})
    wg = {m["miesiac"]: m for m in miesiace}
    naj = max((abs(m["zwrot"]) for m in miesiace), default=0.01) or 0.01

    w = ['<div class="przewin"><table style="min-width:560px"><thead><tr><th></th>']
    w += [f'<th class="l">{m}</th>' for m in MIESIACE]
    w.append('<th class="l">year</th></tr></thead><tbody>')
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
            baza = "var(--wzrost)" if m["zwrot"] >= 0 else "var(--spadek)"
            kolor = f"color-mix(in srgb, {baza} {moc * 100:.0f}%, transparent)"
            gwiazdka = "" if m["pelny"] else "*"
            w.append(f'<td class="l num" style="background:{kolor}">'
                     f'{m["zwrot"] * 100:+.1f}{gwiazdka}</td>')
        w.append(f'<td class="l num"><b>{(il - 1.0) * 100:+.1f}</b></td></tr>')
    w.append('</tbody></table></div>'
             '<div class="mini" style="margin-top:8px">Values in percent. '
             'An asterisk marks a partial month — it does not have a full set '
             'of days, so it is not comparable with closed ones.</div>')
    return "".join(w)


# --------------------------------------------------------------------------- #
#  zakładki
# --------------------------------------------------------------------------- #

def tabela_wkladu(w: dict | None) -> str:
    """Rozkład zmienności na pozycje. Kluczowa jest kolumna „krotność":
    ile razy więcej ryzyka niż kapitału wnosi dana spółka."""
    if not w or not w.get("pozycje"):
        return ('<div class="tresc uwaga">No price history — the risk breakdown '
                'cannot be computed.</div>')
    wiersze = []
    for p in w["pozycje"][:18]:
        kr = p["krotnosc"]
        znak = ('<span class="plak zle">risk above capital</span>' if kr >= 2.0
                else '<span class="plak uw">above weight</span>' if kr >= 1.3
                else '<span class="plak ok">diversifies</span>' if kr < 0.5 else '')
        wiersze.append(
            f'<tr><td class="tyk">{e(p["symbol"])}</td>'
            f'<td class="l num">{_proc(p["waga"], znak=False)}</td>'
            f'<td class="l num">{_proc(p["udzial_w_ryzyku"], znak=False)}</td>'
            f'<td class="l num"><b>{p["krotnosc"]:.2f}×</b></td>'
            f'<td class="l num">{_proc(p["zmiennosc"], znak=False)}</td>'
            f'<td>{znak}</td></tr>')
    pom = ""
    if w.get("pominiete"):
        pom = (f'<div class="tresc"><p class="uwaga">Skipped '
               f'{len(w["pominiete"])} holdings without enough history: '
               f'{e(", ".join(w["pominiete"][:8]))}. The table covers '
               f'{_proc(w.get("udzial_objety", 0), znak=False)} of capital — '
               f'an excluded holding still ties up money, we just cannot say '
               f'honestly how much risk it contributes.</p></div>')
    return ('<div class="przewin"><table><thead><tr><th>Holding</th>'
            '<th class="l">Capital</th><th class="l">Risk</th>'
            '<th class="l">Ratio</th><th class="l">Volatility</th><th></th>'
            f'</tr></thead><tbody>{"".join(wiersze)}</tbody></table></div>{pom}')


def tabela_czynnikow(cz: list[dict] | None) -> str:
    """Wrażliwość portfela na czynniki rynkowe."""
    if not cz:
        return '<div class="tresc uwaga">No benchmark price history.</div>'
    wiersze = "".join(
        f'<tr><td class="tyk">{e(c["opis"])}</td>'
        f'<td class="l num"><b>{c["beta"]:+.2f}</b></td>'
        f'<td class="l num">{_proc(c["r2"], znak=False, po=0)}</td>'
        f'<td class="l num">{c["korelacja"]:+.2f}</td>'
        f'<td class="l num {_kl(c["alfa_roczna"])}">{_proc(c["alfa_roczna"])}</td></tr>'
        for c in cz)
    return ('<div class="przewin"><table><thead><tr><th>Factor</th>'
            '<th class="l">Beta</th><th class="l">R²</th>'
            '<th class="l">Correlation</th><th class="l">Annual alpha</th>'
            f'</tr></thead><tbody>{wiersze}</tbody></table></div>'
            '<div class="mini" style="margin-top:8px">Beta says how far the portfolio '
            'moves per 1% move in the factor. R² says how much of the portfolio\'s '
            'variance that factor explains — a low R² means the beta is computed '
            'but not meaningful.</div>')


def pasek_udzialow(dane: list[dict], ile: int = 10) -> str:
    if not dane:
        return '<div class="tresc uwaga">No data.</div>'
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
                '<div class="tresc uwaga">No classification.</div></div></div>')
    ek = a["ekspozycje"]
    return f'''<div data-panel="ekspozycja" class="panel-ukryty">
  <div class="karta"><h2>Factor betas<span class="obok">portfolio move per 1% factor move</span></h2>
    <div class="tresc">{wykresy.tornado(
        [{"nazwa": f'{c["symbol"]} · {c["opis"]}'[:34], "wartosc": c["beta"]}
         for c in sorted(a.get("czynniki") or [], key=lambda c: c["beta"])],
        fmt=lambda v: f"{v:+.2f}")}</div>
    <div class="tresc"><p class="uwaga">A negative beta means the portfolio moves against the
      factor. Bar length alone does not say whether the relationship is
      meaningful — that is what R² in the table below is for.</p></div>
  </div>
  <div class="karta" style="--op:60ms"><h2>Sensitivity to market factors<span class="obok">regression on daily
      returns</span></h2>{tabela_czynnikow(a.get("czynniki"))}</div>
  <div class="siatka dwie">
    <div class="karta" style="--op:80ms"><h2>Themes<span class="obok">share of value</span></h2>
      <div class="tresc">{wykresy.pierscien(
        [(x["nazwa"], x["wartosc"]) for x in (ek.get("temat") or [])],
        srodek_gora=f'{len(ek.get("temat") or [])}', srodek_dol="themes")}</div></div>
    <div class="karta" style="--op:140ms"><h2>Sectors</h2><div class="tresc">
      {wykresy.slupki_poziome(ek.get("sektor") or [])}</div></div>
  </div>
  <div class="siatka dwie">
    <div class="karta" style="--op:200ms"><h2>Countries</h2><div class="tresc">
      {wykresy.slupki_poziome(ek.get("kraj") or [], ile=6)}</div></div>
    <div class="karta" style="--op:260ms"><h2>Asset classes</h2><div class="tresc">
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
  <div class="kom uw"><b>These are estimates, not forecasts.</b> The mapping is
    linear through betas from the last year. In a real crash correlations rise and
    betas drift — the model understates losses in exactly the deepest scenarios.
    Options enter through delta and gamma, which is also an approximation for
    large moves.</div>
  <div class="karta"><h2>Scenario impact on NAV<span class="obok">percent of account value</span></h2>
    <div class="tresc">{wykresy.tornado(
        [{"nazwa": x["nazwa"], "wartosc": x["wplyw_proc"] * 100} for x in s["polaczone"]])}</div>
  </div>
  <div class="karta" style="--op:60ms"><h2>Single-factor sensitivity<span class="obok">uniform −10% shock</span></h2>
    <div class="tresc">{wykresy.tornado(porownywalne_wstrzasy(s["pojedyncze"]))}</div>
    <div class="tresc"><p class="uwaga">Every factor at the same −10% move, so they can be compared
      with each other. The full shock grid is in the table below.</p></div>
  </div>
  <div class="karta" style="--op:120ms"><h2>Market situations<span class="obok">several shocks at once</span></h2>
    <div class="przewin"><table><thead><tr><th>Scenario</th>
      <th class="l">Impact</th><th class="l">% of NAV</th><th class="l">NAV after</th>
      <th>Components</th></tr></thead><tbody>{pol}</tbody></table></div>
  </div>
  <div class="karta"><h2>Single shocks</h2>
    <div class="przewin"><table><thead><tr><th>Factor</th><th class="l">Move</th>
      <th class="l">Beta</th><th class="l">Impact</th><th class="l">% of NAV</th>
      </tr></thead><tbody>{poj}</tbody></table></div>
  </div>
</div>'''


def zakladka_wynik(a: dict | None) -> str:
    if not a or not a.get("zwrot", {}).get("dostepne"):
        return ('<div data-panel="wynik" class="panel-ukryty"><div class="karta">'
                '<div class="tresc uwaga">Not enough history to compute a return.</div>'
                '</div></div>')
    z = a["zwrot"]
    o = z["obsuniecia"]
    uzg = a.get("uzgodnienie") or {}

    kafle = "".join([
        _kafel("TWR", _proc(z["twr"], po=2), _kl(z["twr"]),
               "time-weighted · comparable to an index"),
        _kafel("TWR annualised", _proc(z["twr_roczny"]), _kl(z["twr_roczny"]),
               f'{z["dni"]} days of history'),
        _kafel("MWR / XIRR", _proc(z["mwr"]), _kl(z["mwr"]),
               "your return on the cash you put in"),
        _kafel("Modified Dietz", _proc(z["dietz"]), _kl(z["dietz"]),
               "approximation when the transfer time is unknown"),
        _kafel("Transfers", f'{z["przeplywow"]}', "mut",
               "days with a deposit or withdrawal"),
        _kafel("Max drawdown", _proc(o["maks"]), "down",
               f'{e(o["maks_od"])} → {e(o["maks_dno"])}'),
        _kafel("Current drawdown", _proc(o["biezace"]), _kl(o["biezace"]),
               f'{o["dni_od_szczytu"]} days since the peak'),
        _kafel("Longest drawdown", f'{o["najdluzsze_dni"]} days', "mut",
               "time taken to regain the peak"),
    ])

    wiersz_uzg = ""
    if uzg.get("ibkr") is not None:
        roz = abs((z["twr"] or 0) * 100 - uzg["ibkr"])
        stan = ('<span class="plak ok">reconciled</span>' if roz < 0.01
                else f'<span class="plak uw">off by {roz:.3f} pp</span>')
        wiersz_uzg = (f'<div class="tresc"><p class="uwaga">Reconciliation: the IBKR statement '
                      f'reports TWR <b>{uzg["ibkr"]:.3f}%</b>, this panel computes '
                      f'<b>{(z["twr"] or 0) * 100:.3f}%</b>. {stan}</p></div>')

    ostrzezenie = ""
    if not z.get("wystarczajaco"):
        ostrzezenie = (f'<div class="kom uw">Only {z["obserwacji"]} observations — some measures '
                       f'are still unreliable ({z["min_obserwacji"]} needed).</div>')

    naiwny = ""
    if z.get("prosty") is not None and z.get("twr") is not None \
            and abs(z["prosty"] - z["twr"]) > 0.05:
        naiwny = (f'<div class="tresc"><p class="uwaga">The raw change in account value is '
                  f'<b>{_proc(z["prosty"], po=1)}</b>, but deposits and withdrawals '
                  f'are not investment results. Strip them out and '
                  f'<b>{_proc(z["twr"])}</b> is left — that is the portfolio '
                  f'return.</p></div>')

    return f'''<div data-panel="wynik" class="panel-ukryty">
  {ostrzezenie}
  <div class="karta"><h2>Performance<span class="obok">{e(z["od"])} → {e(z["do"])}</span></h2>
    <div class="kafle">{kafle}</div>
    {naiwny}{wiersz_uzg}
  </div>
  <div class="karta" style="--op:60ms"><h2>Performance curve<span class="obok">index, start = 100</span></h2>
    <div class="tresc">{wykresy.obszar(a.get("krzywa") or [], jednostka="",
        odniesienie=100.0, zakresy=True, opis="Cumulative time-weighted return")}</div>
    <div class="tresc"><p class="uwaga">This curve shows the investment result alone: transfers are
      stripped out, so every move in it is the market or a decision, never a
      deposit. The line at 100 is the starting point — this is the only curve
      you may put next to an index.</p></div></div>
  <div class="karta" style="--op:120ms"><h2>Account value<span class="obok">{len(a["szereg"])} days · transfers included</span></h2>
    <div class="tresc">{wykresy.obszar([(w["data"], w["nav"]) for w in a["szereg"]],
        opis="Account value", zakresy=True)}</div></div>
  <div class="karta" style="--op:180ms"><h2>Drawdown from peak<span class="obok">distance from the highest value so
      far</span></h2>
    <div class="tresc">{wykres_obsuniecia(a["szereg"])}</div></div>
  <div class="karta" style="--op:240ms"><h2>Month-by-month returns</h2>
    <div class="tresc">{wykresy.slupki_pionowe(
        [(m["miesiac"], m["zwrot"] * 100) for m in (a.get("miesiace") or [])])}</div>
    {siatka_miesiecy(a.get("miesiace") or [])}</div>
</div>'''


def zakladka_ryzyko(a: dict | None) -> str:
    if not a or not a.get("ryzyko"):
        return ('<div data-panel="ryzyko" class="panel-ukryty"><div class="karta">'
                '<div class="tresc uwaga">No data for risk analysis.</div>'
                '</div></div>')
    r = a["ryzyko"]
    k = a.get("koncentracja") or {}

    kafle = "".join([
        _kafel("Annual volatility", _proc(r["zmiennosc"], znak=False), "mut",
               "standard deviation of returns, annualised"),
        _kafel("Downside volatility", _proc(r["zmiennosc_ujemna"], znak=False), "mut",
               "computed from losing days only"),
        _kafel("Sharpe", _licz(r["sharpe"]), _kl(r["sharpe"]),
               "excess return per unit of volatility"),
        _kafel("Sortino", _licz(r["sortino"]), _kl(r["sortino"]),
               "penalises downside only"),
        _kafel("Calmar", _licz(r["calmar"]), _kl(r["calmar"]),
               "return per unit of drawdown"),
        _kafel("Daily VaR 95%", _proc(r["var95"]), "down",
               "worse than this on 1 day in 20"),
        _kafel("CVaR 95%", _proc(r["cvar95"]), "down",
               "average loss on those bad days"),
        _kafel("Daily VaR 99%", _proc(r["var99"]), "down",
               "worse than this on 1 day in 100"),
    ])

    kafle_konc = "".join([
        _kafel("Largest holding", _proc(k.get("top1", 0) / 100, znak=False), "mut", ""),
        _kafel("Top 3", _proc(k.get("top3", 0) / 100, znak=False), "mut", ""),
        _kafel("Top 5", _proc(k.get("top5", 0) / 100, znak=False), "mut", ""),
        _kafel("Top 10", _proc(k.get("top10", 0) / 100, znak=False), "mut", ""),
        _kafel("HHI", _licz(k.get("hhi"), 0), "mut", "concentration index"),
        _kafel("Effective holdings", _licz(k.get("efektywna_liczba"), 1), "mut",
               f'out of {k.get("pozycji", 0)} actual'),
    ]) if k.get("dostepne") else ""

    braki = ""
    if r.get("braki"):
        braki = ('<div class="kom uw"><b>Not everything can be computed yet.</b><br>'
                 + "<br>".join(e(b) for b in r["braki"]) + '</div>')

    komentarz_konc = ""
    if k.get("dostepne") and k.get("efektywna_liczba"):
        komentarz_konc = (
            f'<div class="tresc"><p class="uwaga">The portfolio holds {k["pozycji"]} '
            f'positions but behaves like <b>{k["efektywna_liczba"]:.1f}</b> — that is '
            f'the effective count once weights are taken into account. The number '
            f'of holdings on its own is not a measure of diversification.</p></div>')

    return f'''<div data-panel="ryzyko" class="panel-ukryty">
  {braki}
  <div class="karta"><h2>Risk<span class="obok">{r["obserwacji"]} daily observations</span></h2>
    <div class="kafle">{kafle}</div>
    <div class="tresc"><p class="uwaga">VaR and CVaR are historical, taken from the actual return
      distribution rather than an assumption of normality — daily returns have
      fatter tails, so normality would understate the loss exactly where it costs
      the most.</p></div>
  </div>
  <div class="karta" style="--op:60ms"><h2>Daily return distribution<span class="obok">{r["obserwacji"]} sessions</span></h2>
    <div class="tresc">{wykresy.histogram(a.get("rozklad_zwrotow") or [], znaczniki=[
        z for z in (
            {"wartosc": r.get("var95"), "etykieta": "VaR 95%", "kolor": "var(--uwaga)"},
            {"wartosc": r.get("cvar95"), "etykieta": "CVaR 95%", "kolor": "var(--spadek)"},
            {"wartosc": r.get("var99"), "etykieta": "VaR 99%", "kolor": "var(--spadek)"},
        ) if z["wartosc"] is not None], opis="Distribution of daily returns")}</div>
    <div class="tresc"><p class="uwaga">Each bar is the number of sessions that ended with a return
      in that band. The frame is symmetric around zero, so a skewed distribution
      shows up as a skewed picture. The vertical lines mark the thresholds from
      the tiles above — the chart only says something once they are on it.</p></div>
  </div>
  <div class="karta" style="--op:120ms"><h2>Volatility over a 30-session window<span class="obok">annualised</span></h2>
    <div class="tresc">{wykresy.obszar(
        [(d, v * 100) for d, v in (a.get("zmiennosc_kroczaca") or [])],
        wys=190, jednostka="", opis="Rolling volatility",
        odniesienie=(r["zmiennosc"] * 100) if r.get("zmiennosc") else None,
        zakresy=True)}</div>
    <div class="tresc"><p class="uwaga">A single number for the whole period averages calm together
      with storm. This curve says which way risk is heading right now; the dashed
      line is the average across all history.</p></div>
  </div>
  <div class="karta"><h2>Capital concentration</h2>
    <div class="kafle">{kafle_konc}</div>{komentarz_konc}
  </div>
  <div class="karta"><h2>Capital versus risk<span class="obok">holding by holding</span></h2>
    <div class="tresc">{wykresy.rozrzut(
        [{"x": p["waga"] * 100, "y": p["udzial_w_ryzyku"] * 100, "etykieta": p["symbol"]}
         for p in ((a.get("wklad") or {}).get("pozycje") or [])],
        os_x="share of capital →", os_y="↑ share of risk",
        opis="Share of capital versus share of risk")}</div>
    <div class="tresc"><p class="uwaga">The diagonal is balance: on it a holding contributes as much
      risk as capital. Points above it work harder than they weigh — and they are
      what drives the volatility of the whole.</p></div>
  </div>
  <div class="karta"><h2>Risk contribution<span class="obok">share of volatility versus share of
      capital</span></h2>{tabela_wkladu(a.get("wklad"))}
    <div class="tresc"><p class="uwaga">A ratio above one means the holding brings more risk than its
      size would suggest. Below one means it acts as a stabiliser. This is a
      different piece of information from weight alone, and usually a more
      interesting one.</p></div>
  </div>
</div>'''
