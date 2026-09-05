from __future__ import annotations
import asyncio,json,shutil
from pathlib import Path

async def _exec(*args:str)->tuple[int,str]:
    p=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    out,err=await p.communicate();return p.returncode,(out+err).decode('utf-8',errors='replace')

async def probe_video(path:Path)->dict:
    ffprobe=shutil.which('ffprobe')
    if not ffprobe or not path.is_file() or path.stat().st_size<1000: raise RuntimeError('Invalid or missing video file')
    code,text=await _exec(ffprobe,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,pix_fmt,sample_aspect_ratio,duration','-of','json',str(path))
    if code: raise RuntimeError(text[-600:])
    data=json.loads(text);streams=data.get('streams') or []
    if not streams: raise RuntimeError('Video has no visual stream')
    return streams[0]

async def normalize_clip(source:Path,destination:Path,seconds:float)->Path:
    await probe_video(source);ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg: raise RuntimeError('FFmpeg is missing')
    vf='scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30,settb=AVTB,format=yuv420p'
    code,text=await _exec(ffmpeg,'-y','-stream_loop','-1','-i',str(source),'-an','-vf',vf,'-t',f'{max(.5,seconds):.3f}','-c:v','libx264','-preset','veryfast','-crf','22','-movflags','+faststart',str(destination))
    if code or not destination.is_file() or destination.stat().st_size<1000: raise RuntimeError('Clip normalization failed: '+text[-700:])
    await probe_video(destination);return destination
