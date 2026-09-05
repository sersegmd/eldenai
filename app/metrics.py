from __future__ import annotations
try:
 from prometheus_client import Counter,Histogram,generate_latest,CONTENT_TYPE_LATEST
 REQUESTS=Counter('elden_ai_requests_total','ELDEN AI requests',['kind','status']);LATENCY=Histogram('elden_ai_request_seconds','ELDEN AI latency',['kind']);SEARCHES=Counter('elden_ai_searches_total','Research decisions',['decision','status']);MODEL_FALLBACKS=Counter('elden_ai_model_fallbacks_total','Model fallback attempts',['status'])
except Exception:
 class N:
  def labels(self,*a,**k):return self
  def inc(self,*a,**k):pass
  def observe(self,*a,**k):pass
 REQUESTS=LATENCY=SEARCHES=MODEL_FALLBACKS=N();CONTENT_TYPE_LATEST='text/plain'
 def generate_latest():return b''
