const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {pathToFileURL}=require('node:url');
(async()=>{
 const handlers={},events={},sent=[];let window;let external=0;
 class Window{constructor(){window=this;this.webContents={setWindowOpenHandler(){},on(){},send:(name,value)=>sent.push({name,value})};}setMenu(){}loadFile(){}once(){}on(){}show(){}focus(){}isMinimized(){return false;}isDestroyed(){return false;}}
 class Tray{on(){}setContextMenu(){}setToolTip(){}destroy(){}}
 const electron={app:{getPath:()=>__dirname,getLoginItemSettings:()=>({openAtLogin:false}),on:(name,fn)=>events[name]=fn},BrowserWindow:Window,Tray,Menu:{buildFromTemplate:v=>v},nativeImage:{createFromPath:()=>({resize(){return {};}})},ipcMain:{handle:(name,fn)=>handlers[name]=fn},shell:{openExternal(){external++;throw new Error('No browser may open.');}},clipboard:{writeText(){}}};
 const module={exports:{}};const filename=path.join(__dirname,'server-manager.js');
 vm.runInNewContext(fs.readFileSync(filename,'utf8'),{module,exports:module.exports,__dirname,process,console,setInterval:()=>({unref(){}}),clearInterval(){},require:name=>name==='electron'?electron:name==='./server-control'?{inspect:async()=>({running:true,url:'http://127.0.0.1:8790',addresses:[]}),localURL:v=>v,request:async()=>({code:'test'})}:require(name)},{filename});
 module.exports.createServerManager({url:()=> 'http://127.0.0.1:8790',readLog:async()=> 'A local log',start:async()=>{},stop:async()=>{}});
 const event={sender:window.webContents,senderFrame:{url:pathToFileURL(path.join(__dirname,'server-manager.html')).href}};
 const engine=await handlers['server-manager:act'](event,'engine-settings');assert.equal(engine.url,'http://127.0.0.1:8790/manage?embedded=1');assert.equal(external,0);
 assert.equal((await handlers['server-manager:act'](event,'open-log')).log,'A local log');assert.equal(external,0);
 assert.throws(()=>handlers['server-manager:act']({...event,senderFrame:{url:engine.url}},'stop'),/Only the server manager/,'embedded engine pages must not get native process controls');
 const html=fs.readFileSync(path.join(__dirname,'server-manager.html'),'utf8');assert.match(html,/id="engine-frame"/);assert.match(html,/id="log-content"/);
  const elements={};for(const name of [...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]))elements[name]={hidden:['engine-screen','log-screen'].includes(name),src:'',textContent:'',disabled:false,classList:{toggle(){}}};
  const renderer={window:{serverManager:{state:()=>handlers['server-manager:state'](event),act:action=>handlers['server-manager:act'](event,action),onProgress(){}}},document:{getElementById:id=>elements[id],querySelectorAll:()=>Object.values(elements)},setInterval(){},console};vm.createContext(renderer);vm.runInContext(fs.readFileSync(path.join(__dirname,'server-manager-ui.js'),'utf8'),renderer);await new Promise(setImmediate);
  await renderer.act('engine-settings');assert.equal(elements['engine-screen'].hidden,false);assert.equal(elements.overview.hidden,true);assert.equal(elements['engine-frame'].src,engine.url);elements['engine-back'].onclick();assert.equal(elements.overview.hidden,false);assert.equal(elements['engine-screen'].hidden,true);
  await renderer.act('open-log');assert.equal(elements['log-screen'].hidden,false);assert.equal(elements['log-content'].textContent,'A local log');elements['log-back'].onclick();assert.equal(elements.overview.hidden,false);assert.equal(external,0);
 console.log('Contained server UI: internal engine/log views, no external browser, and native IPC boundary pass.');
})().catch(error=>{console.error(error);process.exit(1);});
