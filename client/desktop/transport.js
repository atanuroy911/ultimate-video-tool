/* The client owns these UI files; only API/media requests go to its selected server. */
const http=require('http');
const https=require('https');
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const {WebSocket,WebSocketServer}=require('ws');
const ROUTES=/^\/(api|media|bundled|ws|v1|gw|mcp|\.well-known)(\/|\?|$)/;
function serverURL(value){const u=new URL(value);if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw new Error('Choose the processing server address.');return u.origin;}
function cookie(headers,name){return (headers.cookie||'').split(';').map(x=>x.trim()).find(x=>x.startsWith(name+'='))?.slice(name.length+1)||'';}
async function createTransport({server,dist,key=''}){
  const target=serverURL(server),secret=crypto.randomBytes(32).toString('hex');
  const root=path.resolve(dist),sockets=new Set(),upstreams=new Set();let origin='';
  const authorised=req=>cookie(req.headers,'uvt_local_session')===secret&&(!req.headers.origin||req.headers.origin===origin);
  const upstreamHeaders=req=>{const headers={...req.headers,host:new URL(target).host};delete headers.origin;delete headers.authorization;if(key)headers.authorization='Bearer '+key;delete headers.referer;for(const key of ['forwarded','x-forwarded-for','x-real-ip','cf-connecting-ip'])delete headers[key];headers.cookie=(req.headers.cookie||'').split(';').filter(c=>!c.trim().startsWith('uvt_local_session=')).join(';');return headers;};
  const app=http.createServer((req,res)=>{
    if(!authorised(req)){res.writeHead(403);res.end('Open Ultimate Video Tool to use this client.');return;}
    if(req.url==='/__client/connection'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({server:target,role:'client'}));return;}
    if(ROUTES.test(req.url)){
      const remote=new URL(target+req.url);
      const request=(remote.protocol==='https:'?https:http).request(remote,{method:req.method,headers:upstreamHeaders(req)},response=>{
        const headers={...response.headers};
        if(headers['set-cookie'])headers['set-cookie']=headers['set-cookie'].map(c=>c.replace(/;\s*Domain=[^;]+/ig,'').replace(/;\s*Secure\b/ig,''));
        res.writeHead(response.statusCode,headers);response.pipe(res);
      });
      request.on('error',()=>{if(!res.headersSent){res.writeHead(502,{'Content-Type':'application/json'});res.end(JSON.stringify({detail:'The processing server is unavailable. Open File → Change processing server, or start that server.'}));}else res.destroy();});
      req.on('aborted',()=>request.destroy());req.pipe(request);return;
    }
    if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);res.end();return;}
    let name;try{name=decodeURIComponent(new URL(req.url,origin).pathname);}catch{res.writeHead(400);res.end();return;}
    let file=path.resolve(root,'.'+name);
    if(file!==root&&!file.startsWith(root+path.sep)){res.writeHead(404);res.end();return;}
    if(!fs.existsSync(file)||!fs.statSync(file).isFile())file=path.join(root,'index.html');
    const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.webmanifest':'application/manifest+json','.woff2':'font/woff2'};
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Cache-Control':'no-cache'});if(req.method==='HEAD')res.end();else fs.createReadStream(file).on('error',()=>res.destroy()).pipe(res);
  });
  app.on('connection',socket=>{sockets.add(socket);socket.on('close',()=>sockets.delete(socket));});
  const ws=new WebSocketServer({noServer:true});
  app.on('upgrade',(req,socket,head)=>{
    if(!authorised(req)||!/^\/ws(\/|\?|$)/.test(req.url)){socket.destroy();return;}
    const headers=upstreamHeaders(req);for(const name of Object.keys(headers))if(name.startsWith('sec-websocket-')||['connection','upgrade'].includes(name))delete headers[name];
    const remote=new WebSocket(target.replace(/^http/,'ws')+req.url,{headers});upstreams.add(remote);
    remote.once('error',()=>socket.destroy());remote.once('close',()=>{upstreams.delete(remote);socket.destroy();});
    remote.once('open',()=>ws.handleUpgrade(req,socket,head,local=>{
      local.on('message',(data,binary)=>{if(remote.readyState===WebSocket.OPEN)remote.send(data,{binary});});remote.on('message',(data,binary)=>{if(local.readyState===WebSocket.OPEN)local.send(data,{binary});});local.on('close',()=>remote.close());local.on('error',()=>remote.close());remote.on('close',()=>local.close());
    }));
  });
  await new Promise((resolve,reject)=>{app.once('error',reject);app.listen(0,'127.0.0.1',resolve);});origin=`http://127.0.0.1:${app.address().port}`;
  return {origin,secret,server:target,close:async()=>{for(const remote of upstreams)remote.terminate();for(const socket of sockets)socket.destroy();ws.close();await new Promise(resolve=>app.close(resolve));}};
}
module.exports={createTransport,serverURL};
