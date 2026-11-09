/* Attach the native manager to an existing home-folder processing service. */
const {app,shell}=require('electron');
const fs=require('fs');
const path=require('path');
const {execFile}=require('child_process');
const {createServerManager}=require('./server-manager');
const control=require('./server-control');
const config=JSON.parse(fs.readFileSync(path.join(__dirname,'server-manager-config.json'),'utf8'));
const base=control.localURL(config.url);
const root=path.resolve(config.root);
const relative=path.relative(app.getPath('home'),root);
if(relative.startsWith('..')||path.isAbsolute(relative))throw new Error('The server manager configuration must stay in your home folder.');
if(config.service!=='ultimate-video-tool.service')throw new Error('Unsupported processing service.');
app.setName('Ultimate Video Tool Server');
app.setPath('userData',path.join(root,'manager-data'));
app.setDesktopName('ultimate-video-tool-server.desktop');
if(!app.requestSingleInstanceLock()){app.quit();process.exit(0);}
let manager;
app.on('second-instance',()=>manager?.show());
const service=action=>new Promise((resolve,reject)=>execFile('systemctl',['--user',action,config.service],{timeout:30000},(e,stdout,stderr)=>e?reject(new Error(stderr.trim()||e.message)):resolve(stdout)));
app.whenReady().then(()=>{
  manager=createServerManager({url:()=>base,launcher:config.launcher,start:async()=>{await service('start');for(let i=0;i<60;i++){if((await control.inspect(base)).running)return;await new Promise(r=>setTimeout(r,500));}throw new Error('The server is still starting. View the log for details.');},stop:()=>service('stop'),readLog:async()=>(await fs.promises.readFile(path.join(root,'server.log'),'utf8').catch(()=>'' )).slice(-2000000),
    setAutoStart:async on=>{await service(on?'enable':'disable');const target=path.join(app.getPath('appData'),'autostart','ultimate-video-tool-server.desktop');if(on){fs.mkdirSync(path.dirname(target),{recursive:true});const text=fs.readFileSync(config.desktopFile,'utf8').replace(/^(Exec=.+)$/m,'$1 --background');fs.writeFileSync(target,text);}else if(fs.existsSync(target))fs.unlinkSync(target);}});
});
app.on('window-all-closed',()=>{});
app.on('activate',()=>manager?.show());
