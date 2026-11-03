/* Small native client service. No Python, models or project files live here. */
const http = require('http');
const crypto = require('crypto');
const os = require('os');
const WebSocket = require('ws');

class ClientCompanion {
  constructor({runner, codex, log=()=>{}}) {
    this.runners={claude:runner,codex};this.log=log;this.key=crypto.randomBytes(32).toString('hex');
    this.generation=0;this.socket=null;this.timer=null;this.target=null;this.active=false;
  }
  async start() {
    this.http=http.createServer((req,res)=>{
      const expected=Buffer.from(`Bearer ${this.key}`),actual=Buffer.from(req.headers.authorization||'');
      if(expected.length!==actual.length||!crypto.timingSafeEqual(expected,actual)){res.writeHead(401);return res.end();}
      if(req.method!=='GET'||req.url!=='/status'){res.writeHead(404);return res.end();}
      res.setHeader('Content-Type','application/json');res.end(JSON.stringify(this.info()));
    });
    await new Promise((resolve,reject)=>{this.http.once('error',reject);this.http.listen(0,'127.0.0.1',resolve);});
    return this.info();
  }
  info(){return {role:'client-companion',address:this.http?`http://127.0.0.1:${this.http.address().port}`:'',server:this.target?.server||'',connected:this.socket?.readyState===WebSocket.OPEN,busy:this.active};}
  select(target) {
    this.generation++;this.abort?.abort();clearTimeout(this.timer);clearInterval(this.statusTimer);this.socket?.close();this.socket=null;this.target=target;
    if(target)this.connect(this.generation);
  }
  connect(generation) {
    if(generation!==this.generation||!this.target)return;
    const target=this.target,url=new URL('/ws',target.server);url.protocol=url.protocol==='https:'?'wss:':'ws:';
    const sock=new WebSocket(url,{headers:target.token?{Authorization:`Bearer ${target.token}`}:{}});this.socket=sock;
    const send=value=>{if(sock.readyState===WebSocket.OPEN)sock.send(JSON.stringify(value));};
    const refresh=async()=>{
      if(this.checkingStatus)return;this.checkingStatus=true;
      try{
      for(const [kind,runner] of Object.entries(this.runners)) {
        if(!runner)continue;
        try {const s=await runner.status();send({type:'director',director:kind,device_name:os.hostname(),version:s.version,logged_in:s.found&&s.logged_in});}
        catch(e){this.log(`${kind} status: ${e.message}`);}
      }
      }finally{this.checkingStatus=false;}
    };
    sock.on('open',()=>{refresh();clearInterval(this.statusTimer);this.statusTimer=setInterval(refresh,20000);this.statusTimer.unref?.();});
    sock.on('message',async raw=>{
      let task;try{task=JSON.parse(String(raw));}catch{return;}
      if(task.type!=='direct'||generation!==this.generation)return;
      if(this.active){send({type:'director_done',request:task.request,ok:false,error:'This computer is already directing a video.'});return;}
      const runner=this.runners[task.assistant||'claude'];if(!runner)return;
      this.active=true;
      this.abort=new AbortController();
      try {const result=await runner.run({prompt:task.prompt,server:target.server,token:target.token,mcp:target.mcp,signal:this.abort.signal},message=>send({type:'director_log',request:task.request,project:task.project,message}));send({type:'director_done',request:task.request,...result});}
      catch(e){send({type:'director_done',request:task.request,ok:false,error:e.message});}
      finally{this.active=false;}
    });
    sock.on('error',e=>this.log(`Companion connection: ${e.message}`));
    sock.on('close',()=>{if(generation===this.generation){clearInterval(this.statusTimer);this.timer=setTimeout(()=>this.connect(generation),2000);}});
  }
  close(){this.select(null);this.http?.close();}
}
module.exports={ClientCompanion};
