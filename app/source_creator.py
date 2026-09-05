from __future__ import annotations
import asyncio,re
from io import BytesIO
from pathlib import Path
import httpx
from aiogram import F,Router
from aiogram.filters import Command
from aiogram.types import Message
from .creator import start_creator_request
from .document_context import extract_document_text

router=Router(name='source-to-reel');pending:set[int]=set()
async def _url_text(url:str)->str:
 async with httpx.AsyncClient(timeout=30,follow_redirects=True,trust_env=False) as c:r=await c.get(url,headers={'User-Agent':'ELDEN-AI/6.3'});r.raise_for_status();raw=r.text
 raw=re.sub(r'(?is)<(script|style).*?>.*?</\\1>',' ',raw);raw=re.sub(r'(?s)<[^>]+>',' ',raw);return ' '.join(raw.split())[:30000]
@router.message(Command('article'))
@router.message(F.text.in_({'📰 مقال إلى ريلز','📰 Article to Reel','📰 Article en Reel'}))
async def begin(message:Message):pending.add(message.from_user.id);await message.answer('أرسل رابط المقال أو ملف PDF/DOCX/TXT وسأحوّله إلى ريلز.')
@router.message(lambda m:bool(m.from_user and m.from_user.id in pending),F.text)
async def text_source(message:Message):
 pending.discard(message.from_user.id);text=message.text.strip()
 if text.startswith(('http://','https://')):
  try:text=await _url_text(text)
  except Exception:return await message.answer('❌ تعذر قراءة الرابط.')
 await start_creator_request(message,'حوّل هذا المصدر إلى ريلز احترافي بهوك قوي مع الحفاظ على الحقائق:\n'+text,'dz','reel','balanced')
@router.message(lambda m:bool(m.from_user and m.from_user.id in pending),F.document)
async def file_source(message:Message):
 pending.discard(message.from_user.id);doc=message.document
 if doc.file_size and doc.file_size>12*1024*1024:return await message.answer('الملف أكبر من الحد المسموح.')
 b=BytesIO();await message.bot.download(doc,destination=b)
 try:text=await asyncio.to_thread(extract_document_text,b.getvalue(),doc.file_name or '',doc.mime_type or '')
 except Exception:return await message.answer('❌ تعذر قراءة الملف.')
 if not text.strip():return await message.answer('❌ لم أجد نصاً قابلاً للقراءة.')
 await start_creator_request(message,'حوّل هذا المصدر إلى ريلز احترافي بهوك قوي مع الحفاظ على الحقائق:\n'+text[:30000],'dz','reel','balanced')
