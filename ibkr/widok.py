"""Widok panelu portfela.

Układ i typografia celowo bliżej terminala brokerskiego niż strony marketingowej:
jasne tło, wąskie wiersze, cyfry tabelaryczne, kolor tylko tam, gdzie niesie
znaczenie (wynik, ostrzeżenie). Wykresy rysujemy sami w SVG - żadnych bibliotek
z CDN-u, panel ma działać bez wychodzenia na zewnątrz.
"""
from __future__ import annotations

import json
from html import escape as e

import widok_opcje

STYL = """
*{box-sizing:border-box}
:root{
  --tlo:#f4f6f9; --plyta:#fff; --linia:#dfe4ec; --linia2:#eef1f6;
  --tekst:#16202e; --przygas:#63718a; --slaby:#8b98ad;
  --granat:#12395b; --granat2:#1c4f7c; --akcent:#0b6bcb;
  --wzrost:#0a7d55; --spadek:#c0392b; --ostrzez:#9a6700; --tlo-ostrz:#fff8e6;
  --wzrost-tlo:#e8f5ef; --spadek-tlo:#fdecea;
}
@media (prefers-color-scheme:dark){:root{
  --tlo:#0e141d; --plyta:#151d28; --linia:#26313f; --linia2:#1d2632;
  --tekst:#e7edf5; --przygas:#93a3b8; --slaby:#6f7f95;
  --granat:#0f2f4c; --granat2:#17456e; --akcent:#4d9be8;
  --wzrost:#3fbf8a; --spadek:#ef6b5c; --ostrzez:#d9a441; --tlo-ostrz:#2b230f;
  --wzrost-tlo:#12281f; --spadek-tlo:#2a1715;
}}
body{margin:0;background:var(--tlo);color:var(--tekst);
  font:13.5px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--akcent);text-decoration:none}a:hover{text-decoration:underline}
.num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum"}

/* --- pasek górny --- */
.top{background:var(--granat);color:#fff;padding:0 20px;display:flex;align-items:center;gap:18px}
.top .marka{font-weight:650;font-size:15px;letter-spacing:-.01em;padding:13px 0}
.top .konto{font-size:11.5px;color:#a9c4dc;font-variant-numeric:tabular-nums}
.top .prawo{margin-left:auto;display:flex;align-items:center;gap:9px}
.top a{color:#cfe0f0}
.zakladki{background:var(--plyta);border-bottom:1px solid var(--linia);padding:0 20px;
  display:flex;gap:2px;overflow-x:auto}
.zakladki button{background:0;border:0;border-bottom:2px solid transparent;padding:11px 15px;
  font:inherit;font-weight:550;color:var(--przygas);cursor:pointer;white-space:nowrap}
.zakladki button:hover{color:var(--tekst)}
.zakladki button[aria-selected=true]{color:var(--akcent);border-bottom-color:var(--akcent)}

.wrap{max-width:1400px;margin:0 auto;padding:18px 20px 40px}
.karta{background:var(--plyta);border:1px solid var(--linia);border-radius:6px;margin-bottom:14px}
.karta>h2{margin:0;padding:11px 15px;font-size:11px;font-weight:650;letter-spacing:.07em;
  text-transform:uppercase;color:var(--przygas);border-bottom:1px solid var(--linia2);
  display:flex;align-items:center;gap:10px}
.karta>h2 .obok{margin-left:auto;font-weight:500;letter-spacing:0;text-transform:none;font-size:12px}
.tresc{padding:15px}
.siatka{display:grid;gap:14px}
@media(min-width:900px){.dwie{grid-template-columns:1fr 1fr}.trzy{grid-template-columns:2fr 1fr}}

/* --- kafle --- */
.kafle{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  border-top:1px solid var(--linia2)}
.kafel{padding:13px 15px;border-right:1px solid var(--linia2);border-bottom:1px solid var(--linia2)}
.kafel .et{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--slaby)}
.kafel .w{font-size:20px;font-weight:640;letter-spacing:-.02em;margin-top:4px}
.kafel .pod{font-size:11.5px;color:var(--przygas);margin-top:2px}
.up{color:var(--wzrost)}.down{color:var(--spadek)}.mut{color:var(--slaby)}

/* --- tabele --- */
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:8px 12px;font-size:10.5px;font-weight:650;letter-spacing:.06em;
  text-transform:uppercase;color:var(--slaby);border-bottom:1px solid var(--linia);
  white-space:nowrap;background:var(--plyta);position:sticky;top:0;z-index:1}
th.sort{cursor:pointer;user-select:none}
th.sort:hover{color:var(--tekst)}
th.sort::after{content:"⇅";opacity:.35;margin-left:5px;font-size:10px}
th.sort[data-kier=asc]::after{content:"↑";opacity:1}
th.sort[data-kier=desc]::after{content:"↓";opacity:1}
td{padding:7px 12px;border-bottom:1px solid var(--linia2);white-space:nowrap}
tbody tr:hover td{background:var(--tlo)}
td.l,th.l{text-align:right}
tr.grupa td{background:var(--tlo);font-weight:600;border-bottom:1px solid var(--linia)}
tr.lot td{color:var(--przygas);font-size:12.5px}
tr.lot td:first-child{padding-left:30px}
.tyk{font-weight:600}
.opis{color:var(--slaby);font-weight:400;margin-left:6px}

/* --- drobne elementy --- */
.plak{display:inline-block;font-size:10px;font-weight:650;letter-spacing:.04em;
  text-transform:uppercase;padding:2px 6px;border-radius:3px;line-height:1.5}
.plak.zle{background:var(--spadek-tlo);color:var(--spadek)}
.plak.ok{background:var(--wzrost-tlo);color:var(--wzrost)}
.plak.uw{background:var(--tlo-ostrz);color:var(--ostrzez)}
.pasek{height:5px;background:var(--linia2);border-radius:3px;overflow:hidden;min-width:60px}
.pasek i{display:block;height:100%;background:var(--akcent)}
.btn{display:inline-flex;align-items:center;gap:6px;background:var(--akcent);color:#fff;border:0;
  border-radius:4px;padding:7px 13px;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer}
.btn:hover{filter:brightness(1.08);text-decoration:none;color:#fff}
.btn.drugi{background:transparent;color:#cfe0f0;border:1px solid #3d6c93}
.btn.drugi:hover{background:rgba(255,255,255,.1)}
.btn.jasny{background:transparent;color:var(--akcent);border:1px solid var(--linia)}
.btn.jasny:hover{background:var(--tlo);color:var(--akcent)}
input,select{font:inherit;font-size:12.5px;padding:5px 8px;border:1px solid var(--linia);
  border-radius:4px;background:var(--plyta);color:var(--tekst)}
input:focus,select:focus{outline:0;border-color:var(--akcent);box-shadow:0 0 0 2px rgba(11,107,203,.15)}
input.mini{width:84px}
.kom{padding:10px 14px;border-radius:5px;margin-bottom:14px;font-size:13px;
  border:1px solid var(--linia);background:var(--plyta)}
.kom.zle{background:var(--spadek-tlo);border-color:var(--spadek);color:var(--spadek)}
.kom.uw{background:var(--tlo-ostrz);border-color:#e8d08a;color:var(--ostrzez)}
.uwaga{font-size:11.5px;color:var(--slaby)}
.przewin{overflow-x:auto}
.wysoka{max-height:560px;overflow:auto}
.zakres{display:flex;gap:1px;background:var(--linia2);border-radius:4px;padding:2px}
.zakres button{border:0;background:0;font:inherit;font-size:11.5px;font-weight:600;
  padding:4px 10px;border-radius:3px;color:var(--przygas);cursor:pointer}
.zakres button[aria-pressed=true]{background:var(--plyta);color:var(--tekst);
  box-shadow:0 1px 2px rgba(0,0,0,.08)}
.legenda{display:flex;flex-wrap:wrap;gap:12px;font-size:11.5px;color:var(--przygas);margin-top:8px}
.legenda span{display:flex;align-items:center;gap:5px}
.kropka{width:9px;height:9px;border-radius:2px;display:inline-block}
.panel-ukryty{display:none}
"""

PALETA = ["#0b6bcb", "#0a7d55", "#9a6700", "#7b4fb5", "#c0392b", "#0e7490",
          "#b45309", "#4f6bed", "#2f8f4e", "#8c5a2b"]


def _pln(v, waluta="$"):
    if v is None:
        return "—"
    znak = "-" if v < 0 else ""
    return f"{znak}{waluta}{abs(v):,.2f}"


def _proc(v, znak=True):
    if v is None:
        return "—"
    return f"{v:+.2f}%" if znak else f"{v:.2f}%"


def _kl(v):
    if v is None:
        return "mut"
    return "up" if v >= 0 else "down"


def _dzien(s: str) -> str:
    """IBKR podaje daty jako YYYYMMDD - w tabeli chcemy YYYY-MM-DD."""
    s = (s or "").strip()[:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _odm(n: int, jeden: str, kilka: str, wiele: str) -> str:
    """Polska odmiana liczebnika: 1 spółka, 2-4 spółki, 5+ spółek."""
    if n == 1:
        return jeden
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return kilka
    return wiele


# --------------------------------------------------------------------------- #
#  wykresy (czyste SVG, bez bibliotek)
# --------------------------------------------------------------------------- #

def _wykres_slupkowy(dane: list[tuple[str, float, str]], wys=170) -> str:
    """dane: (etykieta, wartość, kolor). Słupki pionowe z osią zerową."""
    if not dane:
        return '<div class="uwaga">Brak danych.</div>'
    maks = max((abs(v) for _, v, _ in dane), default=1) or 1
    szer, luz = 1000, 6
    sz_slupka = szer / len(dane)
    zero = wys / 2 if any(v < 0 for _, v, _ in dane) else wys - 18
    skala = (zero - 10) / maks if zero > 10 else 1
    el = [f'<line x1="0" y1="{zero}" x2="{szer}" y2="{zero}" stroke="var(--linia)" stroke-width="1"/>']
    for i, (etykieta, v, kolor) in enumerate(dane):
        h = abs(v) * skala
        x = i * sz_slupka + luz / 2
        y = zero - h if v >= 0 else zero
        el.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{sz_slupka - luz:.1f}" height="{max(h,1):.1f}" '
                  f'fill="{kolor}" rx="2"><title>{e(etykieta)}: {v:,.2f}</title></rect>')
        el.append(f'<text x="{x + (sz_slupka - luz) / 2:.1f}" y="{wys - 4}" text-anchor="middle" '
                  f'font-size="11" fill="var(--slaby)">{e(etykieta)}</text>')
    return (f'<svg viewBox="0 0 {szer} {wys}" preserveAspectRatio="none" '
            f'style="width:100%;height:{wys}px;overflow:visible">{"".join(el)}</svg>')


def _wykres_poziomy(dane: list[tuple[str, float, float]], fmt=None) -> str:
    """dane: (etykieta, wartość do pokazania, udział 0-100). Lista z paskami."""
    if not dane:
        return '<div class="uwaga">Brak danych.</div>'
    fmt = fmt or (lambda v: f"{v:,.2f}%")
    maks = max((abs(u) for _, _, u in dane), default=1) or 1
    w = ['<table><tbody>']
    for i, (etykieta, v, u) in enumerate(dane):
        kolor = PALETA[i % len(PALETA)]
        w.append(f'<tr><td style="width:34%">{e(etykieta)}</td>'
                 f'<td style="width:46%"><div class="pasek">'
                 f'<i style="width:{abs(u) / maks * 100:.1f}%;background:{kolor}"></i></div></td>'
                 f'<td class="l num" style="width:20%">{fmt(v)}</td></tr>')
    w.append('</tbody></table>')
    return "".join(w)


def _pierscien(dane: list[tuple[str, float]]) -> str:
    """Pierścień udziałów - czytelniejszy niż pełne koło przy wielu kategoriach."""
    suma = sum(v for _, v in dane) or 1
    r, gr = 60, 22
    obwod = 2 * 3.14159265 * r
    offset, seg, leg = 0.0, [], []
    for i, (etykieta, v) in enumerate(dane):
        czesc = v / suma * obwod
        kolor = PALETA[i % len(PALETA)]
        seg.append(f'<circle cx="80" cy="80" r="{r}" fill="none" stroke="{kolor}" '
                   f'stroke-width="{gr}" stroke-dasharray="{czesc:.2f} {obwod - czesc:.2f}" '
                   f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 80 80)">'
                   f'<title>{e(etykieta)}: {v / suma * 100:.1f}%</title></circle>')
        leg.append(f'<span><i class="kropka" style="background:{kolor}"></i>'
                   f'{e(etykieta)} <b class="num">{v / suma * 100:.1f}%</b></span>')
        offset += czesc
    return (f'<div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">'
            f'<svg viewBox="0 0 160 160" style="width:160px;height:160px;flex:none">{"".join(seg)}</svg>'
            f'<div class="legenda" style="flex-direction:column;gap:6px;margin:0">{"".join(leg)}</div></div>')


def _wykres_nav(hist: list[dict]) -> str:
    """Wykres NAV rysowany po stronie klienta, żeby przełączanie zakresu było natychmiastowe."""
    if len(hist) < 2:
        return ('<div class="tresc uwaga">Wykres pojawi się po drugim pobraniu danych — '
                'potrzebne są co najmniej dwa punkty.</div>')
    return f"""
    <div class="tresc" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;
         border-bottom:1px solid var(--linia2);padding-bottom:12px">
      <div class="zakres" id="zakresNav">
        <button data-dni="30">1M</button><button data-dni="90">3M</button>
        <button data-dni="365">1R</button><button data-dni="0" aria-pressed="true">Wszystko</button>
      </div>
      <div class="uwaga" id="podpisNav" style="margin-left:auto"></div>
    </div>
    <div class="tresc"><div id="wykresNav"></div></div>
    <script>window.HIST = {json.dumps(hist)};</script>"""


SKRYPT = r"""
<script>
(function(){
  // --- zakładki ---
  document.querySelectorAll('.zakladki button').forEach(function(b){
    b.onclick = function(){
      document.querySelectorAll('.zakladki button').forEach(function(x){x.setAttribute('aria-selected','false')});
      b.setAttribute('aria-selected','true');
      document.querySelectorAll('[data-panel]').forEach(function(p){
        p.classList.toggle('panel-ukryty', p.dataset.panel !== b.dataset.cel);
      });
      try{ localStorage.setItem('zakladka', b.dataset.cel); }catch(e){}
      if(b.dataset.cel === 'przeglad') rysujNav();
    };
  });
  try{
    var z = localStorage.getItem('zakladka');
    if(z){ var b = document.querySelector('.zakladki button[data-cel="'+z+'"]'); if(b) b.click(); }
  }catch(e){}

  // --- sortowanie tabel ---
  document.querySelectorAll('table[data-sortowalna] th.sort').forEach(function(th){
    th.onclick = function(){
      var tab = th.closest('table'), tb = tab.tBodies[0];
      var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
      var kier = th.dataset.kier === 'desc' ? 'asc' : 'desc';
      tab.querySelectorAll('th.sort').forEach(function(x){ delete x.dataset.kier; });
      th.dataset.kier = kier;
      var wiersze = Array.prototype.slice.call(tb.rows);
      wiersze.sort(function(a,b){
        var x = a.cells[idx], y = b.cells[idx];
        var vx = x && x.dataset.v !== undefined ? parseFloat(x.dataset.v) : NaN;
        var vy = y && y.dataset.v !== undefined ? parseFloat(y.dataset.v) : NaN;
        if(isNaN(vx) || isNaN(vy)){
          var sx = x ? x.textContent.trim() : '', sy = y ? y.textContent.trim() : '';
          return kier === 'asc' ? sx.localeCompare(sy) : sy.localeCompare(sx);
        }
        return kier === 'asc' ? vx - vy : vy - vx;
      });
      wiersze.forEach(function(r){ tb.appendChild(r); });
    };
  });

  // --- filtrowanie ---
  document.querySelectorAll('[data-filtr]').forEach(function(inp){
    inp.oninput = function(){
      var q = inp.value.trim().toUpperCase();
      var tab = document.querySelector(inp.dataset.filtr);
      if(!tab) return;
      Array.prototype.slice.call(tab.tBodies[0].rows).forEach(function(r){
        var pas = r.textContent.toUpperCase().indexOf(q) > -1
               || (r.dataset.sym || '').toUpperCase().indexOf(q) > -1;
        r.style.display = !q || pas ? '' : 'none';
      });
    };
  });

  // --- wykres NAV ---
  var dni = 0;
  function fmt(n){ return '$' + n.toLocaleString('pl-PL',{minimumFractionDigits:0,maximumFractionDigits:0}); }
  function rysujNav(){
    var cel = document.getElementById('wykresNav');
    if(!cel || !window.HIST) return;
    var h = window.HIST.slice();
    if(dni > 0){
      var granica = new Date(); granica.setDate(granica.getDate() - dni);
      var f = h.filter(function(p){ return new Date(p.data) >= granica; });
      if(f.length > 1) h = f;
    }
    if(h.length < 2){ cel.innerHTML = '<div class="uwaga">Za mało punktów w tym zakresie.</div>'; return; }
    var W = 1000, H = 220, PB = 26;
    var wart = h.map(function(p){ return p.nav; });
    var lo = Math.min.apply(null, wart), hi = Math.max.apply(null, wart);
    var mar = (hi - lo) * 0.08 || Math.abs(hi * 0.02) || 1;
    lo -= mar; hi += mar;
    var x = function(i){ return i / (h.length - 1) * W; };
    var y = function(v){ return (H - PB) - (v - lo) / (hi - lo) * (H - PB - 8); };
    var linia = h.map(function(p,i){ return (i?'L':'M') + x(i).toFixed(1) + ' ' + y(p.nav).toFixed(1); }).join(' ');
    var obszar = linia + ' L ' + W + ' ' + (H-PB) + ' L 0 ' + (H-PB) + ' Z';
    var rosnie = wart[wart.length-1] >= wart[0];
    var kol = rosnie ? 'var(--wzrost)' : 'var(--spadek)';
    var siatka = '', kroki = 4;
    for(var i=0;i<=kroki;i++){
      var v = lo + (hi-lo)*i/kroki, yy = y(v);
      siatka += '<line x1="0" y1="'+yy.toFixed(1)+'" x2="'+W+'" y2="'+yy.toFixed(1)+'" stroke="var(--linia2)"/>'
             +  '<text x="4" y="'+(yy-3).toFixed(1)+'" font-size="10" fill="var(--slaby)">'+fmt(v)+'</text>';
    }
    var etyk = '';
    [0, Math.floor((h.length-1)/2), h.length-1].forEach(function(i){
      var ank = i===0?'start':(i===h.length-1?'end':'middle');
      etyk += '<text x="'+x(i).toFixed(1)+'" y="'+(H-8)+'" font-size="10" fill="var(--slaby)" text-anchor="'+ank+'">'+h[i].data+'</text>';
    });
    cel.innerHTML = '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;height:220px">'
      + '<defs><linearGradient id="gr" x1="0" x2="0" y1="0" y2="1">'
      + '<stop offset="0%" stop-color="'+kol+'" stop-opacity=".22"/>'
      + '<stop offset="100%" stop-color="'+kol+'" stop-opacity="0"/></linearGradient></defs>'
      + siatka + '<path d="'+obszar+'" fill="url(#gr)"/>'
      + '<path d="'+linia+'" fill="none" stroke="'+kol+'" stroke-width="2" vector-effect="non-scaling-stroke"/>'
      + etyk + '</svg>';
    var zm = wart[wart.length-1] - wart[0];
    var zmp = wart[0] ? zm / wart[0] * 100 : 0;
    var p = document.getElementById('podpisNav');
    if(p) p.innerHTML = h[0].data + ' → ' + h[h.length-1].data + ' · <b class="'
      + (zm>=0?'up':'down') + '">' + (zm>=0?'+':'') + fmt(zm) + ' (' + zmp.toFixed(2) + '%)</b>';
  }
  var zn = document.getElementById('zakresNav');
  if(zn) zn.querySelectorAll('button').forEach(function(b){
    b.onclick = function(){
      zn.querySelectorAll('button').forEach(function(x){ x.setAttribute('aria-pressed','false'); });
      b.setAttribute('aria-pressed','true');
      dni = parseInt(b.dataset.dni,10); rysujNav();
    };
  });
  rysujNav();

  // --- zwijanie koszyków ---
  document.querySelectorAll('[data-zwin]').forEach(function(el){
    el.onclick = function(){
      var kl = el.dataset.zwin, otw = el.dataset.otw !== '0';
      el.dataset.otw = otw ? '0' : '1';
      el.textContent = otw ? '▸' : '▾';
      document.querySelectorAll('tr[data-nal="'+kl+'"]').forEach(function(r){
        r.style.display = otw ? 'none' : '';
      });
    };
  });
})();
</script>
"""


# --------------------------------------------------------------------------- #
#  strony
# --------------------------------------------------------------------------- #

def logowanie(blad: str = "") -> str:
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Portfel — logowanie</title><style>{STYL}</style></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh">
<form method="post" action="/login" class="karta" style="max-width:340px;width:100%;margin:0">
  <h2>Panel portfela</h2>
  <div class="tresc">
    {f'<div class="kom zle">{e(blad)}</div>' if blad else ''}
    <input type="password" name="haslo" placeholder="Hasło" autofocus required
           style="width:100%;margin-bottom:10px;padding:8px 10px">
    <button class="btn" style="width:100%;justify-content:center;padding:9px">Zaloguj</button>
  </div>
</form></body></html>"""


def _kafle(p: dict, okresy: dict) -> str:
    k = [("NAV", _pln(p["nav"]), "", ""),
         ("Zmiana dzienna", _proc(p["zmiana_nav_proc"]),
          _kl(p["zmiana_nav_proc"]), ""),
         ("Wartość pozycji", _pln(p["wartosc_pozycji"]), "",
          f'{p["liczba_tickerow"]} spółek · {p["liczba_pozycji"]} lotów'),
         ("Wynik otwarty", _pln(p["zysk"]), _kl(p["zysk"]), _proc(p["zysk_proc"])),
         ("Gotówka", _pln(p["gotowka"]), "", f'{p["udzial_gotowki"]:.1f}% aktywów'),
         ("Zyskownych / stratnych", f'{p["zyskownych"]} / {p["stratnych"]}', "", ""),
         ("Koncentracja top 5", f'{p["koncentracja_top5"]:.1f}%', "",
          f'HHI {p["hhi"]:,.0f}'),
         ("Ryzyko stopów", _pln(p["ryzyko_stopow"]),
          "down" if p["ryzyko_stopow"] else "mut", "gdyby wszystkie zadziałały")]
    for etykieta, dane in okresy.items():
        k.append((etykieta, _proc(dane["proc"]), _kl(dane["proc"]),
                  f'od {dane["od"]} · {_pln(dane["kwota"])}'))
    return '<div class="kafle">' + "".join(
        f'<div class="kafel"><div class="et">{e(t)}</div>'
        f'<div class="w num {kl}">{w}</div>'
        f'<div class="pod num">{pod}</div></div>' for t, w, kl, pod in k) + '</div>'


def _tabela_pozycji(p: dict) -> str:
    w = ['<div class="przewin"><table data-sortowalna id="tabPozycje"><thead><tr>'
         '<th style="width:22px"></th><th class="sort">Pozycja</th>'
         '<th class="sort l">Ilość</th><th class="sort l">Wejście</th><th class="sort l">Kurs</th>'
         '<th class="sort l">Wartość</th><th class="sort l">Wynik</th><th class="sort l">%</th>'
         '<th class="sort l">Dzień</th><th class="sort l">Stop</th><th class="sort l">Do stopu</th>'
         '<th class="sort l">Udział</th></tr></thead><tbody>']
    for i, k in enumerate(p["koszyki"]):
        kl = f"k{i}"
        w.append(f'<tr class="grupa"><td><span data-zwin="{kl}" data-otw="1" '
                 f'style="cursor:pointer;color:var(--slaby)">▾</span></td>'
                 f'<td>{e(k["koszyk"])}</td><td class="l"></td><td class="l"></td><td class="l"></td>'
                 f'<td class="l num" data-v="{k["wartosc"]}">{_pln(k["wartosc"])}</td>'
                 f'<td class="l num {_kl(k["zysk"])}" data-v="{k["zysk"]}">{_pln(k["zysk"])}</td>'
                 f'<td class="l num {_kl(k["zysk_proc"])}" data-v="{k["zysk_proc"]}">{_proc(k["zysk_proc"])}</td>'
                 f'<td class="l"></td><td class="l"></td><td class="l"></td>'
                 f'<td class="l num" data-v="{k["udzial"]}">{k["udzial"]:.2f}%</td></tr>')
        for t in k["tickery"]:
            w.append(f'<tr data-nal="{kl}" data-sym="{e(t["symbol"])}"><td></td>'
                     f'<td><span class="tyk">{e(t["symbol"])}</span>'
                     f'<span class="opis">{e((t["opis"] or "")[:30])}</span></td>'
                     f'<td class="l num" data-v="{t["ilosc"]}">{t["ilosc"]:,.0f}</td>'
                     f'<td class="l num" data-v="{t["cena_kosztu"]}">{_pln(t["cena_kosztu"])}</td>'
                     f'<td class="l num" data-v="{t["cena"]}">{_pln(t["cena"])}</td>'
                     f'<td class="l num" data-v="{t["wartosc"]}">{_pln(t["wartosc"])}</td>'
                     f'<td class="l num {_kl(t["zysk"])}" data-v="{t["zysk"]}">{_pln(t["zysk"])}</td>'
                     f'<td class="l num {_kl(t["zysk_proc"])}" data-v="{t["zysk_proc"]}">{_proc(t["zysk_proc"])}</td>'
                     f'<td class="l num {_kl(t["zmiana_dzienna"])}" '
                     f'data-v="{t["zmiana_dzienna"] if t["zmiana_dzienna"] is not None else ""}">'
                     f'{_proc(t["zmiana_dzienna"])}</td>'
                     f'<td class="l"></td><td class="l"></td>'
                     f'<td class="l num" data-v="{t["udzial"]}">{t["udzial"]:.2f}%</td></tr>')
            for lot in t["loty"]:
                stop = _pln(lot["stop"]) if lot.get("stop") else '<span class="plak uw">brak</span>'
                w.append(f'<tr class="lot" data-nal="{kl}" data-sym="{e(t["symbol"])}"><td></td>'
                         f'<td>lot {e(_dzien(str(lot.get("data_otwarcia", ""))))}</td>'
                         f'<td class="l num">{lot.get("ilosc", 0):,.0f}</td>'
                         f'<td class="l num">{_pln(lot.get("cena_kosztu"))}</td>'
                         f'<td class="l num">{_pln(lot.get("cena"))}</td>'
                         f'<td class="l num">{_pln(lot.get("wartosc"))}</td>'
                         f'<td class="l num {_kl(lot.get("zysk"))}">{_pln(lot.get("zysk"))}</td>'
                         f'<td class="l num {_kl(lot.get("zysk_proc"))}">{_proc(lot.get("zysk_proc"))}</td>'
                         f'<td class="l"></td><td class="l num">{stop}</td>'
                         f'<td class="l num">{_proc(lot.get("do_stopu_proc"))}</td>'
                         f'<td class="l"></td></tr>')
    w.append('</tbody></table></div>')
    return "".join(w)


def _tabela_cc(cc: list[dict]) -> str:
    if not cc:
        return ('<div class="tresc uwaga">Brak wystawionych calli. Sekcja wypełni się sama, '
                'gdy w portfelu pojawi się krótka opcja.</div>')
    w = ['<div class="przewin"><table><thead><tr><th>Bazowy</th><th class="l">Kontrakty</th>'
         '<th class="l">Strike</th><th>Wygasa</th><th class="l">Dni</th><th class="l">Spot</th>'
         '<th class="l">Do strike</th><th>Status</th><th class="l">Wynik</th>'
         '</tr></thead><tbody>']
    for c in cc:
        st = ('<span class="plak zle">w pieniądzu</span>' if c["w_pieniadzu"]
              else '<span class="plak ok">poza</span>')
        if not c["pokryte"]:
            st += ' <span class="plak uw">niepokryty</span>'
        w.append(f'<tr><td class="tyk">{e(c["bazowy"])}</td>'
                 f'<td class="l num">{c["kontrakty"]:,.0f}</td>'
                 f'<td class="l num">{_pln(c["strike"])}</td><td>{e(c["wygasa"])}</td>'
                 f'<td class="l num">{c["dni_do_wygasniecia"] if c["dni_do_wygasniecia"] is not None else "—"}</td>'
                 f'<td class="l num">{_pln(c["spot"])}</td>'
                 f'<td class="l num {_kl(c["do_strike_proc"])}">{_proc(c["do_strike_proc"])}</td>'
                 f'<td>{st}</td>'
                 f'<td class="l num {_kl(c["wynik"])}">{_pln(c["wynik"])}</td></tr>')
    w.append('</tbody></table></div>')
    return "".join(w)


def _formularz_meta(p: dict, koszyki: list[str]) -> str:
    wartosci: dict[str, float] = {}
    meta: dict[str, dict] = {}
    for poz in p["pozycje"]:
        s = poz["symbol"]
        wartosci[s] = wartosci.get(s, 0.0) + poz.get("wartosc", 0.0)
        meta.setdefault(s, poz)
    symbole = sorted(wartosci, key=lambda s: -wartosci[s])
    wszystkie = list(dict.fromkeys(koszyki + [m["koszyk"] for m in meta.values()] + ["Nieprzypisane"]))

    w = ['<form method="post" action="/meta">',
         '<div class="tresc" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;'
         'border-bottom:1px solid var(--linia2)">',
         '<label style="display:flex;gap:6px;align-items:center;font-size:12.5px">'
         '<input type="checkbox" onclick="document.querySelectorAll(\'input[name=zazn]\')'
         '.forEach(function(c){c.checked=this.checked}.bind(this))"> zaznacz wszystkie</label>',
         '<span class="uwaga">→ przypisz zaznaczone do:</span>',
         '<select name="masowy_koszyk"><option value="">— nie zmieniaj —</option>',
         "".join(f'<option>{e(k)}</option>' for k in wszystkie),
         '</select><input name="masowy_nowy" placeholder="albo nowy koszyk…" style="width:160px">',
         '<input placeholder="Szukaj tickera…" data-filtr="#tabMeta" style="width:150px">',
         '<button class="btn" style="margin-left:auto">Zapisz zmiany</button></div>',
         '<div class="przewin wysoka"><table id="tabMeta"><thead><tr><th style="width:26px"></th>'
         '<th>Ticker</th><th class="l">Udział</th><th>Koszyk</th><th>Ocena</th>'
         '<th>Stop (GTC)</th></tr></thead><tbody>']
    for s in symbole:
        poz = meta[s]
        opcje = "".join(f'<option{" selected" if k == poz["koszyk"] else ""}>{e(k)}</option>'
                        for k in wszystkie)
        udzial = wartosci[s] / p["suma_aktywow"] * 100 if p["suma_aktywow"] else 0.0
        w.append(f'<tr><td><input type="checkbox" name="zazn" value="{e(s)}"></td>'
                 f'<td><span class="tyk">{e(s)}</span>'
                 f'<span class="opis">{e((poz.get("opis") or "")[:24])}</span></td>'
                 f'<td class="l num">{udzial:.2f}%</td>'
                 f'<td><select name="koszyk__{e(s)}">{opcje}</select></td>'
                 f'<td><input class="mini" name="ocena__{e(s)}" value="{e(poz.get("ocena") or "")}"></td>'
                 f'<td><input class="mini" name="stop__{e(s)}" value="{poz.get("stop") or ""}" '
                 f'placeholder="np. 280"></td></tr>')
    w.append('</tbody></table></div><div class="tresc" style="border-top:1px solid var(--linia2)">'
             '<button class="btn">Zapisz zmiany</button>'
             '<span class="uwaga" style="margin-left:12px">Stop-lossy to zlecenia GTC w IBKR — '
             'Flex nie udostępnia otwartych zleceń, więc poziom wpisujesz tutaj. '
             'Realizacja stopa zaciąga się automatycznie z transakcji.</span></div></form>')
    return "".join(w)


def _tabela_wzorca(por: dict) -> str:
    """Zestawienie udziałów docelowych i faktycznych. Kolor tylko tam, gdzie
    przekroczono próg - inaczej cała tabela świeciłaby się bez powodu."""
    ETYKIETY = {"zgodne": ("Zgodne", "ok"), "dokup": ("Do dokupienia", "uw"),
                "sprzedaj": ("Nadwaga", "uw"), "brakuje": ("Brak w portfelu", "zle"),
                "nadmiarowa": ("Spoza wzorca", "zle")}
    w = ['<div class="przewin"><table data-sortowalna id="tabWzorzec"><thead><tr>'
         '<th class="sort">Ticker</th><th>Koszyk</th>'
         '<th class="sort l">Arkusz</th><th class="sort l">Cel</th>'
         '<th class="sort l">Faktycznie</th><th class="sort l">Różnica</th>'
         '<th class="sort l">Kwota korekty</th><th>Stan</th></tr></thead><tbody>']
    for p in por["pozycje"]:
        et, kl = ETYKIETY[p["rodzaj"]]
        zgodne = p["rodzaj"] == "zgodne"
        w.append(
            f'<tr><td><span class="tyk">{e(p["ticker"])}</span>'
            + (' <span class="plak ok">rdzeń</span>' if p["rdzenna"] else "")
            + f'</td><td class="uwaga">{e(p["koszyk"])}</td>'
            f'<td class="l num" data-v="{p["cel"]}">{p["cel"]:.2f}%</td>'
            f'<td class="l num" data-v="{p["faktyczne"]}">{p["faktyczne"]:.2f}%</td>'
            f'<td class="l num {"mut" if zgodne else _kl(p["roznica"])}" data-v="{p["roznica"]}">'
            f'{p["roznica"]:+.2f} pp</td>'
            f'<td class="l num">{"—" if zgodne else _pln(-p["kwota"])}</td>'
            f'<td><span class="plak {kl}">{et}</span></td></tr>')
    w.append("</tbody></table></div>")
    return "".join(w)


def panel(pods: dict | None, hist, koszyki, przebiegi, komunikat="", blad=False,
          sheets_ok=False, okresy=None, harmonogram="", porownanie=None,
          analiza_opcji=None) -> str:
    okresy = okresy or {}
    log = "".join(f'<tr><td class="num">{e(p["kiedy"])}</td>'
                  f'<td>{"OK" if p["ok"] else "<span class=\'plak zle\'>błąd</span>"}</td>'
                  f'<td class="uwaga">{e(p["komunikat"] or "")}</td></tr>' for p in przebiegi)

    if not pods:
        tresc = f"""<div data-panel="przeglad"><div class="karta"><div class="tresc">
          <p>Brak danych. Uzupełnij <code>IBKR_TOKEN</code> i <code>IBKR_QUERY_ID</code>
             w <code>/opt/ibkr/.env</code>, a potem pobierz raport.</p>
          <form method="post" action="/odswiez"><button class="btn">Pobierz teraz</button></form>
        </div></div>
        <div class="karta"><h2>Ostatnie pobrania</h2><table><tbody>{log}</tbody></table></div></div>"""
        zakladki = ""
    else:
        p = pods
        ostrz = []
        if p["cc_w_pieniadzu"]:
            n = p["cc_w_pieniadzu"]
            ostrz.append(f'{n} {_odm(n, "call", "calle", "calli")} w pieniądzu — ryzyko przypisania')
        if p["cc_niepokryte"]:
            n = p["cc_niepokryte"]
            ostrz.append(f'{n} {_odm(n, "call", "calle", "calli")} bez pokrycia w akcjach')
        if p["pozycje_bez_stopa"]:
            n = p["pozycje_bez_stopa"]
            ostrz.append(f'{n} {_odm(n, "spółka", "spółki", "spółek")} bez wpisanego stopa')
        pasek = f'<div class="kom uw">{" · ".join(ostrz)}</div>' if ostrz else ""

        udzialy = [(k["koszyk"], k["wartosc"]) for k in p["koszyki"]]
        if p["gotowka"] > 0:
            udzialy.append(("Gotówka", p["gotowka"]))
        # przy małym portfelu pokazujemy wszystko; przy dużym skrajne 6 z każdej
        # strony - inaczej te same spółki trafiały do wykresu dwa razy
        ruch = sorted(p["tickery"], key=lambda t: -t["zysk"])
        skrajne = ruch if len(ruch) <= 12 else ruch[:6] + ruch[-6:]
        rozklad = [(r["etykieta"], float(r["ile"]),
                    "var(--wzrost)" if r["dodatni"] else "var(--spadek)") for r in p["rozklad"]]

        zakladki = """<nav class="zakladki">
          <button data-cel="przeglad" aria-selected="true">Przegląd</button>
          <button data-cel="pozycje">Pozycje</button>
          <button data-cel="analiza">Analiza</button>
          <button data-cel="opcje">Opcje</button>
          <button data-cel="wzorzec">Wzorzec</button>
          <button data-cel="ustawienia">Ustawienia</button></nav>"""

        tresc = f"""
<div data-panel="przeglad">
  {pasek}
  <div class="karta"><h2>Podsumowanie<span class="obok">{e(p["kwartal"])} · stan na
      <b>{e(p["data"])}</b></span></h2>{_kafle(p, okresy)}</div>
  <div class="karta"><h2>NAV w czasie</h2>{_wykres_nav(hist)}</div>
  <div class="siatka dwie">
    <div class="karta"><h2>Struktura portfela</h2>
      <div class="tresc">{_pierscien(udzialy)}</div></div>
    <div class="karta"><h2>Największe i najsłabsze pozycje<span class="obok">wynik otwarty</span></h2>
      <div class="tresc">{_wykres_slupkowy([
          (t["symbol"], t["zysk"], "var(--wzrost)" if t["zysk"] >= 0 else "var(--spadek)")
          for t in skrajne])}</div></div>
  </div>
</div>

<div data-panel="pozycje" class="panel-ukryty">
  <div class="karta"><h2>Pozycje wg koszyków
      <span class="obok"><input placeholder="Szukaj…" data-filtr="#tabPozycje" style="width:170px"></span>
    </h2>{_tabela_pozycji(p)}</div>
  <div class="karta"><h2>Covered calls</h2>{_tabela_cc(p["covered_calls"])}</div>
</div>

<div data-panel="analiza" class="panel-ukryty">
  <div class="siatka dwie">
    <div class="karta"><h2>Rozkład wyników<span class="obok">liczba spółek</span></h2>
      <div class="tresc">{_wykres_slupkowy(rozklad)}</div></div>
    <div class="karta"><h2>Udział koszyków</h2><div class="tresc">{_wykres_poziomy(
        [(k["koszyk"], k["udzial"], k["udzial"]) for k in p["koszyki"]])}</div></div>
  </div>
  <div class="siatka dwie">
    <div class="karta"><h2>Kapitał wg długości trzymania</h2><div class="tresc">{_wykres_poziomy(
        [(w["etykieta"], w["wartosc"], w["wartosc"]) for w in p["wiek"]], fmt=_pln)}</div>
      <div class="tresc uwaga" style="padding-top:0">Liczone na lotach — data otwarcia każdej transzy.</div></div>
    <div class="karta"><h2>Ekspozycja walutowa</h2><div class="tresc">{_wykres_poziomy(
        [(w, v, v) for w, v in sorted(p["waluty"].items(), key=lambda x: -x[1])], fmt=_pln)}</div></div>
  </div>
  <div class="karta"><h2>Największe pozycje</h2><div class="przewin">
    <table data-sortowalna><thead><tr><th class="sort">Ticker</th><th class="sort l">Wartość</th>
      <th class="sort l">Udział</th><th class="sort l">Wynik</th><th class="sort l">%</th>
      </tr></thead><tbody>
      {"".join(f'<tr><td class="tyk">{e(t["symbol"])}<span class="opis">{e((t["opis"] or "")[:26])}</span></td>'
               f'<td class="l num" data-v="{t["wartosc"]}">{_pln(t["wartosc"])}</td>'
               f'<td class="l num" data-v="{t["wartosc"] / p["suma_aktywow"] * 100 if p["suma_aktywow"] else 0}">'
               f'{t["wartosc"] / p["suma_aktywow"] * 100 if p["suma_aktywow"] else 0:.2f}%</td>'
               f'<td class="l num {_kl(t["zysk"])}" data-v="{t["zysk"]}">{_pln(t["zysk"])}</td>'
               f'<td class="l num {_kl(t["zysk_proc"])}" data-v="{t["zysk_proc"]}">{_proc(t["zysk_proc"])}</td></tr>'
               for t in p["tickery"][:20])}
    </tbody></table></div></div>
</div>

{widok_opcje.zakladka(analiza_opcji)}

<div data-panel="wzorzec" class="panel-ukryty">
  {("" if porownanie else '<div class="karta"><div class="tresc uwaga">'
    'Nie udało się pobrać arkusza wzorcowego. Sprawdź log pobrań.</div></div>')}
  {(f"""
  <div class="karta"><h2>Zgodność z portfelem wzorcowym
      <span class="obok">próg tolerancji {porownanie["prog"]} pp ·
        wzorzec sumuje się do {porownanie["suma_wzorca"]:.1f}%</span></h2>
    <div class="kafle">
      <div class="kafel"><div class="et">Zgodne</div>
        <div class="w num up">{porownanie["licznik"].get("zgodne", 0)}</div></div>
      <div class="kafel"><div class="et">Do dokupienia</div>
        <div class="w num">{porownanie["licznik"].get("dokup", 0)}</div></div>
      <div class="kafel"><div class="et">Nadwaga</div>
        <div class="w num">{porownanie["licznik"].get("sprzedaj", 0)}</div></div>
      <div class="kafel"><div class="et">Brak w portfelu</div>
        <div class="w num down">{porownanie["licznik"].get("brakuje", 0)}</div></div>
      <div class="kafel"><div class="et">Spoza wzorca</div>
        <div class="w num down">{porownanie["licznik"].get("nadmiarowa", 0)}</div></div>
      <div class="kafel"><div class="et">Największa rozbieżność</div>
        <div class="w num">{porownanie["max_roznica"]:.2f} pp</div></div>
    </div>
  </div>

  <div class="karta"><h2>Koszyki</h2><div class="przewin"><table><thead><tr>
    <th>Koszyk</th><th class="l">Cel</th><th class="l">Faktycznie</th>
    <th class="l">Różnica</th></tr></thead><tbody>
    {"".join(f'<tr><td>{e(k["koszyk"])}</td>'
             f'<td class="l num">{k["cel"]:.2f}%</td>'
             f'<td class="l num">{k["faktyczne"]:.2f}%</td>'
             f'<td class="l num {"mut" if k["zgodne"] else _kl(k["roznica"])}">'
             f'{k["roznica"]:+.2f} pp</td></tr>' for k in porownanie["koszyki"])}
  </tbody></table></div></div>

  <div class="karta"><h2>Pominięte w porównaniu
      <span class="obok">{len(porownanie["pominiete"])} instrumentów ·
        dostępne uniwersum to {porownanie["suma_dostepnych"]:.1f}% wzorca</span></h2>
    <div class="tresc">
      <p class="uwaga" style="margin-bottom:10px">Kryptowaluty są wyłączone,
        a amerykańskich ETF-ów i instrumentów lewarowanych nie kupisz jako
        inwestor detaliczny z UE. Udziały pozostałych pozycji przeliczyliśmy
        tak, by sumowały się do 100% tego, co realnie możesz mieć
        (mnożnik {porownanie["skala"]:.3f}).</p>
      <div style="display:flex;flex-wrap:wrap;gap:6px">
        {"".join(f'<span class="plak {"zle" if p == "krypto" else "uw"}">{e(t)}</span>'
                 for t, p in porownanie["pominiete"])}
      </div>
    </div>
  </div>

  <div class="karta"><h2>Pozycje<span class="obok">posortowane po wielkości rozbieżności</span></h2>
    {_tabela_wzorca(porownanie)}
    <div class="tresc uwaga"><b>Arkusz</b> to udział wprost z Twojego wzorca,
      <b>Cel</b> to ten sam udział przeskalowany na dostępne uniwersum
      (mnożnik {porownanie["skala"]:.3f}) — dlatego Cel jest wyższy.
      Kwota korekty to wartość dokupu (dodatnia) albo
      sprzedaży (ujemna) potrzebna do zrównania udziału z wzorcem, liczona
      od sumy aktywów {_pln(porownanie["podstawa"])}.</div>
  </div>
  """ if porownanie else "")}
</div>

<div data-panel="ustawienia" class="panel-ukryty">
  <div class="karta"><h2>Koszyki, oceny i stopy<span class="obok">dane wprowadzane ręcznie</span></h2>
    {_formularz_meta(p, koszyki)}</div>
  <div class="karta"><h2>Pobrania<span class="obok">{e(harmonogram)} ·
      {"Google Sheets podłączone" if sheets_ok else "Google Sheets nieskonfigurowane"}</span></h2>
    <table><tbody>{log or '<tr><td class="uwaga">Brak wpisów.</td></tr>'}</tbody></table></div>
</div>"""

    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Portfel IBKR</title><style>{STYL}</style></head><body>
<header class="top">
  <span class="marka">Portfel</span>
  <span class="konto">{e(pods["konto"]) if pods else "—"}</span>
  <span class="prawo">
    <form method="post" action="/odswiez" style="display:inline"><button class="btn">Pobierz teraz</button></form>
    <a class="btn drugi" href="/pobierz.xlsx">Excel</a>
    <a href="/wyloguj">Wyloguj</a>
  </span>
</header>
{zakladki}
<div class="wrap">
  {f'<div class="kom {"zle" if blad else ""}">{e(komunikat)}</div>' if komunikat else ''}
  {tresc}
</div>
{SKRYPT}
</body></html>"""
