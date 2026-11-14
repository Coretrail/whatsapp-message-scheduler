import os
import signal
import time
import threading
from . import settings
from .db import Database
from .store import Store
from .providers import Channels,Result

def tick(store,channels,now=None,late_tolerance=None,hour_limit=None):
    explicit_time=now is not None
    now=time.time() if now is None else now
    job=store.claim(now,late_tolerance if late_tolerance is not None else settings.LATE_TOLERANCE,
                    hour_limit if hour_limit is not None else settings.HOUR_LIMIT)
    if not job: return False
    done=threading.Event()
    def renew():
        while not done.wait(15):
            try:
                with store.db.connect(True) as c:
                    current=time.time()
                    c.execute("UPDATE attempts SET lease_until=? WHERE id=? AND state='processing'",(current+120,job['id']))
                    c.execute("INSERT OR REPLACE INTO runtime VALUES('heartbeat',?)",(str(current),))
            except Exception: pass
    keeper=threading.Thread(target=renew,daemon=True);keeper.start()
    try:
        result=channels.send(job)
    except Exception: result=Result('unknown',error='adapter_exception')
    finally:
        done.set();keeper.join(timeout=2)
    store.finish(job,result,now if explicit_time else time.time())
    return True

def main():
    os.umask(0o077)
    store=Store(Database(settings.DB_PATH));channels=Channels()
    running=True
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    while running:
        try:
            busy=tick(store,channels)
        except Exception as exc:
            # Never log payloads, provider responses, tokens, contacts or message text.
            print('worker_error '+type(exc).__name__,flush=True);busy=False
        time.sleep(1 if busy else 3)

if __name__=='__main__': main()
