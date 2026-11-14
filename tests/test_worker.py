from concurrent.futures import ThreadPoolExecutor
import pytest
from scheduler.providers import Result, Channels
from scheduler.worker import tick
from scheduler.db import Database
from scheduler.store import Store
from scheduler.models import Message
from scheduler.recurrence import local_instant
from test_core import BASE

@pytest.fixture
def store(tmp_path): return Store(Database(tmp_path/'worker.db'))

def prepared(store, **kwargs):
    return store.create(Message(**(BASE|kwargs)),'worker-create-key',now=100)

class Accepted:
    def send(self, job): return Result('accepted',provider_id='provider-test-id')
class Unknown:
    def send(self, job): return Result('unknown',error='timeout')
class Retry:
    def send(self, job): return Result('retry',error='channel_offline')

def test_accepted_and_concurrent_workers(store):
    a=prepared(store)
    now=local_instant(BASE['scheduled_local']).timestamp()
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _:tick(store,Accepted(),now,600,30),range(3)))
    assert store.get(a['id'])['status']=='accepted'
    assert len(store.history(a['id']))==1
    assert store.history(a['id'])[0]['provider_id']=='provider-test-id'

def test_unknown_never_retried(store):
    a=prepared(store)
    now=local_instant(BASE['scheduled_local']).timestamp()
    tick(store,Unknown(),now,600,30)
    tick(store,Accepted(),now+600,600,30)
    assert store.get(a['id'])['status']=='pending_confirmation'
    assert len(store.history(a['id']))==1

def test_crash_after_claim_never_replays(store):
    a=prepared(store)
    now=local_instant(BASE['scheduled_local']).timestamp()
    assert store.claim(now,600,30)
    tick(Store(Database(store.db.path)),Accepted(),now+121,600,30)
    assert store.get(a['id'])['status']=='pending_confirmation'
    assert store.history(a['id'])[0]['error']=='worker_interrupted'

def test_known_no_send_retry_is_bounded(store):
    a=prepared(store)
    now=local_instant(BASE['scheduled_local']).timestamp()
    for delta in (0,60,180,1000): tick(store,Retry(),now+delta,600,30)
    assert store.get(a['id'])['status']=='failed'
    assert len(store.history(a['id']))==3

def test_recurring_advances_only_on_acceptance(store):
    a=prepared(store,recurrence='daily')
    now=local_instant(BASE['scheduled_local']).timestamp()
    tick(store,Accepted(),now,600,30)
    assert store.get(a['id'])['next_due']==local_instant('2026-10-31T09:00').timestamp()
    assert store.get(a['id'])['status']=='scheduled'

def test_rate_limit_persists(store):
    a=prepared(store,recurrence='daily')
    now=local_instant(BASE['scheduled_local']).timestamp()
    tick(store,Accepted(),now,600,1)
    b=store.create(Message(**BASE),'other-key',now=100)
    tick(store,Accepted(),now+1,600,1)
    assert store.get(b['id'])['status']=='scheduled'

def test_retry_after_long_downtime_requires_confirmation(store):
    a=prepared(store)
    now=local_instant(BASE['scheduled_local']).timestamp()
    tick(store,Retry(),now,900,30)
    tick(store,Accepted(),now+86400,900,30)
    assert store.get(a['id'])['status']=='pending_confirmation'
    assert store.get(a['id'])['last_error']=='overdue'
    assert len(store.history(a['id']))==1
