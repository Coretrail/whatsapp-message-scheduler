"""Create a NEW quarantined database from a snapshot. Never replace live files or manage services."""
import argparse
import os
from pathlib import Path
import sqlite3
import time
from .backup import snapshot


def quarantine(path):
    with sqlite3.connect(path) as connection:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Invalid SQLite snapshot')
        connection.execute("UPDATE messages SET status='pending_confirmation',last_error='restored_snapshot',retry_at=NULL,version=version+1 WHERE status IN ('scheduled','processing','paused','pending_confirmation')")
        connection.execute("UPDATE attempts SET state='unknown',error='restored_snapshot',finished_at=? WHERE state='processing'", (time.time(),))
        connection.execute('DELETE FROM sessions')
        connection.execute('DELETE FROM login_limits')
        connection.execute('DELETE FROM runtime')
        connection.execute("INSERT INTO audit(at,actor,action) VALUES(?,'restore','quarantined_snapshot')", (time.time(),))


def restore(source, destination):
    destination = Path(destination)
    if any(Path(str(destination) + suffix).exists() for suffix in ('', '-wal', '-shm')):
        raise FileExistsError('Destination or SQLite sidecar already exists')
    snapshot(source, destination)
    try:
        quarantine(destination)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    restore(args.snapshot, args.destination)
    print('New database created. Outbound work is quarantined; no automatic replay.')

if __name__ == '__main__':
    main()
