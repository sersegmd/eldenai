from __future__ import annotations
import logging
from . import db
log=logging.getLogger('elden.operations')
async def event(source,name,detail='',*,level='info',operation_id=None,telegram_id=None,metadata=None):
    getattr(log,level if level in {'debug','info','warning','error','critical'} else 'info')('%s | %s | op=%s user=%s | %s',source,name,operation_id or '-',telegram_id or '-',detail)
    try: await db.log_system_event(level,source,name,detail,operation_id,telegram_id,metadata or {})
    except Exception: log.exception('Could not persist operation event')
async def stage(operation_id,source,name,progress,detail='',*,telegram_id=None,voice_profile=''):
    await db.update_operation(operation_id,stage=name,progress=max(0,min(100,progress)),detail=detail,voice_profile=voice_profile)
    await event(source,name,detail,operation_id=operation_id,telegram_id=telegram_id,metadata={'progress':progress,'voice_profile':voice_profile})
