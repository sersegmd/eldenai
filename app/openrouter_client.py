from __future__ import annotations
import aiohttp
from .config import settings

class OpenRouterError(RuntimeError): pass

class ChatResult(str):
    def __new__(cls, content: str, reasoning_details=None):
        obj=super().__new__(cls,content);obj.reasoning_details=reasoning_details;return obj
    def as_message(self):
        value={"role":"assistant","content":str(self)}
        if self.reasoning_details is not None:value["reasoning_details"]=self.reasoning_details
        return value

async def complete(messages:list[dict],temperature:float=.7)->ChatResult:
    if not settings.openrouter_api_key or settings.openrouter_api_key.startswith("PASTE_"):
        raise OpenRouterError("OPENROUTER_API_KEY is missing")
    headers={"Authorization":f"Bearer {settings.openrouter_api_key}","Content-Type":"application/json","X-OpenRouter-Title":"ELDEN AI"}
    if settings.openrouter_site_url:headers["HTTP-Referer"]=settings.openrouter_site_url
    payload={"model":settings.openrouter_model,"messages":messages,"temperature":temperature,"reasoning":{"enabled":True}}
    timeout=aiohttp.ClientTimeout(total=settings.openrouter_timeout,connect=15)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        async with client.post(settings.openrouter_base_url+"/chat/completions",headers=headers,json=payload) as response:
            raw=await response.text()
            if response.status>=400:raise OpenRouterError(f"OpenRouter HTTP {response.status}: {raw[:500]}")
            data=await response.json(content_type=None)
    try:message=data["choices"][0]["message"]
    except Exception as exc:raise OpenRouterError(f"Invalid OpenRouter response: {raw[:500]}") from exc
    return ChatResult((message.get("content") or "…").strip(),message.get("reasoning_details"))
