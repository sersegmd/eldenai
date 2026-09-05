from __future__ import annotations
import logging
from .config import settings
log=logging.getLogger(__name__)
def record_generation(*,model,status,latency_ms,error=''):
 if not getattr(settings,'langfuse_enabled',False):return
 try:
  from langfuse import get_client
  client=get_client();create=getattr(client,'create_event',None)
  if callable(create):create(name='elden.openrouter',metadata={'model':model,'status':status,'latency_ms':latency_ms,'error':error[:200]})
 except Exception:log.debug('Langfuse telemetry unavailable',exc_info=True)
