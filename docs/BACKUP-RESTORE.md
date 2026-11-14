# Backup and restore

Commands below refer only to this installation's Compose project. If you chose a custom `-p` name, use that same name everywhere. Backup encryption and rotation are external responsibilities. Use trusted snapshots only; do not upload them to GitHub.

## Snapshot

```sh
docker compose exec api python -m scheduler.backup /data/scheduler.db /data/snapshot.db
docker compose cp api:/data/snapshot.db ./snapshot.db
```

The destination must not already exist. SQLite's backup API captures committed WAL data, runs integrity checking and removes browser sessions and login throttling records from the copy. Do not copy a live `.db` alone using ordinary filesystem tools. Back up `/data/auth.json` separately and privately if you want to retain the administrator password hash; it is deliberately not embedded in snapshots. The `.env` initial password may differ after a password change.

## Prepare a safe restored copy

```sh
docker compose exec api python -m scheduler.restore /data/snapshot.db /data/restored.db
```

This creates a **new** database and never replaces the active one or manages containers. Existing destinations and SQLite sidecars are refused. Scheduled, paused and processing work is quarantined as `pending_confirmation`; processing attempts become `unknown`. Sessions/runtime health data are cleared. The source remains unchanged.

To inspect recovery without switching the live installation, copy `restored.db` out and use a new isolated installation. Never attach two installations to the same SQLite volume.

## Deliberately switch this demo installation

After inspecting the restored copy, stop only its own services and retain the original file plus any WAL/SHM sidecars:

```sh
docker compose stop api worker
docker compose run --rm --no-deps --entrypoint python api -c 'from pathlib import Path; import sqlite3; from scheduler.restore import quarantine; c=sqlite3.connect("/data/restored.db"); assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; c.close(); quarantine("/data/restored.db"); rollback=Path("/data/before-restore"); rollback.mkdir(mode=0o700); [(Path("/data/scheduler.db"+s).rename(rollback/("scheduler.db"+s))) for s in ("", "-wal", "-shm") if Path("/data/scheduler.db"+s).exists()]; Path("/data/restored.db").rename("/data/scheduler.db")'
docker compose up -d --wait
```

The command refuses an existing rollback directory. Keep the rollback and snapshot securely until recovery is verified. This is an offline maintenance operation; ensure no other process accesses the volume. Recovered schedules cannot be auto-confirmed: review and resolve them, then create a new future demo schedule if appropriate. There is no automatic replay.
