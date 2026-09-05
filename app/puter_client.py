from __future__ import annotations
from .config import settings
class PuterUnavailable(RuntimeError): pass
async def puter_chat(messages:list[dict],temperature:float=0.7)->str:
    if not settings.puter_enabled: raise PuterUnavailable('Optional intelligence router is disabled')
    try:
        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.puter_timeout,connect=5),trust_env=False) as client:
            response=await client.post(f'{settings.puter_base_url}/chat',json={'messages':messages,'model':settings.puter_model,'temperature':temperature})
    except Exception as exc: raise PuterUnavailable('Optional intelligence router is unavailable') from exc
    if response.status_code>=400: raise PuterUnavailable(f'Intelligence router HTTP {response.status_code}')
    text=str(response.json().get('text') or '').strip()
    if not text: raise PuterUnavailable('Intelligence router returned an empty answer')
    return text
