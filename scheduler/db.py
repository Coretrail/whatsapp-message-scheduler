"""SQLite connection boundaries and append-only schema migrations."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS messages(
 id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL,
 next_due REAL, retry_at REAL, version INTEGER NOT NULL DEFAULT 1,
 last_result TEXT, last_error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS messages_due ON messages(status,next_due,retry_at);
CREATE TABLE IF NOT EXISTS attempts(
 id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id),
 due REAL NOT NULL, state TEXT NOT NULL, started_at REAL NOT NULL,
 lease_until REAL NOT NULL, finished_at REAL, provider_id TEXT, error TEXT);
CREATE INDEX IF NOT EXISTS attempts_message ON attempts(message_id,started_at);
CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, digest TEXT NOT NULL, message_id TEXT NOT NULL REFERENCES messages(id));
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, message_id TEXT);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_limits(address TEXT PRIMARY KEY, failures INTEGER NOT NULL, window REAL NOT NULL);
CREATE TABLE IF NOT EXISTS runtime(key TEXT PRIMARY KEY,value TEXT NOT NULL);
PRAGMA user_version=1;
'''

class Database:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            version=c.execute('PRAGMA user_version').fetchone()[0]
            if version > 1: raise RuntimeError('Database schema newer than application')
            if version == 0: c.executescript(SCHEMA)

    @contextmanager
    def connect(self, write=False):
        c=sqlite3.connect(self.path, timeout=15)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA synchronous=FULL')
        try:
            if write: c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally: c.close()
