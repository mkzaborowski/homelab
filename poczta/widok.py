"""Panel pocztowy.

Ten sam neutralny motyw co panel portfela - wspólny `style.py`, bo obie
usługi są moje i nie ma powodu, żeby wyglądały jak dwa różne produkty.

UKŁAD PODPORZĄDKOWANY IZOLACJI SERWISÓW. Serwis wybiera się na samej górze
i wszystko poniżej dotyczy WYŁĄCZNIE jego: kontakty, szablony, log, klucz.
Nie ma widoku „wszystkie kontakty razem", bo taki widok zapraszałby do
wysyłki na mieszaną listę - a tego właśnie ma nie być.
"""
from __future__ import annotations

from html import escape as e

import style

ZAKLADKI = (("przeglad", "Overview"), ("kontakty", "Contacts"),
            ("szablony", "Templates"), ("log", "Send log"),
            ("wykluczenia", "Suppressed"))

STANY = {"czeka": ("queued", "uw"), "wyslany": ("sent", "ok"),
         "przepadl": ("failed", "zle")}


def _plakietka(stan: str) -> str:
    etykieta, klasa = STANY.get(stan, (stan, "uw"))
    return f'<span class="plak {klasa}">{e(etykieta)}</span>'


def _kafel(etykieta: str, wartosc, klasa: str = "", pod: str = "") -> str:
    return (f'<div class="kafel"><div class="et">{e(etykieta)}</div>'
            f'<div class="w num {klasa}">{wartosc}</div>'
            f'<div class="pod num">{e(pod)}</div></div>')


def _skrot(s: str, n: int = 60) -> str:
    s = (s or "").replace("\n", " ").strip()
    return e(s if len(s) <= n else s[:n - 1] + "…")


def _czas(s: str | None) -> str:
    """Znacznik ISO z sekundami skracamy do „RRRR-MM-DD GG:MM" - sekundy
    w logu wysyłek nikomu nie służą, a psują wyrównanie kolumny."""
    if not s:
        return "—"
    return e(s.replace("T", " ")[:16])


def logowanie(blad: str = "") -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><meta name="color-scheme" content="light dark">
<title>Mail — sign in</title><style>{style.STYL}</style></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh">
<form method="post" action="/login" class="karta" style="max-width:340px;width:100%;margin:0">
  <h2>Mail service</h2>
  <div class="tresc">
    {f'<div class="kom zle">{e(blad)}</div>' if blad else ''}
    <input type="password" name="haslo" placeholder="Password" autofocus required
           style="width:100%;margin-bottom:10px;padding:8px 10px">
    <button class="btn" style="width:100%;justify-content:center;padding:9px">Sign in</button>
  </div>
</form>{style.SKRYPT_UI}</body></html>"""


def wypisano(nazwa: str, blad: bool = False) -> str:
    tresc = ('<h2>Link is not valid</h2><div class="tresc"><p>This unsubscribe link '
             'is malformed or has expired. Nothing was changed.</p></div>' if blad else
             f'<h2>Unsubscribed</h2><div class="tresc"><p>You will no longer receive '
             f'e-mail from <b>{e(nazwa)}</b>. Other services are unaffected — this '
             f'link only covers the one that sent it.</p></div>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><meta name="color-scheme" content="light dark">
<title>Unsubscribe</title><style>{style.STYL}</style></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh">
<div class="karta" style="max-width:420px;width:100%;margin:0">{tresc}</div>
{style.SKRYPT_UI}</body></html>"""


# --------------------------------------------------------------------------- #
#  sekcje panelu
# --------------------------------------------------------------------------- #

def _wybor_serwisu(serwisy: list[dict], wybrany: int | None) -> str:
    if not serwisy:
        return ('<div class="kom">No services yet. Add the first one below — one '
                'per app, so their mail and contacts never mix.</div>')
    k = []
    for s in serwisy:
        akt = " wybrany" if s["id"] == wybrany else ""
        martwy = "" if s["aktywny"] else '<span class="plak uw">off</span>'
        k.append(
            f'<a class="serwis{akt}" href="/?serwis={s["id"]}">'
            f'<div class="serwis-n">{e(s["nazwa"])} {martwy}</div>'
            f'<div class="serwis-a num">{e(s["nadawca_email"])}</div>'
            f'<div class="serwis-l num">{s["kontaktow"]} contacts · '
            f'{s["wyslanych"]} sent'
            + (f' · <span class="down">{s["przepadlych"]} failed</span>'
               if s["przepadlych"] else "") + '</div></a>')
    return f'<div class="serwisy">{"".join(k)}</div>'


def _ostrzezenie_nadawcy(s: dict) -> str:
    """Microsoft odrzuca list, którego pole From nie należy do zalogowanej
    skrzynki - błędem 550 5.7.60 SendAsDenied, już po przyjęciu połączenia.

    To jest najczęstszy sposób, w jaki taka konfiguracja zawodzi: wszystko
    wygląda poprawnie, klucz działa, list wchodzi do kolejki i dopiero serwer
    pocztowy odmawia. Lepiej powiedzieć to przy polu niż w logu błędów."""
    import wysylka
    if not wysylka.SMTP_USER:
        return ""
    nadawca = (s.get("nadawca_email") or "").strip().lower()
    if nadawca == wysylka.SMTP_USER.strip().lower():
        return ""
    return (f'<div class="tresc" style="border-top:1px solid var(--linia)">'
            f'<p class="uwaga"><b>From differs from the mailbox you authenticate as</b> '
            f'(<code>{e(wysylka.SMTP_USER)}</code>). Microsoft 365 rejects that with '
            f'<code>550 5.7.60 SendAsDenied</code> unless this address is an alias of '
            f'that mailbox, or a shared mailbox the account has SendAs rights on. '
            f'Worth checking before the first send rather than after.</p></div>')


def _karta_serwisu(s: dict, klucz_jawny: str) -> str:
    jawny = ""
    if klucz_jawny:
        jawny = (f'<div class="kom"><b>API key — copy it now.</b><br>'
                 f'<code class="klucz">{e(klucz_jawny)}</code><br>'
                 f'It is stored only as a hash, so this is the one and only time '
                 f'it is shown. Losing it costs nothing — issue a new one.</div>')
    ostatni = (f'issued {_czas(s["klucz_wydany"])} · ends in …{e(s["klucz_koncowka"] or "")}'
               if s["klucz_skrot"] else "no key issued yet")
    return f'''<div class="karta"><h2>{e(s["nazwa"])}<span class="obok">code
      <code>{e(s["kod"])}</code></span></h2>
  {jawny}
  <form method="post" action="/serwis/{s["id"]}/zmien" class="tresc siatka-form">
    <label>Display name<input name="nazwa" value="{e(s["nazwa"])}"></label>
    <label>From address<input name="nadawca_email" value="{e(s["nadawca_email"])}"></label>
    <label>From name<input name="nadawca_nazwa" value="{e(s["nadawca_nazwa"] or "")}"></label>
    <label>Reply-To<input name="odpowiedz_do" value="{e(s["odpowiedz_do"] or "")}"
           placeholder="optional"></label>
    <label class="ptaszek"><input type="checkbox" name="aktywny"
      {"checked" if s["aktywny"] else ""}> Active</label>
    <div class="akcje"><button class="btn">Save</button></div>
  </form>
  {_ostrzezenie_nadawcy(s)}
  <div class="tresc" style="border-top:1px solid var(--linia);display:flex;
       gap:12px;align-items:center;flex-wrap:wrap">
    <span class="uwaga">API key: {e(ostatni)}</span>
    <form method="post" action="/serwis/{s["id"]}/klucz" style="margin-left:auto">
      <button class="btn szary">Issue new key</button></form>
  </div>
</div>'''


def _kontakty(s: dict, lista: list[dict], szukaj: str) -> str:
    wiersze = "".join(
        f'<tr><td class="tyk">{e(x["email"])}</td>'
        f'<td>{e(x["imie"] or "")}</td>'
        f'<td class="uwaga">{e(x["tagi"] or "")}</td>'
        f'<td class="uwaga">{e(x["zrodlo"] or "")}</td>'
        f'<td class="num">{_czas(x["dodano"])}</td>'
        f'<td class="num">{_czas(x["ostatnia_wysylka"])}</td>'
        f'<td><form method="post" action="/serwis/{s["id"]}/kontakt/usun">'
        f'<input type="hidden" name="email" value="{e(x["email"])}">'
        f'<button class="link-zle">remove</button></form></td></tr>'
        for x in lista)
    if not wiersze:
        wiersze = ('<tr><td colspan="7" class="uwaga" style="text-align:center">'
                   'No contacts in this service yet.</td></tr>')
    return f'''<div data-panel="kontakty" class="panel-ukryty">
  <div class="karta"><h2>Add contact<span class="obok">to {e(s["nazwa"])} only</span></h2>
    <form method="post" action="/serwis/{s["id"]}/kontakt" class="tresc siatka-form">
      <label>E-mail<input name="email" type="email" required placeholder="jan@example.com"></label>
      <label>Name<input name="imie" placeholder="optional"></label>
      <label>Tags<input name="tagi" placeholder="comma separated"></label>
      <div class="akcje"><button class="btn">Add</button></div>
    </form>
  </div>
  <div class="karta"><h2>Contacts<span class="obok">{len(lista)} shown</span></h2>
    <form class="tresc" method="get" action="/">
      <input type="hidden" name="serwis" value="{s["id"]}">
      <input name="szukaj" value="{e(szukaj)}" placeholder="Search e-mail, name or tag"
             style="width:260px">
      <button class="btn szary">Search</button>
    </form>
    <div class="przewin"><table><thead><tr><th>E-mail</th><th>Name</th><th>Tags</th>
      <th>Source</th><th>Added</th><th>Last sent</th><th></th></tr></thead>
      <tbody>{wiersze}</tbody></table></div>
  </div>
</div>'''


def _szablony(s: dict, lista: list[dict]) -> str:
    karty = "".join(
        f'''<div class="karta"><h2><code>{e(x["kod"])}</code>
        <span class="obok">changed {_czas(x["zmieniono"])}</span></h2>
      <form method="post" action="/serwis/{s["id"]}/szablon" class="tresc">
        <input type="hidden" name="kod" value="{e(x["kod"])}">
        <label class="pelna">Subject<input name="temat" value="{e(x["temat"])}"></label>
        <label class="pelna">Body<textarea name="tresc" rows="8">{e(x["tresc"])}</textarea></label>
        <div class="akcje"><button class="btn">Save</button></div>
      </form>
      <form method="post" action="/serwis/{s["id"]}/szablon/usun"
            class="tresc" style="border-top:1px solid var(--linia)">
        <input type="hidden" name="kod" value="{e(x["kod"])}">
        <button class="link-zle">Delete template</button>
      </form>
    </div>''' for x in lista)
    return f'''<div data-panel="szablony" class="panel-ukryty">
  <div class="karta"><h2>New template<span class="obok">for {e(s["nazwa"])}</span></h2>
    <form method="post" action="/serwis/{s["id"]}/szablon" class="tresc">
      <label class="pelna">Code<input name="kod" required
        placeholder="signup-confirmation"></label>
      <label class="pelna">Subject<input name="temat" required
        placeholder="Thanks for signing up, {{imie}}"></label>
      <label class="pelna">Body<textarea name="tresc" rows="8" required
        placeholder="Hello {{imie}},&#10;&#10;we received your form..."></textarea></label>
      <div class="akcje"><button class="btn">Create</button></div>
    </form>
    <div class="tresc" style="border-top:1px solid var(--linia)">
      <p class="uwaga">Write placeholders as <code>{{name}}</code>. A placeholder with
      no value supplied at send time is refused rather than left blank — a mail
      reading “Hello ,” goes unnoticed until someone complains.</p>
    </div>
  </div>
  {karty}
</div>'''


def _log(historia: list[dict]) -> str:
    wiersze = "".join(
        f'<tr><td class="num">{x["id"]}</td>'
        f'<td class="num">{_czas(x["przyjeto"])}</td>'
        f'<td class="tyk">{e(x["do_email"])}</td>'
        f'<td>{_skrot(x["temat"])}</td>'
        f'<td>{"<code>" + e(x["szablon"]) + "</code>" if x["szablon"] else ""}</td>'
        f'<td>{_plakietka(x["stan"])}</td>'
        f'<td class="num">{x["prob"]}</td>'
        f'<td class="uwaga">{_skrot(x["ostatni_blad"] or "", 70)}</td>'
        f'<td>{f"""<form method="post" action="/ponow/{x["id"]}">"""
              f"""<button class="link">retry</button></form>"""
              if x["stan"] == "przepadl" else ""}</td></tr>'
        for x in historia)
    if not wiersze:
        wiersze = ('<tr><td colspan="9" class="uwaga" style="text-align:center">'
                   'Nothing sent from this service yet.</td></tr>')
    return f'''<div data-panel="log" class="panel-ukryty">
  <div class="karta"><h2>Send log<span class="obok">newest first</span></h2>
    <div class="przewin"><table><thead><tr><th>#</th><th>Accepted</th><th>To</th>
      <th>Subject</th><th>Template</th><th>Status</th><th>Tries</th><th>Last error</th>
      <th></th></tr></thead><tbody>{wiersze}</tbody></table></div>
    <div class="tresc"><p class="uwaga">A failed message is one that exhausted its
      retries or hit a permanent rejection. Retrying puts it back at the front of
      the queue — worth doing after fixing the cause, not before.</p></div>
  </div>
</div>'''


def _wykluczenia(s: dict, lista: list[dict]) -> str:
    wiersze = "".join(
        f'<tr><td class="tyk">{e(x["email"])}</td>'
        f'<td>{"<span class=\'plak uw\'>this service</span>" if x["serwis_id"]
               else "<span class=\'plak zle\'>all services</span>"}</td>'
        f'<td>{e(x["powod"])}</td><td class="num">{_czas(x["kiedy"])}</td>'
        f'<td><form method="post" action="/wykluczenie/usun">'
        f'<input type="hidden" name="email" value="{e(x["email"])}">'
        f'<input type="hidden" name="serwis_id" value="{x["serwis_id"] or ""}">'
        f'<button class="link">lift</button></form></td></tr>'
        for x in lista)
    if not wiersze:
        wiersze = ('<tr><td colspan="5" class="uwaga" style="text-align:center">'
                   'Nobody is suppressed.</td></tr>')
    return f'''<div data-panel="wykluczenia" class="panel-ukryty">
  <div class="karta"><h2>Suppress an address</h2>
    <form method="post" action="/wykluczenie" class="tresc siatka-form">
      <label>E-mail<input name="email" type="email" required></label>
      <label>Reason<input name="powod" value="manual"></label>
      <label class="ptaszek"><input type="checkbox" name="serwis_id"
        value="{s["id"]}"> This service only</label>
      <div class="akcje"><button class="btn">Suppress</button></div>
    </form>
    <div class="tresc" style="border-top:1px solid var(--linia)">
      <p class="uwaga">Leave the box unticked and the address is blocked everywhere —
      that is what a hard bounce means: the mailbox does not exist, so no service
      should keep writing to it. Tick it and only {e(s["nazwa"])} stops, which is
      what an unsubscribe means.</p>
    </div>
  </div>
  <div class="karta"><h2>Suppressed<span class="obok">{len(lista)} addresses</span></h2>
    <div class="przewin"><table><thead><tr><th>E-mail</th><th>Scope</th><th>Reason</th>
      <th>Since</th><th></th></tr></thead><tbody>{wiersze}</tbody></table></div>
  </div>
  <div class="karta"><h2>Erase a person<span class="obok">right to be forgotten</span></h2>
    <form method="post" action="/zapomnij" class="tresc siatka-form">
      <label>E-mail<input name="email" type="email" required></label>
      <div class="akcje"><button class="btn szary">Erase everywhere</button></div>
    </form>
    <div class="tresc" style="border-top:1px solid var(--linia)">
      <p class="uwaga">Removes the person from every service and wipes the stored body
      of their messages. The suppression entry stays on purpose: without it the same
      address would come back with the next form submission and the erasure would be
      silently undone.</p>
    </div>
  </div>
</div>'''


def _przeglad(s: dict | None, stat: dict, nadawca: str, klucz_jawny: str,
              serwisy_: list[dict], wszystkie: list[dict]) -> str:
    kafle = "".join([
        _kafel("Sent (24 h)", stat["doba"], "up" if stat["doba"] else "mut", ""),
        _kafel("In queue", stat["czeka"], "mut", "waiting for the next run"),
        _kafel("Failed", stat["przepadl"], "down" if stat["przepadl"] else "mut",
               "gave up after retries"),
        _kafel("Sent in total", stat["wyslany"], "mut", "across all services"),
        _kafel("Services", len(serwisy_), "mut", "each with its own key"),
    ])
    ostatnie = "".join(
        f'<tr><td class="num">{_czas(x["przyjeto"])}</td>'
        f'<td><code>{e(x["serwis_kod"])}</code></td>'
        f'<td class="tyk">{e(x["do_email"])}</td>'
        f'<td>{_skrot(x["temat"], 46)}</td>'
        f'<td>{_plakietka(x["stan"])}</td></tr>' for x in wszystkie)
    return f'''<div data-panel="przeglad">
  <div class="karta"><h2>Delivery<span class="obok">{e(nadawca)}</span></h2>
    <div class="kafle">{kafle}</div>
    <div class="tresc" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <span class="uwaga">Messages leave in the background. Nothing is sent inside
        the request that queued it, so a slow mail server never blocks a form.</span>
      <form method="post" action="/przebieg" style="margin-left:auto">
        <button class="btn szary">Run now</button></form>
    </div>
  </div>
  {_karta_serwisu(s, klucz_jawny) if s else ""}
  <div class="karta"><h2>Latest across all services</h2>
    <div class="przewin"><table><thead><tr><th>Accepted</th><th>Service</th><th>To</th>
      <th>Subject</th><th>Status</th></tr></thead><tbody>{ostatnie or
      '<tr><td colspan="5" class="uwaga" style="text-align:center">Nothing yet.</td></tr>'}
    </tbody></table></div>
  </div>
  <div class="karta"><h2>Add a service<span class="obok">one per app</span></h2>
    <form method="post" action="/serwis" class="tresc siatka-form">
      <label>Code<input name="kod" required placeholder="ochrona"></label>
      <label>Display name<input name="nazwa" required placeholder="Ochrona z klasą"></label>
      <label>From address<input name="nadawca_email" type="email" required
        placeholder="biuro@ochronazklasa.pl"></label>
      <label>From name<input name="nadawca_nazwa" placeholder="Ochrona z klasą"></label>
      <div class="akcje"><button class="btn">Create and issue key</button></div>
    </form>
  </div>
</div>'''


DODATKOWY_STYL = """
.serwisy { display: grid; gap: 10px; margin-bottom: 20px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.serwis {
  display: block; padding: 13px 15px; border-radius: 12px; text-decoration: none;
  background: var(--plyta); border: 1px solid var(--linia); color: var(--tekst);
  transition: border-color var(--dotyk) var(--e), background var(--dotyk) var(--e);
}
.serwis:hover { border-color: var(--linia-2); text-decoration: none; }
/* Wybrany serwis dostaje pełny obrys, nie samą zmianę tła: to jest stan,
   od którego zależy znaczenie WSZYSTKIEGO poniżej, więc musi być widoczny
   kątem oka, a nie po porównaniu odcieni. */
.serwis.wybrany { border-color: var(--akcent); box-shadow: inset 0 0 0 1px var(--akcent); }
.serwis-n { font-weight: 600; font-size: 13.5px; }
.serwis-a { font-size: 11.5px; color: var(--tekst-2); margin-top: 3px; }
.serwis-l { font-size: 11px; color: var(--tekst-3); margin-top: 5px; }

.siatka-form { display: grid; gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); align-items: end; }
.siatka-form label, .tresc label { display: block; font-size: 11.5px;
  color: var(--tekst-2); letter-spacing: .01em; }
.siatka-form label.pelna, .tresc label.pelna { grid-column: 1 / -1; }
.tresc label { margin-bottom: 12px; }
.siatka-form input, .tresc input, .tresc textarea, .tresc select {
  display: block; width: 100%; margin-top: 5px; padding: 8px 10px;
  font: inherit; font-size: 13px; color: var(--tekst);
  background: var(--plyta-2); border: 1px solid var(--linia-2); border-radius: 9px;
}
.tresc textarea { resize: vertical; font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 12.5px; line-height: 1.55; }
.siatka-form input:focus, .tresc input:focus, .tresc textarea:focus {
  outline: 0; border-color: var(--dane);
  box-shadow: 0 0 0 3px color-mix(in oklab, var(--dane) 20%, transparent); }
.ptaszek { grid-column: 1 / -1; display: flex; align-items: center; gap: 8px;
  padding: 2px 0; }
.ptaszek input { width: auto; margin: 0; flex: none; }
.akcje { display: flex; justify-content: flex-end; align-items: end; }

.btn.szary { background: var(--plyta-2); color: var(--tekst); border: 1px solid var(--linia-2); }
.btn.szary:hover { background: var(--akcent-tlo); }
.link, .link-zle { background: 0; border: 0; cursor: pointer; font: inherit;
  font-size: 12px; padding: 0; text-decoration: underline; }
.link { color: var(--dane); }
.link-zle { color: var(--spadek); }

.klucz { display: inline-block; margin: 7px 0; padding: 8px 11px; border-radius: 8px;
  background: var(--plyta-2); border: 1px solid var(--linia-2);
  font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12.5px;
  user-select: all; word-break: break-all; }
code { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px;
  background: var(--akcent-tlo); padding: 1px 5px; border-radius: 5px; }

table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 9px 14px; font-size: 10.5px; font-weight: 600;
  letter-spacing: .06em; text-transform: uppercase; color: var(--tekst-3);
  border-bottom: 1px solid var(--linia); white-space: nowrap; }
td { padding: 8px 14px; border-bottom: 1px solid var(--linia); font-size: 12.8px;
  white-space: nowrap; }
tbody tr:hover td { background: var(--plyta-2); }
.tyk { font-weight: 500; }
.przewin { overflow-x: auto; }
.plak { display: inline-block; font-size: 10px; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; padding: 2px 7px; border-radius: 5px; }
.plak.ok { background: var(--wzrost-tlo); color: var(--wzrost); }
.plak.zle { background: var(--spadek-tlo); color: var(--spadek); }
.plak.uw { background: var(--uwaga-tlo); color: var(--uwaga); }
.panel-ukryty { display: none; }
"""


def panel(serwisy: list[dict], wybrany: int | None, kontakty: list[dict],
          szablony_: list[dict], historia: list[dict], wykluczenia: list[dict],
          stat: dict, nadawca: str, komunikat: str = "", blad: bool = False,
          klucz_jawny: str = "", szukaj: str = "",
          historia_wszystkich: list[dict] | None = None) -> str:
    s = next((x for x in serwisy if x["id"] == wybrany), None)

    tresc = _przeglad(s, stat, nadawca, klucz_jawny, serwisy,
                      historia_wszystkich if historia_wszystkich is not None else historia)
    if s:
        tresc += (_kontakty(s, kontakty, szukaj) + _szablony(s, szablony_)
                  + _log(historia) + _wykluczenia(s, wykluczenia))

    nav = "".join(
        f'<button data-cel="{k}" aria-selected="{"true" if i == 0 else "false"}">'
        f'{style.ikona(k)}<span>{e(n)}</span></button>'
        for i, (k, n) in enumerate(ZAKLADKI))

    ostrzezenie = ""
    if "nieskonfigurowany" in nadawca:
        ostrzezenie = ('<div class="kom zle"><b>No sender configured.</b> Messages will '
                       'queue but nothing leaves until SMTP_HOST, SMTP_USER and '
                       'SMTP_PASS are set in <code>/opt/poczta/.env</code>.</div>')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><meta name="color-scheme" content="light dark">
<title>Mail service</title><style>{style.STYL}\n{DODATKOWY_STYL}</style></head><body>
<div class="szkielet">
<aside class="bok">
  <div class="marka"><i>M</i><div><b>Mail</b><small>{len(serwisy)} services</small></div></div>
  <nav class="nawig zakladki">{nav}</nav>
  <div style="margin-top:22px;display:flex;flex-direction:column;gap:8px;padding:0 4px">
    <form method="post" action="/przebieg">
      <button class="btn" style="width:100%;justify-content:center">Send queue now</button>
    </form>
    <a class="mini" href="/wyloguj" style="text-align:center;padding:6px">Sign out</a>
  </div>
</aside>
<main class="tresc-gl">
  <div class="gora-str">
    <div><h1>{e(s["nazwa"]) if s else "Mail service"}</h1>
      <div class="pod">{e(nadawca)}</div></div>
    <div class="narzedzia">
      <button class="motyw" aria-label="Switch theme" title="Switch between light and dark">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
             stroke-linecap="round"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>
      </button>
    </div>
  </div>
  {ostrzezenie}
  {f'<div class="kom {"zle" if blad else ""}">{e(komunikat)}</div>' if komunikat else ''}
  {_wybor_serwisu(serwisy, wybrany)}
  {tresc}
</main>
</div>
<script>
(function(){{
  // Zakładki. Wybrany serwis musi przetrwać przełączenie, więc jedzie
  // w adresie, a zakładka w pamięci przeglądarki - odwrotnie byłoby gorzej:
  // wracając do panelu chcesz zobaczyć swój serwis, nie ostatnią zakładkę
  // cudzego.
  var przyciski = document.querySelectorAll('.zakladki button');
  function pokaz(cel) {{
    przyciski.forEach(function(b) {{
      b.setAttribute('aria-selected', String(b.dataset.cel === cel));
    }});
    document.querySelectorAll('[data-panel]').forEach(function(p) {{
      p.classList.toggle('panel-ukryty', p.dataset.panel !== cel);
    }});
  }}
  przyciski.forEach(function(b) {{
    b.onclick = function() {{
      pokaz(b.dataset.cel);
      try {{ localStorage.setItem('zakladka-poczta', b.dataset.cel); }} catch (e) {{}}
    }};
  }});
  try {{
    var z = localStorage.getItem('zakladka-poczta');
    if (z && document.querySelector('[data-panel="' + z + '"]')) pokaz(z);
  }} catch (e) {{}}
}})();
</script>
{style.SKRYPT_UI}
</body></html>"""
