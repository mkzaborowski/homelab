import { POLA } from "./pola.js"

const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c])

const STYL = `
*{box-sizing:border-box}
body{margin:0;background:#0f1620;color:#e6edf6;font:15px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif}
a{color:#7dd3a0;text-decoration:none}a:hover{text-decoration:underline}
.top{background:#16202c;border-bottom:1px solid #223041;padding:14px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.marka{font-weight:700}.tag{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#7b8ea6}
.top nav{margin-left:auto;display:flex;gap:16px}
.wrap{max-width:1120px;margin:0 auto;padding:22px}
.panel{background:#16202c;border:1px solid #223041;border-radius:14px;overflow:hidden;margin-bottom:18px}
.panel h2{margin:0;padding:14px 18px;font-size:14px;border-bottom:1px solid #223041;color:#a7bdd6}
.tresc{padding:18px}
.rzad{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
.kafel{background:#111a24;border:1px solid #223041;border-radius:12px;padding:14px 16px}
.kafel .et{font-size:11px;text-transform:uppercase;letter-spacing:.13em;color:#7b8ea6}
.kafel .wart{font-size:20px;font-weight:700;margin-top:5px}
.zielony{color:#6ee7a0}.czerwony{color:#f79c9c}.zolty{color:#fbd38d}
label{display:block;font-size:12px;color:#a7bdd6;margin-bottom:6px}
input,select{width:100%;font:inherit;padding:9px 11px;border:1px solid #2b3a4d;border-radius:9px;background:#0f1620;color:#e6edf6}
input[type=file]{padding:8px;background:#111a24}
input:focus,select:focus{outline:0;border-color:#3f7d5c;box-shadow:0 0 0 3px rgba(110,231,160,.14)}
.uwaga{font-size:11.5px;color:#7b8ea6;margin-top:5px}
.siatka{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.btn{display:inline-flex;align-items:center;gap:7px;background:#2f6f4f;color:#eafff2;border:0;border-radius:9px;padding:10px 18px;font:inherit;font-weight:600;cursor:pointer}
.btn:hover{background:#3a8a62;text-decoration:none}
.btn:disabled{opacity:.6;cursor:progress}
.btn.szary{background:#243244;color:#cfe0f2}.btn.szary:hover{background:#2e4058}
.btn.czerw{background:#7f3535;color:#ffe9e9}.btn.czerw:hover{background:#9a4242}
.plakietka{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;background:#123524;color:#8ff0b8;padding:2px 7px;border-radius:6px}
pre{margin:0;padding:14px 16px;background:#0b1219;color:#c7d6e6;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;max-height:340px;overflow:auto;white-space:pre-wrap}
.konsola{display:flex;gap:8px;padding:12px 16px;border-top:1px solid #223041}
.konsola input{font-family:ui-monospace,Menlo,monospace}
.kom{padding:11px 16px;border-radius:10px;margin-bottom:16px;font-size:14px;font-weight:500}
.kom.ok{background:#123524;color:#8ff0b8}.kom.zle{background:#3a1a1a;color:#ffb4b4}
.kroki{margin:0;padding-left:18px;color:#c7d6e6;font-size:13px;line-height:1.7}
.kroki code{background:#0b1219;padding:1px 6px;border-radius:5px;font-size:12px}
.sep{height:1px;background:#223041;margin:18px 0}
`

export const stronaLogowania = (blad) => `<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Panel Minecraft — logowanie</title><style>${STYL}</style></head>
<body style="display:flex;align-items:center;justify-content:center;min-height:100vh">
<form method="post" action="/login" class="panel" style="padding:28px;max-width:360px;width:100%;margin:0">
    <div class="tag">marcelizaborowski.com</div>
    <h1 style="margin:8px 0 18px;font-size:21px">Panel Minecraft</h1>
    ${blad ? `<div class="kom zle">${esc(blad)}</div>` : ""}
    <input type="password" name="haslo" placeholder="Hasło" autofocus required style="margin-bottom:12px">
    <button class="btn" style="width:100%;justify-content:center">Zaloguj</button>
</form></body></html>`

export const strona = ({ stan, gracze, ustawienia, adres, komunikat, blad, swiaty = [] }) => {
    const pola = POLA.map((p) => {
        const wartosc = ustawienia[p.klucz] ?? ""
        const kontrolka =
            p.typ === "select"
                ? `<select name="${p.klucz}">${p.opcje
                      .map((o) => `<option${o === wartosc ? " selected" : ""}>${esc(o)}</option>`)
                      .join("")}</select>`
                : `<input name="${p.klucz}" type="${p.typ === "number" ? "number" : "text"}" value="${esc(wartosc)}">`
        return `<div><label>${esc(p.etykieta)}</label>${kontrolka}${p.uwaga ? `<div class="uwaga">${esc(p.uwaga)}</div>` : ""}</div>`
    }).join("")

    const wersja = esc(ustawienia.VERSION ?? "")

    return `<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Panel Minecraft</title><style>${STYL}</style></head><body>
<header class="top">
    <span class="marka">Minecraft</span><span class="tag">${esc(adres)}</span>
    <nav><a href="/wyloguj">Wyloguj</a></nav>
</header>
<div class="wrap">
    ${komunikat ? `<div class="kom ${blad ? "zle" : "ok"}">${esc(komunikat)}</div>` : ""}

    <div class="panel"><h2>Stan serwera</h2><div class="tresc">
        <div class="rzad">
            <div class="kafel"><div class="et">Status</div>
                <div class="wart ${stan.dziala ? "zielony" : "czerwony"}">${stan.dziala ? "Działa" : esc(stan.status)}</div></div>
            <div class="kafel"><div class="et">Kondycja</div>
                <div class="wart ${stan.zdrowie === "healthy" ? "zielony" : "zolty"}">${esc(stan.zdrowie || "-")}</div></div>
            <div class="kafel"><div class="et">Wersja</div><div class="wart">${esc(ustawienia.VERSION ?? "?")}</div></div>
            <div class="kafel"><div class="et">Adres dla graczy</div><div class="wart" style="font-size:15px">${esc(adres)}</div></div>
        </div>
        <div class="kafel" style="margin-top:14px"><div class="et">Gracze</div>
            <div style="margin-top:6px">${esc(gracze)}</div></div>
        <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">
            <form method="post" action="/moc/start"><button class="btn">Start</button></form>
            <form method="post" action="/moc/restart"><button class="btn szary">Restart</button></form>
            <form method="post" action="/moc/stop"><button class="btn czerw">Stop</button></form>
        </div>
    </div></div>

    <div class="panel"><h2>Konsola serwera</h2>
        <pre id="wyjscie">Wpisz komendę, np. <b>list</b>, <b>say Cześć</b>, <b>time set day</b>, <b>weather clear</b>, <b>op NICK</b>.</pre>
        <form class="konsola" id="formKonsola">
            <input id="komenda" placeholder="komenda bez ukośnika, np. list" autocomplete="off" style="flex:1">
            <button class="btn">Wyślij</button>
        </form>
    </div>

    <div class="panel"><h2>Import świata (np. z Aternos)</h2><div class="tresc">
        <p style="margin:0 0 10px;color:#c7d6e6;font-size:13.5px">Jak pobrać świat z Aternos:</p>
        <ol class="kroki" style="margin-bottom:16px">
            <li>Zaloguj się na <b>aternos.org</b> i wejdź na swój serwer.</li>
            <li>Menu <b>Pliki</b> (Files) → zaznacz folder świata (zwykle <code>world</code>).</li>
            <li>Kliknij <b>Pobierz</b> — dostaniesz plik <code>.zip</code>.</li>
            <li>Wgraj go poniżej albo wklej link do pobrania (dla dużych światów).</li>
        </ol>

        <form method="post" action="/import" enctype="multipart/form-data" onsubmit="return zablokuj(this)">
            <div class="siatka">
                <div><label>Plik świata (.zip)</label><input type="file" name="swiat" accept=".zip" required></div>
                <div><label>Wersja serwera po imporcie</label><input type="text" name="wersja" value="${wersja}" placeholder="np. 26.2">
                    <div class="uwaga">Zostaw bez zmian, jeśli nie wiesz. Starszy świat zostanie automatycznie zaktualizowany.</div></div>
            </div>
            <div style="margin-top:14px"><button class="btn">Wgraj i zaimportuj</button>
                <span class="uwaga" style="margin-left:10px">Serwer zostanie na chwilę zatrzymany. Obecny świat zachowamy jako kopię.</span></div>
        </form>

        <div class="sep"></div>

        <form method="post" action="/import-url" onsubmit="return zablokuj(this)">
            <label>…albo import z linku (Google Drive, Dropbox, WeTransfer, transfer.sh — link bezpośredni do .zip)</label>
            <div style="display:flex;gap:10px;flex-wrap:wrap">
                <input type="url" name="url" placeholder="https://…/world.zip" required style="flex:1;min-width:240px">
                <input type="text" name="wersja" value="${wersja}" placeholder="wersja" style="width:120px">
                <button class="btn szary">Pobierz i zaimportuj</button>
            </div>
            <div class="uwaga">Dla plików większych niż ~100 MB: domena <b>${esc(adres)}</b> musi być w trybie „DNS only" (szara chmurka w Cloudflare) albo skorzystaj z importu z linku.</div>
        </form>
    </div></div>

    <div class="panel"><h2>Światy</h2><div class="tresc">
        ${swiaty.length === 0
            ? `<div class="uwaga">Nie znaleziono światów.</div>`
            : swiaty.map((w) => `
                <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #223041">
                    <div style="flex:1">
                        <div style="font-weight:600">${esc(w.nazwa)} ${w.aktywny ? '<span class="plakietka">aktywny</span>' : ""}</div>
                        <div class="uwaga" style="margin:0">rozmiar: ${esc(w.rozmiar)}</div>
                    </div>
                    ${w.aktywny
                        ? '<span class="uwaga">świat w użyciu</span>'
                        : `<form method="post" action="/swiaty/usun"
                              onsubmit="return confirm('Skasować świat &quot;${esc(w.nazwa)}&quot;? Tej operacji nie da się cofnąć.')">
                            <input type="hidden" name="nazwa" value="${esc(w.nazwa)}">
                            <button class="btn czerw">Skasuj</button>
                        </form>`}
                </div>`).join("")}
        <div class="uwaga" style="margin-top:14px">
            Po udanym imporcie poprzedni świat zostaje jako kopia <code>${esc(nazwaLevel(ustawienia))}.stary-…</code> —
            możesz go stąd skasować, gdy upewnisz się, że wszystko działa.
        </div>
    </div></div>

    <div class="panel"><h2>Ustawienia serwera</h2><div class="tresc">
        <form method="post" action="/ustawienia">
            <div class="siatka">${pola}</div>
            <div style="margin-top:18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
                <button class="btn">Zapisz i zastosuj</button>
                <span class="uwaga">Zapis restartuje serwer. Zmiana seeda działa dopiero po skasowaniu istniejącego świata.</span>
            </div>
        </form>
    </div></div>

    <div class="panel"><h2>Logi serwera</h2><pre id="logi">wczytywanie…</pre></div>
</div>

<script>
function zablokuj(form) {
    const b = form.querySelector("button");
    b.disabled = true;
    b.textContent = "Import w toku… (może potrwać kilka minut)";
    return true;
}

const wyjscie = document.getElementById("wyjscie");
document.getElementById("formKonsola").addEventListener("submit", async (e) => {
    e.preventDefault();
    const pole = document.getElementById("komenda");
    const komenda = pole.value.trim();
    if (!komenda) return;
    wyjscie.textContent += "\\n> " + komenda;
    pole.value = "";
    try {
        const r = await fetch("/api/konsola", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ komenda }),
        });
        const d = await r.json();
        wyjscie.textContent += "\\n" + (d.odpowiedz ?? ("BŁĄD: " + d.blad));
    } catch (err) {
        wyjscie.textContent += "\\nBŁĄD: " + err;
    }
    wyjscie.scrollTop = wyjscie.scrollHeight;
});

const odswiezLogi = async () => {
    try {
        const r = await fetch("/api/logi");
        const el = document.getElementById("logi");
        const naDole = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
        el.textContent = await r.text();
        if (naDole) el.scrollTop = el.scrollHeight;
    } catch {}
};
odswiezLogi();
setInterval(odswiezLogi, 10000);
</script>
</body></html>`
}

const nazwaLevel = (ustawienia) => ustawienia.LEVEL || "world"
