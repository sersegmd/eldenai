import os,platform,secrets,shutil,time,asyncio
from pathlib import Path
import httpx
from fastapi import Depends,FastAPI,HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic,HTTPBasicCredentials
from .config import settings
from . import db
from .runtime import queue_snapshot
from .tts_client import voice_configuration_status
from .creator_checkpoint import stale as stale_checkpoints
app=FastAPI(title='ELDEN AI Control Room',docs_url=None,redoc_url=None);security=HTTPBasic();START=time.time()
def auth(c:HTTPBasicCredentials=Depends(security)):
 if not(secrets.compare_digest(c.username,settings.dashboard_user) and secrets.compare_digest(c.password,settings.dashboard_password)):raise HTTPException(401,'Unauthorized',headers={'WWW-Authenticate':'Basic'})
async def check(url):
 t=time.perf_counter()
 try:
  async with httpx.AsyncClient(timeout=3,trust_env=False) as c:r=await c.get(url)
  return {'online':r.status_code<500,'latency':round((time.perf_counter()-t)*1000)}
 except Exception:return {'online':False,'latency':None}
@app.get('/',response_class=HTMLResponse)
async def index(_=Depends(auth)):return Path(__file__).with_name('static').joinpath('dashboard.html').read_text(encoding='utf-8')
@app.get('/api/overview')
async def overview(_=Depends(auth)):
 stats,extra,ops,events,deliveries,services=await asyncio.gather(db.stats(),db.dashboard_overview(),db.list_recent_operations(),db.list_recent_events(),db.list_recent_deliveries(),asyncio.gather(check(settings.ollama_base_url+'/api/tags'),check(settings.whisper_base_url+'/health'),check(settings.agnes_base_url+'/api/concurrency'),check(settings.puter_base_url+'/health') if settings.puter_enabled else asyncio.sleep(0,result={'online':False,'disabled':True})))
 disk=shutil.disk_usage(Path.cwd());return {'stats':{**stats,**extra,'recoverable_checkpoints':len(stale_checkpoints())},'operations':ops,'events':events,'deliveries':deliveries,'services':dict(zip(('chat','speech_to_text','video','optional_ai'),services)),'queues':queue_snapshot(),'voices':voice_configuration_status(),'runtime':{'version':Path('VERSION').read_text().strip(),'python':platform.python_version(),'pid':os.getpid(),'uptime':int(time.time()-START),'disk_free':disk.free}}
@app.get('/health')
async def health():return {'status':'ok'}
