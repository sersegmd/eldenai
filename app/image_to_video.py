from __future__ import annotations
import asyncio,tempfile
from pathlib import Path
from aiogram import F,Router
from aiogram.filters import Command
from aiogram.types import Message
from . import db
from .delivery import deliver_path
from .scene_animator import SceneAnimator
from .telegram_safe import safe_edit_text,safe_delete_message

router=Router(name='image-to-video');pending:set[int]=set()
@router.message(Command('animate'))
@router.message(F.text.in_({'🎞 تحريك صورة','🎞 Animate image','🎞 Animer une image'}))
async def begin(message:Message):
 pending.add(message.from_user.id);await message.answer('🖼 أرسل الصورة مع وصف الحركة في التعليق. الأفضل إرسالها كملف للحفاظ على الجودة.')

def _image_message(message:Message)->bool:
 return bool(message.photo or (message.document and (message.document.mime_type or '').startswith('image/')))

@router.message(lambda message:_image_message(message) and bool(message.from_user and (message.from_user.id in pending or (message.caption and any(x in message.caption.lower() for x in ("حرك","animate","animer"))))))
async def animate_image(message:Message):
 if message.from_user.id not in pending and not (message.caption and any(x in message.caption.lower() for x in ('حرك','animate','animer'))):return
 pending.discard(message.from_user.id);status=await message.answer('🎞 جاري تحريك الصورة…');op=await db.create_operation(message.from_user.id,'image_to_video','')
 try:
  source=message.document or message.photo[-1];suffix=Path(getattr(source,'file_name','') or '.jpg').suffix or '.jpg'
  with tempfile.TemporaryDirectory(prefix='elden_i2v_') as folder:
   root=Path(folder);image=root/f'input{suffix}';await message.bot.download(source,destination=image)
   prompt=(message.caption or 'Subtle cinematic camera movement and natural subject motion').strip();scene={'motion_prompt':prompt,'visual_prompt':prompt}
   output=root/'animated.mp4';await SceneAnimator().animate(0,image,scene,5,output)
   result=await deliver_path(message.bot,message.chat.id,'video',output,'ELDEN_Animated_Image.mp4','✅ تم تحريك الصورة بنجاح.',op)
   if result.success:await safe_delete_message(status)
   else:await safe_edit_text(status,'✅ تم إنشاء الفيديو، لكن تعذر تأكيد الإرسال ولن يتكرر تلقائياً.')
 except Exception as exc:
  await db.update_operation(op,status='failed',error=str(exc),error_code='image_to_video');await safe_edit_text(status,'❌ تعذر تحريك الصورة حالياً.')
