/* Independent processing server. Its only native UI is server management. */
const {app,shell}=require('electron'),path=require('path'),fs=require('fs'),http=require('http');
const {spawn,spawnSync}=require('child_process'),B=require('./bootstrap'),{choosePort}=require('./server-port'),{createServerManager}=require('./server-manager');
app.setName('Ultimate Video Tool Server');app.setPath('userData',(!app.isPackaged&&process.env.UVT_DEV_HOME)?path.join(process.env.UVT_DEV_HOME,'server'):path.join(app.getPath('appData'),'Ultimate Video Tool Server'));
const home=app.getPath('userData');fs.mkdirSync(home,{recursive:true});const logFile=path.join(home,'desktop.log');
let manager,child=null,origin=null,stopping=false;const log=line=>fs.appendFileSync(logFile,`[${new Date().toISOString()}] ${line}\n`);
if(!app.requestSingleInstanceLock()){app.quit();process.exit(0);}app.on('second-instance',()=>manager?.show());
function ready(port){return new Promise(resolve=>{const req=http.get(`http://127.0.0.1:${port}/.well-known/video-tool`,{timeout:1500},res=>{let body='';res.on('data',b=>body+=b);res.on('end',()=>{try{resolve(JSON.parse(body).app==='video-tool');}catch{resolve(false);}});});req.on('error',()=>resolve(false));req.on('timeout',()=>{req.destroy();resolve(false);});});}
async function stop(){stopping=true;const current=child;if(current&&current.exitCode===null){if(process.platform==='win32')spawnSync('taskkill',['/pid',String(current.pid),'/T','/F'],{windowsHide:true});else current.kill('SIGTERM');if(current.exitCode===null)await new Promise(resolve=>{current.once('exit',resolve);setTimeout(resolve,8000);});}child=null;origin=null;stopping=false;fs.writeFileSync(path.join(home,'server-status.json'),JSON.stringify({running:false}));}
async function start(){
  if(child&&child.exitCode===null&&origin&&await ready(new URL(origin).port))return;
  const source=app.isPackaged?path.join(process.resourcesPath,'app-src'):path.resolve(__dirname,'..');let python,cwd,env;
  if(process.env.VT_USE_REPO==='1'){cwd=source;python=process.env.VT_PYTHON||path.join(source,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');env={...process.env,VT_DATA:process.env.VT_DATA||path.join(home,'data'),PYTHONIOENCODING:'utf-8',PYTHONUNBUFFERED:'1'};}
  else{const layout=B.layout(home,source,app.getVersion());if(!B.isReady(layout))await B.bootstrap(layout,value=>{if(value.line)log(value.line);manager.progress(value);});python=layout.python;cwd=layout.runtime;env=B.serverEnv(layout);}
  env={...env,VT_SUPERVISOR:'desktop'};                 // the server may ask this app to restart it (exit code 75): Restart on the Server page works here too
  let port=await choosePort(Number(process.env.VT_SERVER_PORT||8790),!!process.env.VT_SERVER_PORT);
  for(let attempt=0;attempt<4;attempt++){
    let output='',spawnError;log(`Starting processing API on ${port}`);
    child=spawn(python,['-m','vt.cli','studio','--host','0.0.0.0','--port',String(port),'--no-open'],{cwd,env,windowsHide:true});
    const capture=value=>{output=(output+value).slice(-12000);log(String(value).trimEnd());};child.stdout.on('data',capture);child.stderr.on('data',capture);child.once('error',e=>{spawnError=e;});child.once('exit',code=>{log(`Processing server exited ${code}`);if(stopping)return;if(code===75){child=null;origin=null;manager.progress({step:'Restarting…'});start().catch(e=>{log(e.stack||e);manager.progress({error:true,step:e.message});});return;}manager.progress({step:code?'The server stopped. View its log or start it again.':'Server stopped.'});});
    const until=Date.now()+90000;while(Date.now()<until&&child.exitCode===null&&!spawnError){if(await ready(port)){origin=`http://127.0.0.1:${port}`;fs.writeFileSync(path.join(home,'server-status.json'),JSON.stringify({running:true,url:origin,pid:child.pid,at:new Date().toISOString()}));manager.ready();return;}await new Promise(r=>setTimeout(r,350));}
    if(spawnError)throw spawnError;
    if(attempt<3&&!process.env.VT_SERVER_PORT&&/already in use|EADDRINUSE|address.+in use|10048/i.test(output)){await stop();port=await choosePort();manager.progress({step:'Choosing another address automatically…'});continue;}
    throw new Error('The processing server could not start. View the log for details.');
  }
}
app.whenReady().then(async()=>{manager=createServerManager({url:()=>origin,start,stop,readLog:async()=>(await fs.promises.readFile(logFile,'utf8').catch(()=>'' )).slice(-2000000)});const marker=path.join(home,'server-manager-initialized.json');if(!process.env.UVT_DEV_HOME&&!fs.existsSync(marker)){manager.enableAutoStart();fs.writeFileSync(marker,'{}');}try{await manager.start();}catch(e){log(e.stack||e);manager.progress({error:true,step:e.message});}});
app.on('before-quit',()=>{if(child&&child.exitCode===null){if(process.platform==='win32')spawnSync('taskkill',['/pid',String(child.pid),'/T','/F'],{windowsHide:true});else child.kill('SIGTERM');}});app.on('window-all-closed',()=>{});app.on('activate',()=>manager?.show());
