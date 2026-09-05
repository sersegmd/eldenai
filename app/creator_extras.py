from __future__ import annotations
import asyncio,textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from .config import settings
from .ai_client import generate_publish_pack

def _font(size:int):
    candidates=[settings.caption_font_file,settings.caption_font_name,'C:/Windows/Fonts/arial.ttf','C:/Windows/Fonts/tahoma.ttf']
    for value in candidates:
        try:
            if value:return ImageFont.truetype(value,size)
        except Exception:pass
    return ImageFont.load_default()

def _make(source:Path,title:str,output:Path):
    image=Image.open(source).convert('RGB');image.thumbnail((1080,1920))
    canvas=Image.new('RGB',(1080,1920),(7,11,19));x=(1080-image.width)//2;y=(1920-image.height)//2;canvas.paste(image,(x,y))
    overlay=Image.new('RGBA',canvas.size,(0,0,0,0));draw=ImageDraw.Draw(overlay);draw.rectangle((0,1180,1080,1920),fill=(0,0,0,175))
    font=_font(76);lines=textwrap.wrap(title,width=22)[:3];text='\n'.join(lines)
    box=draw.multiline_textbbox((0,0),text,font=font,spacing=18,align='center',stroke_width=2);tw=box[2]-box[0]
    draw.multiline_text(((1080-tw)//2,1320),text,font=font,fill='white',spacing=18,align='center',stroke_width=3,stroke_fill='black')
    Image.alpha_composite(canvas.convert('RGBA'),overlay).convert('RGB').save(output,quality=95,subsampling=0)
    return output

async def create_thumbnail(source:Path,title:str,output:Path)->Path:return await asyncio.to_thread(_make,source,title,output)
async def publishing_pack(title:str,narration:str,platform:str,language:str)->str:return await generate_publish_pack(title,narration,platform,language)
