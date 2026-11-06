/* The server's own native control window and tray. No remote page gets these IPC controls. */
const {app,BrowserWindow,Tray,Menu,nativeImage,ipcMain,clipboard}=require('electron');
const path=require('path');
const fs=require('fs');
const os=require('os');
const {pathToFileURL}=require('url');
const control=require('./server-control');

function createServerManager(controller){
  let win=null,tray=null,quitting=false,operation='',error='',progress={},lastState={running:false};
  const page=pathToFileURL(path.join(__dirname,'server-manager.html')).href;
  const icon=path.join(__dirname,'server-icon.png');
  const autostartFile=path.join(app.getPath('appData'),'autostart','ultimate-video-tool-server.desktop');
  const launcher=controller.launcher||process.env.APPIMAGE||app.getPath('exe');
  const gpuMarker=path.join(app.getPath('userData'),'gpu-question-shown');       // the question about the graphics cards opens by itself once, the first time
  function autoEnabled(){return process.platform==='win32'?app.getLoginItemSettings().openAtLogin:fs.existsSync(autostartFile);}
  function setAuto(on){
    if(controller.setAutoStart)return controller.setAutoStart(on);
    if(process.platform==='win32'){app.setLoginItemSettings({openAtLogin:on,path:launcher,args:['--background']});return;}
    if(on){fs.mkdirSync(path.dirname(autostartFile),{recursive:true});fs.writeFileSync(autostartFile,`[Desktop Entry]\nType=Application\nName=Ultimate Video Tool Server\nExec="${launcher.replace(/[%"`$\\]/g,c=>'\\'+c)}" --background\nIcon=${icon}\nTerminal=false\n`);}
    else if(fs.existsSync(autostartFile))fs.unlinkSync(autostartFile);
  }
  const trusted=e=>!!win&&e.sender===win.webContents&&e.senderFrame?.url===page;
  function show(){if(!win||win.isDestroyed())makeWindow();win.show();if(win.isMinimized())win.restore();win.focus();}
  async function state(){
    const status=await control.inspect(controller.url());lastState=status;
    if(tray){tray.setToolTip(`Ultimate Video Tool Server — ${operation|| (status.running?'Running':'Stopped')}`);setTrayMenu();}
    return {...status,computer:os.hostname(),operation,error,progress,autostart:autoEnabled(),tray:!!tray,askGpu:!!(status.gpu&&status.gpu.needs_choice&&status.gpu.cards>=2&&!fs.existsSync(gpuMarker))};
  }
  async function act(action){
    if(action==='copy-address'){const s=await state();if(!s.addresses.length)throw new Error('Start the server to get a client address.');clipboard.writeText(s.addresses[0]);return {ok:true};}
    if(action==='engine-settings'){if(!controller.url()||!(await state()).running)throw new Error('Start the server first.');return {url:control.localURL(controller.url())+'/manage?embedded=1'};}
    if(action==='gpu-settings'){if(!controller.url()||!(await state()).running)throw new Error('Start the server first.');try{fs.mkdirSync(path.dirname(gpuMarker),{recursive:true});fs.writeFileSync(gpuMarker,'shown');}catch{}return {url:control.localURL(controller.url())+'/manage?embedded=1#cards'};}
    if(action==='open-log'){return {log:await controller.readLog()};}
    if(action==='autostart-on'||action==='autostart-off'){await setAuto(action==='autostart-on');return {ok:true};}
    if(!['start','stop','restart','quit'].includes(action))throw new Error('Unknown server action.');
    if(operation)throw new Error('Wait for the current server action to finish.');
    operation=action==='start'?'Starting':action==='restart'?'Restarting':'Stopping';error='';
    try{
      if(action==='stop'||action==='restart'||action==='quit')await controller.stop();
      if(action==='start'||action==='restart')await controller.start();
      if(action==='quit'){quitting=true;app.quit();}
      return {ok:true};
    }catch(e){error=e.message;throw e;}finally{operation='';}
  }
  function setTrayMenu(){
    tray.setContextMenu(Menu.buildFromTemplate([
      {label:'Ultimate Video Tool Server',enabled:false},{label:operation|| (lastState.running?'● Running':'○ Stopped'),enabled:false},
      {type:'separator'},{label:'Open server manager',click:show},
      {label:'Engine settings',enabled:lastState.running,click:()=>{show();win.webContents.send('server-manager:progress',{engines:true});}},
      {label:'Graphics cards',enabled:lastState.running&&!!(lastState.gpu&&lastState.gpu.cards>=2),click:()=>{show();win.webContents.send('server-manager:progress',{gpu:true});}},
      {label:'Copy address',enabled:lastState.running,click:()=>act('copy-address').catch(notify)},
      {type:'separator'},{label:lastState.running?'Stop server':'Start server',enabled:!operation,click:()=>act(lastState.running?'stop':'start').then(state).catch(notify)},
      {label:'Quit server',click:()=>act('quit').catch(notify)},
    ]));
  }
  function notify(e){error=e.message;show();}
  function makeWindow(){
    win=new BrowserWindow({width:850,height:820,minWidth:560,minHeight:600,show:false,title:'Ultimate Video Tool Server',icon,backgroundColor:'#f4f5f8',webPreferences:{preload:path.join(__dirname,'server-manager-preload.js'),contextIsolation:true,sandbox:true}});
    win.setMenu(null);win.webContents.setWindowOpenHandler(()=>({action:'deny'}));win.webContents.on('will-navigate',e=>e.preventDefault());
    win.loadFile(path.join(__dirname,'server-manager.html'));
    win.once('ready-to-show',()=>{if(!process.argv.includes('--background')||!tray)show();});
    win.on('close',e=>{if(!quitting&&tray){e.preventDefault();win.hide();}});
    win.on('closed',()=>{win=null;});
  }
  try{tray=new Tray(nativeImage.createFromPath(icon).resize({width:24,height:24}));tray.on('click',show);tray.on('double-click',show);setTrayMenu();}catch(e){console.warn('Tray unavailable:',e.message);}
  ipcMain.handle('server-manager:state',e=>{if(!trusted(e))throw new Error('Only the server manager can read local controls.');return state();});
  ipcMain.handle('server-manager:act',(e,action)=>{if(!trusted(e))throw new Error('Only the server manager can use local controls.');return act(action);});
  app.on('before-quit',()=>{quitting=true;});
  makeWindow();
  const timer=setInterval(()=>state().catch(()=>{}),5000);timer.unref();
  app.on('will-quit',()=>{clearInterval(timer);tray?.destroy();});
  return {show,state,start:()=>act('start'),ready:()=>{progress={};state().catch(()=>{});},progress:value=>{progress={...progress,...value};if(win&&!win.isDestroyed())win.webContents.send('server-manager:progress',value);},enableAutoStart:()=>setAuto(true)};
}
module.exports={createServerManager};
