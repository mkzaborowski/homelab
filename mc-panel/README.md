# mc-panel — panel serwera Minecraft

Webowy panel do serwera Minecraft (Paper) działającego w Dockerze na Hetznerze.

- **Adres panelu:** https://mc.marcelizaborowski.com (logowanie hasłem)
- **Adres serwera dla graczy:** `mc.marcelizaborowski.com:25565`
  — **wymaga rekordu DNS „DNS only” (szara chmurka w Cloudflare)**; proxy
  Cloudflare przepuszcza tylko HTTP/HTTPS, więc port gry przez nie nie przejdzie.

## Co potrafi

- stan serwera (działa/nie, kondycja, wersja) i lista graczy przez RCON
- konsola: dowolne komendy serwera (`list`, `say`, `time set day`, `op NICK`…)
- podgląd logów (odświeżany co 10 s)
- edycja ustawień: wersja, silnik (Paper/Vanilla/Spigot/Fabric), pamięć, MOTD,
  seed, trudność, tryb gry, limit graczy, zasięg widzenia, PvP, Nether,
  weryfikacja kont — zapis do `.env` stacka i restart
- start / restart / stop serwera

## Stacki na serwerze

| Katalog | Rola |
|---|---|
| `/opt/minecraft` | serwer gry (itzg/minecraft-server, wolumen `mc_data`, port 25565) |
| `/opt/mc-panel` | ten panel (obraz z GHCR, w sieci `edge`, za wspólnym Caddy) |

Panel montuje `/var/run/docker.sock` (steruje kontenerem serwera) oraz
`/opt/minecraft` (edytuje `.env`). Dostęp do socketu Dockera oznacza pełnię
władzy na hoście — dlatego panel jest za hasłem i nie ma publicznej rejestracji.

## Zmiana wersji / seeda

Wersję zmienia się w panelu i zatwierdza „Zapisz i zastosuj” (restart pobiera
nowy build Papera). **Seed działa tylko dla nowego świata** — istniejący świat
trzeba najpierw skasować:

```bash
cd /opt/minecraft && docker compose down
docker run --rm -v minecraft_mc_data:/data alpine sh -c "rm -rf /data/world /data/world_nether /data/world_the_end"
docker compose up -d
```
