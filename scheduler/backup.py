"""Create a consistent SQLite snapshot in a NEW file. Snapshots contain private data."""
import argparse
import os
from pathlib import Path
import sqlite3


def snapshot(source, dest):
    source, dest = Path(source).resolve(), Path(dest).resolve()
    if source == dest:
        raise ValueError('Snapshot destination must differ from source')
    # Reserve the destination before opening SQLite, without following symlinks.
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(dest) as target:
            src.backup(target, pages=256, sleep=.05)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Snapshot integrity check failed')
            target.execute('DELETE FROM sessions')
            target.execute('DELETE FROM login_limits')
    except BaseException:
        dest.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    snapshot(args.source, args.destination)
    print('Snapshot created; sessions excluded. Store and encrypt it securely.')

if __name__ == '__main__':
    main()
