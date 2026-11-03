const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
const {createTransport}=require('./transport');const {WebSocket,WebSocketServer}=require('ws');
(async()=>{
 const temp=await fs.mkdtemp(path.join(os.tmpdir(),'uvt-client-transport-'));let transport;const upstream=http.createServer((req,res)=>{if(req.url==='/api/pair'){res.setHeader('Set-Cookie','vt_token=paired; HttpOnly; Secure; SameSite=Strict');res.end('{}');return;}if(req.url==='/api/health'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({source:'processing-server',cookie:req.headers.cookie||''}));return;}if(req.url.startsWith('/media/')){res.writeHead(206,{'Content-Range':'bytes 0-2/8'});res.end('vid');return;}res.end('THIS IS THE SERVER PAGE, NOT THE EDITOR');});const sockets=new WebSocketServer({server:upstream,path:'/ws'});sockets.on('connection',socket=>socket.on('message',data=>socket.send(data)));
 try{
  await fs.writeFile(path.join(temp,'index.html'),'<main>CLIENT EDITOR</main>');await new Promise(r=>upstream.listen(0,'127.0.0.1',r));transport=await createTransport({server:'http://127.0.0.1:'+upstream.address().port,dist:temp});
  assert.equal((await fetch(transport.origin+'/api/health')).status,403,'the native local session is required');
  const headers={cookie:'uvt_local_session='+transport.secret+'; vt_token=paired'};
  assert.match(await (await fetch(transport.origin+'/p/example',{headers})).text(),/CLIENT EDITOR/,'editor navigation must use the client bundle');
  const api=await (await fetch(transport.origin+'/api/health',{headers})).json();assert.equal(api.source,'processing-server');assert.equal(api.cookie.trim(),'vt_token=paired','the local session secret must never reach the processing server');
  const media=await fetch(transport.origin+'/media/test.mp4',{headers:{...headers,Range:'bytes=0-2'}});assert.equal(media.status,206);assert.equal(await media.text(),'vid');
  const pair=await fetch(transport.origin+'/api/pair',{method:'POST',headers});assert.match(pair.headers.get('set-cookie'),/HttpOnly/);assert.doesNotMatch(pair.headers.get('set-cookie'),/; Secure/);
  assert.equal((await fetch(transport.origin+'/api/health',{headers:{...headers,Origin:'https://other.example'}})).status,403);
  const message=await new Promise((resolve,reject)=>{const socket=new WebSocket(transport.origin.replace('http','ws')+'/ws',{headers});socket.once('error',reject);socket.once('open',()=>socket.send('live-preview'));socket.once('message',data=>{resolve(String(data));socket.close();});});assert.equal(message,'live-preview');
  console.log('Independent client: own editor, authenticated proxy, media ranges, pairing cookie, origin boundary and live WebSocket pass.');
 }finally{await transport?.close();for(const socket of sockets.clients)socket.terminate();await new Promise(r=>sockets.close(r));await new Promise(r=>upstream.close(r));if(!path.resolve(temp).startsWith(path.resolve(os.tmpdir())+path.sep))throw new Error('Unsafe test cleanup');await fs.rm(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exit(1);});
