/* Independent editor client: the local UI, and the helper (helper.js) that keeps Claude and Codex ready for the selected server. */
const {app,BrowserWindow,Menu,ipcMain,shell,session,dialog}=require('electron');
const path=require('path'),fs=require('fs'),os=require('os'),crypto=require('crypto');
// The app's own folder (UVT_DEV_HOME/client when run from source). The helper uses the same one: its servers, its device name and its log live beside the app's.
const home=(!app.isPackaged&&process.env.UVT_DEV_HOME)?path.join(process.env.UVT_DEV_HOME,'client'):path.join(app.getPath('appData'),'Video Tool');
app.setPath('userData',home);fs.mkdirSync(home,{recursive:true});
const helper=require('./helper-control'),helperPath=path.join(__dirname,'helper.js'),version=app.getVersion();
const ensureHelper=()=>helper.ensure({home,helperPath,version});
// "--helper" is what the start-with-the-computer entry runs: make sure the helper runs, then leave, before anything else loads (no window, no server connection).
if(process.argv.includes('--helper')){app.whenReady().then(ensureHelper).catch(()=>{}).finally(()=>app.quit());return;}
const discover=require('./discover'),assistants=require('./assistants');
const {createTransport,serverURL}=require('./transport');
let win=null,chooser=null,transport=null,selected='',selectedSession=null,changing=false;
const connectionFile=path.join(home,'connection.json');
const log=message=>fs.appendFileSync(path.join(home,'desktop.log'),`[${new Date().toISOString()}] ${message}\n`);
if(!app.requestSingleInstanceLock()){app.quit();process.exit(0);}
// Command line, the same thing the connect window does:  "Ultimate Video Tool.exe" --server 192.168.1.20
// (the address is all a server on the person's network needs). Works when the app is already running too: the second launch hands its arguments to the first.
function cliOptions(argv){const o={};for(let i=0;i<argv.length;i++){const m=/^--(server)(?:=(.*))?$/.exec(argv[i]);if(m)o[m[1]]=m[2]!==undefined?m[2]:argv[i+1];}return o;}
async function applyCli(argv){const o=cliOptions(argv);if(!o.server)return false;log('Command line: server '+o.server);await connect(o.server);return true;}
app.on('second-instance',(_event,argv)=>{if(cliOptions(argv||[]).server){applyCli(argv).catch(e=>{log(e.message);dialog.showErrorBox('Could not connect',e.message);});return;}const window=win||chooser;if(window){window.show();window.focus();}});
function chooseServer(){
  if(chooser&&!chooser.isDestroyed()){chooser.show();chooser.focus();return;}
  chooser=new BrowserWindow({width:580,height:700,resizable:true,minWidth:500,minHeight:580,title:'Choose a server',icon:appIcon(),webPreferences:{preload:path.join(__dirname,'preload.js'),contextIsolation:true,sandbox:true}});
  chooser.setMenu(null);chooser.loadFile(path.join(__dirname,'connect.html'));chooser.on('closed',()=>{chooser=null;if(!win&&!changing)app.quit();});
}
function appIcon(){const f=app.isPackaged?path.join(process.resourcesPath,'icon.png'):path.join(__dirname,'build','icon.png');return require('fs').existsSync(f)?f:undefined;}
// ---- the helper: it calls the server itself, so the app only tells it which servers to reach
async function attach(){
  if(!selected)return;
  try{await ensureHelper();await helper.request(home,'POST','/servers',{server:selected});}   // no key: a server accepts the computers on its own network
  catch(e){log('The helper could not be set up: '+e.message);}
}
// ---- start with the computer: the entry runs this app with --helper, which starts the helper and leaves
const launcher=process.env.APPIMAGE||app.getPath('exe'),entry=path.join(os.homedir(),'.config','autostart','video-tool-helper.desktop');
function runEntry(name){try{return require('child_process').execFileSync('reg',['query','HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run','/v',name],{encoding:'utf8',windowsHide:true,stdio:['ignore','pipe','ignore']});}catch{return '';}}
// Windows: read the Run entry itself. Electron's own check compares a quoted path and reported an existing entry as off (2026-11-08).
function autostartOn(){if(process.platform==='linux')return fs.existsSync(entry);if(process.platform==='win32')return runEntry('Ultimate Video Tool Helper').toLowerCase().includes(launcher.toLowerCase());return app.getLoginItemSettings({name:'Ultimate Video Tool Helper',path:launcher,args:['--helper']}).openAtLogin;}
function setAutostart(on){
  if(process.platform==='linux'){
    if(on){fs.mkdirSync(path.dirname(entry),{recursive:true});fs.writeFileSync(entry,`[Desktop Entry]\nType=Application\nName=Video Tool helper\nExec="${launcher.replace(/[%"`$\\]/g,c=>'\\'+c)}" --helper\nTerminal=false\nX-GNOME-Autostart-enabled=true\n`);}
    else fs.rmSync(entry,{force:true});
    return;
  }
  app.setLoginItemSettings({openAtLogin:on,name:'Ultimate Video Tool Helper',path:launcher,args:['--helper']});
  const off=path.join(home,'login-item-off');          // the person's choice, kept apart from the entry: a reinstall elsewhere must not lose it
  if(on)fs.rmSync(off,{force:true});else fs.writeFileSync(off,'The person turned off starting the helper with the computer.');
}
async function helperState(){const have=await helper.status(home);return {running:!!have,...(have?have.info:{}),autostart:autostartOn(),installed:app.isPackaged};}
async function connect(address){
  const found=await discover.probe(address);if(!found)throw new Error('No server answers at that address. Check the address, and that the server is running.');
  const target=serverURL(found.url);
  const dist=app.isPackaged?path.join(process.resourcesPath,'studio'):path.resolve(__dirname,'../studio/dist');
  if(!fs.existsSync(path.join(dist,'index.html')))throw new Error('Build the client UI first: npm --prefix client/studio run build.');
  changing=true;
  try{
    if(win&&!win.isDestroyed()){win.destroy();win=null;}await transport?.close();
    selected=target;transport=await createTransport({server:target,dist});
    const partition='persist:processing-'+crypto.createHash('sha256').update(target).digest('hex').slice(0,20);
    selectedSession=session.fromPartition(partition);
    await selectedSession.cookies.set({url:transport.origin,name:'uvt_local_session',value:transport.secret,httpOnly:true,sameSite:'strict',path:'/'});
    win=new BrowserWindow({width:1360,height:880,minWidth:640,minHeight:540,title:'Ultimate Video Tool',icon:appIcon(),backgroundColor:'#f5f5f7',webPreferences:{partition,preload:path.join(__dirname,'main-preload.js'),contextIsolation:true,sandbox:true}});
    const current=win;current.on('closed',()=>{if(win===current)win=null;});
    current.webContents.setWindowOpenHandler(({url})=>{if(/^https?:/.test(url)&&!url.startsWith(transport.origin+'/'))shell.openExternal(url);return {action:'deny'};});
    current.webContents.on('will-navigate',(event,url)=>{if(new URL(url).origin!==transport.origin){event.preventDefault();if(/^https?:/.test(url))shell.openExternal(url);}});
    selectedSession.setPermissionRequestHandler((contents,permission,callback)=>callback(contents===current.webContents&&contents.getURL().startsWith(transport.origin+'/')&&['media','audioCapture','fullscreen','clipboard-sanitized-write'].includes(permission)));
    await current.loadURL(transport.origin+'/');
    fs.writeFileSync(connectionFile,JSON.stringify({server:target}));if(chooser&&!chooser.isDestroyed())chooser.close();
    await attach();buildMenu();log('Client UI is local; processing server: '+target);
  }finally{changing=false;}
}
function buildMenu(){Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'File',submenu:[{label:'New video',accelerator:'CmdOrCtrl+N',click:()=>win?.loadURL(transport.origin+'/new')},{label:'Switch Server…',click:chooseServer},{type:'separator'},{role:'quit'}]},{role:'editMenu'},{label:'View',submenu:app.isPackaged?[{role:'reload'},{type:'separator'},{role:'togglefullscreen'}]:[{role:'reload'},{role:'forceReload'},{role:'togglefullscreen'},{role:'toggleDevTools'}]},{label:'Help',submenu:[{label:'Show App Log',click:()=>shell.openPath(path.join(home,'desktop.log'))},{label:'Show Helper Log',click:()=>shell.openPath(path.join(home,'helper.log'))}]}]));}
// only the app's own window may use these
const fromApp=event=>!!win&&!win.isDestroyed()&&event.sender===win.webContents;
const onlyApp=handler=>async(event,...args)=>{if(!fromApp(event))throw new Error('Only the app window can use the helper.');return handler(...args);};
const stopped=async()=>{for(let i=0;i<25&&await helper.status(home);i++)await new Promise(r=>setTimeout(r,120));};
ipcMain.handle('find-servers',()=>discover.find(2000));
ipcMain.handle('connect',async(_event,address)=>{try{await connect(address);return {ok:true};}catch(e){return {error:e.message};}});
ipcMain.on('use-this-computer',async()=>{for(const port of [8790,8765,8791,8792]){const found=await discover.probe(`http://127.0.0.1:${port}`,1000);if(found){await connect(found.url);return;}}dialog.showMessageBox(chooser,{type:'info',title:'No server on this computer',message:'Ultimate Video Tool Server isn\'t running on this computer.',detail:'Open it (or install it) on this computer, then choose This computer again. Or choose a server on your network.',buttons:['OK']});});
ipcMain.handle('choose-processing-server',()=>chooseServer());
ipcMain.handle('assistants-status',()=>assistants.status());
ipcMain.handle('assistants-connect',(event,id,remote)=>{if(!win||event.sender!==win.webContents||!remote||!String(remote.url||'').startsWith(selected+'/'))throw new Error('That is not the selected processing server.');return assistants.connect(id,remote,{command:process.execPath,args:[path.join(__dirname,'mcp-bridge.js').replace('app.asar'+path.sep,'app.asar.unpacked'+path.sep)]});});
ipcMain.handle('helper-status',onlyApp(helperState));
ipcMain.handle('helper-start',onlyApp(async()=>{await ensureHelper();return helperState();}));
ipcMain.handle('helper-stop',onlyApp(async()=>{await helper.request(home,'POST','/stop',{}).catch(()=>{});await stopped();return helperState();}));
ipcMain.handle('helper-refresh',onlyApp(async()=>{await helper.request(home,'POST','/refresh',{});return helperState();}));
ipcMain.handle('helper-remove-server',onlyApp(async address=>{await helper.request(home,'DELETE','/servers',{server:String(address)});return helperState();}));
ipcMain.handle('helper-autostart',onlyApp(async on=>{setAutostart(!!on);return helperState();}));
app.whenReady().then(async()=>{
  buildMenu();
  const decided=path.join(home,'login-item-decided');      // an installed app starts its helper with the computer unless the person turns that off (Settings)
  // installed again in another folder (C: to E:, 2026-11-08): the entry still started the old, removed program. Point it at this one.
  if(app.isPackaged&&fs.existsSync(decided)&&!fs.existsSync(path.join(home,'login-item-off'))&&!autostartOn()){try{setAutostart(true);log('The helper start-with-computer entry now points at this copy of the app.');}catch(e){log('Could not update the start-with-computer entry: '+e.message);}}
  if(app.isPackaged&&!fs.existsSync(decided)){try{setAutostart(true);fs.writeFileSync(decided,'The helper starts with the computer by default; the person can turn it off in Settings.');log('The helper will start with this computer.');}catch(e){log('Could not set the helper to start with the computer: '+e.message);}}
  try{if(await applyCli(process.argv))return;}catch(e){log(e.message);dialog.showErrorBox('Could not connect',e.message);}
  let saved='';try{saved=JSON.parse(fs.readFileSync(connectionFile,'utf8')).server;}catch{}
  if(saved&&saved!=='here'){try{await connect(saved);return;}catch(e){log(e.message);}}
  chooseServer();
}).catch(e=>{log(e.stack||e);dialog.showErrorBox('Client could not start',e.message);app.quit();});
app.on('before-quit',()=>{transport?.close();});     // the helper is not stopped: it keeps Claude and Codex ready when the window is closed
app.on('window-all-closed',()=>{if(!changing)app.quit();});
