"""Wykresy SVG rysowane ręcznie, bez bibliotek.

Po co bez bibliotek: cały panel jest składany po stronie serwera i nie ma
kroku budowania. Doładowanie kilkuset kilobajtów JavaScriptu po to, żeby
narysować kilkanaście wykresów, byłoby gorszym rozwiązaniem niż napisanie
tych kilkuset linii SVG.

Zasady rysowania, wspólne dla wszystkiego niżej:

  * animujemy WYŁĄCZNIE `transform`, `opacity` i `stroke-dashoffset` -
    to jedyne właściwości, które przeglądarka umie kompozytować bez
    przeliczania układu,
  * każdy wykres ma opis dla czytnika ekranu, bo sam SVG jest dla niego
    niemy,
  * przy `prefers-reduced-motion` rysunek pojawia się od razu w stanie
    końcowym - ruch znika, informacja zostaje,
  * liczby na osiach i w etykietach idą `tabular-nums`, żeby nie tańczyły
    przy zmianie wartości.
"""
from __future__ import annotations

import math
from html import escape as e

# Wspólna paleta. Semantyka (wzrost/spadek/uwaga) jest ODDZIELONA od akcentu:
# akcent oznacza „to jest interaktywne albo wyróżnione", a nie „to jest dobre".
# Kolory idą przez zmienne CSS, nie przez stałe. Dzięki temu wykresy zmieniają
# się razem z motywem, zamiast zostawać niebieskie na fioletowym tle albo
# białoszare na jasnym. SVG rozumie var() w atrybutach stroke i fill,
# a także w stop-color gradientu.
AKCENT = "var(--akcent)"
AKCENT_2 = "var(--akcent-2)"
WZROST = "var(--wzrost)"
SPADEK = "var(--spadek)"
UWAGA = "var(--uwaga)"
SIATKA = "var(--siatka)"
TEKST_SLABY = "var(--tekst-3)"

# Paleta pierścieni. Tu potrzebne są wartości bezwzględne, bo kategorii bywa
# osiem i muszą być rozróżnialne między sobą, a nie tylko wobec tła.
PALETA = ["#7C5CFC", "#9E86FF", "#5B8DEF", "#3DBFA0", "#12A150",
          "#E5A21A", "#EE7C4E", "#C05FD8"]

_licznik = [0]


def _id(prefiks: str) -> str:
    """Unikalny identyfikator gradientu. Bez tego dwa wykresy na stronie
    dzieliłyby definicję i drugi przejmowałby kolory pierwszego."""
    _licznik[0] += 1
    return f"{prefiks}{_licznik[0]}"


def _sciezka_gladka(punkty: list[tuple[float, float]], napiecie: float = 0.22) -> str:
    """Krzywa Catmulla-Roma zamieniona na Béziera.

    Łamana z ostrymi wierzchołkami wygląda na surowe dane; wygładzenie
    czyta się jako przebieg. Napięcie trzymamy niskie, żeby krzywa nie
    zaczęła zmyślać wartości między punktami - przy 0,22 nie wychodzi
    poza zakres sąsiadów w żadnym realnym szeregu."""
    if len(punkty) < 2:
        return ""
    d = [f"M {punkty[0][0]:.2f} {punkty[0][1]:.2f}"]
    for i in range(len(punkty) - 1):
        p0 = punkty[i - 1] if i else punkty[0]
        p1, p2 = punkty[i], punkty[i + 1]
        p3 = punkty[i + 2] if i + 2 < len(punkty) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * napiecie, p1[1] + (p2[1] - p0[1]) * napiecie)
        c2 = (p2[0] - (p3[0] - p1[0]) * napiecie, p2[1] - (p3[1] - p1[1]) * napiecie)
        d.append(f"C {c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} "
                 f"{p2[0]:.2f} {p2[1]:.2f}")
    return " ".join(d)


# --------------------------------------------------------------------------- #
#  iskierka - mikrowykres do kafla
# --------------------------------------------------------------------------- #

def iskierka(wartosci: list[float], kolor: str = AKCENT, szer: int = 120,
             wys: int = 34, wypelnienie: bool = True) -> str:
    """Przebieg bez osi i podpisów, do wstawienia obok liczby w kaflu.

    Świadomie bez skali: iskierka odpowiada na pytanie „w którą stronę",
    a nie „ile". Kropka na końcu zaznacza stan bieżący, bo bez niej oko
    nie wie, którą stroną czytać."""
    if len(wartosci) < 2:
        return ""
    lo, hi = min(wartosci), max(wartosci)
    rozpietosc = (hi - lo) or 1.0
    krok = szer / (len(wartosci) - 1)
    pkt = [(i * krok, wys - 3 - ((v - lo) / rozpietosc) * (wys - 8))
           for i, v in enumerate(wartosci)]
    d = _sciezka_gladka(pkt)
    g = _id("isk")
    wyp = (f'<defs><linearGradient id="{g}" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="{kolor}" stop-opacity=".26"/>'
           f'<stop offset="1" stop-color="{kolor}" stop-opacity="0"/></linearGradient></defs>'
           f'<path d="{d} L {szer} {wys} L 0 {wys} Z" fill="url(#{g})"/>') if wypelnienie else ""
    return (f'<svg class="isk" viewBox="0 0 {szer} {wys}" width="{szer}" height="{wys}" '
            f'aria-hidden="true" preserveAspectRatio="none">{wyp}'
            f'<path class="isk-linia" d="{d}" fill="none" stroke="{kolor}" '
            f'stroke-width="1.8" stroke-linecap="round"/>'
            f'<circle cx="{pkt[-1][0]:.1f}" cy="{pkt[-1][1]:.1f}" r="2.6" fill="{kolor}"/></svg>')


# --------------------------------------------------------------------------- #
#  wykres warstwowy z gradientem
# --------------------------------------------------------------------------- #

def obszar(szereg: list[tuple[str, float]], wys: int = 230, kolor: str = AKCENT,
           opis: str = "", jednostka: str = "$", odniesienie: float | None = None) -> str:
    """Główny wykres przebiegu: linia z gradientowym wypełnieniem pod spodem.

    Siatka jest celowo ledwo widoczna. Ma dać oku punkt odniesienia, a nie
    konkurować z danymi - to dane mają być najjaśniejszym elementem kadru."""
    if len(szereg) < 2:
        return '<div class="pusto">Za mało danych na wykres.</div>'
    wartosci = [v for _, v in szereg]
    lo, hi = min(wartosci), max(wartosci)
    if odniesienie is not None:
        lo, hi = min(lo, odniesienie), max(hi, odniesienie)
    margines = (hi - lo) * 0.12 or (abs(hi) * 0.05 or 1.0)
    lo, hi = lo - margines, hi + margines
    rozp = (hi - lo) or 1.0

    szer = 1000
    krok = szer / (len(szereg) - 1)
    y = lambda v: wys - ((v - lo) / rozp) * wys           # noqa: E731
    pkt = [(i * krok, y(v)) for i, v in enumerate(wartosci)]
    d = _sciezka_gladka(pkt)
    g, gl = _id("obs"), _id("gl")

    linie = "".join(
        f'<line x1="0" y1="{wys * u:.1f}" x2="{szer}" y2="{wys * u:.1f}" stroke="{SIATKA}"/>'
        for u in (0.25, 0.5, 0.75))
    odn = ""
    if odniesienie is not None:
        yo = y(odniesienie)
        odn = (f'<line x1="0" y1="{yo:.1f}" x2="{szer}" y2="{yo:.1f}" '
               f'stroke="{TEKST_SLABY}" stroke-dasharray="4 4"/>')

    # Dane dla podpowiedzi trafiają do atrybutu, a nie do osobnego żądania -
    # przy 262 punktach to kilka kilobajtów, a unika się całej maszynerii
    # asynchronicznej dla czegoś, co i tak jest już na stronie.
    dane_json = "|".join(f"{d};{v:.2f}" for d, v in szereg)

    return f'''<div class="wykres" data-wykres data-punkty="{e(dane_json)}"
     data-jedn="{e(jednostka)}" data-lo="{lo:.4f}" data-hi="{hi:.4f}">
<svg viewBox="0 0 {szer} {wys}" preserveAspectRatio="none" role="img"
     aria-label="{e(opis or "Przebieg wartości")}: od {jednostka}{wartosci[0]:,.0f} do {jednostka}{wartosci[-1]:,.0f}">
  <defs>
    <linearGradient id="{g}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{kolor}" stop-opacity=".30"/>
      <stop offset="1" stop-color="{kolor}" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="{gl}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{kolor}"/>
      <stop offset="1" stop-color="{AKCENT_2}"/>
    </linearGradient>
  </defs>
  {linie}{odn}
  <path class="obszar-wyp" d="{d} L {szer} {wys} L 0 {wys} Z" fill="url(#{g})"/>
  <path class="obszar-linia" d="{d}" fill="none" stroke="url(#{gl})" stroke-width="2.2"
        stroke-linecap="round" stroke-linejoin="round"/>
  <circle class="obszar-koniec" cx="{pkt[-1][0]:.1f}" cy="{pkt[-1][1]:.1f}" r="4" fill="{kolor}"/>
</svg>
<div class="kursor-linia"></div><div class="kursor-kropka"></div>
<div class="podp"><div class="p-data"></div><div class="p-wart num"></div></div>
<div class="wykres-osx"><span>{e(szereg[0][0])}</span><span>{e(szereg[-1][0])}</span></div>
</div>'''.replace(",", " ")


# --------------------------------------------------------------------------- #
#  pierścień
# --------------------------------------------------------------------------- #

def pierscien(dane: list[tuple[str, float]], srodek_gora: str = "",
              srodek_dol: str = "", rozmiar: int = 190) -> str:
    """Udziały jako pierścień z podpisem w środku.

    Pierścień, nie koło: dziura w środku daje miejsce na liczbę, która i tak
    jest ważniejsza niż same proporcje. Powyżej ośmiu kategorii zwijamy resztę,
    bo cieńszych wycinków oko i tak nie rozróżni."""
    dane = [(n, abs(v)) for n, v in dane if v]
    if not dane:
        return '<div class="pusto">Brak danych.</div>'
    dane.sort(key=lambda x: -x[1])
    if len(dane) > 8:
        reszta = sum(v for _, v in dane[7:])
        dane = dane[:7] + [("Pozostałe", reszta)]
    suma = sum(v for _, v in dane) or 1.0

    palet = PALETA
    r, gr = rozmiar / 2 - 16, 15
    obwod = 2 * math.pi * r
    kat = -90.0
    seg, legenda = [], []
    for i, (nazwa, v) in enumerate(dane):
        udzial = v / suma
        kolor = palet[i % len(palet)]
        seg.append(
            f'<circle class="pier-seg" cx="{rozmiar/2}" cy="{rozmiar/2}" r="{r:.1f}" '
            f'fill="none" stroke="{kolor}" stroke-width="{gr}" '
            f'stroke-dasharray="{obwod * udzial:.2f} {obwod:.2f}" '
            f'stroke-dashoffset="{-obwod * (kat + 90) / 360:.2f}" '
            f'transform="rotate(-90 {rozmiar/2} {rozmiar/2})" stroke-linecap="butt"/>')
        legenda.append(
            f'<div class="leg-w"><i style="background:{kolor}"></i>'
            f'<span class="leg-n">{e(nazwa)}</span>'
            f'<span class="leg-v num">{udzial*100:.1f}%</span></div>')
        kat += udzial * 360

    srodek = ""
    if srodek_gora or srodek_dol:
        srodek = (f'<div class="pier-srodek">'
                  f'<div class="pier-gora num">{srodek_gora}</div>'
                  f'<div class="pier-dol">{e(srodek_dol)}</div></div>')
    return (f'<div class="pier-uklad"><div class="pier-obraz" '
            f'style="width:{rozmiar}px;height:{rozmiar}px">'
            f'<svg viewBox="0 0 {rozmiar} {rozmiar}" role="img" '
            f'aria-label="Udziały: ' + e(", ".join(f"{n} {v/suma*100:.0f}%" for n, v in dane[:5])) + '">'
            f'<circle cx="{rozmiar/2}" cy="{rozmiar/2}" r="{r:.1f}" fill="none" '
            f'stroke="rgba(255,255,255,.05)" stroke-width="{gr}"/>'
            + "".join(seg) + f'</svg>{srodek}</div>'
            f'<div class="pier-legenda">' + "".join(legenda) + '</div></div>')


# --------------------------------------------------------------------------- #
#  słupki poziome
# --------------------------------------------------------------------------- #

def slupki_poziome(dane: list[dict], klucz_nazwy: str = "nazwa",
                   klucz_wartosci: str = "udzial", ile: int = 10,
                   przyrostek: str = "%", kolor=None) -> str:
    """Ranking. Skala do najwyższej pozycji, nie do stu procent - inaczej
    przy rozdrobnionym portfelu wszystkie paski są równie krótkie i nie da
    się porównać niczego z niczym."""
    if not dane:
        return '<div class="pusto">Brak danych.</div>'
    dane = dane[:ile]
    naj = max(abs(d[klucz_wartosci]) for d in dane) or 1.0
    w = []
    for i, d in enumerate(dane):
        v = d[klucz_wartosci]
        szer = abs(v) / naj * 100
        k = kolor(d) if callable(kolor) else (kolor or AKCENT)
        w.append(
            f'<div class="pasek-w" style="--op:{i * 45}ms">'
            f'<span class="pasek-n">{e(str(d[klucz_nazwy]))}</span>'
            f'<span class="pasek-t"><i style="--szer:{szer:.1f}%;background:'
            f'linear-gradient(90deg,{k},{k}dd)"></i></span>'
            f'<span class="pasek-v num">{v:.1f}{przyrostek}</span></div>')
    return f'<div class="paski">{"".join(w)}</div>'


# --------------------------------------------------------------------------- #
#  mapa ciepła
# --------------------------------------------------------------------------- #

def mapa_ciepla(wiersze: list[dict], kolumny: list[str], wartosci: dict,
                fmt=lambda v: f"{v * 100:+.1f}") -> str:
    """Siatka kolorowana natężeniem wartości.

    Nasycenie skalujemy do najmocniejszej komórki, nie do wartości bezwzględnej.
    Dzięki temu spokojny rok nie wygląda na bezbarwny, a burzliwy nie zlewa się
    w jedną plamę."""
    if not wartosci:
        return '<div class="pusto">Brak danych.</div>'
    naj = max(abs(v) for v in wartosci.values() if v is not None) or 0.01
    naglowek = "".join(f'<th class="l">{e(k)}</th>' for k in kolumny)
    body = []
    for w in wiersze:
        kom = []
        for k in kolumny:
            v = wartosci.get((w["klucz"], k))
            if v is None:
                kom.append('<td class="hm-pusta">·</td>')
                continue
            moc = min(abs(v) / naj, 1.0)
            baza = WZROST if v >= 0 else SPADEK
            kom.append(f'<td class="hm-k num" style="--moc:{moc:.3f};--kol:{baza}">'
                       f'{fmt(v)}</td>')
        body.append(f'<tr><th class="hm-r">{e(w["etykieta"])}</th>{"".join(kom)}</tr>')
    return (f'<div class="przewin"><table class="hm"><thead><tr><th></th>{naglowek}</tr>'
            f'</thead><tbody>{"".join(body)}</tbody></table></div>')


# --------------------------------------------------------------------------- #
#  słupki pionowe ze znakiem
# --------------------------------------------------------------------------- #

def slupki_pionowe(dane: list[tuple[str, float]], wys: int = 150,
                   fmt=lambda v: f"{v:+.1f}%") -> str:
    """Wartości dodatnie i ujemne wokół osi zera. Oś rysujemy zawsze, nawet
    gdy wszystko jest po jednej stronie - bez niej nie widać, gdzie jest zero."""
    if not dane:
        return '<div class="pusto">Brak danych.</div>'
    naj = max(abs(v) for _, v in dane) or 1.0
    szer_s = max(100.0 / len(dane) - 1.6, 2.0)
    w = []
    for i, (n, v) in enumerate(dane):
        h = abs(v) / naj * 46
        gora = 50 - h if v >= 0 else 50
        kolor = WZROST if v >= 0 else SPADEK
        w.append(
            f'<div class="sp-k" style="--op:{i * 26}ms" title="{e(n)}: {fmt(v)}">'
            f'<i style="--h:{h:.1f}%;--gora:{gora:.1f}%;background:{kolor}"></i></div>')
    return (f'<div class="sp" style="height:{wys}px;--szer:{szer_s:.2f}%">'
            f'<div class="sp-os"></div>{"".join(w)}</div>')


# --------------------------------------------------------------------------- #
#  siatka kropek
# --------------------------------------------------------------------------- #

def kropki(ile_pelnych: int, ile_wszystkich: int, kolumny: int = 14,
           kolor: str = AKCENT) -> str:
    """Proporcja jako policzalne kropki. Przy małych liczbach czyta się to
    dokładniej niż pasek postępu, bo widać pojedyncze sztuki."""
    ile_wszystkich = max(ile_wszystkich, 1)
    w = []
    for i in range(ile_wszystkich):
        pelna = i < ile_pelnych
        w.append(f'<i class="kropka{" pelna" if pelna else ""}" '
                 f'style="--op:{i * 14}ms;--kol:{kolor}"></i>')
    return (f'<div class="kropki" style="--kol:{kolumny}" role="img" '
            f'aria-label="{ile_pelnych} z {ile_wszystkich}">{"".join(w)}</div>')


# --------------------------------------------------------------------------- #
#  wskaźnik półkolisty
# --------------------------------------------------------------------------- #

def wskaznik(wartosc: float, minimum: float = 0.0, maksimum: float = 1.0,
             etykieta: str = "", podpis: str = "", kolor: str = AKCENT,
             rozmiar: int = 170) -> str:
    """Półokrąg dla wielkości z naturalnym zakresem - pokrycia, udziału,
    wykorzystania limitu. Dla wartości bez górnej granicy wskaźnik kłamie,
    bo sugeruje maksimum, którego nie ma."""
    zakres = (maksimum - minimum) or 1.0
    u = max(0.0, min(1.0, (wartosc - minimum) / zakres))
    r = rozmiar / 2 - 14
    obwod = math.pi * r
    return (f'<div class="wsk" style="width:{rozmiar}px">'
            f'<svg viewBox="0 0 {rozmiar} {rozmiar/2 + 12}" role="img" '
            f'aria-label="{e(etykieta)}: {u*100:.0f} procent">'
            f'<path d="M 14 {rozmiar/2} A {r:.1f} {r:.1f} 0 0 1 {rozmiar-14} {rozmiar/2}" '
            f'fill="none" stroke="rgba(255,255,255,.07)" stroke-width="11" stroke-linecap="round"/>'
            f'<path class="wsk-luk" d="M 14 {rozmiar/2} A {r:.1f} {r:.1f} 0 0 1 '
            f'{rozmiar-14} {rozmiar/2}" fill="none" stroke="{kolor}" stroke-width="11" '
            f'stroke-linecap="round" stroke-dasharray="{obwod:.1f}" '
            f'style="--doc:{obwod * (1 - u):.1f}"/>'
            f'</svg><div class="wsk-tekst"><div class="wsk-w num">{e(etykieta)}</div>'
            f'<div class="wsk-p">{e(podpis)}</div></div></div>')
