from __future__ import annotations
from dataclasses import dataclass
import re
import unicodedata

@dataclass(frozen=True)
class ResearchDecision:
    needed: bool
    query: str = ""
    reason: str = "internal_or_stable"

_EXPLICIT=("ابحث","بحث عن","فتش","تحقق من","search for","look up","recherche","cherche")
_CURRENT=("اليوم","حاليا","الان","اخر","احدث","الجديد","سعر","طقس","نتيجة","اخبار","2026","today","current","latest","news","price","weather","score","maintenant","aujourd'hui","actualité","prix","météo")
_INTERNAL=("وش تقدر","ماذا تستطيع","قدراتك","البوت","باقتي","حصتي","اشتراكي","اعدادات","/help","/plans","/voice","/menu","what can you do","my plan","quota","capabilities")
_TRANSFORM=("لخص","اختصر","ترجم","اعد صياغة","صحح","summarize","translate","rewrite","corrige","résume","traduis")
_GREETING=re.compile(r"^(سلام|السلام عليكم|مرحبا|اهلا|صباح الخير|مساء الخير|hi|hello|hey|bonjour|salut)[!؟?. ]*$",re.I)
_URL=re.compile(r"https?://\S+",re.I)

def _norm(text:str)->str:
    value=unicodedata.normalize("NFKC",text).lower().strip()
    return value.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي"}))

def decide_research(text:str,mode:str="quick")->ResearchDecision:
    value=_norm(text)
    if not value or _GREETING.match(value):return ResearchDecision(False,reason="conversation")
    if any(x in value for x in _INTERNAL):return ResearchDecision(False,reason="bot_or_account")
    if any(value.startswith(x) for x in _TRANSFORM) and len(value)>20:return ResearchDecision(False,reason="user_content")
    if mode=="research" or any(x in value for x in _EXPLICIT):return ResearchDecision(True,text.strip()[:500],"explicit_research")
    if _URL.search(text):return ResearchDecision(True,text.strip()[:500],"url_or_verification")
    if any(x in value for x in _CURRENT):return ResearchDecision(True,text.strip()[:500],"time_sensitive")
    return ResearchDecision(False,reason="stable_knowledge")
