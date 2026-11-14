import hashlib
import hmac
import secrets
import time
from fastapi import HTTPException

SESSION_SECONDS=12*3600

def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()

class Auth:
    def __init__(self,db,config,origins):
        self.db=db; self.config=config; self.origins=set(origins)

    def origin(self,request):
        if request.headers.get('origin') not in self.origins: raise HTTPException(403,'Origem não autorizada.')

    def login(self,request,username,password):
        self.origin(request)
        address=request.client.host;now=time.time()
        with self.db.connect(True) as c:
            row=c.execute('SELECT * FROM login_limits WHERE address=?',(address,)).fetchone()
            if row and row['window']>now-900 and row['failures']>=6: raise HTTPException(429,'Aguarde 15 minutos antes de tentar novamente.')
            valid=hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),self.config['password_salt'].encode(),600000).hex(),self.config['password_hash'])
            if not (hmac.compare_digest(username.encode(),self.config['username'].encode()) and valid):
                count=row['failures']+1 if row and row['window']>now-900 else 1
                window=row['window'] if count>1 else now
                c.execute('INSERT OR REPLACE INTO login_limits VALUES(?,?,?)',(address,count,window))
            else:
                c.execute('DELETE FROM login_limits WHERE address=?',(address,))
                c.execute('DELETE FROM sessions WHERE expires<?',(now,))
                token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(32)
                c.execute('INSERT INTO sessions VALUES(?,?,?)',(token_hash(token),csrf,now+SESSION_SECONDS))
                return token,csrf
        raise HTTPException(401,'Credenciais inválidas.')

    def user(self,request,write=False):
        token=request.cookies.get('scheduler_session','')
        with self.db.connect() as c:
            row=c.execute('SELECT * FROM sessions WHERE token_hash=? AND expires>?',(token_hash(token),time.time())).fetchone()
        if not row: raise HTTPException(401,'Inicie sessão.')
        if write:
            self.origin(request)
            if not hmac.compare_digest(request.headers.get('x-csrf-token',''),row['csrf']): raise HTTPException(403,'Sessão de segurança inválida. Atualize a página.')
        return dict(row)
