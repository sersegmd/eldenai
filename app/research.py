from __future__ import annotations
import asyncio

async def research_context(query:str,language:str,limit:int=5)->str:
    def search():
        from ddgs import DDGS
        return list(DDGS().text(query,max_results=limit))
    try: rows=await asyncio.to_thread(search)
    except Exception:return ""
    parts=[]
    for i,row in enumerate(rows,1):
        title=str(row.get("title") or "");body=str(row.get("body") or "");url=str(row.get("href") or row.get("url") or "")
        if url:parts.append(f"[{i}] {title}\n{body[:700]}\nSource: {url}")
    return "\n\n".join(parts)
