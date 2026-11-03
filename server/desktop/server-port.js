const net=require('net');
function freePort(preferred=0){return new Promise((resolve,reject)=>{const socket=net.createServer();socket.once('error',reject);socket.listen(preferred,'127.0.0.1',()=>{const port=socket.address().port;socket.close(()=>resolve(port));});});}
function occupied(port,host){return new Promise(resolve=>{const socket=net.connect({host,port});const finish=value=>{socket.destroy();resolve(value);};socket.once('connect',()=>finish(true));socket.once('error',e=>finish(!['ECONNREFUSED','EAFNOSUPPORT','ENETUNREACH','EADDRNOTAVAIL'].includes(e.code)));socket.setTimeout(800,()=>finish(true));});}
async function inUse(port){return (await Promise.all([occupied(port,'127.0.0.1'),occupied(port,'::1')])).some(Boolean);}
async function choosePort(preferred=0,required=false){
  // Windows can accept overlapping wildcard/loopback binds. An actual connection
  // check catches that conflict before Python's stricter bind fails later.
  if(preferred&&await inUse(preferred)){
    if(required){const error=new Error(`Port ${preferred} is already in use.`);error.code='EADDRINUSE';throw error;}
    preferred=0;
  }
  for(let attempt=0;attempt<8;attempt++){
    let port;try{port=await freePort(preferred);}catch(e){if(e.code!=='EADDRINUSE'||required)throw e;preferred=0;continue;}
    if(!await inUse(port))return port;
    preferred=0;
  }
  throw new Error('Could not find an available local server port.');
}
module.exports={freePort,choosePort,inUse};
