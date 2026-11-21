/* The server window's "Computers on my network can connect without the key" switch and "Copy key": native actions that only the manager's own page can use,
   and a key that is copied to the clipboard without ever reaching the page. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),http=require('node:http');
const {pathToFileURL}=require('node:url');
(async()=>{
  const calls=[];let trust=false;
  const server=http.createServer((req,res)=>{
    let body='';req.on('data',d=>body+=d);req.on('end',()=>{
      res.setHeader('Content-Type','application/json');
      if(req.url==='/api/health')return res.end('{}');
      if(req.url==='/api/server')return res.end(JSON.stringify({name:'Test',addresses:['http://192.168.1.42:8790'],trust_network:trust}));
      if(req.url==='/api/system/gpus')return res.end('{}');
      if(req.url==='/api/server/trust-network'&&req.method==='POST'){calls.push(JSON.parse(body));trust=JSON.parse(body).on;return res.end(JSON.stringify({trust_network:trust}));}
      if(req.url==='/api/server/key'&&req.method==='GET')return res.end(JSON.stringify({key:'secret-key-for-the-test'}));
      res.statusCode=404;res.end('{"detail":"no"}');
    });
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
  const control=require('./server-control');
  try{
    assert.equal((await control.inspect(base)).trust,false);
    await control.request(base,'/api/server/trust-network','POST',{on:true});
    assert.deepEqual(calls,[{on:true}],'the body reaches the server');assert.equal((await control.inspect(base)).trust,true);
    await control.request(base,'/api/server/trust-network','POST');assert.deepEqual(calls[1],{},'a POST without a body still sends valid JSON');

    // the window: native actions, only from its own page
    const handlers={};let clip='';let window;
    class Window{constructor(){window=this;this.webContents={setWindowOpenHandler(){},on(){},send(){}};}setMenu(){}loadFile(){}once(){}on(){}show(){}focus(){}isMinimized(){return false;}isDestroyed(){return false;}}
    class Tray{on(){}setContextMenu(){}setToolTip(){}destroy(){}}
    const electron={app:{getPath:()=>__dirname,getLoginItemSettings:()=>({openAtLogin:false}),on(){}},BrowserWindow:Window,Tray,Menu:{buildFromTemplate:v=>v},nativeImage:{createFromPath:()=>({resize(){return {};}})},ipcMain:{handle:(name,fn)=>handlers[name]=fn},shell:{openExternal(){throw new Error('No browser may open.');}},clipboard:{writeText:v=>{clip=v;}}};
    const module={exports:{}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'server-manager.js'),'utf8'),{module,exports:module.exports,__dirname,process,console,setInterval:()=>({unref(){}}),clearInterval(){},require:name=>name==='electron'?electron:name==='./server-control'?control:require(name)});
    module.exports.createServerManager({url:()=>base,readLog:async()=>'',start:async()=>{},stop:async()=>{}});
    const page=pathToFileURL(path.join(__dirname,'server-manager.html')).href;
    const own={sender:window.webContents,senderFrame:{url:page}};
    trust=false;calls.length=0;
    await handlers['server-manager:act'](own,'trust-on');assert.deepEqual(calls,[{on:true}]);
    assert.equal((await handlers['server-manager:state'](own)).trust,true);
    await handlers['server-manager:act'](own,'trust-off');assert.deepEqual(calls[1],{on:false});
    await handlers['server-manager:act'](own,'copy-key');assert.equal(clip,'secret-key-for-the-test','the key is copied');
    assert.ok(!JSON.stringify(await handlers['server-manager:state'](own)).includes('secret-key'),'the key never reaches the page');
    for(const action of ['trust-on','trust-off','copy-key'])assert.throws(()=>handlers['server-manager:act']({...own,senderFrame:{url:base+'/manage?embedded=1'}},action),/Only the server manager/,'an embedded engine page cannot use '+action);

    // the page: the switch asks first, and turning it off needs no question
    const html=fs.readFileSync(path.join(__dirname,'server-manager.html'),'utf8');
    for(const id of ['copy-key','trust','trust-note','trust-confirm','trust-yes','trust-no'])assert.match(html,new RegExp(`id="${id}"`),id);
    assert.match(html,/id="trust-confirm"[^>]*hidden/,'the warning starts hidden');
    assert.match(html,/Leave this off unless this is your own home or office network/);
    console.log('Server window: network-trust switch, copy key, and the native boundary pass.');
  }finally{server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
