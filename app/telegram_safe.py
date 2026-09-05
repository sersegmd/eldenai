from __future__ import annotations
import logging
from typing import Any
from aiogram.exceptions import TelegramBadRequest,TelegramNetworkError
from aiogram.types import CallbackQuery,InlineKeyboardMarkup,Message
log=logging.getLogger(__name__)
async def safe_callback_answer(callback:CallbackQuery,text:str|None=None,*,show_alert:bool=False,**kwargs:Any)->bool:
 try: await callback.answer(text=text,show_alert=show_alert,**kwargs);return True
 except TelegramBadRequest as exc:
  value=str(exc).lower()
  if any(x in value for x in ('query is too old','query id is invalid','response timeout expired')): return False
  raise
 except TelegramNetworkError:return False
async def safe_edit_text(message:Message|None,text:str,*,reply_markup:InlineKeyboardMarkup|None=None)->bool:
 if message is None:return False
 try: await message.edit_text(text,reply_markup=reply_markup);return True
 except TelegramBadRequest as exc:
  if any(x in str(exc).lower() for x in ('message is not modified','message to edit not found',"message can't be edited")):return False
  raise
 except TelegramNetworkError:return False
async def safe_delete_message(message:Message|None)->bool:
 if message is None:return False
 try:await message.delete();return True
 except (TelegramBadRequest,TelegramNetworkError):return False
