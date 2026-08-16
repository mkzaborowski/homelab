"""Warstwa wizualna panelu.

Wydzielona ze `widok.py`, bo styl zmienia się z innego powodu niż układ
danych i mieszanie ich w jednym pliku utrudniało jedno i drugie.

Założenia, świadome i możliwe do obrony:

  * Dwa pełne motywy, jasny domyślny. Oba mają KOMPLET zmiennych - kolor
    zdefiniowany tylko w jednym znika w drugim i zostawia tekst jednego
    motywu na tle drugiego. Wybór zapamiętuje przeglądarka.
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
/* Motyw jasny jest domyślny, ciemny wchodzi atrybutem na <html>. Oba mają
   PEŁNY komplet zmiennych - kolor zdefiniowany tylko w jednym motywie znika
   w drugim i zostawia tekst jednego motywu na tle drugiego. */
:root {
  --tlo:        #F6F4FC;
  --tlo-2:      #FFFFFF;
  --plyta:      #FFFFFF;
  --plyta-2:    #FBFAFE;
  --linia:      rgba(24,20,44,.09);
  --linia-2:    rgba(24,20,44,.16);
  --tekst:      #1B1730;
  --tekst-2:    #5C5578;
  --tekst-3:    #8E88A6;

  --akcent:     #7C5CFC;
  --akcent-2:   #9E86FF;
  --akcent-tlo: rgba(124,92,252,.10);
  --wzrost:     #12A150;
  --wzrost-tlo: rgba(18,161,80,.11);
  --spadek:     #E5484D;
  --spadek-tlo: rgba(229,72,77,.10);
  --uwaga:      #C77700;
  --uwaga-tlo:  rgba(199,119,0,.11);

  --cien:       0 1px 2px rgba(24,20,44,.05), 0 12px 32px -18px rgba(24,20,44,.22);
  --poswiata-1: rgba(160,110,255,.20);
  --poswiata-2: rgba(110,140,255,.14);
  --siatka:     rgba(24,20,44,.07);

  --e:          cubic-bezier(.22,.61,.36,1);
  --dotyk:      100ms;
}

html[data-motyw="ciemny"] {
  --tlo:        #0C0A16;
  --tlo-2:      #12101E;
  --plyta:      #161424;
  --plyta-2:    #1C1930;
  --linia:      rgba(255,255,255,.08);
  --linia-2:    rgba(255,255,255,.15);
  --tekst:      #ECEAF6;
  --tekst-2:    #A29CBE;
  --tekst-3:    #6E6890;

  --akcent:     #9E86FF;
  --akcent-2:   #B9A6FF;
  --akcent-tlo: rgba(158,134,255,.15);
  --wzrost:     #3DD68C;
  --wzrost-tlo: rgba(61,214,140,.13);
  --spadek:     #FF6369;
  --spadek-tlo: rgba(255,99,105,.13);
  --uwaga:      #E5B94E;
  --uwaga-tlo:  rgba(229,185,78,.13);

  --cien:       0 1px 0 rgba(255,255,255,.03) inset, 0 20px 44px -30px rgba(0,0,0,.9);
  --poswiata-1: rgba(124,92,252,.22);
  --poswiata-2: rgba(60,100,255,.14);
  --siatka:     rgba(255,255,255,.06);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background:
    radial-gradient(1100px 620px at 12% -8%, var(--poswiata-1), transparent 62%),
    radial-gradient(900px 520px at 88% 4%, var(--poswiata-2), transparent 58%),
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
  background: color-mix(in oklab, var(--plyta) 88%, transparent);
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
  background: linear-gradient(135deg, var(--akcent), #B57BFF);
  font-style: normal; font-weight: 700; font-size: 13px; color: #fff;
  box-shadow: 0 6px 18px -6px color-mix(in oklab, var(--akcent) 70%, transparent);
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
.nawig button:hover { background: var(--akcent-tlo); color: var(--tekst); }
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
  background: var(--plyta);
  border: 1px solid var(--linia);
  border-radius: 16px;
  margin-bottom: 18px;
  overflow: hidden;
  box-shadow: var(--cien);
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
.kafel .zmiana {
  display: inline-flex; align-items: center; gap: 3px; margin-left: 8px;
  font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 20px;
  letter-spacing: .01em; vertical-align: middle;
}
.kafel .zmiana.up { background: var(--wzrost-tlo); color: var(--wzrost); }
.kafel .zmiana.down { background: var(--spadek-tlo); color: var(--spadek); }
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
  border-bottom: 1px solid var(--linia); background: var(--plyta-2);
}
td { padding: 10px 14px; border-bottom: 1px solid var(--linia); }
tbody tr { transition: background 140ms var(--e); }
tbody tr:hover { background: var(--plyta-2); }
tbody tr:last-child td { border-bottom: 0; }
.l { text-align: right; }
.tyk { font-weight: 600; letter-spacing: -.004em; }

.plak {
  display: inline-block; font-size: 10px; font-weight: 700;
  letter-spacing: .045em; padding: 2.5px 8px; border-radius: 20px;
  text-transform: uppercase; white-space: nowrap;
}
.plak.ok { background: var(--wzrost-tlo); color: var(--wzrost); }
.plak.zle { background: var(--spadek-tlo); color: var(--spadek); }
.plak.uw { background: var(--uwaga-tlo); color: var(--uwaga); }

.kom {
  padding: 12px 16px; border-radius: 11px; margin-bottom: 16px;
  font-size: 12.8px; line-height: 1.6;
  background: var(--akcent-tlo); color: var(--akcent);
  border: 1px solid color-mix(in oklab, var(--akcent) 26%, transparent);
}
.kom.uw { background: var(--uwaga-tlo); color: var(--uwaga);
  border-color: color-mix(in oklab, var(--uwaga) 30%, transparent); }
.kom.zle { background: var(--spadek-tlo); color: var(--spadek);
  border-color: color-mix(in oklab, var(--spadek) 30%, transparent); }

.btn {
  display: inline-flex; align-items: center; gap: 7px;
  background: linear-gradient(180deg, var(--akcent), color-mix(in oklab, var(--akcent) 82%, #000));
  color: #fff; border: 0; border-radius: 9px;
  padding: 9px 16px; font: inherit; font-size: 13px; font-weight: 500;
  cursor: pointer; letter-spacing: -.004em;
  box-shadow: 0 8px 20px -10px color-mix(in oklab, var(--akcent) 80%, transparent);
  transition: transform var(--dotyk) var(--e), box-shadow 200ms var(--e);
}
.btn:hover { box-shadow: 0 12px 26px -10px color-mix(in oklab, var(--akcent) 90%, transparent); }
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
.pasek-t { height: 8px; background: var(--linia); border-radius: 5px; overflow: hidden; }
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
          background: var(--linia); }
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

/* ------------------------------------------------------------- histogram */
.hg-pole {
  position: relative; display: flex; align-items: flex-end; gap: 0;
  --szer: 3%; padding-top: 18px;
}
.hg-k {
  flex: 1; height: var(--h); min-height: 1px; background: var(--kol);
  opacity: .78; border-radius: 3px 3px 0 0; margin: 0 .6px;
  transform-origin: bottom;
}
.hg-k:hover { opacity: 1; }
/* Znacznik progu. Cała treść histogramu zwrotów siedzi w tej linii - sam
   kształt mówi „bywa różnie", dopiero próg pokazuje, gdzie leży granica. */
.hg-znacznik {
  position: absolute; top: 0; bottom: 0; left: var(--x); width: 0;
  border-left: 1px dashed var(--kol);
}
.hg-znacznik span {
  position: absolute; top: -2px; left: 4px; font-size: 10px; font-weight: 600;
  letter-spacing: .02em; color: var(--kol); white-space: nowrap;
}

/* --------------------------------------------------------------- tornado */
.tor { position: relative; display: flex; flex-direction: column; gap: 9px; }
/* Oś zera przechodzi przez środek pola słupków, nie przez środek wiersza -
   podpisy po bokach mają stałą szerokość, więc muszą być z niej wyłączone. */
.tor-os {
  position: absolute; top: 0; bottom: 0; left: calc(148px + (100% - 148px - 78px) / 2);
  width: 1px; background: var(--linia-2);
}
.tor-w {
  display: grid; grid-template-columns: 148px 1fr 78px; align-items: center; gap: 10px;
  font-size: 12.3px;
}
.tor-n { color: var(--tekst-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tor-t { position: relative; height: 15px; }
.tor-t i {
  position: absolute; top: 0; bottom: 0; left: var(--lewo); width: var(--szer);
  border-radius: 3px; opacity: .88;
}
.tor-v { text-align: right; font-weight: 600; font-size: 12px; }

/* --------------------------------------------------------------- rozrzut */
.rz svg { width: 100%; display: block; overflow: visible; }
.rz-et { font-size: 15px; font-weight: 600; }
.rz-osie {
  display: flex; justify-content: space-between; margin-top: 8px;
  font-size: 11px; color: var(--tekst-3); letter-spacing: .02em;
}

.legenda-pozioma {
  display: flex; flex-wrap: wrap; gap: 8px 20px; margin-top: 12px;
  padding-top: 12px; border-top: 1px solid var(--linia);
}

/* ------------------------------------------------- sterowniki nad wykresem */
.narzedzia { display: flex; gap: 6px; align-items: center; }
/* Pigułki zakresu w normalnym przepływie nad wykresem, dosunięte do prawej.
   Świadomie nie absolutnie: nad wykresem siedzi już nagłówek karty z własnym
   podpisem po prawej, a dwie rzeczy pozycjonowane absolutnie w tym samym
   rogu zderzają się przy pierwszym dłuższym podpisie. */
.wykres > .zakres { display: flex; width: max-content; margin: 0 2px 12px auto; }
.zakres {
  display: inline-flex; background: var(--plyta-2); border: 1px solid var(--linia);
  border-radius: 9px; padding: 2px; gap: 2px;
}
.zakres button {
  background: 0; border: 0; cursor: pointer; font: inherit; font-size: 11.5px;
  font-weight: 600; letter-spacing: .01em; color: var(--tekst-3);
  padding: 5px 11px; border-radius: 7px;
  transition: background var(--dotyk) var(--e), color var(--dotyk) var(--e);
}
.zakres button:hover { color: var(--tekst); }
.zakres button:active { transform: scale(.96); }
.zakres button[aria-pressed=true] {
  background: var(--plyta); color: var(--akcent);
  box-shadow: 0 1px 3px rgba(24,20,44,.10);
}

.motyw {
  background: var(--plyta-2); border: 1px solid var(--linia); cursor: pointer;
  width: 32px; height: 32px; border-radius: 9px; color: var(--tekst-2);
  display: grid; place-items: center; padding: 0;
  transition: transform var(--dotyk) var(--e), color var(--dotyk) var(--e);
}
.motyw:hover { color: var(--tekst); }
.motyw:active { transform: scale(.94); }
.motyw svg { width: 15px; height: 15px; }

/* Podpowiedź śledząca kursor. Pozycjonowana transformem, nie left/top -
   przy ruchu myszy to jedyna droga, która nie wymusza przeliczania układu
   przy każdej klatce. */
.wykres { position: relative; }
.podp {
  position: absolute; pointer-events: none; z-index: 5;
  background: var(--plyta); border: 1px solid var(--linia-2);
  border-radius: 10px; padding: 8px 11px; box-shadow: var(--cien);
  font-size: 11.5px; white-space: nowrap;
  opacity: 0; transition: opacity 130ms var(--e);
  transform: translate(-50%, -118%);
}
.podp.widoczna { opacity: 1; }
.podp .p-data { color: var(--tekst-3); font-size: 10.5px; letter-spacing: .02em; }
.podp .p-wart { color: var(--akcent); font-weight: 700; font-size: 13px; margin-top: 1px; }
.kursor-linia {
  position: absolute; top: 0; bottom: 22px; width: 1px;
  background: var(--linia-2); opacity: 0; pointer-events: none;
  transition: opacity 130ms var(--e);
}
.kursor-linia.widoczna { opacity: 1; }
.kursor-kropka {
  position: absolute; width: 9px; height: 9px; border-radius: 50%;
  background: var(--akcent); border: 2px solid var(--plyta);
  opacity: 0; pointer-events: none; transform: translate(-50%, -50%);
  transition: opacity 130ms var(--e);
  box-shadow: 0 0 0 3px var(--akcent-tlo);
}
.kursor-kropka.widoczna { opacity: 1; }

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

/* Histogram rośnie od podstawy, bo tak przyrasta liczba obserwacji.
   Skalujemy transformem, nie wysokością - to jedyna z tych dwóch dróg,
   której przeglądarka nie musi przeliczać w każdej klatce. */
@keyframes wzrost_y { from { transform: scaleY(0) } }
.hg-k { animation: wzrost_y .55s var(--e) both; animation-delay: var(--op, 0ms); }

@keyframes rozejdz { from { width: 0; left: 50% } }
.tor-t i { animation: rozejdz .7s var(--e) both; animation-delay: var(--op, 0ms); }

.rz-p { animation: kropnij .45s var(--e) both; animation-delay: var(--op, 0ms); }

/* Kto prosi o mniej ruchu, dostaje ten sam obraz od razu w stanie końcowym.
   Nie chodzi o odebranie informacji, tylko o odebranie wędrówki po ekranie. */
@media (prefers-reduced-motion: reduce) {
  .karta, .obszar-wyp, .obszar-koniec, .pier-seg, .pasek-t i, .sp-k i, .kropka,
  .hg-k, .tor-t i, .rz-p {
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


# Zachowanie warstwy wizualnej. Świadomie w jednym miejscu i bez zależności -
# to kilkadziesiąt linii, a nie powód do wprowadzania kroku budowania.
SKRYPT_UI = """
<script>
(function(){
  // ---- motyw ----------------------------------------------------------
  // Zapisany wybór wygrywa z ustawieniem systemu, bo jest nowszą decyzją
  // tej samej osoby. Stosujemy go przed pierwszym rysowaniem, żeby nie
  // było mignięcia jasnym tłem przy wejściu w motywie ciemnym.
  var H = document.documentElement;
  try {
    var zap = localStorage.getItem('motyw');
    if (zap) H.dataset.motyw = zap;
    else if (matchMedia('(prefers-color-scheme: dark)').matches) H.dataset.motyw = 'ciemny';
  } catch(e) {}

  document.addEventListener('click', function(ev){
    var b = ev.target.closest('.motyw');
    if (!b) return;
    var ciemny = H.dataset.motyw === 'ciemny';
    H.dataset.motyw = ciemny ? 'jasny' : 'ciemny';
    try { localStorage.setItem('motyw', H.dataset.motyw); } catch(e) {}
    b.setAttribute('aria-label', ciemny ? 'Włącz motyw ciemny' : 'Włącz motyw jasny');
  });

  // ---- wykres przebiegu: podpowiedź i zakres --------------------------
  // Ta sama krzywa Catmulla-Roma co na serwerze. Powtórzenie wzoru w dwóch
  // językach jest kosztem, ale alternatywą było odpytywanie serwera przy
  // każdej zmianie zakresu - opóźnienie i stan do zsynchronizowania w zamian
  // za zero nowych danych, bo wszystkie punkty i tak są już na stronie.
  function sciezka(pkt, nap){
    if (pkt.length < 2) return '';
    var d = ['M ' + pkt[0][0].toFixed(2) + ' ' + pkt[0][1].toFixed(2)];
    for (var i = 0; i < pkt.length - 1; i++) {
      var p0 = i ? pkt[i-1] : pkt[0], p1 = pkt[i], p2 = pkt[i+1],
          p3 = (i + 2 < pkt.length) ? pkt[i+2] : p2;
      d.push('C ' + (p1[0] + (p2[0]-p0[0])*nap).toFixed(2) + ' '
                  + (p1[1] + (p2[1]-p0[1])*nap).toFixed(2) + ' '
                  + (p2[0] - (p3[0]-p1[0])*nap).toFixed(2) + ' '
                  + (p2[1] - (p3[1]-p1[1])*nap).toFixed(2) + ' '
                  + p2[0].toFixed(2) + ' ' + p2[1].toFixed(2));
    }
    return d.join(' ');
  }

  function podepnij(w){
    var wszystkie = (w.dataset.punkty || '').split('|').map(function(x){
      var c = x.split(';'); return { d: c[0], v: parseFloat(c[1]) };
    }).filter(function(p){ return p.d && !isNaN(p.v); });
    if (wszystkie.length < 2) return;

    var jedn = w.dataset.jedn || '', WYS = parseFloat(w.dataset.wys) || 230, SZER = 1000;
    var podp = w.querySelector('.podp'), linia = w.querySelector('.kursor-linia'),
        kropka = w.querySelector('.kursor-kropka'), svg = w.querySelector('svg');
    if (!podp || !svg) return;
    var pData = podp.querySelector('.p-data'), pWart = podp.querySelector('.p-wart'),
        wyp = svg.querySelector('.obszar-wyp'), lin = svg.querySelector('.obszar-linia'),
        koniec = svg.querySelector('.obszar-koniec'),
        osx = w.querySelectorAll('.wykres-osx span');
    var punkty = wszystkie, lo = parseFloat(w.dataset.lo), hi = parseFloat(w.dataset.hi);

    // Przerysowanie zakresu. Skalę liczymy od nowa dla widocznego wycinka -
    // gdyby została z całości, miesięczny wykres byłby płaską kreską przez
    // środek i nie pokazywałby tego, po co się go otwiera.
    function przerysuj(dni){
      punkty = (dni > 0 && dni < wszystkie.length)
        ? wszystkie.slice(wszystkie.length - dni) : wszystkie;
      var v = punkty.map(function(p){ return p.v; });
      var mn = Math.min.apply(null, v), mx = Math.max.apply(null, v);
      var marg = (mx - mn) * 0.12 || (Math.abs(mx) * 0.05 || 1);
      lo = mn - marg; hi = mx + marg;
      var rozp = (hi - lo) || 1, krok = SZER / (punkty.length - 1);
      var pkt = punkty.map(function(p, i){
        return [i * krok, WYS - ((p.v - lo) / rozp) * WYS];
      });
      var d = sciezka(pkt, 0.22);
      if (lin) lin.setAttribute('d', d);
      if (wyp) wyp.setAttribute('d', d + ' L ' + SZER + ' ' + WYS + ' L 0 ' + WYS + ' Z');
      if (koniec) {
        koniec.setAttribute('cx', pkt[pkt.length-1][0].toFixed(1));
        koniec.setAttribute('cy', pkt[pkt.length-1][1].toFixed(1));
      }
      if (osx.length === 2) {
        osx[0].textContent = punkty[0].d;
        osx[1].textContent = punkty[punkty.length-1].d;
      }
      schowaj();
    }

    // Pozycjonujemy transformem, nie left/top: przy ruchu myszy to jedyna
    // droga, która nie wymusza przeliczania układu w każdej klatce.
    var czeka = 0;
    function rusz(ev){
      if (czeka) return;
      czeka = requestAnimationFrame(function(){
        czeka = 0;
        var r = svg.getBoundingClientRect();
        var u = Math.min(Math.max((ev.clientX - r.left) / r.width, 0), 1);
        var i = Math.round(u * (punkty.length - 1));
        var p = punkty[i];
        var x = (i / (punkty.length - 1)) * r.width;
        var y = r.height - ((p.v - lo) / ((hi - lo) || 1)) * r.height;

        pData.textContent = p.d;
        pWart.textContent = jedn + p.v.toLocaleString('pl-PL',
          { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        podp.style.transform = 'translate(' + x + 'px,' + (y - 14) + 'px) translate(-50%,-100%)';
        linia.style.transform = 'translateX(' + x + 'px)';
        kropka.style.transform = 'translate(' + x + 'px,' + y + 'px) translate(-50%,-50%)';
        podp.classList.add('widoczna');
        linia.classList.add('widoczna');
        kropka.classList.add('widoczna');
      });
    }
    function schowaj(){
      podp.classList.remove('widoczna');
      linia.classList.remove('widoczna');
      kropka.classList.remove('widoczna');
    }
    // pointer, nie mouse - ten sam kod obsługuje rysik i dotyk
    w.addEventListener('pointermove', rusz);
    w.addEventListener('pointerleave', schowaj);
    w.addEventListener('pointercancel', schowaj);

    var pig = w.querySelector('.zakres');
    if (pig) pig.addEventListener('click', function(ev){
      var b = ev.target.closest('button');
      if (!b) return;
      pig.querySelectorAll('button').forEach(function(x){
        x.setAttribute('aria-pressed', String(x === b));
      });
      przerysuj(parseInt(b.dataset.dni || '0', 10));
    });
  }
  document.querySelectorAll('[data-wykres]').forEach(podepnij);
})();
</script>
"""
