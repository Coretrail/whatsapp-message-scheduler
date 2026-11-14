"""Freeze store validation only, so the inherited dated regression fixtures stay reproducible."""
from types import SimpleNamespace
import pytest
import scheduler.store

@pytest.fixture(autouse=True)
def stable_store_clock(monkeypatch):
    monkeypatch.setattr(scheduler.store, 'time', SimpleNamespace(time=lambda: 1790812800.0))
