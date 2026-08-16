"""Zakładka „Opcje" w panelu.

Wydzielona z widok.py, bo tamten plik i tak jest już duży, a analiza opcji
ma własny zestaw tabel i kafli, którego nie używa nic innego.
"""
from __future__ import annotations

from html import escape as e


def _pln(v, waluta="$"):
    if v is None:
        return "—"
    znak = "-" if v < 0 else ""
    return f"{znak}{waluta}{abs(v):,.2f}".replace(",", " ")


def _proc(v, znak=True):
    if v is None:
        return "—"
    return f"{v:+.2f}%" if znak else f"{v:.2f}%"


def _kl(v):
    if v is None:
        return "mut"
    return "up" if v >= 0 else "down"


def _licz(v, po=0):
    return f"{v:,.{po}f}".replace(",", " ")


def _odm(n: int, jeden: str, mnogie: str) -> str:
    """Liczba mnoga po angielsku. Kopia tej z widok.py - widok.py importuje ten
    plik, więc import w drugą stronę zamknąłby cykl. To ta duplikacja sprawiła,
    że przejście na angielski naprawiło jedną kopię i zostawiło drugą z trzema
    argumentami; stąd dymiący test renderujący WSZYSTKIE zakładki niżej."""
    return jeden if n == 1 else mnogie


def _kafel(etykieta: str, wartosc: str, klasa: str = "", pod: str = "") -> str:
    return (f'<div class="kafel"><div class="et">{e(etykieta)}</div>'
            f'<div class="w num {klasa}">{wartosc}</div>'
            f'<div class="pod num">{pod}</div></div>')


def kafle(a: dict) -> str:
    """Nagłówkowe liczby. Premia i zysk są rozdzielone celowo: premia
    z żywego kontraktu nie jest jeszcze zyskiem, bo trzeba go móc odkupić."""
    m, s, r = a["miesiac"], a["podsumowanie"], a["rejestr"]
    kompletny = bool(r["od"]) and r["od"] <= m["od"]
    przypis = ("full month" if kompletny
               else f'ledger only from {r["od"]}' if r["od"] else "ledger empty")
    iv = _proc(s["iv_srednia"] * 100, znak=False) if s.get("iv_srednia") else "—"
    k = [
        _kafel("Premium this month", _pln(m["netto"]),
               "up" if m["netto"] > 0 else "mut",
               f'gross {_pln(m["brutto"])} − fees {_pln(m["prowizje"])}'),
        _kafel("Contracts sold", _licz(m["kontraktow_sprzedanych"]), "",
               f'{m["transakcji"]} {_odm(m["transakcji"], "trade", "trades")} · {przypis}'),
        _kafel("Realised P/L", _pln(m["zrealizowany"]), _kl(m["zrealizowany"]),
               "closed and expired positions"),
        _kafel("Unrealised P/L", _pln(s["zysk_otwarty"]), _kl(s["zysk_otwarty"]),
               f'from {_pln(s["premia"])} of premium'),
        _kafel("Left to collect", _pln(s["do_zainkasowania"]), "mut",
               "if everything expired worthless"),
        _kafel("Option book delta", f'{_licz(s["delta_akcji"])} shares',
               _kl(s["delta_akcji"]), f'{_pln(s["delta_dolarowa"])} of exposure'),
        _kafel("Daily theta", _pln(s["theta_dzienna"]), _kl(s["theta_dzienna"]),
               "what one day of decay alone gives"),
        _kafel("Vega", _pln(s["vega"]), _kl(s["vega"]), "per 1 pp of volatility"),
        _kafel("Average IV", iv, "mut", "weighted by contract count"),
        _kafel("Capital at assignment", _pln(s["notional"]), "mut",
               f'{_licz(s["kontraktow"])} {_odm(int(s["kontraktow"]), "contract", "contracts")}'),
    ]
    return '<div class="kafle">' + "".join(k) + '</div>'


def tabela(poz: list[dict]) -> str:
    if not poz:
        return '<div class="tresc uwaga">No open option positions.</div>'
    w = ['<div class="przewin"><table data-sortowalna id="tabOpcje"><thead><tr>'
         '<th class="sort">Contract</th><th class="l">Qty</th><th class="l">Spot</th>'
         '<th class="l">Strike</th><th class="l">To strike</th><th class="l">Days</th>'
         '<th class="l">IV</th><th class="l">Delta</th><th class="l">Theta/d</th>'
         '<th class="l">P(ITM)</th><th class="l">P(touch)</th><th class="l">Premium</th>'
         '<th class="l">Buyback</th><th class="l">P/L</th><th class="l">Return p.a.</th>'
         '<th>Status</th></tr></thead><tbody>']
    for p in poz:
        plak = []
        if p["w_pieniadzu"]:
            plak.append('<span class="plak zle">in the money</span>')
        if p["pokrycie"] < 1.0:
            plak.append('<span class="plak uw">uncovered</span>')
        if p["ryzyko_wczesniejszego"]:
            plak.append('<span class="plak uw">exercise risk</span>')
        if not plak:
            plak.append('<span class="plak ok">out of the money</span>')
        iv = _proc(p["iv"] * 100, znak=False) if p["iv"] else "—"
        p_itm = _proc(p["p_itm"] * 100, znak=False) if p["p_itm"] is not None else "—"
        p_dot = _proc(p["p_dot"] * 100, znak=False) if p["p_dot"] is not None else "—"
        w.append(
            f'<tr><td class="tyk">{e(p["etykieta"])}</td>'
            f'<td class="l num">{p["ilosc"]:+.0f}</td>'
            f'<td class="l num">{_pln(p["spot"])}</td>'
            f'<td class="l num">{_pln(p["strike"])}</td>'
            f'<td class="l num {_kl(p["zapas_proc"])}">{_proc(p["zapas_proc"])}</td>'
            f'<td class="l num">{p["dni"]}</td>'
            f'<td class="l num">{iv}</td>'
            f'<td class="l num">{_licz(p["delta_akcji"])}</td>'
            f'<td class="l num {_kl(p["theta"])}">{_pln(p["theta"])}</td>'
            f'<td class="l num">{p_itm}</td>'
            f'<td class="l num">{p_dot}</td>'
            f'<td class="l num">{_pln(p["premia"])}</td>'
            f'<td class="l num">{_pln(p["teraz"])}</td>'
            f'<td class="l num {_kl(p["wynik"])}">{_pln(p["wynik"])}</td>'
            f'<td class="l num">{_proc(p["zwrot_roczny"] * 100)}</td>'
            f'<td>{" ".join(plak)}</td></tr>')
    w.append('</tbody></table></div>')
    return "".join(w)


OPIS_GREKOW = [
    ("delta", "Delta", "value change per $1 move in the underlying"),
    ("gamma", "Gamma", "how fast delta itself changes"),
    ("vega", "Vega", "effect of 1 pp of volatility"),
    ("theta", "Theta", "value lost over one day"),
    ("rho", "Rho", "effect of 1 pp of interest rate"),
    ("vanna", "Vanna", "delta versus volatility"),
    ("volga", "Volga", "vega versus volatility"),
    ("charm", "Charm", "delta versus passage of time"),
]


def karta(p: dict) -> str:
    """Pełny rozkład jednej pozycji: greki, progi, scenariusze wygaśnięcia."""
    g = p["greki"]
    if g:
        dopiski = {
            "delta": f'{_licz(p["delta_akcji"])} shares',
            "gamma": f'{p["gamma"]:+.2f} on the position',
            "vega": f'{_pln(p["vega"])} on the position',
            "theta": f'{_pln(p["theta"])} per day',
        }
        grek = '<div class="kafle">' + "".join(
            _kafel(nazwa, f'{g.get(klucz, 0.0):+.5f}'.rstrip("0").rstrip("."),
                   "", dopiski.get(klucz, opis))
            for klucz, nazwa, opis in OPIS_GREKOW) + '</div>'
    else:
        grek = '<div class="tresc uwaga">Greeks not computed — no underlying price or IV.</div>'

    wiersze = "".join(
        f'<tr><td class="tyk">{s["zmiana"]:+.0%}</td>'
        f'<td class="l num">{_pln(s["kurs"])}</td>'
        f'<td class="l num {_kl(s["opcja"])}">{_pln(s["opcja"])}</td>'
        f'<td class="l num {_kl(s["akcje"])}">{_pln(s["akcje"])}</td>'
        f'<td class="l num {_kl(s["razem"])}"><b>{_pln(s["razem"])}</b></td>'
        f'<td class="uwaga">{"shares called away" if s["przypisanie"] else ""}</td></tr>'
        for s in p["scenariusze"])
    tabela_sc = (
        '<div class="przewin"><table><thead><tr><th>Move</th><th class="l">Price</th>'
        '<th class="l">Option</th><th class="l">Shares</th><th class="l">Total</th>'
        f'<th></th></tr></thead><tbody>{wiersze}</tbody></table></div>'
    ) if wiersze else '<div class="tresc uwaga">No underlying price — scenarios not computed.</div>'

    uwagi = "".join(f'<div class="kom uw">{e(u)}</div>' for u in p["uwagi"])

    return f'''<div class="karta">
  <h2>{e(p["etykieta"])}<span class="obok">{p["ilosc"]:+.0f} {_odm(int(abs(p["ilosc"])), "contract", "contracts")}
      · expires {e(p["wygasa"])} · {p["dni"]} {_odm(p["dni"], "day", "days")}</span></h2>
  {uwagi}
  <div class="tresc"><p class="uwaga">
    Premium {_pln(p["premia"])}, buying it back would cost {_pln(p["teraz"])} today —
    {_proc(p["zrealizowany_udzial"] * 100, znak=False)} of the maximum profit already
    banked. On assignment the shares go at {_pln(p["cena_efektywna"])} each
    (strike {_pln(p["strike"])} plus the premium spread over the shares), which is
    {_proc(p["zwrot_przypisanie"] * 100)} against today\'s price.
    Cover {_proc(p["pokrycie"] * 100, znak=False)}: {_licz(p["akcje_pod"])} shares
    against {_licz(p["akcje_zaang"])} required. Time value {_pln(p["wartosc_czasowa"])}
    per share — that is what disappears by expiry.
  </p></div>
  {grek}
  <h2 style="margin-top:4px">P/L at expiry<span class="obok">option leg and share leg
      separately, and combined</span></h2>
  {tabela_sc}
</div>'''


def pasek_alertow(a: dict) -> str:
    """Czerwony pasek nad wszystkim — to jest rzecz, na którą trzeba zareagować."""
    if not a.get("alerty"):
        return ""
    w = []
    for x in a["alerty"]:
        w.append(f'<b>{e(x["etykieta"])}</b>: option at {_pln(x["cena_teraz"])} '
                 f'(threshold {_pln(x["cena_docelowa"])}), buying back today would give '
                 f'{_pln(x["zysk"])} — {e(" · ".join(x["powody"]))}')
    return '<div class="kom zle"><b>Buyback threshold reached</b><br>' + "<br>".join(w) + '</div>'


def tabela_odkupu(poz: list[dict]) -> str:
    """Przy jakiej cenie opcji i jakim kursie bazowego warto odkupić."""
    wiersze = []
    for p in poz:
        o = p.get("odkup")
        if not o:
            continue
        for i, lv in enumerate(o["poziomy"]):
            zalecany = abs(lv["udzial"] - o["udzial_docelowy"]) < 1e-9
            kurs = _pln(lv["kurs_bazowego"]) if lv["kurs_bazowego"] else "—"
            znacznik = (' <span class="plak ok">recommended</span>' if zalecany else "")
            osiagniete = (' <span class="plak zle">reached</span>'
                          if lv["osiagniete"] else "")
            wiersze.append(
                f'<tr><td class="tyk">{e(p["etykieta"]) if i == 0 else ""}</td>'
                f'<td class="l num">{lv["udzial"]:.0%}{znacznik}{osiagniete}</td>'
                f'<td class="l num">{_pln(lv["cena"])}</td>'
                f'<td class="l num">{_pln(lv["koszt"])}</td>'
                f'<td class="l num up">{_pln(lv["zysk"])}</td>'
                f'<td class="l num">{kurs}</td>'
                f'<td class="l num">{_pln(p["spot"]) if i == 0 else ""}</td></tr>')
    if not wiersze:
        return '<div class="tresc uwaga">No short positions to buy back.</div>'
    return ('<div class="przewin"><table><thead><tr><th>Contract</th>'
            '<th class="l">Banked</th><th class="l">Buyback price</th>'
            '<th class="l">Cost to close</th><th class="l">Profit</th>'
            '<th class="l">Underlying at</th><th class="l">Price today</th>'
            f'</tr></thead><tbody>{"".join(wiersze)}</tbody></table></div>')


def tabela_miesiecy(m: list[dict]) -> str:
    if not m:
        return ('<div class="tresc uwaga">The trade ledger is empty — this table fills in '
                'after the first fetch that carries trades.</div>')
    w = ['<div class="przewin"><table><thead><tr><th>Month</th>'
         '<th class="l">Gross premium</th><th class="l">Fees</th>'
         '<th class="l">Net premium</th><th class="l">Buybacks</th>'
         '<th class="l">Realised P/L</th><th class="l">Sold</th>'
         '<th>Underlyings</th></tr></thead><tbody>']
    for x in m:
        spolki = ", ".join(f'{e(s["bazowy"])} {_pln(s["netto"])}' for s in x["spolki"][:5])
        w.append(f'<tr><td class="tyk">{e(x["nazwa"])}</td>'
                 f'<td class="l num">{_pln(x["brutto"])}</td>'
                 f'<td class="l num">−{_pln(x["prowizje"])}</td>'
                 f'<td class="l num up"><b>{_pln(x["netto"])}</b></td>'
                 f'<td class="l num">{_pln(x["odkup"])}</td>'
                 f'<td class="l num {_kl(x["zrealizowany"])}">{_pln(x["zrealizowany"])}</td>'
                 f'<td class="l num">{_licz(x["kontraktow_sprzedanych"])}</td>'
                 f'<td class="uwaga">{spolki}</td></tr>')
    w.append('</tbody></table></div>')
    return "".join(w)


def tabela_kubelkow(k: list[dict]) -> str:
    """Rozkład ekspozycji po terminach wygaśnięcia."""
    if not k:
        return '<div class="tresc uwaga">No open contracts.</div>'
    w = ['<div class="przewin"><table><thead><tr><th>Expiry</th>'
         '<th class="l">Positions</th><th class="l">Contracts</th>'
         '<th class="l">Premium</th><th class="l">To collect</th>'
         '<th class="l">Delta</th><th class="l">Theta/d</th>'
         '<th class="l">Capital at assign.</th></tr></thead><tbody>']
    for x in k:
        w.append(f'<tr><td class="tyk">{e(x["kubelek"])}</td>'
                 f'<td class="l num">{x["pozycji"]}</td>'
                 f'<td class="l num">{_licz(x["kontraktow"])}</td>'
                 f'<td class="l num">{_pln(x["premia"])}</td>'
                 f'<td class="l num">{_pln(x["do_zainkasowania"])}</td>'
                 f'<td class="l num">{_licz(x["delta_akcji"])}</td>'
                 f'<td class="l num {_kl(x["theta"])}">{_pln(x["theta"])}</td>'
                 f'<td class="l num">{_pln(x["notional"])}</td></tr>')
    w.append('</tbody></table></div>')
    return "".join(w)


def karta_cyklu(c: dict) -> str:
    """Jak kończyły się dotychczasowe kontrakty."""
    if not c or not c.get("zdarzen"):
        return ""
    kafle_c = "".join([
        _kafel("Expired worthless", f'{c["wygaslo"]}', "up",
               f'{_licz(c["kontraktow_wygaslo"])} contracts · the premium is kept in full'),
        _kafel("Assigned", f'{c["przypisano"]}', "mut",
               f'{_licz(c["kontraktow_przypisano"])} contracts · shares went at the strike'),
        _kafel("P/L on shares sold", _pln(c["wynik_nogi_akcyjnej"]),
               _kl(c["wynik_nogi_akcyjnej"]), "from forced sales on assignment"),
    ])
    najs = ""
    if c.get("najslabsze"):
        wiersze = "".join(
            f'<tr><td class="tyk">{e(x["symbol"])}</td><td>{e(x["data"])}</td>'
            f'<td class="l num">{_pln(x["cena"])}</td>'
            f'<td class="l num {_kl(x["wynik"])}">{_pln(x["wynik"])}</td></tr>'
            for x in c["najslabsze"] if x["wynik"] < 0)
        if wiersze:
            najs = ('<div class="przewin"><table><thead><tr><th>Underlying</th><th>Date</th>'
                    '<th class="l">Strike price</th><th class="l">P/L</th>'
                    f'</tr></thead><tbody>{wiersze}</tbody></table></div>')
    return f'''<div class="karta"><h2>How contracts have ended<span class="obok">
      {c["zdarzen"]} events in the ledger</span></h2>
    <div class="kafle">{kafle_c}</div>
    <div class="tresc"><p class="uwaga">Expiring worthless is the best ending: the premium is kept in
      full. On assignment the premium is kept too, but the shares go at the strike
      — and the real result of the trade sits on that sale. The option row itself
      shows zero, because the premium was banked earlier, so looking only at it
      would suggest assignment costs nothing.</p></div>
    {najs}
  </div>'''


def zakladka(a: dict | None) -> str:
    if not a:
        return ('<div data-panel="opcje" class="panel-ukryty"><div class="karta"><div class="tresc uwaga">'
                'No option data.</div></div></div>')
    if not a["pozycje"]:
        return (f'<div data-panel="opcje" class="panel-ukryty"><div class="karta">'
                f'<h2>Options</h2>{kafle(a)}<div class="tresc uwaga">'
                f'No open option positions. The tiles above show the premium '
                f'banked this month.</div></div></div>')
    karty = "".join(karta(p) for p in a["pozycje"])
    r = a["rejestr"]
    stopka = (f'The trade ledger holds {r["wierszy"]} '
              f'{_odm(r["wierszy"], "entry", "entries")} '
              f'from {r["od"]} to {r["do"]}. '
              'Flex returns trades from the last session only, so premium for earlier '
              'periods fills in with subsequent fetches.') if r["wierszy"] else (
        'The trade ledger is empty — monthly premium fills in after the first fetch '
        'that carries trades.')
    return f'''<div data-panel="opcje" class="panel-ukryty">
  {pasek_alertow(a)}
  <div class="karta"><h2>Options<span class="obok">as of {e(a["data"])}</span></h2>
    {kafle(a)}
    <div class="tresc"><p class="uwaga">{stopka}<br>
      Implied volatility and the Greeks come from the Black-Scholes-Merton model,
      inverted from the market price of the option at a rate of
      {_proc(a["stopa"] * 100, znak=False)}. P(ITM) is the probability of expiring
      in the money under the martingale measure; P(touch) is the probability the
      price touches the strike at least once before expiry.</p></div>
  </div>
  <div class="karta"><h2>Open positions</h2>{tabela(a["pozycje"])}</div>
  <div class="karta"><h2>When to buy back<span class="obok">threshold scaled to days left</span></h2>{tabela_odkupu(a["pozycje"])}
    <div class="tresc"><p class="uwaga">The "Underlying at" column says at what share price the option
      would cost what the column beside it shows — at today\'s volatility and
      today\'s expiry. Time decay alone lowers the price without any move, so the
      threshold is usually reached before the price gets there.</p></div>
  </div>
  <div class="karta"><h2>Expiry dates<span class="obok">where risk sits in time</span></h2>{tabela_kubelkow(a.get("kubelki") or [])}</div>
  {karta_cyklu(a.get("cykl") or {})}
  <div class="karta"><h2>Month by month<span class="obok">from actual trades only</span></h2>{tabela_miesiecy(a["miesiace"])}</div>
  {karty}
</div>'''
