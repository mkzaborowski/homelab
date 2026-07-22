/** Pola ustawień serwera pokazywane w panelu (klucze pliku .env stacka minecraft). */
export const POLA = [
    { klucz: "VERSION", etykieta: "Wersja Minecrafta", typ: "text", uwaga: "np. 1.21.4 albo LATEST" },
    { klucz: "TYPE", etykieta: "Silnik", typ: "select", opcje: ["PAPER", "VANILLA", "SPIGOT", "FABRIC"] },
    { klucz: "MEMORY", etykieta: "Pamięć dla serwera", typ: "text", uwaga: "np. 2G (limit kontenera: 3G)" },
    { klucz: "MOTD", etykieta: "Opis na liście serwerów", typ: "text" },
    { klucz: "LEVEL_SEED", etykieta: "Seed świata", typ: "text", uwaga: "zmiana działa dopiero po usunięciu świata" },
    { klucz: "DIFFICULTY", etykieta: "Poziom trudności", typ: "select", opcje: ["peaceful", "easy", "normal", "hard"] },
    { klucz: "MODE", etykieta: "Tryb gry", typ: "select", opcje: ["survival", "creative", "adventure", "spectator"] },
    { klucz: "MAX_PLAYERS", etykieta: "Maks. graczy", typ: "number" },
    { klucz: "VIEW_DISTANCE", etykieta: "Zasięg widzenia (chunki)", typ: "number" },
    { klucz: "SPAWN_PROTECTION", etykieta: "Ochrona spawnu (bloki)", typ: "number" },
    { klucz: "PVP", etykieta: "PvP", typ: "select", opcje: ["true", "false"] },
    { klucz: "ALLOW_NETHER", etykieta: "Nether", typ: "select", opcje: ["true", "false"] },
    { klucz: "ONLINE_MODE", etykieta: "Weryfikacja kont Mojang", typ: "select", opcje: ["true", "false"] },
]
