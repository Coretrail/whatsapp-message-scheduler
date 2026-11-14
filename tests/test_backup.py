import sqlite3
from scheduler.db import Database
from scheduler.backup import snapshot

def test_snapshot_restores_committed_wal_without_sessions(tmp_path):
    db=Database(tmp_path/'source.db')
    with db.connect(True) as c:
        c.execute("INSERT INTO runtime VALUES('restore-proof','persisted')")
        c.execute("INSERT INTO sessions VALUES('test-token','csrf',9999999999)")
    dest=tmp_path/'restore.db'
    snapshot(db.path,dest)
    with sqlite3.connect(dest) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('SELECT value FROM runtime').fetchone()[0]=='persisted'
        assert c.execute('SELECT count(*) FROM sessions').fetchone()[0]==0

def test_restore_quarantines_all_possible_outbound_work(tmp_path):
    from scheduler.restore import quarantine
    from scheduler.store import Store
    from scheduler.models import Message
    from test_core import BASE
    db=Database(tmp_path/'source.db');store=Store(db)
    a=store.create(Message(**BASE),'scheduled-key',now=100)
    b=store.create(Message(**(BASE|{'draft':True})),'draft-key',now=100)
    quarantine(db.path)
    assert store.get(a['id'])['status']=='pending_confirmation'
    assert store.get(a['id'])['last_error']=='restored_snapshot'
    assert store.get(b['id'])['status']=='draft'
    assert store.claim(9999999999,900,30) is None
