import hashlib
import json
import time
import uuid
from .models import Message
from .recurrence import local_instant, next_occurrence, first_occurrence

class Conflict(ValueError): pass

def unpack(row):
    if row is None: raise KeyError('Agendamento não encontrado.')
    item=dict(row)
    if 'payload' in item: item['message']=json.loads(item.pop('payload'))
    return item

def audit(c, action, mid=None, actor='user'):
    c.execute('INSERT INTO audit(at,actor,action,message_id) VALUES(?,?,?,?)',(time.time(),actor,action,mid))

class Store:
    def __init__(self, db): self.db=db

    def create(self, m, key, now=None, actor='user'):
        now=time.time() if now is None else now
        payload=m.model_dump_json()
        digest=hashlib.sha256(payload.encode()).hexdigest()
        with self.db.connect(True) as c:
            old=c.execute('SELECT * FROM idempotency WHERE key=?',(key,)).fetchone()
            if old:
                if old['digest']!=digest: raise Conflict('Chave de idempotência reutilizada com outro conteúdo.')
                return unpack(c.execute('SELECT * FROM messages WHERE id=?',(old['message_id'],)).fetchone())
            if not m.draft and local_instant(m.scheduled_local).timestamp()<=now:
                raise ValueError('Escolha uma data e hora futuras.')
            if c.execute("SELECT COUNT(*) FROM messages WHERE status IN ('scheduled','draft','paused','pending_confirmation')").fetchone()[0]>=1000:
                raise Conflict('Limite de 1000 agendamentos ativos atingido.')
            mid=str(uuid.uuid4())
            due=None if m.draft else first_occurrence(m)
            c.execute('INSERT INTO messages(id,payload,status,next_due,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                      (mid,payload,'draft' if m.draft else 'scheduled',due,now,now))
            c.execute('INSERT INTO idempotency VALUES(?,?,?)',(key,digest,mid))
            audit(c,'create',mid,actor)
            return unpack(c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone())

    def get(self,mid):
        with self.db.connect() as c: return unpack(c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone())

    def list(self):
        with self.db.connect() as c:
            return [unpack(r) for r in c.execute('SELECT * FROM messages ORDER BY COALESCE(next_due,created_at) DESC LIMIT 2000')]

    def edit(self,mid,m,version,actor='user'):
        with self.db.connect(True) as c:
            row=unpack(c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone())
            if row['version']!=version or row['status'] not in ('draft','scheduled','paused','failed'):
                raise Conflict('Atualize a página; este agendamento já mudou ou não pode ser editado.')
            due=first_occurrence(m)
            if not m.draft and c.execute('SELECT 1 FROM attempts WHERE message_id=? AND due=?',(mid,due)).fetchone():
                raise Conflict('Escolha outra data/hora para reagendar uma ocorrência que já foi tentada.')
            if not m.draft and due<=time.time(): raise ValueError('Escolha uma data e hora futuras.')
            c.execute('UPDATE messages SET payload=?,status=?,next_due=?,retry_at=NULL,last_error=NULL,version=version+1,updated_at=? WHERE id=?',
                      (m.model_dump_json(),'draft' if m.draft else 'scheduled',None if m.draft else due,time.time(),mid))
            audit(c,'edit',mid,actor)
        return self.get(mid)

    def action(self,mid,action,version,actor='user'):
        with self.db.connect(True) as c:
            row=unpack(c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone())
            if row['version']!=version: raise Conflict('Versão desatualizada. Atualize a página.')
            status=row['status']
            if action=='duplicate':
                m=Message(**(row['message']|{'draft':True}))
            elif action=='cancel':
                if status not in ('draft','scheduled','paused','pending_confirmation','failed'): raise Conflict('Não é possível cancelar um envio em curso ou aceite.')
                c.execute("UPDATE messages SET status='cancelled',next_due=NULL,version=version+1 WHERE id=?",(mid,))
            elif action=='pause':
                if status!='scheduled' or row['message']['recurrence']=='once': raise Conflict('Só pode suspender recorrências agendadas.')
                c.execute("UPDATE messages SET status='paused',version=version+1 WHERE id=?",(mid,))
            elif action=='resume':
                if status!='paused': raise Conflict('Esta recorrência não está suspensa.')
                c.execute("UPDATE messages SET status='scheduled',version=version+1 WHERE id=?",(mid,))
            elif action=='confirm':
                if status!='pending_confirmation' or row['last_error']!='overdue': raise Conflict('Um resultado desconhecido não pode ser repetido. Consulte o histórico e encerre-o manualmente.')
                c.execute("UPDATE messages SET status='scheduled',next_due=?,retry_at=NULL,last_error=NULL,version=version+1 WHERE id=?",(time.time(),mid))
            elif action=='resolve':
                if status!='pending_confirmation' or row['last_error']=='overdue': raise Conflict('Não há resultado desconhecido para encerrar.')
                c.execute("UPDATE messages SET status='failed',next_due=NULL,last_error='manual_resolution',version=version+1 WHERE id=?",(mid,))
            else: raise ValueError('Ação inválida.')
            audit(c,action,mid,actor)
        if action=='duplicate': return self.create(m,str(uuid.uuid4()),actor=actor)
        return self.get(mid)

    def history(self,mid):
        self.get(mid)
        with self.db.connect() as c:
            return [dict(r) for r in c.execute('SELECT * FROM attempts WHERE message_id=? ORDER BY started_at DESC',(mid,))]

    def claim(self,now,late_tolerance,hour_limit):
        with self.db.connect(True) as c:
            c.execute("INSERT OR REPLACE INTO runtime VALUES('heartbeat',?)",(str(now),))
            # No automatic replay of a dispatch whose lease expired.
            expired=c.execute("SELECT * FROM attempts WHERE state='processing' AND lease_until<?",(now,)).fetchall()
            for a in expired:
                c.execute("UPDATE attempts SET state='unknown',error='worker_interrupted',finished_at=? WHERE id=?",(now,a['id']))
                c.execute("UPDATE messages SET status='pending_confirmation',last_error='worker_interrupted',version=version+1 WHERE id=? AND status='processing'",(a['message_id'],))
                audit(c,'interrupted',a['message_id'],'worker')
            if c.execute("SELECT count(*) FROM attempts WHERE started_at>?",(now-3600,)).fetchone()[0]>=hour_limit: return None
            rows=c.execute("SELECT * FROM messages WHERE status='scheduled' AND next_due<=? AND (retry_at IS NULL OR retry_at<=?) ORDER BY next_due LIMIT 100",(now,now)).fetchall()
            for row in rows:
                count=c.execute('SELECT count(*) FROM attempts WHERE message_id=? AND due=?',(row['id'],row['next_due'])).fetchone()[0]
                if now-row['next_due']>late_tolerance:
                    c.execute("UPDATE messages SET status='pending_confirmation',last_error='overdue',version=version+1 WHERE id=?",(row['id'],))
                    audit(c,'overdue',row['id'],'worker')
                    continue
                aid='scheduler-'+str(uuid.uuid4())
                c.execute("INSERT INTO attempts(id,message_id,due,state,started_at,lease_until) VALUES(?,?,?,'processing',?,?)",(aid,row['id'],row['next_due'],now,now+120))
                c.execute("UPDATE messages SET status='processing',version=version+1 WHERE id=?",(row['id'],))
                audit(c,'claim',row['id'],'worker')
                return {'id':aid,'message_id':row['id'],'due':row['next_due'],'message':json.loads(row['payload'])}
        return None

    def finish(self,attempt,result,now=None):
        now=time.time() if now is None else now
        with self.db.connect(True) as c:
            a=c.execute('SELECT * FROM attempts WHERE id=?',(attempt['id'],)).fetchone()
            if not a or a['state']!='processing': return
            row=c.execute('SELECT * FROM messages WHERE id=?',(a['message_id'],)).fetchone()
            state=result.state
            c.execute('UPDATE attempts SET state=?,finished_at=?,provider_id=?,error=? WHERE id=?',(state,now,result.provider_id,result.error,a['id']))
            due=row['next_due']; retry=None; error=result.error
            if state=='accepted':
                due=next_occurrence(Message(**json.loads(row['payload'])),a['due'])
                status='scheduled' if due is not None else 'accepted'
            elif state=='retry':
                n=c.execute('SELECT count(*) FROM attempts WHERE message_id=? AND due=?',(row['id'],a['due'])).fetchone()[0]
                if n>=3: status='failed'; due=None
                else: status='scheduled'; retry=now+60*(2**(n-1))
            elif state=='failed': status='failed'; due=None
            else: status='pending_confirmation'
            c.execute('UPDATE messages SET status=?,next_due=?,retry_at=?,last_result=?,last_error=?,version=version+1,updated_at=? WHERE id=?',
                      (status,due,retry,state,error,now,row['id']))
            audit(c,state,row['id'],'worker')
