# Installation

## Clean Docker installation

Use a clean directory containing this source release, Docker Engine with Compose v2, and Python 3.10+. Linux was tested; Docker Desktop on other platforms is not yet verified. The first build downloads public base images and dependencies. At runtime, API and worker use only an internal network with no normal external routing. A small unprivileged Nginx gateway connects that network to a separate ingress network and publishes the loopback port; it has no credentials or data volume. Its only upstream is the API. This also supports Docker versions that do not publish ports directly from internal-only containers. There are no host sockets, external databases, account sessions or other application mounts.

```sh
python3 scripts/setup.py
docker compose up -d --build --wait
docker compose ps
```

Read `.env` privately for the generated initial administrator password. Open <http://localhost:8080>. Settings allows password changes. A new salted PBKDF2 hash is stored in the named volume, never the clear password. Keep `.env` private (the helper creates mode 0600); it is required by Compose and is not a password-reset mechanism.

Create a fictional schedule, tick the consent simulation checkbox, then let the worker process it. A simulated receipt begins with `demo:`. Without consent, the attempt fails with `consent_required`; edit and choose a new future occurrence to try again.

## Remote access and HTTPS

Port 8080 binds to loopback. To use a remote server without publishing the port:

```sh
ssh -L 8080:127.0.0.1:8080 your-user@your-server
```

Then browse localhost. For HTTPS, configure your own reverse proxy on the host to `127.0.0.1:8080`, set `ALLOWED_ORIGINS=https://scheduler.example.invalid` to your actual public origin, and set `COOKIE_SECURE=true`. Apply configuration with `docker compose up -d`. Forwarded headers are not trusted by the application. A containerised proxy requires deliberately configuring appropriate connectivity; the shipped internal network is intentionally closed. Do not expose plain HTTP publicly.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| SCHEDULER_ADMIN_USER | admin | First-start username only |
| SCHEDULER_ADMIN_PASSWORD | generated | Required first-start secret, minimum 12 characters |
| SCHEDULER_PORT | 8080 | Host loopback port |
| ALLOWED_ORIGINS | localhost/loopback:8080 | Exact comma-separated browser origins |
| COOKIE_SECURE | false | Set true for HTTPS browser access |
| LATE_TOLERANCE_SECONDS | 900 | Older jobs require confirmation |
| MAX_SENDS_PER_HOUR | 30 | Global persistent attempt limit, 1–1000 |

`MESSAGE_PROVIDER=demo` is fixed in Compose. Running outside Compose with any other value fails closed. Europe/Lisbon is fixed; changing container TZ does not change scheduling semantics. A daily schedule with an end date will not run after that inclusive date. Editing a paused schedule saves it as scheduled unless you save a draft; pause again if required.

## Operations

```sh
docker compose ps
docker compose logs --tail=50 api worker
docker compose stop api worker
docker compose up -d --wait
```

Use `docker compose -p your-unique-name` consistently when running multiple independent installations; they must have distinct loopback ports and volumes. Never reuse an existing application's project name or data volume. Normal `docker compose down` keeps data; adding `-v` deletes the installation data and is not part of upgrade or recovery procedures.

## Upgrade and troubleshooting

Back up the database and auth hash before upgrading. Rebuild with `docker compose up -d --build --wait`. This release supports schema version 1; do not downgrade over a newer schema. If login is rejected, check exact origin/port and HTTPS cookie settings. If the worker has no heartbeat, inspect its container health and logs. Unknown providers must be corrected to `demo`, not bypassed. Jobs delayed beyond tolerance require manual confirmation. Never reset a volume just to fix login.
