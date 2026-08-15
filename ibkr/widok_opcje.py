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


def _odm(n: int, jeden: str, kilka: str, wiele: str) -> str:
    if n == 1:
        return jeden
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return kilka
    return wiele


def _kafel(etykieta: str, wartosc: str, klasa: str = "", pod: str = "") -> str:
    return (f'<div class="kafel"><div class="et">{e(etykieta)}</div>'
            f'<div class="w num {klasa}">{wartosc}</div>'
            f'<div class="pod num">{pod}</div></div>')


def kafle(a: dict) -> str:
    """Nagłówkowe liczby. Premia i zysk są rozdzielone celowo: premia
    z żywego kontraktu nie jest jeszcze zyskiem, bo trzeba go móc odkupić."""
    m, s, r = a["miesiac"], a["podsumowanie"], a["rejestr"]
    kompletny = bool(r["od"]) and r["od"] <= m["od"]
    przypis = ("cały miesiąc" if kompletny
               else f'rejestr dopiero od {r["od"]}' if r["od"] else "rejestr pusty")
    iv = _proc(s["iv_srednia"] * 100, znak=False) if s.get("iv_srednia") else "—"
    k = [
        _kafel("Premia w tym miesiącu", _pln(m["netto"]),
               "up" if m["netto"] > 0 else "mut",
               f'brutto {_pln(m["brutto"])} − prowizje {_pln(m["prowizje"])}'),
        _kafel("Sprzedanych kontraktów", _licz(m["kontraktow_sprzedanych"]), "",
               f'{m["transakcji"]} {_odm(m["transakcji"], "transakcja", "transakcje", "transakcji")} · {przypis}'),
        _kafel("Zysk zrealizowany", _pln(m["zrealizowany"]), _kl(m["zrealizowany"]),
               "pozycje domknięte i wygasłe"),
        _kafel("Wynik otwarty", _pln(s["zysk_otwarty"]), _kl(s["zysk_otwarty"]),
               f'z premii {_pln(s["premia"])}'),
        _kafel("Zostało do wzięcia", _pln(s["do_zainkasowania"]), "mut",
               "gdyby wszystko wygasło bez wartości"),
        _kafel("Delta portfela opcji", f'{_licz(s["delta_akcji"])} akcji',
               _kl(s["delta_akcji"]), f'{_pln(s["delta_dolarowa"])} ekspozycji'),
        _kafel("Theta dzienna", _pln(s["theta_dzienna"]), _kl(s["theta_dzienna"]),
               "tyle daje sam upływ doby"),
        _kafel("Vega", _pln(s["vega"]), _kl(s["vega"]), "na 1 pkt proc. zmienności"),
        _kafel("Średnia IV", iv, "mut", "ważona liczbą kontraktów"),
        _kafel("Kapitał pod przypisaniem", _pln(s["notional"]), "mut",
               f'{_licz(s["kontraktow"])} {_odm(int(s["kontraktow"]), "kontrakt", "kontrakty", "kontraktów")}'),
    ]
    return '<div class="kafle">' + "".join(k) + '</div>'


def tabela(poz: list[dict]) -> str:
    if not poz:
        return '<div class="tresc uwaga">Brak otwartych pozycji opcyjnych.</div>'
    w = ['<div class="przewin"><table data-sortowalna id="tabOpcje"><thead><tr>'
         '<th class="sort">Kontrakt</th><th class="l">Szt.</th><th class="l">Spot</th>'
         '<th class="l">Strike</th><th class="l">Do strike</th><th class="l">Dni</th>'
         '<th class="l">IV</th><th class="l">Delta</th><th class="l">Theta/d</th>'
         '<th class="l">P(ITM)</th><th class="l">P(dotk.)</th><th class="l">Premia</th>'
         '<th class="l">Odkup</th><th class="l">Wynik</th><th class="l">Zwrot p.a.</th>'
         '<th>Stan</th></tr></thead><tbody>']
    for p in poz:
        plak = []
        if p["w_pieniadzu"]:
            plak.append('<span class="plak zle">w pieniądzu</span>')
        if p["pokrycie"] < 1.0:
            plak.append('<span class="plak uw">niepokryty</span>')
        if p["ryzyko_wczesniejszego"]:
            plak.append('<span class="plak uw">ryzyko wykonania</span>')
        if not plak:
            plak.append('<span class="plak ok">poza pieniądzem</span>')
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
    ("delta", "Delta", "zmiana wartości na 1 $ ruchu bazowego"),
    ("gamma", "Gamma", "jak szybko zmienia się sama delta"),
    ("vega", "Vega", "wpływ 1 pkt proc. zmienności"),
    ("theta", "Theta", "ubytek wartości przez jedną dobę"),
    ("rho", "Rho", "wpływ 1 pkt proc. stopy"),
    ("vanna", "Vanna", "delta wobec zmienności"),
    ("volga", "Volga", "vega wobec zmienności"),
    ("charm", "Charm", "delta wobec upływu czasu"),
]


def karta(p: dict) -> str:
    """Pełny rozkład jednej pozycji: greki, progi, scenariusze wygaśnięcia."""
    g = p["greki"]
    if g:
        dopiski = {
            "delta": f'{_licz(p["delta_akcji"])} akcji',
            "gamma": f'{p["gamma"]:+.2f} na pozycji',
            "vega": f'{_pln(p["vega"])} na pozycji',
            "theta": f'{_pln(p["theta"])} dziennie',
        }
        grek = '<div class="kafle">' + "".join(
            _kafel(nazwa, f'{g.get(klucz, 0.0):+.5f}'.rstrip("0").rstrip("."),
                   "", dopiski.get(klucz, opis))
            for klucz, nazwa, opis in OPIS_GREKOW) + '</div>'
    else:
        grek = '<div class="tresc uwaga">Greków nie policzono — brak kursu bazowego albo IV.</div>'

    wiersze = "".join(
        f'<tr><td class="tyk">{s["zmiana"]:+.0%}</td>'
        f'<td class="l num">{_pln(s["kurs"])}</td>'
        f'<td class="l num {_kl(s["opcja"])}">{_pln(s["opcja"])}</td>'
        f'<td class="l num {_kl(s["akcje"])}">{_pln(s["akcje"])}</td>'
        f'<td class="l num {_kl(s["razem"])}"><b>{_pln(s["razem"])}</b></td>'
        f'<td class="uwaga">{"akcje odchodzą" if s["przypisanie"] else ""}</td></tr>'
        for s in p["scenariusze"])
    tabela_sc = (
        '<div class="przewin"><table><thead><tr><th>Ruch</th><th class="l">Kurs</th>'
        '<th class="l">Opcja</th><th class="l">Akcje</th><th class="l">Razem</th>'
        f'<th></th></tr></thead><tbody>{wiersze}</tbody></table></div>'
    ) if wiersze else '<div class="tresc uwaga">Brak kursu bazowego — scenariuszy nie liczę.</div>'

    uwagi = "".join(f'<div class="kom uw">{e(u)}</div>' for u in p["uwagi"])

    return f'''<div class="karta">
  <h2>{e(p["etykieta"])}<span class="obok">{p["ilosc"]:+.0f} {_odm(int(abs(p["ilosc"])), "kontrakt", "kontrakty", "kontraktów")}
      · wygasa {e(p["wygasa"])} · {p["dni"]} {_odm(p["dni"], "dzień", "dni", "dni")}</span></h2>
  {uwagi}
  <div class="tresc"><p class="uwaga">
    Premia {_pln(p["premia"])}, odkupienie kosztowałoby dziś {_pln(p["teraz"])} —
    zainkasowane {_proc(p["zrealizowany_udzial"] * 100, znak=False)} maksymalnego zysku.
    Przy przypisaniu akcje odchodzą po {_pln(p["cena_efektywna"])} za sztukę
    (strike {_pln(p["strike"])} plus premia rozłożona na akcję), co daje
    {_proc(p["zwrot_przypisanie"] * 100)} wobec dzisiejszego kursu.
    Pokrycie {_proc(p["pokrycie"] * 100, znak=False)}: {_licz(p["akcje_pod"])} akcji
    na {_licz(p["akcje_zaang"])} potrzebnych. Wartość czasowa {_pln(p["wartosc_czasowa"])}
    na akcję — to ona znika do dnia wygaśnięcia.
  </p></div>
  {grek}
  <h2 style="margin-top:4px">Wynik w dniu wygaśnięcia<span class="obok">osobno noga
      opcyjna i akcyjna, oraz razem</span></h2>
  {tabela_sc}
</div>'''


def pasek_alertow(a: dict) -> str:
    """Czerwony pasek nad wszystkim — to jest rzecz, na którą trzeba zareagować."""
    if not a.get("alerty"):
        return ""
    w = []
    for x in a["alerty"]:
        w.append(f'<b>{e(x["etykieta"])}</b>: opcja po {_pln(x["cena_teraz"])} '
                 f'(próg {_pln(x["cena_docelowa"])}), odkup dałby dziś '
                 f'{_pln(x["zysk"])} — {e(" · ".join(x["powody"]))}')
    return '<div class="kom zle"><b>Próg odkupu osiągnięty</b><br>' + "<br>".join(w) + '</div>'


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
            znacznik = (' <span class="plak ok">zalecany</span>' if zalecany else "")
            osiagniete = (' <span class="plak zle">osiągnięty</span>'
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
        return '<div class="tresc uwaga">Brak krótkich pozycji do odkupu.</div>'
    return ('<div class="przewin"><table><thead><tr><th>Kontrakt</th>'
            '<th class="l">Zainkasowane</th><th class="l">Cena odkupu</th>'
            '<th class="l">Koszt zamknięcia</th><th class="l">Zysk</th>'
            '<th class="l">Kurs bazowego</th><th class="l">Kurs dziś</th>'
            f'</tr></thead><tbody>{"".join(wiersze)}</tbody></table></div>')


def tabela_miesiecy(m: list[dict]) -> str:
    if not m:
        return ('<div class="tresc uwaga">Rejestr transakcji jest pusty — '
                'zestawienie wypełni się po pierwszym pobraniu z transakcjami.</div>')
    w = ['<div class="przewin"><table><thead><tr><th>Miesiąc</th>'
         '<th class="l">Premia brutto</th><th class="l">Prowizje</th>'
         '<th class="l">Premia netto</th><th class="l">Odkupy</th>'
         '<th class="l">Zysk zrealizowany</th><th class="l">Sprzedanych</th>'
         '<th>Spółki</th></tr></thead><tbody>']
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


def zakladka(a: dict | None) -> str:
    if not a:
        return ('<div data-panel="opcje" class="panel-ukryty"><div class="karta"><div class="tresc uwaga">'
                'Brak danych o opcjach.</div></div></div>')
    if not a["pozycje"]:
        return (f'<div data-panel="opcje" class="panel-ukryty"><div class="karta">'
                f'<h2>Opcje</h2>{kafle(a)}<div class="tresc uwaga">'
                f'Brak otwartych pozycji opcyjnych. Kafle powyżej pokazują premię '
                f'zainkasowaną w tym miesiącu.</div></div></div>')
    karty = "".join(karta(p) for p in a["pozycje"])
    r = a["rejestr"]
    stopka = (f'Rejestr transakcji obejmuje {r["wierszy"]} '
              f'{_odm(r["wierszy"], "pozycję", "pozycje", "pozycji")} '
              f'od {r["od"]} do {r["do"]}. '
              'Flex oddaje transakcje tylko z ostatniej sesji, więc premia za wcześniejsze '
              'okresy uzupełni się dopiero z kolejnymi pobraniami.') if r["wierszy"] else (
        'Rejestr transakcji jest pusty — premia miesięczna wypełni się po pierwszym '
        'pobraniu z transakcjami.')
    return f'''<div data-panel="opcje" class="panel-ukryty">
  {pasek_alertow(a)}
  <div class="karta"><h2>Opcje<span class="obok">stan na {e(a["data"])}</span></h2>
    {kafle(a)}
    <div class="tresc"><p class="uwaga">{stopka}<br>
      Zmienność implikowana i greki liczone są z modelu Blacka-Scholesa-Mertona,
      odwróconego z ceny rynkowej opcji przy stopie {_proc(a["stopa"] * 100, znak=False)}.
      P(ITM) to prawdopodobieństwo wygaśnięcia w pieniądzu w mierze martyngałowej,
      P(dotk.) — że kurs dotknie strike'a choć raz przed terminem.</p></div>
  </div>
  <div class="karta"><h2>Otwarte pozycje</h2>{tabela(a["pozycje"])}</div>
  <div class="karta"><h2>Kiedy odkupić<span class="obok">próg dobrany do liczby dni
      do wygaśnięcia</span></h2>{tabela_odkupu(a["pozycje"])}
    <div class="tresc"><p class="uwaga">Kolumna „Kurs bazowego" mówi, przy jakim
      kursie akcji opcja kosztowałaby tyle co w kolumnie obok — przy dzisiejszej
      zmienności i dzisiejszym terminie. Sam upływ czasu obniża cenę i bez ruchu
      kursu, więc próg zwykle zostanie osiągnięty wcześniej niż przy tym kursie.</p></div>
  </div>
  <div class="karta"><h2>Miesiąc po miesiącu<span class="obok">wyłącznie z faktycznych
      transakcji</span></h2>{tabela_miesiecy(a["miesiace"])}</div>
  {karty}
</div>'''
