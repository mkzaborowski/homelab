"""Warstwa wizualna panelu.

Wydzielona ze `widok.py`, bo styl zmienia się z innego powodu niż układ
danych i mieszanie ich w jednym pliku utrudniało jedno i drugie.

Założenia, świadome i możliwe do obrony:

  * Ciemność jest tłem, nie motywem. Panel ogląda się rano i wieczorem,
    często obok wykresów maklerskich - jasne tło męczyłoby przy długim
    czytaniu liczb.
  * Akcent oznacza „interaktywne albo wyróżnione". Zieleń i czerwień znaczą
    „lepiej / gorzej". To dwa rozłączne języki i nigdy się nie mieszają -
    niebieski nigdy nie znaczy „dobrze".
  * Ruch jest krytycznie tłumiony, bez odbicia. Dane finansowe mają
    wyglądać na spokojne; sprężystość pasuje do przeciągania kart,
    nie do liczby, która właśnie się pojawiła.
  * Śledzenie liter zależy od rozmiaru: duże liczby ujemne, drobne etykiety
    dodatnie. Jedna wartość dla wszystkiego jest zawsze gdzieś zła.
"""

STYL = """
:root {
  --tlo:        #0B0E14;
  --tlo-2:      #0E121B;
  --plyta:      #131824;
  --plyta-2:    #171D2B;
  --linia:      rgba(255,255,255,.07);
  --linia-2:    rgba(255,255,255,.12);
  --tekst:      #E8ECF4;
  --tekst-2:    #9BA6BC;
  --tekst-3:    #5F6B82;

  --akcent:     #4C8DFF;
  --akcent-2:   #7AA7FF;
  --akcent-tlo: rgba(76,141,255,.12);
  --wzrost:     #3FB950;
  --spadek:     #F85149;
  --uwaga:      #D29922;

  /* Ruch: jedna krzywa na cały panel. Krytycznie tłumiona - bez odbicia,
     bo liczby finansowe nie powinny podskakiwać. */
  --e:          cubic-bezier(.22,.61,.36,1);
  --e-wyjscie:  cubic-bezier(.4,0,.68,.06);
  --dotyk:      100ms;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background:
    radial-gradient(1200px 600px at 15% -10%, rgba(76,141,255,.10), transparent 60%),
    radial-gradient(900px 500px at 85% 0%, rgba(139,123,255,.07), transparent 55%),
    var(--tlo);
  background-attachment: fixed;
  color: var(--tekst);
  font: 400 14.5px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  font-variant-numeric: tabular-nums;
}

.num { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }
.up { color: var(--wzrost); }
.down { color: var(--spadek); }
.mut { color: var(--tekst-2); }

/* ---------------------------------------------------------------- układ */
.szkielet { display: grid; grid-template-columns: 232px 1fr; min-height: 100vh; }

.bok {
  background: linear-gradient(180deg, rgba(19,24,36,.92), rgba(11,14,20,.92));
  backdrop-filter: blur(24px) saturate(160%);
  border-right: 1px solid var(--linia);
  padding: 22px 14px;
  position: sticky; top: 0; height: 100vh; overflow-y: auto;
}
.marka {
  display: flex; align-items: center; gap: 10px;
  padding: 0 10px 22px; margin-bottom: 6px;
  border-bottom: 1px solid var(--linia);
}
.marka b { font-size: 15px; letter-spacing: -.01em; font-weight: 600; }
.marka i {
  width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
  background: linear-gradient(135deg, var(--akcent), #8B7BFF);
  font-style: normal; font-weight: 700; font-size: 13px; color: #fff;
  box-shadow: 0 6px 18px -6px rgba(76,141,255,.7);
}
.marka small { display: block; color: var(--tekst-3); font-size: 10.5px; letter-spacing: .06em; }

.nawig { display: flex; flex-direction: column; gap: 2px; margin-top: 14px; }
.nawig button {
  display: flex; align-items: center; gap: 11px; width: 100%;
  background: 0; border: 0; cursor: pointer;
  padding: 9px 11px; border-radius: 9px;
  color: var(--tekst-2); font: inherit; font-size: 13.5px; text-align: left;
  letter-spacing: -.005em;
  transition: background var(--dotyk) var(--e), color var(--dotyk) var(--e);
}
.nawig button svg { width: 16px; height: 16px; flex: none; opacity: .8; }
.nawig button:hover { background: rgba(255,255,255,.04); color: var(--tekst); }
.nawig button:active { transform: scale(.98); }
.nawig button[aria-selected=true] {
  background: var(--akcent-tlo); color: var(--akcent-2);
  box-shadow: inset 2px 0 0 var(--akcent);
}
.nawig button[aria-selected=true] svg { opacity: 1; }

.tresc-gl { padding: 26px 30px 80px; max-width: 1560px; }

.gora-str {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 20px; flex-wrap: wrap; margin-bottom: 24px;
}
.gora-str h1 {
  margin: 0; font-size: 26px; font-weight: 600;
  letter-spacing: -.022em; line-height: 1.15;
}
.gora-str .pod { color: var(--tekst-3); font-size: 12.5px; margin-top: 5px; letter-spacing: .002em; }

/* ---------------------------------------------------------------- karty */
.karta {
  background: linear-gradient(180deg, var(--plyta), var(--tlo-2));
  border: 1px solid var(--linia);
  border-radius: 16px;
  margin-bottom: 18px;
  overflow: hidden;
  box-shadow: 0 1px 0 rgba(255,255,255,.03) inset, 0 20px 44px -32px rgba(0,0,0,.9);
}
.karta > h2 {
  margin: 0; padding: 16px 20px 14px;
  font-size: 14px; font-weight: 600; letter-spacing: -.008em;
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 14px; flex-wrap: wrap;
  border-bottom: 1px solid var(--linia);
}
.karta > h2 .obok {
  font-weight: 400; font-size: 11.5px; color: var(--tekst-3);
  letter-spacing: .01em;
}
.tresc { padding: 18px 20px; }
.tresc p { margin: 0 0 10px; color: var(--tekst-2); }
.tresc p:last-child { margin-bottom: 0; }
.uwaga { color: var(--tekst-2); font-size: 12.5px; line-height: 1.6; }
.mini { color: var(--tekst-3); font-size: 11px; letter-spacing: .012em; }
.pusto { padding: 26px 20px; color: var(--tekst-3); font-size: 12.5px; text-align: center; }

.siatka { display: grid; gap: 18px; }
.siatka.dwie { grid-template-columns: repeat(auto-fit, minmax(370px, 1fr)); }
.siatka.trzy { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }

/* ---------------------------------------------------------------- kafle */
.kafle {
  display: grid; gap: 1px; background: var(--linia);
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
}
.kafel {
  background: var(--plyta); padding: 15px 17px 14px;
  position: relative; overflow: hidden;
  transition: background 180ms var(--e);
}
.kafel:hover { background: var(--plyta-2); }
.kafel .et {
  font-size: 10.5px; text-transform: uppercase; letter-spacing: .085em;
  color: var(--tekst-3); font-weight: 600; margin-bottom: 7px;
}
.kafel .w {
  font-size: 22px; font-weight: 600; letter-spacing: -.022em; line-height: 1.1;
}
.kafel .pod { font-size: 11px; color: var(--tekst-3); margin-top: 5px; letter-spacing: .012em; }
.kafel .isk { position: absolute; right: 12px; bottom: 10px; opacity: .75; }

/* ---------------------------------------------------------------- tabele */
.przewin { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12.8px; }
th {
  text-align: left; padding: 11px 14px;
  font-size: 10.5px; text-transform: uppercase; letter-spacing: .075em;
  color: var(--tekst-3); font-weight: 600; white-space: nowrap;
  border-bottom: 1px solid var(--linia); background: rgba(255,255,255,.012);
}
td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.04); }
tbody tr { transition: background 140ms var(--e); }
tbody tr:hover { background: rgba(255,255,255,.028); }
tbody tr:last-child td { border-bottom: 0; }
.l { text-align: right; }
.tyk { font-weight: 600; letter-spacing: -.004em; }

.plak {
  display: inline-block; font-size: 10px; font-weight: 700;
  letter-spacing: .045em; padding: 2.5px 8px; border-radius: 20px;
  text-transform: uppercase; white-space: nowrap;
}
.plak.ok { background: rgba(63,185,80,.13); color: var(--wzrost); }
.plak.zle { background: rgba(248,81,73,.13); color: var(--spadek); }
.plak.uw { background: rgba(210,153,34,.14); color: var(--uwaga); }

.kom {
  padding: 12px 16px; border-radius: 11px; margin-bottom: 16px;
  font-size: 12.8px; line-height: 1.6;
  background: var(--akcent-tlo); color: var(--akcent-2);
  border: 1px solid rgba(76,141,255,.2);
}
.kom.uw { background: rgba(210,153,34,.1); color: #E8C468; border-color: rgba(210,153,34,.24); }
.kom.zle { background: rgba(248,81,73,.1); color: #FF9B93; border-color: rgba(248,81,73,.24); }

.btn {
  display: inline-flex; align-items: center; gap: 7px;
  background: linear-gradient(180deg, var(--akcent), #3B7AE8);
  color: #fff; border: 0; border-radius: 9px;
  padding: 9px 16px; font: inherit; font-size: 13px; font-weight: 500;
  cursor: pointer; letter-spacing: -.004em;
  box-shadow: 0 8px 20px -10px rgba(76,141,255,.85);
  transition: transform var(--dotyk) var(--e), box-shadow 200ms var(--e);
}
.btn:hover { box-shadow: 0 12px 26px -10px rgba(76,141,255,.95); }
.btn:active { transform: scale(.97); }
.btn.szary {
  background: rgba(255,255,255,.06); box-shadow: none;
  border: 1px solid var(--linia-2); color: var(--tekst);
}

/* ---------------------------------------------------------------- wykresy */
.wykres { padding: 6px 4px 0; }
.wykres svg { width: 100%; display: block; }
.wykres-osx {
  display: flex; justify-content: space-between;
  font-size: 10.5px; color: var(--tekst-3); margin-top: 8px;
  letter-spacing: .015em;
}

.isk { display: block; }

.pier-uklad { display: flex; gap: 26px; align-items: center; flex-wrap: wrap; }
.pier-obraz { position: relative; flex: none; }
.pier-srodek {
  position: absolute; inset: 0; display: grid; place-content: center; text-align: center;
}
.pier-gora { font-size: 21px; font-weight: 600; letter-spacing: -.022em; }
.pier-dol { font-size: 10.5px; color: var(--tekst-3); margin-top: 2px; letter-spacing: .04em;
            text-transform: uppercase; }
.pier-legenda { flex: 1; min-width: 190px; display: flex; flex-direction: column; gap: 7px; }
.leg-w { display: flex; align-items: center; gap: 9px; font-size: 12.3px; }
.leg-w i { width: 9px; height: 9px; border-radius: 3px; flex: none; }
.leg-n { flex: 1; color: var(--tekst-2); overflow: hidden; text-overflow: ellipsis;
         white-space: nowrap; }
.leg-v { color: var(--tekst); font-weight: 600; }

.paski { display: flex; flex-direction: column; gap: 9px; }
.pasek-w { display: grid; grid-template-columns: 132px 1fr 62px; gap: 13px; align-items: center; }
.pasek-n { font-size: 12.3px; color: var(--tekst-2); text-align: right;
           overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pasek-t { height: 8px; background: rgba(255,255,255,.05); border-radius: 5px; overflow: hidden; }
.pasek-t i { display: block; height: 100%; width: var(--szer); border-radius: 5px; }
.pasek-v { font-size: 12.3px; font-weight: 600; text-align: right; }

.sp { display: flex; align-items: flex-end; gap: 2px; position: relative; padding: 8px 0; }
.sp-os { position: absolute; left: 0; right: 0; top: 50%; height: 1px;
         background: var(--linia-2); }
.sp-k { flex: 1; height: 100%; position: relative; }
.sp-k i { position: absolute; left: 0; right: 0; top: var(--gora); height: var(--h);
          border-radius: 2px; display: block; }

.kropki { display: grid; grid-template-columns: repeat(var(--kol), 1fr); gap: 5px; }
.kropka { width: 9px; height: 9px; border-radius: 50%; display: block;
          background: rgba(255,255,255,.09); }
.kropka.pelna { background: var(--kol, var(--akcent)); }

.wsk { position: relative; }
.wsk svg { width: 100%; display: block; }
.wsk-tekst { text-align: center; margin-top: -30px; }
.wsk-w { font-size: 21px; font-weight: 600; letter-spacing: -.022em; }
.wsk-p { font-size: 10.5px; color: var(--tekst-3); letter-spacing: .04em;
         text-transform: uppercase; margin-top: 2px; }

.hm { font-size: 11.5px; }
.hm th { background: 0; }
.hm-r { text-align: left; color: var(--tekst-2); font-weight: 600; }
.hm-k {
  text-align: right; border-radius: 5px; position: relative;
  background: color-mix(in oklab, var(--kol) calc(var(--moc) * 42%), transparent);
}
.hm-pusta { text-align: center; color: var(--tekst-3); }

/* ---------------------------------------------------------------- ruch */
/* Wejście kaskadowe. Opóźnienie rośnie z pozycją, ale zatrzymuje się na
   ósmym elemencie - dłuższa kaskada zaczyna się dłużyć zamiast prowadzić oko. */
@keyframes wejscie {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: none; }
}
.karta { animation: wejscie .5s var(--e) both; animation-delay: var(--op, 0ms); }

@keyframes rysuj { to { stroke-dashoffset: 0; } }
.obszar-linia {
  stroke-dasharray: 3000; stroke-dashoffset: 3000;
  animation: rysuj 1.5s var(--e) forwards .18s;
}
@keyframes pojaw { from { opacity: 0 } to { opacity: 1 } }
.obszar-wyp { animation: pojaw .9s var(--e) both .55s; }
.obszar-koniec { animation: pojaw .4s var(--e) both 1.5s; }
.isk-linia { stroke-dasharray: 400; stroke-dashoffset: 400;
             animation: rysuj 1.1s var(--e) forwards .25s; }

@keyframes rozwin { from { stroke-dasharray: 0 9999 } }
.pier-seg { animation: rozwin .9s var(--e) both .2s; }

.wsk-luk { stroke-dashoffset: 9999; animation: luk 1.1s var(--e) forwards .2s; }
@keyframes luk { to { stroke-dashoffset: var(--doc) } }

@keyframes wysun { from { width: 0 } }
.pasek-t i { animation: wysun .8s var(--e) both; animation-delay: var(--op, 0ms); }

@keyframes wyrosnij { from { height: 0; top: 50% } }
.sp-k i { animation: wyrosnij .6s var(--e) both; animation-delay: var(--op, 0ms); }

@keyframes kropnij { from { opacity: 0; transform: scale(.3) } }
.kropka { animation: kropnij .4s var(--e) both; animation-delay: var(--op, 0ms); }

/* Kto prosi o mniej ruchu, dostaje ten sam obraz od razu w stanie końcowym.
   Nie chodzi o odebranie informacji, tylko o odebranie wędrówki po ekranie. */
@media (prefers-reduced-motion: reduce) {
  .karta, .obszar-wyp, .obszar-koniec, .pier-seg, .pasek-t i, .sp-k i, .kropka {
    animation: none !important;
  }
  .obszar-linia, .isk-linia, .wsk-luk {
    animation: none !important; stroke-dashoffset: 0 !important;
  }
  .wsk-luk { stroke-dashoffset: var(--doc) !important; }
  .btn:active, .nawig button:active { transform: none; opacity: .78; }
}

@media (prefers-reduced-transparency: reduce) {
  .bok { backdrop-filter: none; background: var(--plyta); }
}

@media (max-width: 900px) {
  .szkielet { grid-template-columns: 1fr; }
  .bok {
    position: static; height: auto; border-right: 0;
    border-bottom: 1px solid var(--linia); padding: 14px;
  }
  .nawig { flex-direction: row; overflow-x: auto; gap: 6px; }
  .nawig button { white-space: nowrap; }
  .nawig button[aria-selected=true] { box-shadow: inset 0 -2px 0 var(--akcent); }
  .tresc-gl { padding: 18px 14px 60px; }
  .pasek-w { grid-template-columns: 96px 1fr 54px; }
}
"""

# Ikony nawigacji. Rysowane liniowo, jednym obrysem - w tej skali wypełnienia
# zlewają się w plamę i przestają być rozpoznawalne.
IKONY = {
    "przeglad": "M3 12h4l3-8 4 16 3-8h4",
    "wynik": "M3 17l6-6 4 4 8-8M21 7v5h-5",
    "ryzyko": "M12 3l9 16H3zM12 10v4M12 17h.01",
    "ekspozycja": "M12 3a9 9 0 109 9h-9z M12 3v9h9",
    "scenariusze": "M4 20V10M10 20V4M16 20v-7M22 20v-4",
    "opcje": "M4 18l5-6 4 3 7-9M4 6v14h16",
    "pozycje": "M4 6h16M4 12h16M4 18h10",
    "wzorzec": "M12 3v18M5 8l7-5 7 5M5 16l7 5 7-5",
    "ustawienia": "M12 15a3 3 0 100-6 3 3 0 000 6z M19 12a7 7 0 00-.1-1l2-1.5-2-3.4-2.3 1a7 7 0 00-1.7-1L14.5 3h-4l-.4 2.6a7 7 0 00-1.7 1l-2.3-1-2 3.4L6 11a7 7 0 000 2l-2 1.5 2 3.4 2.3-1a7 7 0 001.7 1l.4 2.6h4l.4-2.6a7 7 0 001.7-1l2.3 1 2-3.4-2-1.5a7 7 0 00.1-1z",
}


def ikona(nazwa: str) -> str:
    d = IKONY.get(nazwa, IKONY["przeglad"])
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true"><path d="{d}"/></svg>')
