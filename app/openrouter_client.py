from __future__ import annotations
import asyncio,json,os,time
import aiohttp
from .config import settings
from .metrics import MODEL_FALLBACKS
from .llm_observability import record_generation
class OpenRouterError(RuntimeError):pass
class ChatResult(str):
 def __new__(cls,content,reasoning_details=None,model=''):
  obj=super().__new__(cls,content);obj.reasoning_details=reasoning_details;obj.model=model;return obj
 def as_message(self):
  value={'role':'assistant','content':str(self)}
  if self.reasoning_details is not None:value['reasoning_details']=self.reasoning_details
  return value
def _models():
 fallback=getattr(settings,'openrouter_fallback_models',os.getenv('OPENROUTER_FALLBACK_MODELS','openrouter/free'))
 return list(dict.fromkeys(x.strip() for x in [settings.openrouter_model,*fallback.split(',')] if x.strip()))
def _safe_error(status,raw):
 try:message=str(json.loads(raw).get('error',{}).get('message') or '')
 except Exception:message=''
 return f'OpenRouter HTTP {status}: {(message or "request failed")[:300]}'
async def _request(model,messages,temperature):
 headers={'Authorization':f'Bearer {settings.openrouter_api_key}','Content-Type':'application/json','X-OpenRouter-Title':'ELDEN AI'}
 if settings.openrouter_site_url:headers['HTTP-Referer']=settings.openrouter_site_url
 reasoning=getattr(settings,'openrouter_reasoning',os.getenv('OPENROUTER_REASONING','true').lower() in {'1','true','yes','on'})
 payload={'model':model,'messages':messages,'temperature':temperature,'reasoning':{'enabled':reasoning}}
 started=time.perf_counter()
 async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.openrouter_timeout,connect=15)) as client:
  async with client.post(settings.openrouter_base_url+'/chat/completions',headers=headers,json=payload) as response:
   raw=await response.text();latency=int((time.perf_counter()-started)*1000)
   if response.status>=400:record_generation(model=model,status=str(response.status),latency_ms=latency,error=_safe_error(response.status,raw));raise OpenRouterError(_safe_error(response.status,raw))
   data=await response.json(content_type=None)
 try:message=data['choices'][0]['message']
 except Exception as exc:raise OpenRouterError('OpenRouter returned an invalid response') from exc
 record_generation(model=model,status='ok',latency_ms=latency)
 return ChatResult((message.get('content') or '…').strip(),message.get('reasoning_details'),str(data.get('model') or model))
async def complete(messages,temperature=.7):
 if not settings.openrouter_api_key or settings.openrouter_api_key.startswith('PASTE_'):raise OpenRouterError('OPENROUTER_API_KEY is missing')
 errors=[]
 for index,model in enumerate(_models()):
  attempts=2 if index==0 else 1
  for attempt in range(attempts):
   try:return await _request(model,messages,temperature)
   except OpenRouterError as exc:
    errors.append(str(exc));status=next((x for x in (401,402,403,404,429,500,502,503,504) if f'HTTP {x}' in str(exc)),0)
    if status in {401,402}:raise
    if status in {403,404}:break
    if (status==429 or status>=500) and attempt+1<attempts:await asyncio.sleep(1.5*(attempt+1));continue
    break
   except (aiohttp.ClientError,asyncio.TimeoutError) as exc:
    errors.append(type(exc).__name__)
    if attempt+1<attempts:await asyncio.sleep(1.5);continue
    break
  MODEL_FALLBACKS.labels('attempt').inc()
 MODEL_FALLBACKS.labels('failed').inc();raise OpenRouterError('All configured language models are unavailable: '+' | '.join(errors[-3:]))
