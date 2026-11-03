const assert=require('node:assert/strict');
const http=require('node:http');
const {localURL,inspect,request}=require('./server-control');
(async()=>{
  for(const bad of ['http://192.168.1.2:8765','http://example.com','http://127.0.0.1:3/path','file:///tmp/a','http://user:pass@127.0.0.1:3','http://127.0.0.1:3/?token=abc'])assert.throws(()=>localURL(bad));
  let pairing=0;
  const server=http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');if(req.url==='/api/health')res.end('{}');else if(req.url==='/api/server')res.end(JSON.stringify({name:'Test server',addresses:['http://192.168.1.42:8790']}));else if(req.url==='/api/server/code'&&req.method==='POST'){pairing++;res.end('{"code":"test-code"}');}else {res.statusCode=403;res.end('{"detail":"Not allowed"}');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
  try{const state=await inspect(base);assert.equal(state.running,true);assert.equal(state.name,'Test server');assert.deepEqual(state.addresses,['http://192.168.1.42:8790']);assert.equal(pairing,0,'status must not generate or invalidate client codes');assert.equal((await request(base,'/api/server/code','POST')).code,'test-code');assert.equal(pairing,1);await assert.rejects(request(base,'/other'),/Not allowed/);assert.throws(()=>request(base,'http://example.com'),/Invalid local/);}finally{await new Promise(r=>server.close(r));}
  assert.equal((await inspect(base)).running,false);
  console.log('Server manager: loopback boundary, readiness, explicit pairing and offline handling pass.');
})().catch(e=>{console.error(e);process.exit(1);});
