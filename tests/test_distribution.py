"""Safety boundaries of the public demo distribution; synthetic fixtures only."""
import hashlib
import importlib.util
import json
import socket
import sqlite3
import pytest


def test_demo_dispatch_never_opens_network(monkeypatch):
    assert importlib.util.find_spec('scheduler.providers'), 'Demo provider package is missing'
    from scheduler.providers import Channels
    def forbidden(*args, **kwargs):
        pytest.fail('Demo attempted a network operation')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    channels = Channels('demo')
    job = {'id': 'synthetic-attempt', 'message': {'channel': 'whatsapp', 'consent': True}}
    result = channels.send(job)
    assert result.state == 'accepted'
    assert result.provider_id == 'demo:synthetic-attempt'
    assert channels.send(job) == result
    assert channels.health()['mode'] == 'demo'
    assert channels.health()['real_sending'] is False


def test_provider_selection_fails_closed():
    assert importlib.util.find_spec('scheduler.providers'), 'Demo provider package is missing'
    from scheduler.providers import Channels
    for name in ['cloud', 'whatsapp', '', 'DEMO']:
        with pytest.raises(ValueError, match='demo'):
            Channels(name)


def test_demo_requires_explicit_consent():
    assert importlib.util.find_spec('scheduler.providers'), 'Demo provider package is missing'
    from scheduler.providers import Channels
    for consent in [False, None, 'true', 1]:
        result = Channels('demo').send({'id': 'synthetic', 'message': {'consent': consent}})
        assert result.state == 'failed'
        assert result.error == 'consent_required'
        assert result.provider_id is None


def test_bootstrap_is_strong_and_does_not_reset_password(tmp_path, monkeypatch):
    assert importlib.util.find_spec('scheduler.bootstrap'), 'Portable bootstrap is missing'
    from scheduler.bootstrap import load_config
    path = tmp_path / 'auth.json'
    monkeypatch.setenv('SCHEDULER_ADMIN_PASSWORD', 'weak')
    with pytest.raises(ValueError):
        load_config(path)
    assert not path.exists()
    monkeypatch.setenv('SCHEDULER_ADMIN_PASSWORD', 'synthetic-password-long')
    monkeypatch.setenv('SCHEDULER_ADMIN_USER', 'admin')
    config = load_config(path)
    assert config['username'] == 'admin'
    assert 'synthetic-password-long' not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    monkeypatch.delenv('SCHEDULER_ADMIN_PASSWORD')
    assert load_config(path) == config


def test_restore_creates_new_quarantined_database_only(tmp_path):
    from scheduler.db import Database
    from scheduler.models import Message
    from scheduler.store import Store
    from scheduler.restore import restore
    from test_core import BASE
    source = tmp_path / 'source.db'
    store = Store(Database(source))
    item = store.create(Message(**BASE), 'synthetic-key', now=100)
    destination = tmp_path / 'restored.db'
    restore(source, destination)
    assert Store(Database(destination)).get(item['id'])['status'] == 'pending_confirmation'
    assert store.get(item['id'])['status'] == 'scheduled'
    with pytest.raises(FileExistsError):
        restore(source, destination)
    with pytest.raises((FileExistsError, ValueError)):
        restore(source, source)


def test_backup_does_not_overwrite_existing_database(tmp_path):
    from scheduler.db import Database
    from scheduler.backup import snapshot
    source = tmp_path / 'source.db'
    Database(source)
    with pytest.raises((FileExistsError, ValueError)):
        snapshot(source, source)
    destination = tmp_path / 'existing.db'
    destination.write_bytes(b'do not overwrite')
    with pytest.raises(FileExistsError):
        snapshot(source, destination)
    assert destination.read_bytes() == b'do not overwrite'
