const assert=require('node:assert/strict');
const net=require('net');
const {choosePort}=require('./server-port');
(async()=>{
  const other=net.createServer();await new Promise(r=>other.listen(0,'0.0.0.0',r));const occupied=other.address().port;
  try{const selected=await choosePort(occupied);assert.notEqual(selected,occupied);assert(selected>0);assert(other.listening,'another program must remain running');await assert.rejects(choosePort(occupied,true),e=>e.code==='EADDRINUSE');}finally{await new Promise(r=>other.close(r));}
  assert.equal(await choosePort(occupied),occupied);
  console.log('Server ports: occupied ports fall back automatically; explicit choices report conflicts; other programs remain running.');
})().catch(e=>{console.error(e);process.exit(1);});
