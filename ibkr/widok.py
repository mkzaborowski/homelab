"""Widok panelu portfela.

Układ i typografia celowo bliżej terminala brokerskiego niż strony marketingowej:
jasne tło, wąskie wiersze, cyfry tabelaryczne, kolor tylko tam, gdzie niesie
znaczenie (wynik, ostrzeżenie). Wykresy rysujemy sami w SVG - żadnych bibliotek
z CDN-u, panel ma działać bez wychodzenia na zewnątrz.
"""
from __future__ import annotations

import json
import os
import re
from html import escape as e
from urllib.parse import quote

import style
import widok_analityka
import historia
import przegladarka
import wykresy
import widok_opcje

STYL_DODATKOWY = """
*{box-sizing:border-box}
/* Stare nazwy zmapowane na nowe tokeny. Wcześniej ten arkusz definiował
   własny komplet kolorów RAZEM z zapytaniem o prefers-color-scheme, przez co
   zmienne, których nowy arkusz nie nadpisuje (--slaby, --przygas, --linia2),
   szły za ustawieniem systemu, a nie za wyborem użytkownika: kto miał ciemny
   system i wybrał jasny motyw, dostawał ciemne szarości w tabelach na białym
   tle. Aliasy zamiast wartości usuwają cały ten rozjazd u źródła. */
:root{
  --linia2: var(--linia);
  --przygas: var(--tekst-2);
  --slaby: var(--tekst-3);
  --granat: var(--akcent);
  --granat2: var(--akcent-2);
  --ostrzez: var(--uwaga);
  --tlo-ostrz: var(--uwaga-tlo);
}
body{margin:0;background:var(--tlo);color:var(--tekst);
  font:13.5px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--akcent);text-decoration:none}a:hover{text-decoration:underline}
.num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum"}

/* --- pasek górny --- */
.top{background:var(--plyta);color:var(--tekst);padding:0 20px;display:flex;align-items:center;gap:18px}
.top .marka{font-weight:650;font-size:15px;letter-spacing:-.01em;padding:13px 0}
.top .konto{font-size:11.5px;color:var(--tekst-2);font-variant-numeric:tabular-nums}
.top .prawo{margin-left:auto;display:flex;align-items:center;gap:9px}
.top a{color:var(--tekst-2)}
.zakladki{background:var(--plyta);border-bottom:1px solid var(--linia);padding:0 20px;
  display:flex;gap:2px;overflow-x:auto}
.zakladki button{background:0;border:0;border-bottom:2px solid transparent;padding:11px 15px;
  font:inherit;font-weight:550;color:var(--przygas);cursor:pointer;white-space:nowrap}
.zakladki button:hover{color:var(--tekst)}
/* --- wykres spółki w tabeli pozycji --- */
.wyk-otw{background:0;border:1px solid var(--linia);border-radius:4px;color:var(--tekst-2);
  font-size:10px;letter-spacing:.04em;text-transform:uppercase;padding:1px 6px;margin-left:8px;
  cursor:pointer;vertical-align:middle}
.wyk-otw:hover{color:var(--akcent);border-color:var(--akcent)}
.wyk-otw[aria-expanded=true]{color:var(--akcent);border-color:var(--akcent)}
tr.wykres>td{padding:14px 15px;background:var(--tlo)}
.wyk-ramka img{display:block;max-width:100%;height:auto;border:1px solid var(--linia);border-radius:4px}
.wyk-stopka{display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;align-items:baseline;
  margin-top:8px;font-size:11px;color:var(--tekst-2)}
.wyk-stopka a{color:var(--akcent);text-decoration:none}
.wyk-stopka a:hover{text-decoration:underline}
.wyk-brak{margin:0;font-size:12px;color:var(--tekst-2)}
.wyk-ster{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;margin-bottom:12px;
  padding:9px 11px;background:var(--plyta);border:1px solid var(--linia);border-radius:5px;
  font-size:11.5px;color:var(--tekst-2)}
.wyk-ster label{display:inline-flex;align-items:center;gap:5px;cursor:pointer}
.wyk-ster input[type=text],.wyk-ster input:not([type]),.wyk-ster select{
  background:var(--tlo);border:1px solid var(--linia);border-radius:4px;color:var(--tekst);
  padding:2px 5px;font:inherit;font-variant-numeric:tabular-nums}
.wyk-grupa{display:inline-flex;border:1px solid var(--linia);border-radius:4px;overflow:hidden}
.wyk-zakres{background:0;border:0;border-right:1px solid var(--linia);color:var(--tekst-2);
  padding:3px 9px;font:inherit;cursor:pointer}
.wyk-zakres:last-child{border-right:0}
.wyk-zakres:hover{color:var(--tekst)}
.wyk-zakres.akt{background:var(--akcent);color:#fff}
.wyk-osc{display:inline-flex;gap:12px}
.wyk-ramka[aria-busy=true]{opacity:.45;transition:opacity .15s}
/* --- odczyt pod kursorem ---
   Pasek jest MATERIAŁEM leżącym nad wykresem, nie kolejnym wierszem tabeli:
   przykrywa górny fragment rysunku, więc nie przesuwa go przy pojawieniu się
   i oko nie musi skakać między krzyżem a liczbami na dole ekranu. */
.wyk-plotno{position:relative}
.wyk-odczyt{position:absolute;top:8px;left:8px;right:8px;z-index:2;display:flex;
  flex-wrap:wrap;align-items:baseline;gap:2px 14px;padding:7px 11px;border-radius:8px;
  background:color-mix(in srgb, var(--plyta) 82%, transparent);
  border:1px solid var(--linia);backdrop-filter:blur(14px) saturate(160%);
  -webkit-backdrop-filter:blur(14px) saturate(160%);
  box-shadow:0 8px 22px -14px rgba(0,0,0,.5);
  font-size:11.5px;color:var(--tekst-2);font-variant-numeric:tabular-nums;
  opacity:0;transform:translateY(-3px);transition:opacity .16s ease,transform .16s ease;
  pointer-events:none}
.wyk-odczyt.widoczny{opacity:1;transform:none}
.wyk-odczyt i{font-style:normal;color:var(--tekst-3);margin-right:4px;
  font-size:10px;letter-spacing:.04em;text-transform:uppercase}
.wyk-odczyt b{font-weight:650;color:var(--tekst)}
.wyk-odczyt .wyk-data{font-weight:650;color:var(--tekst);letter-spacing:-.01em}
.wyk-odczyt .wz{color:var(--wzrost)}
.wyk-odczyt .sp{color:var(--spadek)}

/* krzyż i zaznaczenie rysują się w SVG, więc kolory biorą z motywu */
.wyk-os{stroke:var(--tekst-3);stroke-width:1;stroke-dasharray:3 3;opacity:.75}
.wyk-zazn{fill:var(--akcent);opacity:.14;stroke:var(--akcent);stroke-width:1;stroke-opacity:.5}
.wyk-lapacz{cursor:crosshair}
.wyk-svg:focus{outline:2px solid var(--akcent);outline-offset:2px;border-radius:4px}
.wyk-svg:focus:not(:focus-visible){outline:none}
.wyk-podpowiedz{margin-top:6px;font-size:11px;color:var(--tekst-3)}

@media (prefers-reduced-motion: reduce){
  .wyk-odczyt{transition:none;transform:none}
  .wyk-ramka[aria-busy=true]{transition:none}
}
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
.btn:hover{text-decoration:none}
.btn.drugi{background:transparent;color:var(--tekst-2);border:1px solid var(--linia-2)}
.btn.drugi:hover{background:var(--akcent-tlo)}
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

PALETA = wykresy.PALETA


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
    """IBKR podaje daty jako YYYYMMDD - w tabeli chcemy YYYY-MM-DD.

    Data otwarcia transzy bywa z przyrostkiem („20260615;1"), którym IBKR
    rozróżnia transze otwarte tego samego dnia. Do wyświetlenia jest
    nieprzydatny, a przez niego cała wartość przelatywała przez formatowanie
    nietknięta i w tabeli stało surowe „20260615;1"."""
    s = (s or "").strip().split(";")[0][:10]
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _odm(n: int, jeden: str, mnogie: str) -> str:
    """Liczba mnoga po angielsku - jedna forma zamiast trzech.

    Zostaje osobną funkcją mimo trywialności: interfejs bywał już po polsku
    i może wrócić do wielojęzyczności, a wtedy wszystkie miejsca decydujące
    o formie liczebnika są nadal w jednym."""
    return jeden if n == 1 else mnogie


# --------------------------------------------------------------------------- #
#  wykresy (czyste SVG, bez bibliotek)
# --------------------------------------------------------------------------- #

def _wykres_slupkowy(dane: list[tuple[str, float, str]], wys=170) -> str:
    """dane: (etykieta, wartość, kolor). Słupki pionowe z osią zerową."""
    if not dane:
        return '<div class="uwaga">No data.</div>'
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
        return '<div class="uwaga">No data.</div>'
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

  // --- zwijanie: koszyk → spółka → transze ---
  // Widoczność wiersza zależy od DWÓCH niezależnych stanów, więc liczymy ją
  // z nich za każdym razem, zamiast przełączać display przy kliknięciu.
  // Przy przełączaniu rozwinięcie koszyka pokazywało też transze wszystkich
  // spółek w środku - bo nie miało skąd wiedzieć, że były schowane.
  var koszZamkniete = {}, lotyOtwarte = {}, wykresyOtwarte = {};

  function odswiezTabele(){
    document.querySelectorAll('tr[data-kosz]').forEach(function(r){
      if (r.dataset.naglowek) return;                 // wiersz koszyka zostaje
      var lot = r.dataset.lotOf, wyk = r.dataset.wykresOf;
      if (wyk) { r.hidden = koszZamkniete[r.dataset.kosz] || !wykresyOtwarte[wyk]; return; }
      r.hidden = koszZamkniete[r.dataset.kosz] || (lot ? !lotyOtwarte[lot] : false);
    });
    document.querySelectorAll('[data-zwin-kosz]').forEach(function(b){
      b.setAttribute('aria-expanded', String(!koszZamkniete[b.dataset.zwinKosz]));
    });
    document.querySelectorAll('[data-zwin-lot]').forEach(function(b){
      b.setAttribute('aria-expanded', String(!!lotyOtwarte[b.dataset.zwinLot]));
    });
    document.querySelectorAll('[data-wykres]').forEach(function(b){
      b.setAttribute('aria-expanded', String(!!wykresyOtwarte[b.dataset.wykres]));
    });
  }

  // --- interakcja z wykresem: krzyż, odczyt, zaznaczanie zakresu ---
  //
  // Wszystko dzieje się po stronie przeglądarki, na danych dołączonych do
  // rysunku. Pytanie serwera przy każdym ruchu myszy byłoby niewykonalne,
  // a bez odczytu pod kursorem wykres pozostaje obrazkiem.
  //
  // Ruch śledzimy WSKAŹNIKIEM (Pointer Events), nie myszą: ta sama ścieżka
  // obsługuje palec na tablecie i rysik, a przechwycenie wskaźnika sprawia,
  // że zaznaczanie nie gubi się, gdy kursor wyjedzie poza wykres.
  var BEZ_RUCHU = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function podepnijWykres(ramka){
    var svg = ramka.querySelector('svg.wyk-svg');
    var blok = ramka.querySelector('script.wyk-dane');
    if (!svg || !blok) return;

    var dane;
    try { dane = JSON.parse(blok.textContent); } catch (e) { return; }

    var x0 = parseFloat(svg.dataset.x0), krok = parseFloat(svg.dataset.krok);
    var n = parseInt(svg.dataset.n, 10);
    var gora = parseFloat(svg.dataset.gora), dolG = parseFloat(svg.dataset.dol);
    var prawy = parseFloat(svg.dataset.prawy);
    var warstwa = svg.querySelector('.wyk-krzyz');
    var lapacz = svg.querySelector('.wyk-lapacz');
    if (!warstwa || !lapacz) return;

    var odczyt = ramka.closest('.wyk-plotno').querySelector('.wyk-odczyt');
    var iBiez = -1, zaznOd = null;

    function svgX(ev){
      var r = svg.getBoundingClientRect();
      return (ev.clientX - r.left) / r.width * svg.viewBox.baseVal.width;
    }
    function svgY(ev){
      var r = svg.getBoundingClientRect();
      return (ev.clientY - r.top) / r.height * svg.viewBox.baseVal.height;
    }
    function indeks(x){
      var i = Math.round((x - x0) / krok - 0.5);
      return Math.max(0, Math.min(n - 1, i));
    }
    function xInd(i){ return x0 + krok * (i + 0.5); }

    function liczba(v, mp){
      if (v === null || v === undefined) return '—';
      return v.toLocaleString('en-US', {minimumFractionDigits: mp === undefined ? 2 : mp,
                                        maximumFractionDigits: mp === undefined ? 2 : mp});
    }
    function wolumen(v){
      if (!v) return '—';
      if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
      if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
      if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
      return String(Math.round(v));
    }

    function pokazOdczyt(i){
      if (!odczyt) return;
      var zm = i > 0 ? (dane.c[i] - dane.c[i-1]) / dane.c[i-1] * 100 : null;
      var kl = zm === null ? '' : (zm >= 0 ? 'wz' : 'sp');
      var czesci = [
        '<span class="wyk-data">' + dane.daty[i] + '</span>',
        '<span><i>O</i>' + liczba(dane.o[i]) + '</span>',
        '<span><i>H</i>' + liczba(dane.h[i]) + '</span>',
        '<span><i>L</i>' + liczba(dane.l[i]) + '</span>',
        '<span><i>C</i><b>' + liczba(dane.c[i]) + '</b></span>',
        '<span class="' + kl + '">' + (zm === null ? '' : (zm >= 0 ? '+' : '') + zm.toFixed(2) + '%') + '</span>',
        '<span><i>Vol</i>' + wolumen(dane.v[i]) + '</span>'
      ];
      dane.serie.forEach(function(sr){
        czesci.push('<span style="color:' + sr.k + '"><i>' + sr.n + '</i>' + liczba(sr.w[i]) + '</span>');
      });
      odczyt.innerHTML = czesci.join('');
      odczyt.classList.add('widoczny');
    }

    function schowajOdczyt(){
      if (odczyt) odczyt.classList.remove('widoczny');
      warstwa.innerHTML = '';
      iBiez = -1;
    }

    function rysujKrzyz(i, y){
      var x = xInd(i);
      var el = '<line x1="' + x.toFixed(2) + '" y1="' + gora + '" x2="' + x.toFixed(2) +
               '" y2="' + dolG + '" class="wyk-os"/>';
      if (y !== null && y >= gora && y <= dolG) {
        el += '<line x1="' + x0 + '" y1="' + y.toFixed(2) + '" x2="' + prawy +
              '" y2="' + y.toFixed(2) + '" class="wyk-os"/>';
      }
      warstwa.innerHTML = el;
    }

    lapacz.addEventListener('pointermove', function(ev){
      var i = indeks(svgX(ev));
      if (zaznOd !== null) { rysujZaznaczenie(zaznOd, i); pokazOdczyt(i); return; }
      if (i !== iBiez) { iBiez = i; pokazOdczyt(i); }
      rysujKrzyz(i, svgY(ev));
    });
    lapacz.addEventListener('pointerleave', function(){ if (zaznOd === null) schowajOdczyt(); });

    function rysujZaznaczenie(a, b){
      var od = Math.min(a, b), do_ = Math.max(a, b);
      var x = xInd(od) - krok / 2, sz = (do_ - od + 1) * krok;
      warstwa.innerHTML = '<rect class="wyk-zazn" x="' + x.toFixed(2) + '" y="' + gora +
                          '" width="' + sz.toFixed(2) + '" height="' + (dolG - gora).toFixed(2) + '"/>';
    }

    lapacz.addEventListener('pointerdown', function(ev){
      if (ev.button !== 0 && ev.pointerType === 'mouse') return;
      zaznOd = indeks(svgX(ev));
      lapacz.setPointerCapture(ev.pointerId);   // zaznaczanie nie gubi się poza wykresem
      rysujZaznaczenie(zaznOd, zaznOd);
    });

    lapacz.addEventListener('pointerup', function(ev){
      if (zaznOd === null) return;
      var a = zaznOd, b = indeks(svgX(ev));
      zaznOd = null;
      try { lapacz.releasePointerCapture(ev.pointerId); } catch (e) {}
      // Trzy sesje to próg celowo niski, ale nie zerowy: bez niego zwykłe
      // kliknięcie w wykres przybliżałoby do jednej świecy.
      if (Math.abs(b - a) < 3) { warstwa.innerHTML = ''; return; }
      var form = ramka.closest('tr').querySelector('.wyk-ster');
      form.querySelector('input[name=od]').value = dane.daty[Math.min(a, b)];
      form.querySelector('input[name=do]').value = dane.daty[Math.max(a, b)];
      rysujWykres(form.dataset.sym);
    });

    // Podwójne kliknięcie zdejmuje przybliżenie. Jest odpowiednikiem
    // „wróć", którego przy zaznaczaniu myszą szuka się odruchowo.
    lapacz.addEventListener('dblclick', function(){
      var form = ramka.closest('tr').querySelector('.wyk-ster');
      if (!form.querySelector('input[name=od]').value) return;
      form.querySelector('input[name=od]').value = '';
      form.querySelector('input[name=do]').value = '';
      rysujWykres(form.dataset.sym);
    });

    // Klawiatura: wykres bez niej jest niedostępny dla kogoś, kto nie używa
    // myszy. Strzałki przesuwają krzyż, Escape go zdejmuje.
    svg.setAttribute('tabindex', '0');
    svg.addEventListener('keydown', function(ev){
      var skok = ev.shiftKey ? 10 : 1;
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') {
        ev.preventDefault();
        var i = iBiez < 0 ? n - 1 : iBiez + (ev.key === 'ArrowRight' ? skok : -skok);
        iBiez = Math.max(0, Math.min(n - 1, i));
        rysujKrzyz(iBiez, null);
        pokazOdczyt(iBiez);
      } else if (ev.key === 'Escape') {
        schowajOdczyt();
      }
    });
    svg.addEventListener('blur', schowajOdczyt);
  }

  // --- przeglądarka wykresu ---
  // Ustawienia czytamy z formularza przy każdej zmianie i wysyłamy w adresie
  // rysunku. Dzięki temu stan wykresu ma jedno miejsce - pola formularza -
  // i nie trzeba go duplikować w zmiennych.
  var wCzasie = {};

  function rysujWykres(sym){
    var r = document.querySelector('tr[data-wykres-of="' + CSS.escape(sym) + '"]');
    if (!r) return;
    var ramka = r.querySelector('.wyk-ramka');
    var form = r.querySelector('.wyk-ster');
    if (!ramka || !form) return;

    var dane = new FormData(form);
    var q = new URLSearchParams();
    q.set('zakres', dane.get('zakres') || '1y');
    q.set('typ', dane.get('typ') || 'swiece');
    q.set('sma', dane.get('sma') || '');
    q.set('ema', dane.get('ema') || '');
    q.set('bb', dane.get('bb') ? '1' : '0');
    q.set('wol', dane.get('wol') ? '1' : '0');
    q.set('osc', dane.getAll('osc').join(','));
    q.set('od', dane.get('od') || '');
    q.set('do', dane.get('do') || '');

    // Kolejne żądanie unieważnia poprzednie: przy szybkim klikaniu zakresów
    // odpowiedzi wracają w dowolnej kolejności i bez tego na ekranie
    // zostawałby wykres z żądania, które wyszło wcześniej.
    var bilet = (wCzasie[sym] = (wCzasie[sym] || 0) + 1);
    ramka.setAttribute('aria-busy', 'true');
    fetch('/wykres/' + encodeURIComponent(sym) + '.svg?' + q.toString(),
          {credentials: 'same-origin'})
      .then(function(o){ if(!o.ok) throw 0; return o.text(); })
      .then(function(svg){
        if (wCzasie[sym] !== bilet) return;
        ramka.innerHTML = svg;
        ramka.removeAttribute('aria-busy');
        podepnijWykres(ramka);
      })
      .catch(function(){
        if (wCzasie[sym] !== bilet) return;
        ramka.innerHTML = '<p class="wyk-brak">Chart unavailable for ' + sym + '.</p>';
        ramka.removeAttribute('aria-busy');
      });
  }

  document.addEventListener('click', function(ev){
    var z = ev.target.closest('.wyk-zakres');
    if (!z) return;
    var form = z.closest('.wyk-ster');
    form.querySelectorAll('.wyk-zakres').forEach(function(b){ b.classList.remove('akt'); });
    z.classList.add('akt');
    form.querySelector('input[name=zakres]').value = z.dataset.zakres;
    rysujWykres(form.dataset.sym);
  });

  document.addEventListener('change', function(ev){
    var form = ev.target.closest('.wyk-ster');
    if (form) rysujWykres(form.dataset.sym);
  });
  // Pola tekstowe okresów: rysujemy po chwili bez pisania, a nie na każdą
  // literę - inaczej wpisanie "100" wysyła trzy żądania, z czego dwa na
  // wartościach, których użytkownik nie miał na myśli.
  var stoper;
  document.addEventListener('input', function(ev){
    var form = ev.target.closest('.wyk-ster');
    if (!form || ev.target.type === 'checkbox') return;
    clearTimeout(stoper);
    stoper = setTimeout(function(){ rysujWykres(form.dataset.sym); }, 450);
  });

  var tabela = document.getElementById('tabPozycje');
  if (tabela) tabela.addEventListener('click', function(ev){
    var wb = ev.target.closest('.wyk-otw');
    if (wb) {
      var sym = wb.dataset.wykres;
      wykresyOtwarte[sym] = !wykresyOtwarte[sym];
      if (wykresyOtwarte[sym]) rysujWykres(sym);
      odswiezTabele();
      return;
    }
    var b = ev.target.closest('.zwin');
    if (!b) return;
    if (b.dataset.zwinKosz) {
      var k = b.dataset.zwinKosz;
      koszZamkniete[k] = !koszZamkniete[k];
    } else {
      var g = b.dataset.zwinLot;
      lotyOtwarte[g] = !lotyOtwarte[g];
    }
    odswiezTabele();
  });
})();
</script>
"""


# --------------------------------------------------------------------------- #
#  strony
# --------------------------------------------------------------------------- #

def logowanie(blad: str = "") -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Portfolio — sign in</title><style>{STYL_DODATKOWY}\n{style.STYL}</style></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh">
<form method="post" action="/login" class="karta" style="max-width:340px;width:100%;margin:0">
  <h2>Portfolio dashboard</h2>
  <div class="tresc">
    {f'<div class="kom zle">{e(blad)}</div>' if blad else ''}
    <input type="password" name="haslo" placeholder="Password" autofocus required
           style="width:100%;margin-bottom:10px;padding:8px 10px">
    <button class="btn" style="width:100%;justify-content:center;padding:9px">Sign in</button>
  </div>
</form></body></html>"""


def _kafel_polityki(p: dict) -> tuple:
    """Zastępuje dawne „Ryzyko stopów $0".

    Zero było arytmetycznie prawdziwe (żaden stop nie był ustawiony), ale
    czytało się jako „brak ryzyka". Pozycja długoterminowa bez stopa nie ma
    zerowego ryzyka - ma inny sposób zarządzania. Pokazujemy więc pokrycie
    polityką, a kwotę tylko wtedy, gdy jakikolwiek stop faktycznie istnieje."""
    bez = p.get("pozycje_bez_stopa", 0)
    ryzyko = p.get("ryzyko_stopow", 0.0)
    lacznie = p.get("liczba_tickerow", 0)
    if not ryzyko and bez:
        return ("Risk policy", f"{lacznie - bez}/{lacznie}",
                "mut", f'{bez} with no level set')
    return ("Stop risk", _pln(ryzyko), "down" if ryzyko else "mut",
            f'{bez} with no level · if every stop fired')


def _kafle(p: dict, okresy: dict, hist=None) -> str:
    # Iskierka tylko przy NAV, bo tylko dla NAV mamy prawdziwy szereg dzienny.
    # Dorysowanie jej przy pozostałych kaflach wyglądałoby spójniej i byłoby
    # zmyślaniem - kafel „Gotówka" nie ma historii, z której dałoby się ją
    # narysować.
    isk = ""
    if hist and len(hist) > 3:
        isk = wykresy.iskierka([h["nav"] for h in hist[-90:]], szer=150, wys=38)
    k = [("NAV", _pln(p["nav"]), "", "", isk),
         ("Daily change", _proc(p["zmiana_nav_proc"]),
          _kl(p["zmiana_nav_proc"]), ""),
         ("Position value", _pln(p["wartosc_pozycji"]), "",
          f'{p["liczba_tickerow"]} holdings · {p["liczba_pozycji"]} lots'),
         ("Unrealised P/L", _pln(p["zysk"]), _kl(p["zysk"]), _proc(p["zysk_proc"])),
         ("Cash", _pln(p["gotowka"]), "", f'{p["udzial_gotowki"]:.1f}% of assets'),
         ("Winners / losers", f'{p["zyskownych"]} / {p["stratnych"]}', "", ""),
         ("Top 5 concentration", f'{p["koncentracja_top5"]:.1f}%', "",
          f'HHI {p["hhi"]:,.0f}'),
         _kafel_polityki(p)]
    for etykieta, dane in okresy.items():
        if not dane.get("dostepny", True):
            # Zamiast liczby, której nie ma na czym oprzeć - jasna informacja
            # skąd sięga historia. Pusty okres jest uczciwszy niż powtórzony.
            k.append((etykieta, "—", "mut", f'not enough history · data from {dane["od"]}'))
            continue
        k.append((etykieta, _proc(dane["proc"]), _kl(dane["proc"]),
                  f'from {dane["od"]} · {_pln(dane["kwota"])}'))
    return '<div class="kafle">' + "".join(
        f'<div class="kafel"><div class="et">{e(x[0])}</div>'
        f'<div class="w num {x[2]}">{x[1]}</div>'
        f'<div class="pod num">{x[3]}</div>'
        f'{x[4] if len(x) > 4 else ""}</div>' for x in k) + '</div>'


# Symbol nadający się do wykresu: same litery, kropka i myślnik. Odsiewa
# opcje ("AAPL 260918C00250000"), gotówkę i wpisy techniczne - dla nich
# nie ma czego rysować.
_SYMBOL_WYKRESU = re.compile(r"^[A-Za-z][A-Za-z.\-]{0,9}$")


def wykres_symbolu(symbol: str, parametry: dict | None = None) -> str:
    """SVG wykresu spółki dla podanych ustawień."""
    if not symbol or not _SYMBOL_WYKRESU.match(symbol):
        return '<p class="wyk-brak">No chart for this symbol.</p>'
    return przegladarka.rysuj(symbol, przegladarka.ustawienia(parametry or {}))


def _sterowanie(sym: str) -> str:
    """Pasek ustawień wykresu.

    Zwykły formularz, nie widżet: przeglądarka sama pamięta stan pól, a my
    czytamy je jednym `FormData` przy każdej zmianie. Zakres i wskaźniki
    idą do adresu rysunku, więc dokładnie ten sam układ da się odtworzyć
    z linku.
    """
    zakresy = "".join(
        f'<button type="button" class="wyk-zakres{" akt" if k == "1y" else ""}" '
        f'data-zakres="{k}">{historia.ETYKIETY_ZAKRESU[k]}</button>'
        for k in historia.ZAKRESY)
    oscylatory = "".join(
        f'<label><input type="checkbox" name="osc" value="{k}"'
        f'{" checked" if k == "rsi" else ""}> {n}</label>'
        for k, n in przegladarka.OSCYLATORY.items())
    return (
        f'<form class="wyk-ster" data-sym="{sym}">'
        f'<div class="wyk-grupa" role="group" aria-label="Time range">{zakresy}</div>'
        f'<input type="hidden" name="zakres" value="1y">'
        f'<input type="hidden" name="od" value="">'
        f'<input type="hidden" name="do" value="">'
        f'<label class="wyk-pole">SMA <input name="sma" value="50,100" size="10" '
        f'inputmode="numeric" placeholder="50,100,200"></label>'
        f'<label class="wyk-pole">EMA <input name="ema" value="" size="8" '
        f'inputmode="numeric" placeholder="20,50"></label>'
        f'<label><input type="checkbox" name="bb"> Bollinger</label>'
        f'<label><input type="checkbox" name="wol" checked> Volume</label>'
        f'<span class="wyk-osc">{oscylatory}</span>'
        f'<label class="wyk-pole">Type '
        f'<select name="typ"><option value="swiece">Candles</option>'
        f'<option value="linia">Line</option></select></label>'
        f'</form>')


def _wiersz_wykresu(symbol: str, kosz: str, kolumn: int) -> str:
    """Schowany wiersz z przeglądarką wykresu, na całą szerokość tabeli.

    Rysunek dociąga się dopiero przy otwarciu i jest WSTAWIANY W STRONĘ,
    a nie ładowany jako <img>: SVG w obrazku żyje we własnym dokumencie
    i nie widzi zmiennych CSS motywu, więc świece wyszłyby czarne na czarnym
    po przełączeniu na ciemny.
    """
    if not _SYMBOL_WYKRESU.match(symbol or ""):
        return ""
    sym = e(symbol)
    return (f'<tr class="wykres" data-kosz="{kosz}" data-wykres-of="{sym}" hidden>'
            f'<td colspan="{kolumn}">'
            f'{_sterowanie(sym)}'
            f'<div class="wyk-plotno">'
            f'<div class="wyk-odczyt" aria-live="polite"></div>'
            f'<div class="wyk-ramka" data-sym="{sym}">'
            f'<p class="wyk-brak">Loading…</p></div>'
            f'</div>'
            f'<div class="wyk-stopka">'
            f'<span>Drag to zoom · double-click to reset · arrow keys move the crosshair</span>'
            f'<a href="https://stockcharts.com/h-sc/ui?s={quote(symbol.upper(), safe="")}" '
            f'target="_blank" rel="noopener noreferrer">open on StockCharts →</a>'
            f'</div></td></tr>')


def _tabela_pozycji(p: dict) -> str:
    """Koszyk → spółka → transze zakupu, każdy poziom zwijany osobno.

    Transze są domyślnie SCHOWANE. Wcześniej rozwijały się wszystkie naraz
    i tabela liczyła kilkaset wierszy, w których jedna spółka z piętnastoma
    lotami wypychała z ekranu czternaście innych spółek. Pytanie „co mam
    w portfelu" zadaje się dużo częściej niż „po ile kupowałem trzy transze
    temu", więc to pierwsze należy się domyślnie, a drugie na kliknięcie.

    Liczba transz jedzie w plakietce przy nazwie, bo strzałka mówi tylko, że
    coś się rozwinie - nie mówi, czy warto."""
    w = ['<div class="przewin"><table data-sortowalna id="tabPozycje"><thead><tr>'
         '<th style="width:26px"></th><th class="sort">Position</th>'
         '<th class="sort l">Qty</th><th class="sort l">Cost</th><th class="sort l">Price</th>'
         '<th class="sort l">Value</th><th class="sort l">P/L</th><th class="sort l">%</th>'
         '<th class="sort l">Day</th><th class="sort l">Stop</th><th class="sort l">To stop</th>'
         '<th class="sort l">Weight</th></tr></thead><tbody>']
    for i, k in enumerate(p["koszyki"]):
        kl = f"k{i}"
        w.append(f'<tr class="grupa" data-kosz="{kl}" data-naglowek="1">'
                 f'<td><button class="zwin" data-zwin-kosz="{kl}" aria-expanded="true" '
                 f'aria-label="Collapse {e(k["koszyk"])}"></button></td>'
                 f'<td>{e(k["koszyk"])}</td><td class="l"></td><td class="l"></td><td class="l"></td>'
                 f'<td class="l num" data-v="{k["wartosc"]}">{_pln(k["wartosc"])}</td>'
                 f'<td class="l num {_kl(k["zysk"])}" data-v="{k["zysk"]}">{_pln(k["zysk"])}</td>'
                 f'<td class="l num {_kl(k["zysk_proc"])}" data-v="{k["zysk_proc"]}">{_proc(k["zysk_proc"])}</td>'
                 f'<td class="l"></td><td class="l"></td><td class="l"></td>'
                 f'<td class="l num" data-v="{k["udzial"]}">{k["udzial"]:.2f}%</td></tr>')
        for t in k["tickery"]:
            loty = t["loty"] or []
            grupa_lotow = f'{kl}-{t["symbol"]}'
            if loty:
                strzalka = (f'<button class="zwin" data-zwin-lot="{grupa_lotow}" '
                            f'aria-expanded="false" '
                            f'aria-label="Show purchases of {e(t["symbol"])}"></button>')
                licznik = (f'<span class="plak licz">{len(loty)} '
                           f'{_odm(len(loty), "lot", "lots")}</span>')
            else:
                strzalka = licznik = ""
            # Wykres jest osobnym przełącznikiem, nie częścią rozwijania transz:
            # „ile mam" i „jak się zachowuje" to dwa różne pytania i rzadko
            # zadaje się je naraz.
            wykres_btn = (
                f'<button class="wyk-otw" data-wykres="{e(t["symbol"])}" '
                f'aria-expanded="false" title="Chart" '
                f'aria-label="Chart for {e(t["symbol"])}">chart</button>'
                if _SYMBOL_WYKRESU.match(t["symbol"] or "") else "")
            # Stop i odległość do niego są cechą SPÓŁKI, nie transzy - poziom
            # wpisuje się raz na ticker. Wcześniej stały tylko przy lotach,
            # więc po ich schowaniu zniknęłyby z widoku zupełnie.
            stop = _pln(t.get("stop")) if t.get("stop") else '<span class="plak uw">none</span>'
            w.append(f'<tr class="spolka" data-kosz="{kl}" data-sym="{e(t["symbol"])}">'
                     f'<td>{strzalka}</td>'
                     f'<td><span class="tyk">{e(t["symbol"])}</span>'
                     f'<span class="opis">{e((t["opis"] or "")[:30])}</span>{licznik}{wykres_btn}</td>'
                     f'<td class="l num" data-v="{t["ilosc"]}">{t["ilosc"]:,.0f}</td>'
                     f'<td class="l num" data-v="{t["cena_kosztu"]}">{_pln(t["cena_kosztu"])}</td>'
                     f'<td class="l num" data-v="{t["cena"]}">{_pln(t["cena"])}</td>'
                     f'<td class="l num" data-v="{t["wartosc"]}">{_pln(t["wartosc"])}</td>'
                     f'<td class="l num {_kl(t["zysk"])}" data-v="{t["zysk"]}">{_pln(t["zysk"])}</td>'
                     f'<td class="l num {_kl(t["zysk_proc"])}" data-v="{t["zysk_proc"]}">{_proc(t["zysk_proc"])}</td>'
                     f'<td class="l num {_kl(t["zmiana_dzienna"])}" '
                     f'data-v="{t["zmiana_dzienna"] if t["zmiana_dzienna"] is not None else ""}">'
                     f'{_proc(t["zmiana_dzienna"])}</td>'
                     f'<td class="l num">{stop}</td>'
                     f'<td class="l num">{_proc(t.get("do_stopu_proc"))}</td>'
                     f'<td class="l num" data-v="{t["udzial"]}">{t["udzial"]:.2f}%</td></tr>')
            w.append(_wiersz_wykresu(t["symbol"], kl, 12))
            for nr, lot in enumerate(loty, 1):
                w.append(f'<tr class="lot" data-kosz="{kl}" data-lot-of="{grupa_lotow}" '
                         f'data-sym="{e(t["symbol"])}" hidden><td></td>'
                         f'<td>Buy {nr} · {e(_dzien(str(lot.get("data_otwarcia", ""))))}</td>'
                         f'<td class="l num">{lot.get("ilosc", 0):,.0f}</td>'
                         f'<td class="l num">{_pln(lot.get("cena_kosztu"))}</td>'
                         f'<td class="l num">{_pln(lot.get("cena"))}</td>'
                         f'<td class="l num">{_pln(lot.get("wartosc"))}</td>'
                         f'<td class="l num {_kl(lot.get("zysk"))}">{_pln(lot.get("zysk"))}</td>'
                         f'<td class="l num {_kl(lot.get("zysk_proc"))}">{_proc(lot.get("zysk_proc"))}</td>'
                         f'<td class="l"></td><td class="l"></td><td class="l"></td>'
                         f'<td class="l"></td></tr>')
    w.append('</tbody></table></div>')
    return "".join(w)


def _tabela_cc(cc: list[dict]) -> str:
    if not cc:
        return ('<div class="tresc uwaga">No calls written. This section fills itself as soon '
                'as a short option appears in the portfolio.</div>')
    w = ['<div class="przewin"><table><thead><tr><th>Underlying</th><th class="l">Contracts</th>'
         '<th class="l">Strike</th><th>Expires</th><th class="l">Days</th><th class="l">Spot</th>'
         '<th class="l">To strike</th><th>Status</th><th class="l">P/L</th>'
         '</tr></thead><tbody>']
    for c in cc:
        st = ('<span class="plak zle">in the money</span>' if c["w_pieniadzu"]
              else '<span class="plak ok">out</span>')
        if not c["pokryte"]:
            st += ' <span class="plak uw">uncovered</span>'
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
    wszystkie = list(dict.fromkeys(koszyki + [m["koszyk"] for m in meta.values()] + ["Unassigned"]))

    w = ['<form method="post" action="/meta">',
         '<div class="tresc" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;'
         'border-bottom:1px solid var(--linia2)">',
         '<label style="display:flex;gap:6px;align-items:center;font-size:12.5px">'
         '<input type="checkbox" onclick="document.querySelectorAll(\'input[name=zazn]\')'
         '.forEach(function(c){c.checked=this.checked}.bind(this))"> select all</label>',
         '<span class="uwaga">→ assign selected to:</span>',
         '<select name="masowy_koszyk"><option value="">— leave unchanged —</option>',
         "".join(f'<option>{e(k)}</option>' for k in wszystkie),
         '</select><input name="masowy_nowy" placeholder="or a new basket…" style="width:160px">',
         '<input placeholder="Search ticker…" data-filtr="#tabMeta" style="width:150px">',
         '<button class="btn" style="margin-left:auto">Save changes</button></div>',
         '<div class="przewin wysoka"><table id="tabMeta"><thead><tr><th style="width:26px"></th>'
         '<th>Ticker</th><th class="l">Weight</th><th>Basket</th><th>Rating</th>'
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
                 f'placeholder="e.g. 280"></td></tr>')
    w.append('</tbody></table></div><div class="tresc" style="border-top:1px solid var(--linia2)">'
             '<button class="btn">Save changes</button>'
             '<span class="uwaga" style="margin-left:12px">Stop-losses are GTC orders in IBKR — '
             'Flex does not expose open orders, so you enter the level here. '
             'A triggered stop is picked up automatically from the trades.</span></div></form>')
    return "".join(w)


def _tabela_wzorca(por: dict) -> str:
    """Zestawienie udziałów docelowych i faktycznych. Kolor tylko tam, gdzie
    przekroczono próg - inaczej cała tabela świeciłaby się bez powodu."""
    ETYKIETY = {"zgodne": ("On target", "ok"), "dokup": ("Add", "uw"),
                "sprzedaj": ("Overweight", "uw"), "brakuje": ("Missing", "zle"),
                "nadmiarowa": ("Not in model", "zle")}
    w = ['<div class="przewin"><table data-sortowalna id="tabWzorzec"><thead><tr>'
         '<th class="sort">Ticker</th><th>Basket</th>'
         '<th class="sort l">Sheet</th><th class="sort l">Target</th>'
         '<th class="sort l">Actual</th><th class="sort l">Gap</th>'
         '<th class="sort l">Trade size</th><th>Status</th></tr></thead><tbody>']
    for p in por["pozycje"]:
        et, kl = ETYKIETY[p["rodzaj"]]
        zgodne = p["rodzaj"] == "zgodne"
        w.append(
            f'<tr><td><span class="tyk">{e(p["ticker"])}</span>'
            + (' <span class="plak ok">core</span>' if p["rdzenna"] else "")
            + f'</td><td class="uwaga">{e(p["koszyk"])}</td>'
            # Kolumna "Sheet" to wartość WPROST Z ARKUSZA. Bez niej nagłówek
            # obiecywał osiem kolumn przy siedmiu komórkach, więc cała tabela
            # była przesunięta o jedną pozycję: pod "Sheet" stał przeskalowany
            # cel, pod "Target" stan faktyczny, a "Status" nie miał komórki.
            f'<td class="l num mut" data-v="{p["cel_arkusz"]}">{p["cel_arkusz"]:.2f}%</td>'
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
          analiza_opcji=None, analityka=None) -> str:
    okresy = okresy or {}
    log = "".join(f'<tr><td class="num">{e(p["kiedy"])}</td>'
                  f'<td>{"OK" if p["ok"] else "<span class=\'plak zle\'>error</span>"}</td>'
                  f'<td class="uwaga">{e(p["komunikat"] or "")}</td></tr>' for p in przebiegi)

    if not pods:
        tresc = f"""<div data-panel="przeglad"><div class="karta"><div class="tresc">
          <p>No data yet. Fill in <code>IBKR_TOKEN</code> and <code>IBKR_QUERY_ID</code>
             in <code>/opt/ibkr/.env</code>, then fetch the report.</p>
          <form method="post" action="/odswiez"><button class="btn">Fetch now</button></form>
        </div></div>
        <div class="karta"><h2>Recent fetches</h2><table><tbody>{log}</tbody></table></div></div>"""
        zakladki = ""   # nawigacja jest teraz w pasku bocznym
    else:
        p = pods
        ostrz = []
        if p["cc_w_pieniadzu"]:
            n = p["cc_w_pieniadzu"]
            ostrz.append(f'{n} {_odm(n, "call is", "calls are")} in the money — assignment risk')
        if p["cc_niepokryte"]:
            n = p["cc_niepokryte"]
            ostrz.append(f'{n} {_odm(n, "call has", "calls have")} no share cover')
        if p["pozycje_bez_stopa"]:
            n = p["pozycje_bez_stopa"]
            ostrz.append(f'{n} {_odm(n, "holding has", "holdings have")} no stop level set')
        pasek = f'<div class="kom uw">{" · ".join(ostrz)}</div>' if ostrz else ""

        udzialy = [(k["koszyk"], k["wartosc"]) for k in p["koszyki"]]
        if p["gotowka"] > 0:
            udzialy.append(("Cash", p["gotowka"]))
        # przy małym portfelu pokazujemy wszystko; przy dużym skrajne 6 z każdej
        # strony - inaczej te same spółki trafiały do wykresu dwa razy
        ruch = sorted(p["tickery"], key=lambda t: -t["zysk"])
        skrajne = ruch if len(ruch) <= 12 else ruch[:6] + ruch[-6:]
        rozklad = [(r["etykieta"], float(r["ile"]),
                    "var(--wzrost)" if r["dodatni"] else "var(--spadek)") for r in p["rozklad"]]

        zakladki = ""

        tresc = f"""
<div data-panel="przeglad">
  {pasek}
  <div class="karta"><h2>Summary<span class="obok">{e(p["kwartal"])} · as of
      <b>{e(p["data"])}</b></span></h2>{_kafle(p, okresy, hist)}</div>
  <div class="karta" style="--op:60ms"><h2>Account value over time<span class="obok">{len(hist)} days ·
      from {e(hist[0]["data"]) if hist else "—"}</span></h2>
    <div class="tresc">{wykresy.obszar([(h["data"], h["nav"]) for h in hist],
        wys=250, opis="Account value", zakresy=True)}</div></div>
  <div class="siatka dwie">
    <div class="karta"><h2>Portfolio breakdown</h2>
      <div class="tresc">{wykresy.pierscien(udzialy,
        srodek_gora=_pln(p["nav"]), srodek_dol="NAV")}</div></div>
    <div class="karta"><h2>Best and worst holdings<span class="obok">unrealised P/L</span></h2>
      <div class="tresc">{wykresy.slupki_pionowe(
          [(t["symbol"], t["zysk"]) for t in skrajne], wys=170,
          fmt=lambda v: _pln(v))}</div></div>
  </div>
</div>

<div data-panel="pozycje" class="panel-ukryty">
  <div class="karta"><h2>Holdings by basket
      <span class="obok"><input placeholder="Search…" data-filtr="#tabPozycje" style="width:170px"></span>
    </h2>{_tabela_pozycji(p)}</div>
  <div class="karta"><h2>Covered calls</h2>{_tabela_cc(p["covered_calls"])}</div>
</div>

<div data-panel="analiza" class="panel-ukryty">
  <div class="siatka dwie">
    <div class="karta"><h2>P/L distribution<span class="obok">number of holdings</span></h2>
      <div class="tresc">{_wykres_slupkowy(rozklad)}</div></div>
    <div class="karta"><h2>Basket weights</h2><div class="tresc">{wykresy.slupki_poziome([{"nazwa": k["koszyk"], "udzial": k["udzial"]} for k in p["koszyki"]], ile=8)}</div></div>
  </div>
  <div class="siatka dwie">
    <div class="karta"><h2>Capital by holding period</h2><div class="tresc">{_wykres_poziomy(
        [(w["etykieta"], w["wartosc"], w["wartosc"]) for w in p["wiek"]], fmt=_pln)}</div>
      <div class="tresc uwaga" style="padding-top:0">Measured per lot — the opening date of each purchase.</div></div>
    <div class="karta"><h2>Currency exposure</h2><div class="tresc">{_wykres_poziomy(
        [(w, v, v) for w, v in sorted(p["waluty"].items(), key=lambda x: -x[1])], fmt=_pln)}</div></div>
  </div>
  <div class="karta"><h2>Largest holdings</h2><div class="przewin">
    <table data-sortowalna><thead><tr><th class="sort">Ticker</th><th class="sort l">Value</th>
      <th class="sort l">Weight</th><th class="sort l">P/L</th><th class="sort l">%</th>
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

{widok_analityka.zakladka_wynik(analityka)}

{widok_analityka.zakladka_ryzyko(analityka)}

{widok_analityka.zakladka_ekspozycja(analityka)}

{widok_analityka.zakladka_scenariusze((analityka or {}).get("scenariusze"))}

{widok_opcje.zakladka(analiza_opcji)}

<div data-panel="wzorzec" class="panel-ukryty">
  {("" if porownanie else '<div class="karta"><div class="tresc uwaga">'
    'Could not fetch the model sheet. Check the fetch log.</div></div>')}
  {(f"""
  <div class="karta"><h2>Model portfolio fit
      <span class="obok">tolerance {porownanie["prog"]} pp ·
        model sums to {porownanie["suma_wzorca"]:.1f}%</span></h2>
    <div class="kafle">
      <div class="kafel"><div class="et">On target</div>
        <div class="w num up">{porownanie["licznik"].get("zgodne", 0)}</div></div>
      <div class="kafel"><div class="et">To add</div>
        <div class="w num">{porownanie["licznik"].get("dokup", 0)}</div></div>
      <div class="kafel"><div class="et">Overweight</div>
        <div class="w num">{porownanie["licznik"].get("sprzedaj", 0)}</div></div>
      <div class="kafel"><div class="et">Missing</div>
        <div class="w num down">{porownanie["licznik"].get("brakuje", 0)}</div></div>
      <div class="kafel"><div class="et">Not in model</div>
        <div class="w num down">{porownanie["licznik"].get("nadmiarowa", 0)}</div></div>
      <div class="kafel"><div class="et">Largest gap</div>
        <div class="w num">{porownanie["max_roznica"]:.2f} pp</div></div>
    </div>
  </div>

  <div class="karta"><h2>Baskets<span class="obok">Target is the weight straight from your model; baskets leave out what you cannot buy</span></h2><div class="przewin"><table><thead><tr>
    <th>Basket</th><th class="l">Sheet</th><th class="l">Target</th><th class="l">Actual</th>
    <th class="l">Gap</th></tr></thead><tbody>
    {"".join(f'<tr><td>{e(k["koszyk"])}</td>'
             f'<td class="l num mut">{k["cel_arkusz"]:.2f}%</td>'
             f'<td class="l num">{k["cel"]:.2f}%</td>'
             f'<td class="l num">{k["faktyczne"]:.2f}%</td>'
             f'<td class="l num {"mut" if k["zgodne"] else _kl(k["roznica"])}">'
             f'{k["roznica"]:+.2f} pp</td></tr>' for k in porownanie["koszyki"])}
  </tbody></table></div></div>

  <div class="karta"><h2>Excluded from the comparison
      <span class="obok">{len(porownanie["pominiete"])} instruments ·
        investable universe is {porownanie["suma_dostepnych"]:.1f}% of the model</span></h2>
    <div class="tresc">
      <p class="uwaga" style="margin-bottom:10px">Crypto is excluded, and US ETFs
        and leveraged instruments are not available to an EU retail investor.
        The remaining targets are taken from the sheet as they are.</p>
      <div style="display:flex;flex-wrap:wrap;gap:6px">
        {"".join(f'<span class="plak {"zle" if p == "krypto" else "uw"}">{e(t)}</span>'
                 for t, p in porownanie["pominiete"])}
      </div>
    </div>
  </div>

  <div class="karta"><h2>Holdings<span class="obok">sorted by size of the gap</span></h2>
    {_tabela_wzorca(porownanie)}
    <div class="tresc uwaga"><b>Sheet</b> is the weight straight from your model,
      <b>Target</b> is the same weight — no rescaling.
      Trade size is the buy (positive) or sell (negative) needed to bring the
      weight in line with the model, measured against total assets
      {_pln(porownanie["podstawa"])}.</div>
  </div>
  """ if porownanie else "")}
</div>

<div data-panel="ustawienia" class="panel-ukryty">
  <div class="karta"><h2>Baskets, ratings and stops<span class="obok">entered by hand</span></h2>
    {_formularz_meta(p, koszyki)}</div>
  <div class="karta"><h2>Fetches<span class="obok">{e(harmonogram)} ·
      {"Google Sheets connected" if sheets_ok else "Google Sheets not configured"}</span></h2>
    <table><tbody>{log or '<tr><td class="uwaga">No entries yet.</td></tr>'}</tbody></table></div>
</div>"""

    pozycje_nav = [
        ("przeglad", "Overview"), ("wynik", "Performance"), ("ryzyko", "Risk"),
        ("ekspozycja", "Exposure"), ("scenariusze", "Scenarios"),
        ("opcje", "Options"), ("pozycje", "Holdings"), ("wzorzec", "Model"),
        ("ustawienia", "Settings"),
    ]
    nav = "".join(
        f'<button data-cel="{k}" aria-selected="{"true" if i == 0 else "false"}">'
        f'{style.ikona(k)}<span>{e(n)}</span></button>'
        for i, (k, n) in enumerate(pozycje_nav))

    nav_szkielet = f"""<aside class="bok">
  <div class="marka"><i>P</i><div><b>Portfolio</b>
    <small>{e(pods["konto"]) if pods else "—"}</small></div></div>
  <nav class="nawig zakladki">{nav}</nav>
  <div style="margin-top:22px;display:flex;flex-direction:column;gap:8px;padding:0 4px">
    <form method="post" action="/odswiez"><button class="btn" style="width:100%;justify-content:center">Fetch now</button></form>
    <a class="btn szary" href="/pobierz.xlsx" style="justify-content:center">Excel</a>
    <a class="mini" href="/wyloguj" style="text-align:center;padding:6px">Sign out</a>
  </div>
</aside>"""

    naglowek = f"""<div class="gora-str">
  <div><h1>{e(pods["kwartal"]) if pods else "Portfolio"}</h1>
    <div class="pod">as of {e(pods["data"]) if pods else "—"} · {e(harmonogram)}</div></div>
  <div class="narzedzia">
    <button class="motyw" aria-label="Switch theme" title="Switch between light and dark">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
           stroke-linecap="round"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>
    </button>
  </div>
</div>"""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<title>IBKR Portfolio</title><style>{STYL_DODATKOWY}\n{style.STYL}</style></head><body>
<div class="szkielet">
{nav_szkielet}
<main class="tresc-gl">
  {naglowek}
  {f'<div class="kom {"zle" if blad else ""}">{e(komunikat)}</div>' if komunikat else ''}
  {tresc}
</main>
</div>
{SKRYPT}
{style.SKRYPT_UI}
</body></html>"""
