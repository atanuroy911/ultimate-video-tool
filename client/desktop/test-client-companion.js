const assert=require('assert');
const http=require('http');
const {WebSocketServer}=require('ws');
const {ClientCompanion}=require('./client-companion');
const codex=require('./codex-runner');
const wait=async predicate=>{for(let i=0;i<100;i++){if(predicate())return;await new Promise(r=>setTimeout(r,30));}throw new Error('Timed out');};
(async()=>{
  const upstream=http.createServer();await new Promise(r=>upstream.listen(0,'127.0.0.1',r));
  const wss=new WebSocketServer({server:upstream});let connection;const messages=[],runs=[];
  wss.on('connection',(sock,request)=>{assert.equal(request.headers.authorization,'Bearer test-token');connection=sock;sock.on('message',raw=>messages.push(JSON.parse(raw)));});
  const runner={status:()=>({found:true,logged_in:true,version:'test'}),run:async task=>{runs.push(task);return {ok:true};}};
  const companion=new ClientCompanion({runner,codex:runner});
  try{
    await companion.start();const status=await fetch(companion.info().address+'/status');assert.equal(status.status,401);
    const good=await fetch(companion.info().address+'/status',{headers:{Authorization:'Bearer '+companion.key}});assert.equal(good.status,200);
    const server=`http://127.0.0.1:${upstream.address().port}`;companion.select({server,token:'test-token'});
    await wait(()=>messages.filter(m=>m.type==='director').length===2);
    assert.deepEqual(messages.filter(m=>m.type==='director').map(m=>m.director),['claude','codex']);
    connection.send(JSON.stringify({type:'direct',request:'r1',assistant:'codex',prompt:'Test',project:'p1'}));
    await wait(()=>messages.some(m=>m.type==='director_done'));
    assert.equal(runs[0].server,server);assert.equal(runs[0].token,'test-token');assert.equal(runs[0].prompt,'Test');
    companion.select(null);assert.equal(companion.info().server,'');
    const args=codex.args(server,'test-token');assert(args.includes('--ignore-user-config'));assert(args.includes('read-only'));assert(!args.includes('--dangerously-bypass-approvals-and-sandbox'));
    console.log('Client companion: authenticated local service, Claude/Codex registration, remote MCP routing and disconnect pass.');
  }finally{companion.close();for(const sock of wss.clients)sock.terminate();wss.close();upstream.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
