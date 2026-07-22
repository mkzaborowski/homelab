import express from "express"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
import { readFileSync, writeFileSync, existsSync } from "node:fs"
import { createHmac, timingSafeEqual } from "node:crypto"
import { rcon } from "./rcon.js"
import { strona, stronaLogowania } from "./widok.js"
import { POLA } from "./pola.js"

const wykonaj = promisify(execFile)

const config = {
    port: Number(process.env.PORT ?? 8080),
    haslo: process.env.PANEL_PASSWORD ?? "",
    envServera: process.env.MC_ENV_FILE ?? "/mc/.env",
    kontener: process.env.MC_CONTAINER ?? "minecraft-minecraft-1",
    katalogStacka: process.env.MC_STACK_DIR ?? "/mc",
    rconHost: process.env.RCON_HOST ?? "minecraft",
    rconPort: Number(process.env.RCON_PORT ?? 25575),
    adresSerwera: process.env.MC_ADDRESS ?? "mc.marcelizaborowski.com",
    wolumenDanych: process.env.MC_DATA_VOLUME ?? "minecraft_mc_data",
}

// --- ustawienia serwera (plik .env stacka minecraft) ---

const czytajEnv = () => {
    if (!existsSync(config.envServera)) return {}
    const wynik = {}
    for (const linia of readFileSync(config.envServera, "utf8").split("\n")) {
        const m = linia.match(/^([A-Z0-9_]+)=(.*)$/)
        if (m) wynik[m[1]] = m[2]
    }
    return wynik
}

const zapiszEnv = (zmiany) => {
    const linie = existsSync(config.envServera) ? readFileSync(config.envServera, "utf8").split("\n") : []
    const obsluzone = new Set()
    const nowe = linie.map((linia) => {
        const m = linia.match(/^([A-Z0-9_]+)=/)
        if (m && Object.prototype.hasOwnProperty.call(zmiany, m[1])) {
            obsluzone.add(m[1])
            return `${m[1]}=${zmiany[m[1]]}`
        }
        return linia
    })
    for (const [k, v] of Object.entries(zmiany)) if (!obsluzone.has(k)) nowe.push(`${k}=${v}`)
    writeFileSync(config.envServera, nowe.join("\n"))
}

// --- docker ---

const docker = async (...args) => {
    const { stdout } = await wykonaj("docker", args, { maxBuffer: 4 * 1024 * 1024 })
    return stdout
}

const stanSerwera = async () => {
    try {
        const out = await docker("inspect", config.kontener, "--format", "{{.State.Status}}|{{.State.Health.Status}}|{{.State.StartedAt}}")
        const [status, zdrowie, start] = out.trim().split("|")
        return { dziala: status === "running", status, zdrowie, start }
    } catch {
        return { dziala: false, status: "brak kontenera", zdrowie: "-", start: "" }
    }
}

const gracze = async () => {
    try {
        const odp = await rcon(config.rconHost, config.rconPort, process.env.RCON_PASSWORD ?? "", "list")
        return odp.replace(/§./g, "").trim()
    } catch (e) {
        return `RCON niedostępny (${String(e.message ?? e)})`
    }
}

// --- logowanie ---

const CIASTKO = "mcpanel"
const WAZNOSC = 12 * 60 * 60 * 1000
const podpisz = (w) => createHmac("sha256", config.haslo).update(String(w)).digest("hex")
const rowne = (a, b) => {
    const x = Buffer.from(a)
    const y = Buffer.from(b)
    return x.length === y.length && timingSafeEqual(x, y)
}
const sesjaOk = (v) => {
    const [w, p] = String(v).split(".")
    return Number(w) > Date.now() && rowne(podpisz(Number(w)), String(p ?? ""))
}
const ciastko = (req) => {
    for (const c of (req.headers.cookie ?? "").split(";")) {
        const [k, ...v] = c.trim().split("=")
        if (k === CIASTKO) return decodeURIComponent(v.join("="))
    }
    return ""
}
const wymagajLogowania = (req, res, next) => {
    if (!config.haslo) return res.status(503).send("Ustaw PANEL_PASSWORD.")
    if (sesjaOk(ciastko(req))) return next()
    res.status(401).type("html").send(stronaLogowania())
}

// --- aplikacja ---

const app = express()
app.disable("x-powered-by")
app.set("trust proxy", 1)
app.use(express.urlencoded({ extended: false, limit: "64kb" }))
app.use(express.json({ limit: "64kb" }))

app.get("/healthz", (_req, res) => res.json({ ok: true }))

app.get("/login", (_req, res) => res.type("html").send(stronaLogowania()))
app.post("/login", (req, res) => {
    if (!config.haslo || !rowne(config.haslo, String(req.body?.haslo ?? ""))) {
        return res.status(401).type("html").send(stronaLogowania("Nieprawidłowe hasło"))
    }
    const w = Date.now() + WAZNOSC
    res.setHeader(
        "Set-Cookie",
        `${CIASTKO}=${encodeURIComponent(`${w}.${podpisz(w)}`)}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${WAZNOSC / 1000}`
    )
    res.redirect("/")
})
app.get("/wyloguj", (_req, res) => {
    res.setHeader("Set-Cookie", `${CIASTKO}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`)
    res.redirect("/login")
})

app.get("/", wymagajLogowania, async (req, res) => {
    const [stan, lista, listaSwiatow] = await Promise.all([stanSerwera(), gracze(), swiaty()])
    res.type("html").send(
        strona({
            stan,
            gracze: lista,
            swiaty: listaSwiatow,
            ustawienia: czytajEnv(),
            adres: config.adresSerwera,
            komunikat: req.query.ok ? String(req.query.ok) : req.query.blad ? String(req.query.blad) : "",
            blad: !!req.query.blad,
        })
    )
})

/** Zapis ustawień + restart, żeby weszły w życie. */
app.post("/ustawienia", wymagajLogowania, async (req, res) => {
    try {
        const zmiany = {}
        for (const pole of POLA) {
            const v = req.body[pole.klucz]
            if (v !== undefined) zmiany[pole.klucz] = String(v).replace(/[\r\n]/g, "").slice(0, 200)
        }
        zapiszEnv(zmiany)
        await docker("compose", "--project-directory", config.katalogStacka, "up", "-d")
        res.redirect("/?ok=" + encodeURIComponent("Ustawienia zapisane, serwer wstaje z nową konfiguracją"))
    } catch (e) {
        res.redirect("/?blad=" + encodeURIComponent(String(e.message ?? e).slice(0, 200)))
    }
})

app.post("/moc/:akcja", wymagajLogowania, async (req, res) => {
    const akcje = { start: ["start"], stop: ["stop"], restart: ["restart"] }
    const akcja = akcje[req.params.akcja]
    if (!akcja) return res.redirect("/?blad=Nieznana+akcja")
    try {
        await docker(...akcja, config.kontener)
        res.redirect("/?ok=" + encodeURIComponent(`Wykonano: ${req.params.akcja}`))
    } catch (e) {
        res.redirect("/?blad=" + encodeURIComponent(String(e.message ?? e).slice(0, 200)))
    }
})

/** Konsola: komenda przez RCON. */
app.post("/api/konsola", wymagajLogowania, async (req, res) => {
    const komenda = String(req.body?.komenda ?? "").trim().slice(0, 300)
    if (!komenda) return res.status(400).json({ blad: "Pusta komenda" })
    try {
        const odpowiedz = await rcon(config.rconHost, config.rconPort, process.env.RCON_PASSWORD ?? "", komenda)
        res.json({ odpowiedz: odpowiedz.replace(/§./g, "") || "(serwer nie zwrócił treści)" })
    } catch (e) {
        res.status(502).json({ blad: String(e.message ?? e) })
    }
})

/** Ostatnie linie logów serwera. */
app.get("/api/logi", wymagajLogowania, async (_req, res) => {
    try {
        const out = await docker("logs", "--tail", "120", config.kontener)
        res.type("text/plain").send(out.replace(/\[[0-9;]*m/g, "").replace(/>\.*\[K/g, ""))
    } catch (e) {
        res.status(502).type("text/plain").send(String(e.message ?? e))
    }
})

/** Lista światów na wolumenie serwera (nazwa + rozmiar). */
const swiaty = async () => {
    try {
        const out = await docker(
            "exec", config.kontener, "sh", "-c",
            "for d in /data/*/; do [ -f \"$d/level.dat\" ] && printf '%s|%s\\n' \"$(basename $d)\" \"$(du -sh $d | cut -f1)\"; done"
        )
        return out.trim().split("\n").filter(Boolean).map((l) => {
            const [nazwa, rozmiar] = l.split("|")
            return { nazwa, rozmiar }
        })
    } catch {
        return []
    }
}

app.get("/api/swiaty", wymagajLogowania, async (_req, res) => res.json(await swiaty()))

/**
 * Kasowanie świata. Serwer musi być zatrzymany, inaczej odtworzy pliki z
 * pamięci. Po skasowaniu wstaje z nowym światem (i aktualnym seedem).
 */
app.post("/swiaty/usun", wymagajLogowania, async (req, res) => {
    const nazwa = String(req.body?.nazwa ?? "").trim()
    // tylko nazwy katalogów - żadnych ścieżek ani znaków specjalnych
    if (!/^[A-Za-z0-9_.-]+$/.test(nazwa) || nazwa === "." || nazwa === "..") {
        return res.redirect("/?blad=" + encodeURIComponent("Niepoprawna nazwa świata"))
    }
    try {
        await docker("stop", config.kontener)
        // kasujemy świat wraz z wymiarami (nether/end tworzą osobne katalogi)
        await docker(
            "run", "--rm", "-v", `${config.wolumenDanych}:/data`, "alpine",
            "sh", "-c", `rm -rf "/data/${nazwa}" "/data/${nazwa}_nether" "/data/${nazwa}_the_end"`
        )
        await docker("start", config.kontener)
        res.redirect("/?ok=" + encodeURIComponent(`Świat „${nazwa}" skasowany, serwer generuje nowy`))
    } catch (e) {
        try { await docker("start", config.kontener) } catch { /* serwer i tak trzeba podnieść */ }
        res.redirect("/?blad=" + encodeURIComponent(String(e.message ?? e).slice(0, 200)))
    }
})

app.get("/api/stan", wymagajLogowania, async (_req, res) => {
    const [stan, lista] = await Promise.all([stanSerwera(), gracze()])
    res.json({ ...stan, gracze: lista })
})

app.listen(config.port, () => console.info(`mc-panel na :${config.port} (kontener ${config.kontener})`))
