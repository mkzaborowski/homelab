"""Widok panelu: statystyki portfela, edycja koszyków/stopów, pobieranie raportu."""
from __future__ import annotations

from html import escape as e

STYL = """
*{box-sizing:border-box}
body{margin:0;background:#0d1420;color:#e6edf6;font:15px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif}
a{color:#7dd3a0;text-decoration:none}a:hover{text-decoration:underline}
.top{background:#141d2b;border-bottom:1px solid #223041;padding:14px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.marka{font-weight:700}.tag{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#7b8ea6}
.top nav{margin-left:auto;display:flex;gap:14px;align-items:center}
.wrap{max-width:1240px;margin:0 auto;padding:22px}
.panel{background:#141d2b;border:1px solid #223041;border-radius:14px;overflow:hidden;margin-bottom:18px}
.panel h2{margin:0;padding:13px 18px;font-size:13px;letter-spacing:.04em;border-bottom:1px solid #223041;color:#a7bdd6;text-transform:uppercase}
.tresc{padding:18px}
.kafle{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}
.kafel{background:#0f1826;border:1px solid #223041;border-radius:12px;padding:14px 16px}
.kafel .et{font-size:10.5px;text-transform:uppercase;letter-spacing:.13em;color:#7b8ea6}
.kafel .wart{font-size:21px;font-weight:700;margin-top:5px;letter-spacing:-.02em}
.zielony{color:#5ee6a0}.czerwony{color:#ff8b8b}.zolty{color:#fbd38d}.szary{color:#7b8ea6}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;padding:9px 12px;color:#7b8ea6;font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid #223041;font-weight:600}
td{padding:9px 12px;border-bottom:1px solid #1b2636}
tr:last-child td{border-bottom:0}
tr:hover td{background:#0f1826}
td.l{text-align:right;font-variant-numeric:tabular-nums}
th.l{text-align:right}
.koszyk td{background:#101b2a;font-weight:600}
.lot td{color:#8fa5bd;font-size:12.5px}
.pasek{height:6px;background:#1b2636;border-radius:99px;overflow:hidden;min-width:80px}
.pasek i{display:block;height:100%;background:linear-gradient(90deg,#2f6f4f,#5ee6a0)}
.btn{display:inline-flex;align-items:center;gap:7px;background:#2f6f4f;color:#eafff2;border:0;border-radius:9px;padding:9px 16px;font:inherit;font-weight:600;cursor:pointer;font-size:14px}
.btn:hover{background:#3a8a62;text-decoration:none}
.btn.szary{background:#243244;color:#cfe0f2}.btn.szary:hover{background:#2e4058}
input,select{font:inherit;padding:7px 10px;border:1px solid #2b3a4d;border-radius:8px;background:#0d1420;color:#e6edf6;font-size:13px}
input:focus,select:focus{outline:0;border-color:#3f7d5c}
input.mini{width:92px}
.kom{padding:11px 16px;border-radius:10px;margin-bottom:16px;font-size:14px;font-weight:500}
.kom.ok{background:#123524;color:#8ff0b8}.kom.zle{background:#3a1a1a;color:#ffb4b4}
.plak{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:2px 7px;border-radius:6px}
.plak.itm{background:#4a1d1d;color:#ffb4b4}.plak.otm{background:#123524;color:#8ff0b8}
.plak.brak{background:#3a2f14;color:#fbd38d}
.uwaga{font-size:11.5px;color:#7b8ea6;margin-top:6px}
.dwie{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:900px){.dwie{grid-template-columns:1fr}}
"""


def _pln(v, w="$"):
    if v is None:
        return "—"
    return f"{v:,.2f} {w}"


def _proc(v):
    return "—" if v is None else f"{v:+.2f}%"


def _kl(v):
    if v is None:
        return "szary"
    return "zielony" if v >= 0 else "czerwony"


def logowanie(blad: str = "") -> str:
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Portfel — logowanie</title><style>{STYL}</style></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh">
<form method="post" action="/login" class="panel" style="padding:28px;max-width:360px;width:100%;margin:0">
    <div class="tag">portfel IBKR</div>
    <h1 style="margin:8px 0 18px;font-size:21px">Panel portfela</h1>
    {f'<div class="kom zle">{e(blad)}</div>' if blad else ''}
    <input type="password" name="haslo" placeholder="Hasło" autofocus required style="width:100%;margin-bottom:12px">
    <button class="btn" style="width:100%;justify-content:center">Zaloguj</button>
</form></body></html>"""


def _wykres_nav(historia: list[tuple[str, float]]) -> str:
    if len(historia) < 2:
        return '<div class="uwaga">Wykres pojawi się po drugim pobraniu danych.</div>'
    wart = [v for _, v in historia]
    lo, hi = min(wart), max(wart)
    rozp = (hi - lo) or 1
    szer, wys = 1000, 150
    pkt = []
    for i, v in enumerate(wart):
        x = i / (len(wart) - 1) * szer
        y = wys - (v - lo) / rozp * (wys - 20) - 10
        pkt.append(f"{x:.1f},{y:.1f}")
    linia = " ".join(pkt)
    wzrost = wart[-1] >= wart[0]
    kolor = "#5ee6a0" if wzrost else "#ff8b8b"
    return f"""<svg viewBox="0 0 {szer} {wys}" preserveAspectRatio="none" style="width:100%;height:150px">
      <polyline points="{linia}" fill="none" stroke="{kolor}" stroke-width="2.5" vector-effect="non-scaling-stroke"/>
    </svg>
    <div style="display:flex;justify-content:space-between" class="uwaga">
      <span>{e(historia[0][0])} · {historia[0][1]:,.0f}</span>
      <span>{e(historia[-1][0])} · {historia[-1][1]:,.0f}</span>
    </div>"""


def _tabela_pozycji(pods: dict) -> str:
    w = ['<table><thead><tr><th>Pozycja</th><th class="l">Akcje</th><th class="l">Cena wejścia</th>'
         '<th class="l">Cena</th><th class="l">Wartość</th><th class="l">Wynik</th><th class="l">%</th>'
         '<th class="l">Stop</th><th class="l">Do stopu</th><th>Udział</th></tr></thead><tbody>']
    for k in pods["koszyki"]:
        w.append(f'<tr class="koszyk"><td>{e(k["koszyk"])}</td><td class="l"></td><td class="l"></td>'
                 f'<td class="l"></td><td class="l">{_pln(k["wartosc"])}</td>'
                 f'<td class="l {_kl(k["zysk"])}">{_pln(k["zysk"])}</td>'
                 f'<td class="l {_kl(k["zysk_proc"])}">{_proc(k["zysk_proc"])}</td><td></td><td></td>'
                 f'<td><div class="pasek"><i style="width:{min(k["udzial"],100):.1f}%"></i></div>'
                 f'<span class="uwaga">{k["udzial"]:.1f}%</span></td></tr>')
        for t in k["tickery"]:
            w.append(f'<tr><td><b>{e(t["symbol"])}</b> <span class="szary">{e(t["opis"][:28])}</span></td>'
                     f'<td class="l">{t["ilosc"]:,.0f}</td><td class="l">{_pln(t["cena_kosztu"])}</td>'
                     f'<td class="l">{_pln(t["cena"])}</td><td class="l">{_pln(t["wartosc"])}</td>'
                     f'<td class="l {_kl(t["zysk"])}">{_pln(t["zysk"])}</td>'
                     f'<td class="l {_kl(t["zysk_proc"])}">{_proc(t["zysk_proc"])}</td><td></td><td></td>'
                     f'<td class="uwaga">{t["udzial"]:.1f}%</td></tr>')
            for lot in t["loty"]:
                stop = _pln(lot["stop"]) if lot.get("stop") else '<span class="plak brak">brak</span>'
                dost = _proc(lot["do_stopu_proc"]) if lot.get("do_stopu_proc") is not None else "—"
                w.append(f'<tr class="lot"><td>&nbsp;&nbsp;&nbsp;lot od {e(str(lot.get("data_otwarcia",""))[:10])}</td>'
                         f'<td class="l">{lot.get("ilosc",0):,.0f}</td><td class="l">{_pln(lot.get("cena_kosztu"))}</td>'
                         f'<td class="l">{_pln(lot.get("cena"))}</td><td class="l">{_pln(lot.get("wartosc"))}</td>'
                         f'<td class="l {_kl(lot.get("zysk"))}">{_pln(lot.get("zysk"))}</td>'
                         f'<td class="l {_kl(lot.get("zysk_proc"))}">{_proc(lot.get("zysk_proc"))}</td>'
                         f'<td class="l">{stop}</td><td class="l">{dost}</td><td></td></tr>')
    w.append("</tbody></table>")
    return "".join(w)


def _tabela_cc(cc: list[dict]) -> str:
    if not cc:
        return '<div class="tresc uwaga">Brak wystawionych calli.</div>'
    w = ['<table><thead><tr><th>Bazowy</th><th class="l">Kontrakty</th><th class="l">Strike</th>'
         '<th>Wygasa</th><th class="l">Dni</th><th class="l">Spot</th><th class="l">Do strike</th>'
         '<th>Status</th><th class="l">Wynik</th></tr></thead><tbody>']
    for c in cc:
        st = '<span class="plak itm">w pieniądzu</span>' if c["w_pieniadzu"] else '<span class="plak otm">poza</span>'
        if not c["pokryte"]:
            st += ' <span class="plak brak">niepokryty</span>'
        w.append(f'<tr><td><b>{e(c["bazowy"])}</b></td><td class="l">{c["kontrakty"]:,.0f}</td>'
                 f'<td class="l">{_pln(c["strike"])}</td><td>{e(c["wygasa"])}</td>'
                 f'<td class="l">{c["dni_do_wygasniecia"] if c["dni_do_wygasniecia"] is not None else "—"}</td>'
                 f'<td class="l">{_pln(c["spot"])}</td>'
                 f'<td class="l {_kl(c["do_strike_proc"])}">{_proc(c["do_strike_proc"])}</td>'
                 f'<td>{st}</td><td class="l {_kl(c["wynik"])}">{_pln(c["wynik"])}</td></tr>')
    w.append("</tbody></table>")
    return "".join(w)


def _formularz_meta(pods: dict, koszyki: list[str]) -> str:
    w = ['<table><thead><tr><th>Ticker</th><th>Koszyk</th><th>Ocena</th><th>Stop (GTC)</th><th></th></tr></thead><tbody>']
    symbole = sorted({p["symbol"] for p in pods["pozycje"]})
    meta = {p["symbol"]: p for p in pods["pozycje"]}
    for s in symbole:
        p = meta[s]
        opcje = "".join(f'<option{" selected" if k == p["koszyk"] else ""}>{e(k)}</option>'
                        for k in dict.fromkeys(koszyki + [p["koszyk"], "Nieprzypisane"]))
        w.append(f'<tr><td><form method="post" action="/meta" style="display:flex;gap:8px;align-items:center">'
                 f'<input type="hidden" name="symbol" value="{e(s)}"><b>{e(s)}</b></td>'
                 f'<td><select name="koszyk">{opcje}</select> '
                 f'<input class="mini" name="nowy_koszyk" placeholder="nowy…"></td>'
                 f'<td><input class="mini" name="ocena" value="{e(p.get("ocena",""))}"></td>'
                 f'<td><input class="mini" name="stop" value="{p.get("stop") or ""}" placeholder="np. 280"></td>'
                 f'<td><button class="btn szary">Zapisz</button></form></td></tr>')
    w.append("</tbody></table>")
    return "".join(w)


def panel(pods: dict | None, historia, koszyki, przebiegi, komunikat="", blad=False,
          sheets_ok=False, dni=None) -> str:
    if not pods:
        srodek = """<div class="panel"><div class="tresc">
        <p>Brak danych. Uzupełnij <code>IBKR_TOKEN</code> i <code>IBKR_QUERY_ID</code>
        w <code>/opt/ibkr/.env</code>, a potem kliknij „Pobierz teraz”.</p>
        <form method="post" action="/odswiez"><button class="btn">Pobierz teraz</button></form>
        </div></div>"""
    else:
        ostrz = []
        if pods["cc_w_pieniadzu"]:
            ostrz.append(f'{pods["cc_w_pieniadzu"]} call(e) w pieniądzu — ryzyko przypisania')
        if pods["cc_niepokryte"]:
            ostrz.append(f'{pods["cc_niepokryte"]} call(e) bez pokrycia w akcjach')
        if pods["pozycje_bez_stopa"]:
            ostrz.append(f'{pods["pozycje_bez_stopa"]} pozycji bez wpisanego stopa')
        pasek_ostrz = ('<div class="kom zle">⚠ ' + " · ".join(ostrz) + "</div>") if ostrz else ""

        srodek = f"""
        {pasek_ostrz}
        <div class="panel"><h2>Podsumowanie — {e(pods['kwartal'])} · stan na {e(pods['data'])}</h2><div class="tresc">
          <div class="kafle">
            <div class="kafel"><div class="et">NAV</div><div class="wart">{_pln(pods['nav'])}</div></div>
            <div class="kafel"><div class="et">Wartość pozycji</div><div class="wart">{_pln(pods['wartosc_pozycji'])}</div></div>
            <div class="kafel"><div class="et">Gotówka</div><div class="wart">{_pln(pods['gotowka'])}</div>
                 <div class="uwaga">{pods['udzial_gotowki']:.1f}% aktywów</div></div>
            <div class="kafel"><div class="et">Wynik otwarty</div>
                 <div class="wart {_kl(pods['zysk'])}">{_pln(pods['zysk'])}</div>
                 <div class="uwaga {_kl(pods['zysk_proc'])}">{_proc(pods['zysk_proc'])}</div></div>
            <div class="kafel"><div class="et">Zmiana dzienna</div>
                 <div class="wart {_kl(pods['zmiana_nav_proc'])}">{_proc(pods['zmiana_nav_proc'])}</div></div>
            <div class="kafel"><div class="et">Koncentracja top 5</div><div class="wart">{pods['koncentracja_top5']:.1f}%</div></div>
            <div class="kafel"><div class="et">Ryzyko stopów</div>
                 <div class="wart czerwony">{_pln(pods['ryzyko_stopow'])}</div>
                 <div class="uwaga">gdyby wszystkie stopy zadziałały</div></div>
            <div class="kafel"><div class="et">Pozycje / tickery</div>
                 <div class="wart">{pods['liczba_pozycji']} / {pods['liczba_tickerow']}</div></div>
          </div>
        </div></div>

        <div class="panel"><h2>NAV w czasie</h2><div class="tresc">{_wykres_nav(historia)}</div></div>

        <div class="panel"><h2>Pozycje wg koszyków</h2>{_tabela_pozycji(pods)}</div>

        <div class="panel"><h2>Covered calls</h2>{_tabela_cc(pods['covered_calls'])}</div>

        <div class="dwie">
          <div class="panel"><h2>Najlepsze</h2><table><tbody>
            {''.join(f'<tr><td><b>{e(p["symbol"])}</b></td><td class="l {_kl(p["zysk"])}">{_pln(p["zysk"])}</td>'
                     f'<td class="l {_kl(p["zysk_proc"])}">{_proc(p["zysk_proc"])}</td></tr>' for p in pods['najlepsze'])}
          </tbody></table></div>
          <div class="panel"><h2>Najsłabsze</h2><table><tbody>
            {''.join(f'<tr><td><b>{e(p["symbol"])}</b></td><td class="l {_kl(p["zysk"])}">{_pln(p["zysk"])}</td>'
                     f'<td class="l {_kl(p["zysk_proc"])}">{_proc(p["zysk_proc"])}</td></tr>' for p in pods['najgorsze'])}
          </tbody></table></div>
        </div>

        <div class="panel"><h2>Koszyki, oceny i stopy (dane wprowadzane ręcznie)</h2>
          {_formularz_meta(pods, koszyki)}
          <div class="tresc uwaga">Stop-lossy są zleceniami GTC w IBKR — Flex nie udostępnia
          otwartych zleceń, więc poziom wpisujesz tutaj. Realizacja stopa (data i cena sprzedaży)
          zaciąga się automatycznie z transakcji.</div>
        </div>"""

    log = "".join(f'<tr><td>{e(p["kiedy"])}</td><td>{"OK" if p["ok"] else "błąd"}</td>'
                  f'<td class="uwaga">{e(p["komunikat"] or "")}</td></tr>' for p in przebiegi)

    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Portfel IBKR</title><style>{STYL}</style></head><body>
<header class="top">
  <span class="marka">Portfel</span><span class="tag">IBKR · {e(pods['konto']) if pods else 'brak danych'}</span>
  <nav>
    <form method="post" action="/odswiez" style="display:inline"><button class="btn">Pobierz teraz</button></form>
    <a class="btn szary" href="/pobierz.xlsx">Pobierz Excel</a>
    <a href="/wyloguj">Wyloguj</a>
  </nav>
</header>
<div class="wrap">
  {f'<div class="kom {"zle" if blad else "ok"}">{e(komunikat)}</div>' if komunikat else ''}
  {srodek}
  <div class="panel"><h2>Ostatnie pobrania {'· Google Sheets podłączone' if sheets_ok else '· Google Sheets nieskonfigurowane'}</h2>
    <table><tbody>{log or '<tr><td class="uwaga">Brak wpisów.</td></tr>'}</tbody></table></div>
</div></body></html>"""
