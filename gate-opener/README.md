# gate-opener

Tiny stdlib-only HTTP API that arms a `garage` or `gate` command for a few
seconds. A poller (ESP32, Home Assistant, shell loop) reads `GET /command` and
acts on whatever is armed.

## Endpoints

| Method | Path       | Behavior                                              |
| ------ | ---------- | ----------------------------------------------------- |
| POST   | `/garage`  | arms `"garage"` for `COMMAND_TTL` seconds             |
| POST   | `/gate`    | arms `"gate"` for `COMMAND_TTL` seconds               |
| GET    | `/command` | `{"command": "garage\|gate\|none", "expires_in": N}`  |
| GET    | `/healthz` | `{"status": "ok"}`                                    |

The most recent POST wins and resets the timer. Once the TTL lapses,
`/command` returns the base response `none`.

## Config

| Env var       | Default | Meaning                        |
| ------------- | ------- | ------------------------------ |
| `PORT`        | `8080`  | listen port                    |
| `COMMAND_TTL` | `1.5`   | seconds a command stays armed (fractional ok) |
| `CONSUME_ON_READ` | unset | when `1`/`true`, `/command` clears the command as it returns it |

## Run

On the server, from a clone of this repo:

```bash
cd homelab/gate-opener && docker compose up -d --build
```

The image is built locally from this directory — no registry involved. To pick
up changes after a `git pull`, re-run the same command.

Or without Docker: `python3 app.py` (no dependencies).

## Notes

State is in-memory, so a restart clears any armed command — intended, given the
short TTL.

There is **no authentication**. Anything that can reach the port can trigger a
door, so keep it on a trusted network segment. Add a shared-secret header before
exposing it through an ingress.

With a 1.5s TTL, a client polling slower than the TTL can miss a command. Either
poll well under `COMMAND_TTL` (~500ms), or set `CONSUME_ON_READ=1` so the first
reader takes the command and delivery no longer depends on timing.

Note that under `CONSUME_ON_READ` only one reader ever sees a given command —
correct for a single poller, wrong if several clients each need to react.
