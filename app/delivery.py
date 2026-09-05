from __future__ import annotations
import asyncio,logging,mimetypes,shutil,uuid
from dataclasses import dataclass
from pathlib import Path
import httpx
from aiogram.types import FSInputFile
from . import db
from .config import settings
from .runtime import upload_limiter
from .observability import event
log=logging.getLogger(__name__)
@dataclass
class DeliveryResult: success:bool; delivery_id:str; message_id:int|None=None; error:str=''
def root():
 p=Path(settings.output_dir);p=p if p.is_absolute() else Path.cwd()/p;p.mkdir(parents=True,exist_ok=True);return p
def persist(source:Path,name:str):
 safe=''.join(c if c.isalnum() or c in '._- ' else '_' for c in name).strip() or 'ELDEN_file'; target=root()/f'{uuid.uuid4().hex[:10]}_{safe}';shutil.copy2(source,target);return target
def persist_bytes(data:bytes,name:str):
 target=root()/f'{uuid.uuid4().hex[:10]}_{name}';target.write_bytes(data);return target
async def _send(bot,chat,kind,path,name,caption):
 f=FSInputFile(path,filename=name);t=settings.telegram_upload_timeout
 if kind=='video': return await bot.send_video(chat,f,caption=caption or None,supports_streaming=True,request_timeout=t)
 if kind=='voice': return await bot.send_voice(chat,f,caption=caption or None,request_timeout=t)
 if kind=='audio': return await bot.send_audio(chat,f,caption=caption or None,title=Path(name).stem[:64],request_timeout=t)
 if kind=='photo': return await bot.send_photo(chat,f,caption=caption or None,request_timeout=t)
 return await bot.send_document(chat,f,caption=caption or None,request_timeout=t)
async def _fallback(chat,kind,path,name,caption):
 m,f={'video':('sendVideo','video'),'voice':('sendVoice','voice'),'audio':('sendAudio','audio'),'photo':('sendPhoto','photo')}.get(kind,('sendDocument','document'));url=f'https://api.telegram.org/bot{settings.bot_token}/{m}';data={'chat_id':str(chat),'caption':caption[:1000],'parse_mode':'HTML'}
 async with httpx.AsyncClient(timeout=httpx.Timeout(settings.telegram_upload_timeout,connect=30,write=settings.telegram_upload_timeout),transport=httpx.AsyncHTTPTransport(retries=2)) as client:
  with path.open('rb') as stream:r=await client.post(url,data=data,files={f:(name,stream,mimetypes.guess_type(name)[0] or 'application/octet-stream')})
 if r.status_code>=400: raise RuntimeError(f'Telegram HTTP {r.status_code}')
 x=r.json();
 if not x.get('ok'): raise RuntimeError(str(x.get('description')))
 return int(x['result']['message_id'])
async def attempt(bot,row):
 did=row['id'];path=Path(row['file_path']);attempts=int(row.get('attempts') or 0);op=row.get('operation_id')
 if not await db.claim_delivery(did):
  return DeliveryResult(False,did,error='already sending or already sent')
 if not path.is_file():
  await db.update_delivery(did,status='failed',error='file missing');return DeliveryResult(False,did,error='file missing')
 async with upload_limiter.slot():
  await event('delivery','upload_started',row['filename'],operation_id=op,telegram_id=row['telegram_id'])
  try:
   attempts+=1
   # One transport and one request only. This prevents a timeout in one client
   # from being followed by a second upload through another client.
   mid=await _fallback(row['telegram_id'],row['kind'],path,row['filename'],row.get('caption',''))
  except (httpx.ReadTimeout,httpx.WriteTimeout,httpx.RemoteProtocolError) as exc:
   # The server may have accepted the upload before the response was lost.
   # Never retry this ambiguous state automatically, otherwise users can get duplicates.
   err=f'upload result uncertain: {exc}'[:900]
   await db.update_delivery(did,status='uncertain',attempts=attempts,error=err)
   if op: await db.update_operation(op,status='delivery_uncertain',delivery_status='uncertain',error_code='telegram_result_uncertain',error=err)
   await event('delivery','upload_result_uncertain',err,level='warning',operation_id=op,telegram_id=row['telegram_id'])
   return DeliveryResult(False,did,error=err)
  except Exception as exc:
   err=str(exc)[:900];await db.update_delivery(did,status='failed',attempts=attempts,error=err)
   if op: await db.update_operation(op,status='waiting_delivery',delivery_status='pending_retry',error_code='telegram_upload',error=err)
   await event('delivery','upload_failed',err,level='error',operation_id=op,telegram_id=row['telegram_id'])
   return DeliveryResult(False,did,error=err)
  await db.update_delivery(did,status='sent',attempts=attempts,error='',telegram_message_id=mid)
  if op: await db.update_operation(op,status='completed',delivery_status='sent',progress=100)
  await event('delivery','upload_completed',row['filename'],operation_id=op,telegram_id=row['telegram_id'])
  return DeliveryResult(True,did,mid)

async def deliver_path(bot,chat,kind,source,name,caption='',operation_id=None):
 stored=await asyncio.to_thread(persist,Path(source),name);did=await db.register_delivery(operation_id,chat,kind,str(stored),name,caption,settings.delivery_retention_seconds)
 if operation_id: await db.update_operation(operation_id,generation_status='completed',delivery_status='pending',file_path=str(stored),file_size=stored.stat().st_size,stage='uploading')
 return await attempt(bot,{'id':did,'operation_id':operation_id,'telegram_id':chat,'kind':kind,'file_path':str(stored),'filename':name,'caption':caption,'attempts':0})
async def deliver_bytes(bot,chat,kind,data,name,caption='',operation_id=None):
 stored=await asyncio.to_thread(persist_bytes,data,name);did=await db.register_delivery(operation_id,chat,kind,str(stored),name,caption,settings.delivery_retention_seconds)
 if operation_id: await db.update_operation(operation_id,generation_status='completed',delivery_status='pending',file_path=str(stored),file_size=stored.stat().st_size,stage='uploading')
 return await attempt(bot,{'id':did,'operation_id':operation_id,'telegram_id':chat,'kind':kind,'file_path':str(stored),'filename':name,'caption':caption,'attempts':0})
async def worker(bot):
 while True:
  try:
   for row in await db.list_pending_deliveries(10): await attempt(bot,row)
  except asyncio.CancelledError: raise
  except Exception: log.exception('delivery worker failed')
  await asyncio.sleep(settings.delivery_retry_seconds)
