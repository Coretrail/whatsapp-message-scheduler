import hashlib,json,time
import pytest
from fastapi.testclient import TestClient
from scheduler.api import create_app
from scheduler.db import Database
from scheduler.store import Store
from test_core import BASE

@pytest.fixture
def client(tmp_path):
    config={'password_salt':'test-salt','password_hash':hashlib.pbkdf2_hmac('sha256',b'test-password-long',b'test-salt',600000).hex(), 'username':'admin','internal_token':'internal-test-token-long'}
    app=create_app(Store(Database(tmp_path/'api.db')),config,origins=['http://testserver'])
    with TestClient(app) as c: yield c

def login(c):
    r=c.post('/api/login',json={'username':'admin','password':'test-password-long'},headers={'Origin':'http://testserver'})
    assert r.status_code==200
    return {'X-CSRF-Token':r.json()['csrf'],'Origin':'http://testserver'}

def test_auth_csrf_crud_idempotency(client):
    assert client.get('/api/messages').status_code==401
    h=login(client)
    assert client.post('/api/messages',json=BASE).status_code==403
    h['Idempotency-Key']='api-create-12345'
    r=client.post('/api/messages',json=BASE,headers=h)
    assert r.status_code==200,r.text
    a=r.json()
    assert client.post('/api/messages',json=BASE,headers=h).json()['id']==a['id']
    assert client.post('/api/messages',json=BASE|{'body':'different'},headers=h).status_code==409
    r=client.put('/api/messages/'+a['id'],json={'message':BASE|{'body':'edit'},'version':a['version']},headers=h)
    assert r.status_code==200
    b=r.json()
    assert client.post('/api/messages/'+a['id']+'/cancel',json={'version':b['version']},headers=h).json()['status']=='cancelled'
    assert client.get('/api/messages/'+a['id']+'/history').status_code==200
    assert client.post('/api/logout',headers=h).status_code==200
    assert client.get('/api/messages').status_code==401

def test_origin_and_validation(client):
    assert client.post('/api/login',json={'username':'admin','password':'test-password-long'},headers={'Origin':'https://evil.example'}).status_code==403
    h=login(client)|{'Idempotency-Key':'validation-key'}
    assert client.post('/api/messages',json=BASE|{'recipient':'wrong'},headers=h).status_code==422
    r=client.post('/api/messages',json=BASE|{'recipient':'private-secret-value'},headers=h)
    assert 'private-secret-value' not in r.text

def test_internal_api_and_rate_limit(client):
    assert client.get('/internal/v1/messages').status_code==404
    for _ in range(6): client.post('/api/login',json={'username':'bad','password':'bad'},headers={'Origin':'http://testserver'})
    assert client.post('/api/login',json={'username':'bad','password':'bad'},headers={'Origin':'http://testserver'}).status_code==429

def test_calendar_expands_recurrence_and_password_change(client):
    h=login(client)|{'Idempotency-Key':'calendar-12345'}
    r=client.post('/api/messages',json=BASE|{'recurrence':'daily','end_date':'2026-11-02'},headers=h)
    assert r.status_code==200
    r=client.get('/api/calendar?start=2026-10-01&end=2026-11-01')
    assert r.status_code==200
    assert [e['local_date'] for e in r.json()['items']]==['2026-10-30','2026-10-31']
    assert client.get('/api/calendar?start=2026-10-01&end=2028-11-01').status_code==422
    r=client.post('/api/password',json={'current_password':'test-password-long','new_password':'updated-password-long'},headers=h)
    assert r.status_code==200
    assert client.post('/api/login',json={'username':'admin','password':'updated-password-long'},headers={'Origin':'http://testserver'}).status_code==200

def test_unicode_login_is_rejected_without_server_error(client):
    r=client.post('/api/login',json={'username':'utilizador-ç','password':'bad'},headers={'Origin':'http://testserver'})
    assert r.status_code==401
