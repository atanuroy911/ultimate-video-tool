/* Loopback-only server control shared by both native server managers. */
const http=require('http');
const https=require('https');

function localURL(value){
  const url=new URL(value);
  if(!['http:','https:'].includes(url.protocol)||!['127.0.0.1','localhost','[::1]'].includes(url.hostname)||url.username||url.password||url.pathname!=='/'||url.search||url.hash)throw new Error('The server manager can control only a local processing server.');
  return url.origin;
}
function request(base,route,method='GET'){
  const target=new URL(route,localURL(base));
  if(target.origin!==new URL(base).origin)throw new Error('Invalid local server request.');
  return new Promise((resolve,reject)=>{
    const req=(target.protocol==='https:'?https:http).request(target,{method,timeout:5000,headers:{'Content-Type':'application/json'}},res=>{
      let body='';res.setEncoding('utf8');res.on('data',part=>{body+=part;if(body.length>2e6)req.destroy(new Error('Server response too large.'));});
      res.on('end',()=>{let data;try{data=body?JSON.parse(body):{};}catch{return reject(new Error('The local server returned an unreadable response.'));}
        if(res.statusCode>=400)return reject(new Error(typeof data.detail==='string'?data.detail:`Server request failed (${res.statusCode}).`));resolve(data);});
    });
    req.on('timeout',()=>req.destroy(new Error('The local server did not answer in time.')));req.on('error',reject);req.end(method==='POST'?'{}':undefined);
  });
}
async function inspect(base){
  if(!base)return {running:false,addresses:[],name:'This computer'};
  try{
    const health=await request(base,'/api/health');
    if(!health||typeof health!=='object')throw new Error('Unexpected server response.');
    const info=await request(base,'/api/server');
    let gpu=null;                                                  // the graphics cards, when the server can say (an older one cannot, and then there is nothing to show)
    try{const g=await request(base,'/api/system/gpus');if(g&&Array.isArray(g.cards)&&typeof g.needs_choice==='boolean')gpu={cards:g.cards.length,needs_choice:g.needs_choice,allowed:g.cards.filter(c=>c.allowed).map(c=>c.name)};}catch{}
    return {running:true,name:info.name,addresses:info.addresses||[],url:localURL(base),gpu};
  }catch(e){return {running:false,addresses:[],url:localURL(base),reason:e.message};}
}
module.exports={localURL,request,inspect};
