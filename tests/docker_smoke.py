"""Exercise only the isolated demo instance with synthetic data; print no secrets."""
import urllib.request,urllib.error,http.cookiejar,json,time,subprocess,os,secrets
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
base=os.getenv('DEMO_URL','http://127.0.0.1:8080')
root=Path(__file__).resolve().parents[1]
password=os.environ['DEMO_PASSWORD']
compose=['docker','compose']
if os.getenv('DEMO_ENV_FILE'):
    compose += ['--env-file',os.environ['DEMO_ENV_FILE']]
compose += ['-p',os.getenv('COMPOSE_PROJECT_NAME','scheduler-test')]
cookies=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies));csrf=''
def request(path,body=None,key=None):
 headers={'Origin':base,'Content-Type':'application/json','X-CSRF-Token':csrf}
 if key:headers['Idempotency-Key']=key
 data=json.dumps(body).encode() if body is not None else None
 with client.open(urllib.request.Request(base+path,data=data,headers=headers),timeout=10) as response:return json.load(response)
def login(secret):
 global csrf
 csrf=request('/api/login',{'username':'admin','password':secret})['csrf']
def run(*args):
 p=subprocess.run(compose+list(args),cwd=root,capture_output=True,text=True)
 assert p.returncode==0,p.stderr
 return p.stdout
login(password)
status=request('/api/status');assert status['mode']=='demo' and status['real_sending'] is False
future=(datetime.now(ZoneInfo('Europe/Lisbon'))+timedelta(seconds=10)).replace(microsecond=0).replace(tzinfo=None).isoformat()
message={'channel':'whatsapp','recipient':'+12025550123','name':'Synthetic worker check','body':'Fictional fixture. No delivery.','scheduled_local':future,'consent':True}
item=request('/api/messages',message,key='isolated-worker-synthetic')
assert request('/api/messages',message,key='isolated-worker-synthetic')['id']==item['id']
for _ in range(35):
 result=request('/api/messages/'+item['id'])
 if result['status']=='accepted':break
 time.sleep(1)
assert result['status']=='accepted',result['status']
history=request('/api/messages/'+item['id']+'/history')['items'];assert len(history)==1 and history[0]['provider_id'].startswith('demo:')
print('PASS actual worker timed simulation, idempotency, receipt and history')
# Verify admin password change survives an actual container restart.
updated=secrets.token_urlsafe(32)
request('/api/password',{'current_password':password,'new_password':updated})
run('restart','api','worker')
for _ in range(40):
 try:
  login(updated);break
 except Exception:time.sleep(1)
else:raise AssertionError('Restart login failed')
assert request('/api/messages/'+item['id'])['status']=='accepted'
assert len(request('/api/messages/'+item['id']+'/history')['items'])==1
print('PASS persistence and updated administrator password after restart; no duplicate attempt')
# A fresh future job must be quarantined by recovery.
future=(datetime.now(ZoneInfo('Europe/Lisbon'))+timedelta(days=5)).replace(microsecond=0).replace(tzinfo=None).isoformat()
queued=request('/api/messages',message|{'scheduled_local':future,'name':'Synthetic restore check','recurrence':'daily'},key='isolated-restore-synthetic')
run('exec','-T','api','python','-m','scheduler.backup','/data/scheduler.db','/data/snapshot.db')
run('exec','-T','api','python','-m','scheduler.restore','/data/snapshot.db','/data/restored.db')
# Source still operates; actual switch is performed only on this fresh review volume.
assert request('/api/messages/'+queued['id'])['status']=='scheduled'
run('stop','api','worker')
switch='from pathlib import Path; import sqlite3; from scheduler.restore import quarantine; c=sqlite3.connect("/data/restored.db"); assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; c.close(); quarantine("/data/restored.db"); rollback=Path("/data/before-restore"); rollback.mkdir(mode=0o700); [(Path("/data/scheduler.db"+s).rename(rollback/("scheduler.db"+s))) for s in ("", "-wal", "-shm") if Path("/data/scheduler.db"+s).exists()]; Path("/data/restored.db").rename("/data/scheduler.db")'
run('run','--rm','--no-deps','--entrypoint','python','api','-c',switch)
run('up','-d','--wait')
# Restored snapshots cannot authenticate old browser sessions.
try:request('/api/messages');raise AssertionError('Restored session survived')
except urllib.error.HTTPError as e:assert e.code==401
login(updated)
restored=request('/api/messages/'+queued['id']);assert restored['status']=='pending_confirmation' and restored['last_error']=='restored_snapshot'
assert request('/api/messages/'+item['id'])['status']=='accepted'
print('PASS consistent snapshot, actual isolated restore switch, session invalidation and queue quarantine')
print('PASS integration suite; no real provider exists or was invoked')

request('/api/password',{'current_password':updated,'new_password':password})
print('PASS initial test password restored for subsequent browser checks')
