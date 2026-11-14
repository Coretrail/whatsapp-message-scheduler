from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import pytest
from scheduler.db import Database
from scheduler.models import Message
from scheduler.store import Store, Conflict
from scheduler.recurrence import local_instant, next_occurrence

BASE = dict(channel='whatsapp', recipient='+12025550123', name='Teste', body='Mensagem de teste', scheduled_local='2026-10-30T09:00', recurrence='once')

@pytest.fixture
def store(tmp_path):
    return Store(Database(tmp_path/'test.db'))

def create(store, **kw):
    return store.create(Message(**(BASE|kw)), 'create-key-12345', now=100)

def test_idempotency_conflict_and_restart(store):
    a=create(store)
    assert create(store)['id']==a['id']
    with pytest.raises(Conflict): create(store, body='Outra')
    assert Store(Database(store.db.path)).get(a['id'])['message']['body']=='Mensagem de teste'

def test_atomic_claim_and_cancel(store):
    a=create(store)
    now=local_instant(BASE['scheduled_local']).timestamp()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _: store.claim(now, 600, 10),range(4)))
    assert len([r for r in results if r])==1
    with pytest.raises(Conflict): store.action(a['id'],'cancel',a['version'])
    assert len(store.history(a['id']))==1

def test_edit_cancel_and_optimistic_lock(store):
    a=create(store)
    b=store.edit(a['id'],Message(**(BASE|{'body':'Alterada'})),a['version'])
    with pytest.raises(Conflict): store.edit(a['id'],Message(**BASE),a['version'])
    c=store.action(a['id'],'cancel',b['version'])
    assert c['status']=='cancelled'
    assert store.claim(local_instant(BASE['scheduled_local']).timestamp(),600,10) is None

def test_dst_validation_and_one_occurrence_in_autumn():
    with pytest.raises(ValueError,match='existe'): local_instant('2027-03-28T01:30')
    assert local_instant('2027-10-31T01:30').isoformat()=='2027-10-31T00:30:00+00:00'
    m=Message(**(BASE|{'scheduled_local':'2027-03-27T01:30','recurrence':'daily'}))
    assert next_occurrence(m,local_instant(m.scheduled_local).timestamp())==local_instant('2027-03-29T01:30').timestamp()

def test_monthly_yearly_weekdays_and_end():
    m=Message(**(BASE|{'scheduled_local':'2027-01-31T09:00','recurrence':'monthly'}))
    assert next_occurrence(m,local_instant(m.scheduled_local).timestamp())==local_instant('2027-03-31T09:00').timestamp()
    m=Message(**(BASE|{'scheduled_local':'2028-02-29T09:00','recurrence':'yearly'}))
    assert next_occurrence(m,local_instant(m.scheduled_local).timestamp())==local_instant('2032-02-29T09:00').timestamp()
    m=Message(**(BASE|{'recurrence':'weekdays','weekdays':[0,2],'end_date':'2026-11-02'}))
    assert next_occurrence(m,local_instant(m.scheduled_local).timestamp())==local_instant('2026-11-02T09:00').timestamp()
    assert next_occurrence(m,local_instant('2026-11-02T09:00').timestamp()) is None

def test_overdue_requires_confirmation(store):
    a=create(store)
    assert store.claim(local_instant(BASE['scheduled_local']).timestamp()+601,600,10) is None
    assert store.get(a['id'])['status']=='pending_confirmation'

def test_pause_duplicate_and_draft(store):
    a=create(store,recurrence='daily')
    b=store.action(a['id'],'pause',a['version'])
    assert b['status']=='paused'
    d=store.action(a['id'],'duplicate',b['version'])
    assert d['status']=='draft' and d['id']!=a['id']
    assert store.action(a['id'],'resume',b['version'])['status']=='scheduled'

@pytest.mark.parametrize('changes',[{'recipient':'abc'}, {'body':' '}, {'channel':'email','recipient':'a@example.com\nBcc:injected@example.invalid','subject':'oi'}, {'recurrence':'weekdays','weekdays':[]}, {'end_date':'2026-10-01'}, {'subject':'a\nBcc:injected@example.invalid'}])
def test_validation(changes):
    with pytest.raises(ValueError): Message(**(BASE|changes))

def test_selected_weekdays_controls_first_dispatch(store):
    a=create(store,recurrence='weekdays',weekdays=[0,2])
    assert a['next_due']==local_instant('2026-11-02T09:00').timestamp()

def test_edited_schedule_does_not_replay_same_occurrence(store):
    a=create(store)
    now=local_instant(BASE['scheduled_local']).timestamp()
    job=store.claim(now,600,30)
    from scheduler.providers import Result
    store.finish(job,Result('failed',error='rejected'),now)
    a=store.get(a['id'])
    with pytest.raises(Conflict): store.edit(a['id'],Message(**BASE),a['version'])
