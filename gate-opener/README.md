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
| `AUTH_TOKEN`  | unset   | when set, required as the `X-Auth-Token` header |

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

Authentication is **off unless `AUTH_TOKEN` is set**. With it unset, anything
that can reach the port can trigger a door — acceptable on a trusted segment,
not through an ingress. Set `AUTH_TOKEN` and send it as `X-Auth-Token`:

```bash
curl -X POST -H "X-Auth-Token: $AUTH_TOKEN" http://gate-opener:8080/gate
```

`/healthz` stays open so container health checks keep working. The token is
sent in a plain header, so put TLS in front of it before it crosses anything
untrusted.

With a 1.5s TTL, a client polling slower than the TTL can miss a command. Poll
well under `COMMAND_TTL` (~500ms), or switch `/command` to consume-on-read so
delivery no longer depends on timing.
