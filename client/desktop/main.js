/* Independent editor client: local UI + assistant companion, selected server API. */
const {app,BrowserWindow,Menu,ipcMain,shell,session,dialog}=require('electron');
const path=require('path'),fs=require('fs'),crypto=require('crypto');
const {Worker}=require('worker_threads');
const discover=require('./discover'),assistants=require('./assistants');
const director=require('./director-runner'),codex=require('./codex-runner');
const {ClientCompanion}=require('./client-companion'),{createTransport,serverURL}=require('./transport');
app.setPath('userData',(!app.isPackaged&&process.env.UVT_DEV_HOME)?path.join(process.env.UVT_DEV_HOME,'client'):path.join(app.getPath('appData'),'Video Tool'));
let win=null,chooser=null,transport=null,selected='',selectedSession=null,companion=null,changing=false;
const home=app.getPath('userData'),connectionFile=path.join(home,'connection.json');
fs.mkdirSync(home,{recursive:true});
const log=message=>fs.appendFileSync(path.join(home,'desktop.log'),`[${new Date().toISOString()}] ${message}\n`);
if(!app.requestSingleInstanceLock()){app.quit();process.exit(0);}
app.on('second-instance',()=>{const window=win||chooser;if(window){window.show();window.focus();}});
function status(kind){return new Promise(resolve=>{const worker=new Worker(path.join(__dirname,'assistant-status-worker.js'),{workerData:{kind}});const timer=setTimeout(()=>{worker.terminate();resolve({found:false,logged_in:false,reason:'Assistant check timed out.'});},25000);worker.once('message',value=>{clearTimeout(timer);resolve(value);});worker.once('error',error=>{clearTimeout(timer);resolve({found:false,logged_in:false,reason:error.message});});});}
function chooseServer(){
  if(chooser&&!chooser.isDestroyed()){chooser.show();chooser.focus();return;}
  chooser=new BrowserWindow({width:580,height:700,resizable:true,minWidth:500,minHeight:580,title:'Choose a processing server',webPreferences:{preload:path.join(__dirname,'preload.js'),contextIsolation:true,sandbox:true}});
  chooser.setMenu(null);chooser.loadFile(path.join(__dirname,'connect.html'));chooser.on('closed',()=>{chooser=null;if(!win&&!changing)app.quit();});
}
async function attach(){
  if(!selectedSession||!selected)return;
  const target=selected,active=selectedSession,localOrigin=transport?.origin;
  let token=(await active.cookies.get({url:localOrigin})).find(c=>c.name==='vt_token')?.value||'';
  if(!token&&['127.0.0.1','localhost','[::1]'].includes(new URL(target).hostname)){
    try{const response=await active.fetch(target+'/api/directors/token',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(response.ok)token=(await response.json()).token;}catch(e){log(e.message);}
  }
  if(selected!==target||selectedSession!==active)return;
  companion.select(token?{server:target,token}:null);
}
async function connect(address){
  const found=await discover.probe(address);if(!found)throw new Error('The processing server is not answering. Start it or choose another server.');
  const target=serverURL(found.url);
  const dist=app.isPackaged?path.join(process.resourcesPath,'studio'):path.resolve(__dirname,'../studio/dist');
  if(!fs.existsSync(path.join(dist,'index.html')))throw new Error('Build the client UI first: npm --prefix client/studio run build.');
  changing=true;
  try{
    if(win&&!win.isDestroyed()){win.destroy();win=null;}await transport?.close();companion.select(null);
    selected=target;transport=await createTransport({server:target,dist});
    const partition='persist:processing-'+crypto.createHash('sha256').update(target).digest('hex').slice(0,20);
    selectedSession=session.fromPartition(partition);
    await selectedSession.cookies.set({url:transport.origin,name:'uvt_local_session',value:transport.secret,httpOnly:true,sameSite:'strict',path:'/'});
    selectedSession.cookies.on('changed',(_event,cookie)=>{if(cookie.name==='vt_token')attach().catch(e=>log(e.message));});
    win=new BrowserWindow({width:1360,height:880,minWidth:640,minHeight:540,title:'Ultimate Video Tool',backgroundColor:'#f5f5f7',webPreferences:{partition,preload:path.join(__dirname,'main-preload.js'),contextIsolation:true,sandbox:true}});
    const current=win;current.on('closed',()=>{if(win===current)win=null;});
    current.webContents.setWindowOpenHandler(({url})=>{if(/^https?:/.test(url)&&!url.startsWith(transport.origin+'/'))shell.openExternal(url);return {action:'deny'};});
    current.webContents.on('will-navigate',(event,url)=>{if(new URL(url).origin!==transport.origin){event.preventDefault();if(/^https?:/.test(url))shell.openExternal(url);}});
    selectedSession.setPermissionRequestHandler((contents,permission,callback)=>callback(contents===current.webContents&&contents.getURL().startsWith(transport.origin+'/')&&['media','audioCapture','fullscreen','clipboard-sanitized-write'].includes(permission)));
    await current.loadURL(transport.origin+'/');
    fs.writeFileSync(connectionFile,JSON.stringify({server:target}));if(chooser&&!chooser.isDestroyed())chooser.close();
    await attach();buildMenu();log('Client UI is local; processing server: '+target);
  }finally{changing=false;}
}
function buildMenu(){Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'File',submenu:[{label:'New video',accelerator:'CmdOrCtrl+N',click:()=>win?.loadURL(transport.origin+'/new')},{label:'Change processing server…',click:chooseServer},{type:'separator'},{role:'quit'}]},{role:'editMenu'},{label:'View',submenu:[{role:'reload'},{role:'forceReload'},{role:'togglefullscreen'},{role:'toggleDevTools'}]},{label:'Help',submenu:[{label:'Open client log',click:()=>shell.openPath(path.join(home,'desktop.log'))}]}]));}
ipcMain.handle('find-servers',()=>discover.find(2000));
ipcMain.handle('connect',async(_event,address)=>{try{await connect(address);return {ok:true};}catch(e){return {error:e.message};}});
ipcMain.on('use-this-computer',async()=>{for(const port of [8790,8765,8791,8792]){const found=await discover.probe(`http://127.0.0.1:${port}`,1000);if(found){await connect(found.url);return;}}dialog.showMessageBox(chooser,{type:'info',title:'Install the processing server separately',message:'No local processing server is running.',detail:'Install or start Ultimate Video Tool Server on this PC, then choose This computer again. The client does not bundle a server or model environment.',buttons:['OK']});});
ipcMain.handle('choose-processing-server',()=>chooseServer());ipcMain.handle('companion-status',()=>companion?.info());
ipcMain.handle('director-status',()=>status('claude'));ipcMain.handle('codex-status',()=>status('codex'));ipcMain.handle('assistants-status',()=>assistants.status());
ipcMain.handle('assistants-connect',(event,id,remote)=>{if(!win||event.sender!==win.webContents||!remote||!String(remote.url||'').startsWith(selected+'/'))throw new Error('That is not the selected processing server.');return assistants.connect(id,remote,{command:process.execPath,args:[path.join(__dirname,'mcp-bridge.js').replace('app.asar'+path.sep,'app.asar.unpacked'+path.sep)]});});
app.whenReady().then(async()=>{companion=new ClientCompanion({runner:{...director,status:()=>status('claude')},codex:{...codex,status:()=>status('codex')},log});await companion.start();buildMenu();let saved='';try{saved=JSON.parse(fs.readFileSync(connectionFile,'utf8')).server;}catch{}if(saved&&saved!=='here'){try{await connect(saved);return;}catch(e){log(e.message);}}chooseServer();}).catch(e=>{log(e.stack||e);dialog.showErrorBox('Client could not start',e.message);app.quit();});
app.on('before-quit',()=>{companion?.close();transport?.close();});app.on('window-all-closed',()=>{if(!changing)app.quit();});
