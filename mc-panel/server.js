import express from "express"
import multer from "multer"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
import {
    readFileSync,
    writeFileSync,
    existsSync,
    createWriteStream,
} from "node:fs"
import { readdir, mkdir, rm, rename, cp } from "node:fs/promises"
import { Readable } from "node:stream"
import { pipeline } from "node:stream/promises"
import path from "node:path"
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
    // wolumen serwera zamontowany bezpośrednio w panelu - stąd import i lista światów
    dataDir: process.env.MC_DATA_DIR ?? "/data",
}

const KATALOG_UPLOADU = path.join(config.dataDir, ".uploads")

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

const nazwaSwiata = () => czytajEnv().LEVEL || "world"

// --- docker ---

const docker = async (...args) => {
    const { stdout } = await wykonaj("docker", args, { maxBuffer: 8 * 1024 * 1024 })
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

const startSerwera = () => docker("compose", "--project-directory", config.katalogStacka, "up", "-d")
const stopSerwera = () => docker("stop", config.kontener)

const gracze = async () => {
    try {
        const odp = await rcon(config.rconHost, config.rconPort, process.env.RCON_PASSWORD ?? "", "list")
        return odp.replace(/§./g, "").trim()
    } catch (e) {
        return `RCON niedostępny (${String(e.message ?? e)})`
    }
}

// --- światy (czytane wprost z wolumenu) ---

/** Czy folder wygląda na świat Minecrafta (ma level.dat). */
const jestSwiatem = (dir) => existsSync(path.join(dir, "level.dat"))

const swiaty = async () => {
    if (!existsSync(config.dataDir)) return []
    const wpisy = await readdir(config.dataDir, { withFileTypes: true })
    const wynik = []
    for (const w of wpisy) {
        if (!w.isDirectory() || w.name.startsWith(".")) continue
        // pomijamy foldery wymiarów Bukkit/Paper - pokazujemy tylko główny świat
        if (/_(nether|the_end)$/.test(w.name)) continue
        const pelny = path.join(config.dataDir, w.name)
        if (!jestSwiatem(pelny)) continue
        let rozmiar = "?"
        try {
            const { stdout } = await wykonaj("du", ["-sh", pelny], { maxBuffer: 1 << 20 })
            rozmiar = stdout.split("\t")[0].trim()
        } catch {
            /* rozmiar nieistotny, gdy się nie uda */
        }
        wynik.push({ nazwa: w.name, rozmiar, aktywny: w.name === nazwaSwiata() })
    }
    return wynik.sort((a, b) => Number(b.aktywny) - Number(a.aktywny) || a.nazwa.localeCompare(b.nazwa))
}

const bezpiecznaNazwa = (n) => /^[A-Za-z0-9_.-]+$/.test(n) && n !== "." && n !== ".."

// --- import świata ---

/** Zwraca wszystkie foldery zawierające level.dat (do głębokości 6). */
const znajdzSwiaty = async (root) => {
    const wynik = []
    const walk = async (dir, glebokosc) => {
        if (glebokosc > 6) return
        let wpisy
        try {
            wpisy = await readdir(dir, { withFileTypes: true })
        } catch {
            return
        }
        if (wpisy.some((w) => w.isFile() && w.name === "level.dat")) wynik.push(dir)
        for (const w of wpisy) {
            if (w.isDirectory()) await walk(path.join(dir, w.name), glebokosc + 1)
        }
    }
    await walk(root, 0)
    return wynik
}

const przenoscLubScal = async (zrodlo, cel) => {
    if (!existsSync(zrodlo)) return
    if (existsSync(cel)) {
        await cp(zrodlo, cel, { recursive: true, force: true })
    } else {
        await rename(zrodlo, cel).catch(async () => {
            // rename bywa niemożliwy między urządzeniami - wtedy kopiujemy
            await cp(zrodlo, cel, { recursive: true, force: true })
        })
    }
}

/**
 * Rozpakowuje archiwum świata, wykrywa główny świat (i ewentualne wymiary
 * w formacie Paper/Aternos), robi kopię obecnego świata i podmienia go.
 * Serwer musi być zdolny do zatrzymania - robimy to tutaj.
 */
const importujSwiat = async (zipPath, nowaWersja) => {
    const tmp = path.join(config.dataDir, ".import-" + Date.now())
    await mkdir(tmp, { recursive: true })

    try {
        await wykonaj("unzip", ["-oq", zipPath, "-d", tmp], { maxBuffer: 8 << 20 }).catch(() => {
            throw new Error("To nie jest poprawne archiwum .zip")
        })

        const swiatyWArchiwum = await znajdzSwiaty(tmp)
        if (swiatyWArchiwum.length === 0) {
            throw new Error("W archiwum nie znaleziono świata (brak pliku level.dat)")
        }
        // główny świat: folder z level.dat, którego nazwa nie kończy się na wymiar
        const overworld =
            swiatyWArchiwum
                .filter((d) => !/_(nether|the_end)$/.test(path.basename(d)))
                .sort((a, b) => a.split(path.sep).length - b.split(path.sep).length)[0] ?? swiatyWArchiwum[0]

        const level = nazwaSwiata()
        const stempel = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19)

        await stopSerwera()

        // kopia obecnego świata (do skasowania z panelu, gdy import się powiedzie)
        for (const suf of ["", "_nether", "_the_end"]) {
            const p = path.join(config.dataDir, `${level}${suf}`)
            if (existsSync(p)) await rename(p, path.join(config.dataDir, `${level}.stary-${stempel}${suf}`))
        }

        // główny świat
        await rename(overworld, path.join(config.dataDir, level))
        await rm(path.join(config.dataDir, level, "session.lock"), { force: true })

        // wymiary z formatu Paper/Spigot scalamy do układu vanilla (DIM-1 / DIM1)
        const rodzic = path.dirname(overworld)
        const baza = path.basename(overworld)
        const netherDim = path.join(rodzic, `${baza}_nether`, "DIM-1")
        const endDim = path.join(rodzic, `${baza}_the_end`, "DIM1")
        await przenoscLubScal(netherDim, path.join(config.dataDir, level, "DIM-1"))
        await przenoscLubScal(endDim, path.join(config.dataDir, level, "DIM1"))

        if (nowaWersja) zapiszEnv({ VERSION: nowaWersja })

        await startSerwera()

        return { level, backup: `${level}.stary-${stempel}` }
    } finally {
        await rm(tmp, { recursive: true, force: true }).catch(() => {})
        await rm(zipPath, { force: true }).catch(() => {})
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

const upload = multer({
    dest: KATALOG_UPLOADU,
    limits: { fileSize: 6 * 1024 * 1024 * 1024 }, // 6 GB
})

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
        await startSerwera()
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

// --- import świata: z pliku i z linku ---

app.post("/import", wymagajLogowania, upload.single("swiat"), async (req, res) => {
    if (!req.file) return res.redirect("/?blad=" + encodeURIComponent("Nie wybrano pliku"))
    try {
        const wersja = String(req.body?.wersja ?? "").trim() || null
        const { backup } = await importujSwiat(req.file.path, wersja)
        res.redirect("/?ok=" + encodeURIComponent(`Świat zaimportowany. Poprzedni zapisano jako „${backup}" (możesz go skasować niżej).`))
    } catch (e) {
        await startSerwera().catch(() => {})
        res.redirect("/?blad=" + encodeURIComponent(String(e.message ?? e).slice(0, 220)))
    }
})

app.post("/import-url", wymagajLogowania, async (req, res) => {
    const url = String(req.body?.url ?? "").trim()
    if (!/^https?:\/\//i.test(url)) return res.redirect("/?blad=" + encodeURIComponent("Podaj poprawny link http(s) do pliku .zip"))
    const dest = path.join(KATALOG_UPLOADU, `url-${Date.now()}.zip`)
    try {
        await mkdir(KATALOG_UPLOADU, { recursive: true })
        const odp = await fetch(url)
        if (!odp.ok || !odp.body) throw new Error(`Nie udało się pobrać pliku (HTTP ${odp.status})`)
        await pipeline(Readable.fromWeb(odp.body), createWriteStream(dest))

        const wersja = String(req.body?.wersja ?? "").trim() || null
        const { backup } = await importujSwiat(dest, wersja)
        res.redirect("/?ok=" + encodeURIComponent(`Świat pobrany i zaimportowany. Poprzedni zapisano jako „${backup}".`))
    } catch (e) {
        await rm(dest, { force: true }).catch(() => {})
        await startSerwera().catch(() => {})
        res.redirect("/?blad=" + encodeURIComponent(String(e.message ?? e).slice(0, 220)))
    }
})

/** Kasowanie świata (również kopii .stary-*). Serwer zatrzymywany na czas operacji. */
app.post("/swiaty/usun", wymagajLogowania, async (req, res) => {
    const nazwa = String(req.body?.nazwa ?? "").trim()
    if (!bezpiecznaNazwa(nazwa)) return res.redirect("/?blad=" + encodeURIComponent("Niepoprawna nazwa świata"))
    try {
        await stopSerwera()
        for (const suf of ["", "_nether", "_the_end"]) {
            await rm(path.join(config.dataDir, `${nazwa}${suf}`), { recursive: true, force: true })
        }
        await startSerwera()
        res.redirect("/?ok=" + encodeURIComponent(`Świat „${nazwa}" skasowany`))
    } catch (e) {
        await startSerwera().catch(() => {})
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
        res.type("text/plain").send(out.replace(/\[[0-9;]*m/g, "").replace(/>\.*\[K/g, ""))
    } catch (e) {
        res.status(502).type("text/plain").send(String(e.message ?? e))
    }
})

app.get("/api/stan", wymagajLogowania, async (_req, res) => {
    const [stan, lista] = await Promise.all([stanSerwera(), gracze()])
    res.json({ ...stan, gracze: lista })
})

const server = app.listen(config.port, () => console.info(`mc-panel na :${config.port} (kontener ${config.kontener})`))
// import dużych światów może trwać - luzujemy limity czasu żądania
server.requestTimeout = 30 * 60 * 1000
server.headersTimeout = 60 * 1000
