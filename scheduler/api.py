import json
import hashlib
import secrets
import hmac
from datetime import datetime,timedelta
import os
import time
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException,Depends,Query
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel,Field,ConfigDict
from .auth import Auth,token_hash,SESSION_SECONDS
from .models import Message
from .db import Database
from .store import Store,Conflict
from .providers import Channels
from .bootstrap import load_config
from . import settings
from .recurrence import local_instant,next_occurrence,LISBON

class Login(BaseModel):
    username:str=Field(max_length=100)
    password:str=Field(max_length=256)
class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message:Message
    version:int=Field(ge=1)
class Action(BaseModel): version:int=Field(ge=1)
class Password(BaseModel):
    current_password:str=Field(max_length=256)
    new_password:str=Field(min_length=12,max_length=256)

def create_app(store,config,origins=None,config_path=None):
    app=FastAPI(title='Agendador de Mensagens',docs_url=None,redoc_url=None,openapi_url=None)
    auth=Auth(store.db,config,origins or os.getenv('ALLOWED_ORIGINS','http://localhost:8080,http://127.0.0.1:8080').split(','))
    app.state.store=store
    channels=Channels();health_cache={'at':0,'data':None}

    @app.middleware('http')
    async def guard(request,call_next):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            length=request.headers.get('content-length')
            if length and (not length.isdigit() or int(length)>65536): return JSONResponse({'detail':'Pedido demasiado grande.'},status_code=413)
            body=await request.body()
            if len(body)>65536: return JSONResponse({'detail':'Pedido demasiado grande.'},status_code=413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control']='no-store' if request.url.path.startswith(('/api/','/internal/')) else 'no-cache'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc): return JSONResponse({'detail':'Dados inválidos. Verifique os campos, destinatário e data/hora de Lisboa.'},status_code=422)
    @app.exception_handler(Conflict)
    async def conflict(request,exc): return JSONResponse({'detail':str(exc)},status_code=409)
    @app.exception_handler(KeyError)
    async def missing(request,exc): return JSONResponse({'detail':'Agendamento não encontrado.'},status_code=404)
    @app.exception_handler(ValueError)
    async def value_error(request,exc): return JSONResponse({'detail':str(exc)},status_code=422)

    def user(request:Request): return auth.user(request,request.method not in ('GET','HEAD'))
    def idem(request):
        key=request.headers.get('idempotency-key','')
        if len(key)<8 or len(key)>160: raise HTTPException(422,'Envie Idempotency-Key com 8 a 160 caracteres.')
        return key

    @app.get('/healthz')
    def healthz(): return {'ok':True}

    @app.post('/api/login')
    def login(body:Login,request:Request):
        token,csrf=auth.login(request,body.username,body.password)
        response=JSONResponse({'csrf':csrf,'username':config['username']})
        secure=request.url.scheme=='https' or os.getenv('COOKIE_SECURE','false')=='true'
        response.set_cookie('scheduler_session',token,httponly=True,secure=secure,samesite='strict',max_age=SESSION_SECONDS,path='/')
        with store.db.connect(True) as c:
            from .store import audit
            audit(c,'login')
        return response

    @app.get('/api/session')
    def session(request:Request,_=Depends(user)):
        return {'csrf':auth.user(request)['csrf'],'username':config['username']}

    @app.post('/api/logout')
    def logout(request:Request,_=Depends(user)):
        with store.db.connect(True) as c: c.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(request.cookies.get('scheduler_session','')),))
        response=JSONResponse({'ok':True});response.delete_cookie('scheduler_session');return response

    @app.post('/api/password',dependencies=[Depends(user)])
    def password(body:Password,request:Request):
        expected=hashlib.pbkdf2_hmac('sha256',body.current_password.encode(),config['password_salt'].encode(),600000).hex()
        if not hmac.compare_digest(expected,config['password_hash']): raise HTTPException(401,'Palavra-passe atual inválida.')
        salt=secrets.token_hex(24)
        updated=config|{'password_salt':salt,'password_hash':hashlib.pbkdf2_hmac('sha256',body.new_password.encode(),salt.encode(),600000).hex()}
        with store.db.connect(True) as c:
            if config_path:
                target=Path(config_path);temp=target.with_suffix('.tmp')
                temp.write_text(json.dumps(updated));temp.chmod(0o600);temp.replace(target)
            config.update(updated)
            c.execute('DELETE FROM sessions WHERE token_hash!=?',(token_hash(request.cookies.get('scheduler_session','')),))
            from .store import audit
            audit(c,'password_changed')
        return {'ok':True}

    @app.get('/api/calendar',dependencies=[Depends(user)])
    def calendar(start:str,end:str):
        try:
            first=datetime.strptime(start,'%Y-%m-%d');last=datetime.strptime(end,'%Y-%m-%d')
            if not 0<(last-first).days<=93: raise ValueError()
            begin=local_instant(first.isoformat()).timestamp();stop=local_instant(last.isoformat()).timestamp()
        except ValueError: raise HTTPException(422,'Intervalo inválido; máximo de 93 dias.')
        result=[]
        for row in store.list():
            m=Message(**row['message'])
            if row['status'] in ('draft','cancelled','failed'): continue
            due=row['next_due'] or local_instant(m.scheduled_local).timestamp()
            if due<begin and row['status'] in ('scheduled','paused'):
                due=next_occurrence(m,begin-1)
            while due is not None and due<stop:
                if due>=begin:
                    result.append({'id':row['id'],'due':due,'local_date':datetime.fromtimestamp(due,LISBON).date().isoformat(),
                                   'name':m.name,'recipient':m.recipient,'body':m.body,'channel':m.channel,'status':row['status']})
                if len(result)>=1000: break
                if row['status'] not in ('scheduled','paused'): break
                due=next_occurrence(m,due)
            if len(result)>=1000: break
        return {'items':sorted(result,key=lambda e:e['due'])}

    @app.get('/api/messages',dependencies=[Depends(user)])
    def listing(): return {'items':store.list()}

    @app.post('/api/messages',dependencies=[Depends(user)])
    def create(body:Message,request:Request): return store.create(body,idem(request),actor='user')

    @app.get('/api/messages/{mid}',dependencies=[Depends(user)])
    def get(mid:str): return store.get(mid)

    @app.put('/api/messages/{mid}',dependencies=[Depends(user)])
    def edit(mid:str,body:Edit,request:Request): return store.edit(mid,body.message,body.version,actor='user')

    @app.get('/api/messages/{mid}/history',dependencies=[Depends(user)])
    def history(mid:str): return {'items':store.history(mid)}

    @app.post('/api/messages/{mid}/{action}',dependencies=[Depends(user)])
    def action(mid:str,action:str,body:Action,request:Request):
        return store.action(mid,action,body.version,actor='user')

    @app.get('/api/contacts',dependencies=[Depends(user)])
    def contact_search(q:str=Query(default='',max_length=160)):
        return {'items':[]}  # No external address book in the demo distribution.

    @app.get('/api/status',dependencies=[Depends(user)])
    def status():
        if time.time()-health_cache['at']>60:
            health_cache.update(at=time.time(),data=channels.health())
        with store.db.connect() as c:
            row=c.execute("SELECT value FROM runtime WHERE key='heartbeat'").fetchone()
        heartbeat=float(row[0]) if row else 0
        return {'channels':health_cache['data'],'worker':time.time()-heartbeat<30,'heartbeat':heartbeat,
                'mode':'demo','real_sending':False,'timezone':'Europe/Lisbon','late_tolerance_seconds':settings.LATE_TOLERANCE,'max_sends_per_hour':settings.HOUR_LIMIT}

    dist=Path(os.getenv('FRONTEND_DIST','/app/frontend/dist'))
    if dist.exists():
        app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
        @app.get('/{path:path}')
        def frontend(path:str):
            if path.startswith(('api/','internal/')): raise HTTPException(404)
            target=(dist/path).resolve()
            if not target.is_relative_to(dist.resolve()): raise HTTPException(404)
            if target.is_file(): return FileResponse(target)
            return FileResponse(dist/'index.html')
    return app

def production_app():
    os.umask(0o077)
    config=load_config(settings.AUTH_PATH)
    return create_app(Store(Database(settings.DB_PATH)),config,config_path=settings.AUTH_PATH)
