from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from .config import settings

class TrackedLimiter:
    def __init__(self,name:str,limit:int): self.name=name; self.limit=max(1,int(limit)); self.sem=asyncio.Semaphore(self.limit); self.active=0; self.waiting=0
    @asynccontextmanager
    async def slot(self):
        self.waiting+=1
        try: await self.sem.acquire()
        finally: self.waiting=max(0,self.waiting-1)
        self.active+=1
        try: yield
        finally: self.active=max(0,self.active-1); self.sem.release()
    def snapshot(self): return {'name':self.name,'limit':self.limit,'active':self.active,'waiting':self.waiting}
creator_limiter=TrackedLimiter('creator',settings.creator_concurrency)
image_limiter=TrackedLimiter('images',settings.image_concurrency)
tts_limiter=TrackedLimiter('speech',settings.tts_concurrency)
music_limiter=TrackedLimiter('music',settings.music_concurrency)
upload_limiter=TrackedLimiter('uploads',settings.upload_concurrency)
def queue_snapshot(): return [x.snapshot() for x in (creator_limiter,image_limiter,tts_limiter,music_limiter,upload_limiter)]
