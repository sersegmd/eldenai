import http from 'node:http';
import { init } from '@heyputer/puter.js/src/init.cjs';
const token=process.env.PUTER_AUTH_TOKEN||'';
if(!token){console.error('[PUTER] PUTER_AUTH_TOKEN is missing');process.exit(2)}
const puter=init(token); const port=Number(process.env.PUTER_PORT||8770);
const json=(res,code,obj)=>{res.writeHead(code,{'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify(obj))};
const server=http.createServer(async(req,res)=>{
 if(req.method==='GET'&&req.url==='/health')return json(res,200,{status:'ok'});
 if(req.method!=='POST'||req.url!=='/chat')return json(res,404,{error:'not_found'});
 let raw='';req.on('data',c=>{raw+=c;if(raw.length>2_000_000)req.destroy()});
 req.on('end',async()=>{try{const body=JSON.parse(raw||'{}');const messages=Array.isArray(body.messages)?body.messages:[];const result=await puter.ai.chat(messages,{model:body.model||process.env.PUTER_MODEL||'gpt-5.4-nano',temperature:Number(body.temperature??0.7),normalize:true});let content=result?.message?.content??result?.text??result;if(Array.isArray(content))content=content.map(x=>x?.text||'').join('');return json(res,200,{text:String(content||'')})}catch(e){return json(res,500,{error:String(e?.message||e).slice(0,500)})}})
});server.listen(port,'127.0.0.1',()=>console.log(`[PUTER] intelligence router ready on 127.0.0.1:${port}`));
