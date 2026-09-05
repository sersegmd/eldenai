from __future__ import annotations
import asyncio,os,time
from dataclasses import dataclass
import aiohttp
from tenacity import retry,retry_if_exception_type,stop_after_attempt,wait_exponential_jitter
from .config import settings
from .smart_research import decide_research,ResearchDecision
@dataclass(frozen=True)
class SearchResult:
    title:str;snippet:str;url:str
_CACHE={}
@retry(stop=stop_after_attempt(2),wait=wait_exponential_jitter(initial=.4,max=2),retry=retry_if_exception_type((aiohttp.ClientError,asyncio.TimeoutError)),reraise=True)
async def _searxng(query,limit):
    url=getattr(settings,'searxng_url',os.getenv('SEARXNG_URL','')).rstrip('/')
    if not url:return []
    timeout=aiohttp.ClientTimeout(total=getattr(settings,'search_timeout',int(os.getenv('SEARCH_TIMEOUT','12'))))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url+'/search',params={'q':query,'format':'json','language':'all','safesearch':1}) as response:
            response.raise_for_status();data=await response.json(content_type=None)
    return [SearchResult(str(x.get('title') or ''),str(x.get('content') or '')[:700],str(x.get('url') or '')) for x in data.get('results',[])[:limit] if x.get('url')]
async def _ddgs(query,limit):
    def run():
        from ddgs import DDGS
        return [SearchResult(str(x.get('title') or ''),str(x.get('body') or '')[:700],str(x.get('href') or x.get('url') or '')) for x in DDGS().text(query,max_results=limit)]
    try:return await asyncio.wait_for(asyncio.to_thread(run),getattr(settings,'search_timeout',12))
    except Exception:return []
async def search_web(query,limit=None):
    limit=max(1,min(limit or getattr(settings,'search_max_results',5),8));key=query.casefold().strip();cached=_CACHE.get(key)
    if cached and time.monotonic()-cached[0]<getattr(settings,'search_cache_seconds',600):return cached[1]
    try:rows=await _searxng(query,limit)
    except Exception:rows=[]
    if not rows:rows=await _ddgs(query,limit)
    seen=set();clean=[]
    for row in rows:
        url=row.url.split('#',1)[0]
        if url and url not in seen:seen.add(url);clean.append(SearchResult(row.title,row.snippet,url))
    _CACHE[key]=(time.monotonic(),clean[:limit]);return clean[:limit]
class ResearchContext(tuple):
    def __new__(cls,decision,text):return super().__new__(cls,(decision,text))
    def __bool__(self):return bool(self[1])
    def __radd__(self,left):return left+self[1]
async def research_context(query,language,limit=None,mode='quick'):
    decision=decide_research(query,mode)
    if not decision.needed:return ResearchContext(decision,'')
    rows=await search_web(decision.query,limit)
    return ResearchContext(decision,'\n\n'.join(f'[{i}] {x.title}\n{x.snippet}\nSource: {x.url}' for i,x in enumerate(rows,1)))
