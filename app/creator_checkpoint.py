from __future__ import annotations
import asyncio,json,shutil,time
from pathlib import Path

ROOT=Path('data/creator_checkpoints')
def _path(job_id:int)->Path: ROOT.mkdir(parents=True,exist_ok=True);return ROOT/f'{job_id}.json'
async def save(job_id:int,stage:str,**data)->None:
    payload={'job_id':job_id,'stage':stage,'updated_at':time.time(),**data};path=_path(job_id);tmp=path.with_suffix('.tmp')
    await asyncio.to_thread(tmp.write_text,json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
async def load(job_id:int)->dict|None:
    path=_path(job_id)
    if not path.is_file(): return None
    try:return json.loads(await asyncio.to_thread(path.read_text,encoding='utf-8'))
    except Exception:return None
async def complete(job_id:int)->None:
    _path(job_id).unlink(missing_ok=True)
def stale()->list[dict]:
    ROOT.mkdir(parents=True,exist_ok=True);result=[]
    for path in ROOT.glob('*.json'):
        try:result.append(json.loads(path.read_text(encoding='utf-8')))
        except Exception:pass
    return result
