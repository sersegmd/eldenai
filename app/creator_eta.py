from __future__ import annotations

def estimate_seconds(mode:str,scenes:int)->int:
 base=75+max(1,scenes)*28
 animated=0 if mode=='fast' else max(1,(scenes+1)//2) if mode=='balanced' else scenes
 return base+animated*95

def label(seconds:int)->str:
 minutes=max(1,round(seconds/60));return f'حوالي {minutes} دقيقة'
