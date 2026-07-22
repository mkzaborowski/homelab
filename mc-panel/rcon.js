import net from "node:net"

// Minimalna implementacja protokołu RCON (Source RCON) - bez zależności.
const TYP_AUTH = 3
const TYP_KOMENDA = 2

const pakiet = (id, typ, tresc) => {
    const body = Buffer.from(tresc, "utf8")
    const buf = Buffer.alloc(14 + body.length)
    buf.writeInt32LE(10 + body.length, 0)
    buf.writeInt32LE(id, 4)
    buf.writeInt32LE(typ, 8)
    body.copy(buf, 12)
    buf.writeInt16LE(0, 12 + body.length)
    return buf
}

/**
 * Wysyła komendę do serwera Minecraft i zwraca odpowiedź.
 * Otwiera i zamyka połączenie przy każdym wywołaniu - panel wysyła
 * pojedyncze komendy, więc trwałe połączenie nie jest potrzebne.
 */
export const rcon = (host, port, haslo, komenda, timeoutMs = 5000) =>
    new Promise((resolve, reject) => {
        const gniazdo = net.createConnection({ host, port })
        let bufor = Buffer.alloc(0)
        let zalogowany = false

        const koniec = (blad, wynik) => {
            gniazdo.destroy()
            blad ? reject(blad) : resolve(wynik)
        }

        gniazdo.setTimeout(timeoutMs, () => koniec(new Error("RCON: przekroczono czas oczekiwania")))
        gniazdo.on("error", (e) => koniec(e))

        gniazdo.on("connect", () => gniazdo.write(pakiet(1, TYP_AUTH, haslo)))

        gniazdo.on("data", (dane) => {
            bufor = Buffer.concat([bufor, dane])
            while (bufor.length >= 4) {
                const dlugosc = bufor.readInt32LE(0)
                if (bufor.length < 4 + dlugosc) break
                const id = bufor.readInt32LE(4)
                const tresc = bufor.subarray(12, 4 + dlugosc - 2).toString("utf8")
                bufor = bufor.subarray(4 + dlugosc)

                if (!zalogowany) {
                    if (id === -1) return koniec(new Error("RCON: błędne hasło"))
                    zalogowany = true
                    gniazdo.write(pakiet(2, TYP_KOMENDA, komenda))
                } else {
                    return koniec(null, tresc)
                }
            }
        })
    })
