from __future__ import annotations
import json,re
_INJECTION=re.compile(r'(ignore (all|previous) instructions|system prompt|developer message|اكشف.*التعليمات|تجاهل.*التعليمات)',re.I)
def sanitize_evidence(text):return _INJECTION.sub('[blocked instruction]',text.replace('\x00','')[:12000])
def extract_json_object(text):
 match=re.search(r'\{[\s\S]*\}',text)
 if not match:raise ValueError('No JSON object returned')
 value=json.loads(match.group(0))
 if not isinstance(value,dict):raise ValueError('Expected JSON object')
 return value
