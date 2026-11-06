const assert=require('node:assert/strict');
const http=require('node:http');
const {localURL,inspect,request}=require('./server-control');
(async()=>{
  for(const bad of ['http://192.168.1.2:8765','http://example.com','http://127.0.0.1:3/path','file:///tmp/a','http://user:pass@127.0.0.1:3','http://127.0.0.1:3/?token=abc'])assert.throws(()=>localURL(bad));
  let actions=0,gpus=null;
  const server=http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');if(req.url==='/api/health')res.end('{}');else if(req.url==='/api/server')res.end(JSON.stringify({name:'Test server',addresses:['http://192.168.1.42:8790']}));else if(req.url==='/api/server/autostart'&&req.method==='POST'){actions++;res.end('{"autostart":true}');}else if(req.url==='/api/system/gpus'&&gpus)res.end(JSON.stringify(gpus));else {res.statusCode=403;res.end('{"detail":"Not allowed"}');}});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
  try{const state=await inspect(base);assert.equal(state.running,true);assert.equal(state.name,'Test server');assert.deepEqual(state.addresses,['http://192.168.1.42:8790']);assert.equal(actions,0,'status must not change anything on the server');assert.equal(state.gpu,null,'an older server cannot say anything about graphics cards: nothing is shown');gpus={cards:[{name:'Tesla V100',allowed:false},{name:'NVIDIA GeForce RTX 3060',allowed:true}],needs_choice:true};assert.deepEqual((await inspect(base)).gpu,{cards:2,needs_choice:true,allowed:['NVIDIA GeForce RTX 3060']});gpus={cards:'broken'};assert.equal((await inspect(base)).gpu,null,'an answer in a shape that is not understood shows nothing');gpus={cards:[{name:'Tesla V100',allowed:true}],needs_choice:false};assert.deepEqual((await inspect(base)).gpu,{cards:1,needs_choice:false,allowed:['Tesla V100']});assert.equal((await request(base,'/api/server/autostart','POST')).autostart,true);assert.equal(actions,1);await assert.rejects(request(base,'/other'),/Not allowed/);assert.throws(()=>request(base,'http://example.com'),/Invalid local/);}finally{await new Promise(r=>server.close(r));}
  assert.equal((await inspect(base)).running,false);
  console.log('Server manager: loopback boundary, readiness, graphics cards (none for an older server), explicit actions and offline handling pass.');
})().catch(e=>{console.error(e);process.exit(1);});
