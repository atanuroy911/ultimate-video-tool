/* Cross-platform development installer. Shell entry points supply a verified Node. */
import fs from 'node:fs/promises';
import fss from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const args=process.argv.slice(2),options={action:'install',role:'both',source:repo,root:path.join(os.homedir(),'.ultimate-video-tool-dev')};
for(let i=0;i<args.length;i++){const key=args[i].replace(/^--/,'');if(['no-update','no-launch','no-shortcuts','json'].includes(key))options[key]=true;else if(['action','role','source','root','server-url'].includes(key))options[key]=args[++i];else throw new Error('Unknown option: '+args[i]);}
if(!['install','update','launch','check'].includes(options.action)||!['client','server','both'].includes(options.role))throw new Error('Use action install/update/launch/check and role client/server/both.');
const root=path.resolve(options.root),source=path.resolve(options.source),win=process.platform==='win32',roles=options.role==='both'?['server','client']:[options.role];
if(root===path.parse(root).root)throw new Error('Choose a private installation folder, not a drive or filesystem root.');
const env={...process.env,PATH:path.dirname(process.execPath)+path.delimiter+process.env.PATH,UV_CACHE_DIR:path.join(root,'cache/uv'),UV_PYTHON_INSTALL_DIR:path.join(root,'tools/python'),UV_PROJECT_ENVIRONMENT:path.join(root,'env/server'),PYTHONIOENCODING:'utf-8',HYPERFRAMES_NO_TELEMETRY:'1',DO_NOT_TRACK:'1'};
const stateFile=path.join(root,'install-state.json'),exists=p=>fs.access(p).then(()=>true,()=>false);
const readJSON=async(p,fallback={})=>{try{return JSON.parse(await fs.readFile(p,'utf8'));}catch{return fallback;}};
async function run(command,argv,cwd=source,capture=false){return new Promise((resolve,reject)=>{const child=spawn(command,argv,{cwd,env,windowsHide:true,stdio:capture?['ignore','pipe','pipe']:'inherit'});let text='';if(capture){child.stdout.on('data',b=>text+=b);child.stderr.on('data',b=>text+=b);}child.once('error',reject);child.once('exit',code=>code===0?resolve(text.trim()):reject(new Error(path.basename(command)+' exited '+code+(capture?': '+text.trim():''))));});}
function npmCLI(){const home=path.dirname(process.execPath);return [path.join(home,'node_modules/npm/bin/npm-cli.js'),path.resolve(home,'../lib/node_modules/npm/bin/npm-cli.js')].find(fss.existsSync)||'';}
async function npm(argv,cwd){const cli=npmCLI();if(!cli)throw new Error('Node is installed without npm. Run the shell entry point to prepare the private toolchain.');await run(process.execPath,[cli,...argv],cwd);}
async function download(url,file){await fs.mkdir(path.dirname(file),{recursive:true});const response=await fetch(url,{signal:AbortSignal.timeout(180000)});if(!response.ok)throw new Error('Download failed: '+response.status+' '+url);await fs.writeFile(file+'.partial',Buffer.from(await response.arrayBuffer()));await fs.rename(file+'.partial',file);}
async function uv(){
  const executable=path.join(root,'tools/uv',win?'uv.exe':'uv');if(await exists(executable))return executable;
  const found=await run(win?'where.exe':'sh',win?['uv']:['-c','command -v uv'],source,true).catch(()=>'');if(found)return found.split(/\r?\n/)[0];
  const target=win?'uv-x86_64-pc-windows-msvc':process.arch==='arm64'?'uv-aarch64-unknown-linux-gnu':'uv-x86_64-unknown-linux-gnu';
  const extension=win?'zip':'tar.gz',archive=path.join(root,'downloads',target+'.'+extension),unpack=path.join(root,'tools/uv-unpack');
  await download('https://github.com/astral-sh/uv/releases/latest/download/'+target+'.'+extension,archive);await fs.mkdir(unpack,{recursive:true});
  if(win){const script=path.join(root,'expand-uv.ps1');await fs.writeFile(script,'param($Archive,$Destination)\n$ErrorActionPreference="Stop"\nExpand-Archive -LiteralPath $Archive -DestinationPath $Destination -Force\n');await run('powershell.exe',['-NoProfile','-File',script,archive,unpack]);}else await run('tar',['-xzf',archive,'-C',unpack]);
  async function find(dir){for(const item of await fs.readdir(dir,{withFileTypes:true})){const full=path.join(dir,item.name);if(item.isFile()&&item.name===(win?'uv.exe':'uv'))return full;if(item.isDirectory()){const found=await find(full);if(found)return found;}}}
  const binary=await find(unpack);if(!binary)throw new Error('The Python installer archive did not contain uv.');await fs.mkdir(path.dirname(executable),{recursive:true});await fs.copyFile(binary,executable);if(!win)await fs.chmod(executable,0o755);return executable;
}
async function update(){
  if(options['no-update'])return false;
  if(!await exists(path.join(source,'.git'))){console.warn('Source is an archive: automatic Git updates are unavailable. Existing files are preserved.');return false;}
  const dirty=await run('git',['status','--porcelain'],source,true);
  if(dirty){console.warn('Local changes found: skipping Git update and preserving all edits. Explicit install/update still builds your current source.');return false;}
  const before=await run('git',['rev-parse','HEAD'],source,true);
  try{await run('git',['pull','--ff-only'],source);return before!==await run('git',['rev-parse','HEAD'],source,true);}catch(error){if(options.action==='launch'){console.warn('Update check failed; launching the installed development build: '+error.message);return false;}throw error;}
}
async function dependencies(directory){const lock=await fs.readFile(path.join(directory,'package-lock.json'));const digest=crypto.createHash('sha256').update(lock).digest('hex'),stamp=path.join(directory,'node_modules/.uvt-dev-lock');if(await exists(stamp)&&(await fs.readFile(stamp,'utf8'))===digest)return;await npm(['ci','--no-audit','--no-fund'],directory);await fs.mkdir(path.dirname(stamp),{recursive:true});await fs.writeFile(stamp,digest);}
const python=path.join(root,'env/server',win?'Scripts/python.exe':'bin/python');
async function install(){
  if(roles.includes('server')){
    const tool=await uv();await run(tool,['sync','--project',path.join(source,'server'),'--frozen','--no-dev','--extra','cpu','--python','3.11']);
    await dependencies(path.join(source,'server/renderer'));await dependencies(path.join(source,'server/desktop'));
    if(!await exists(path.join(source,'server/design/fonts/fonts.css')))await run(process.execPath,['scripts/build-fonts.mjs'],path.join(source,'server/renderer'));
    if(!await exists(path.join(source,'server/design/icons/lucide.json')))await run(process.execPath,['scripts/build-icons.mjs'],path.join(source,'server/renderer'));
  }
  if(roles.includes('client')){await dependencies(path.join(source,'client/studio'));await npm(['run','build'],path.join(source,'client/studio'));await dependencies(path.join(source,'client/desktop'));}
  const state=await readJSON(stateFile);state.source=source;state.root=root;state.updatedAt=new Date().toISOString();state.roles=[...new Set([...(state.roles||[]),...roles])];state.python=python;await fs.writeFile(stateFile,JSON.stringify(state,null,2)+'\n');
  for(const role of roles){
    const ps=s=>"'"+s.replaceAll("'","''")+"'",quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
    if(win)await fs.writeFile(path.join(root,'launch-'+role+'.ps1'),`& ${ps(path.join(source,'scripts/dev-install.ps1'))} -Action Launch -Role ${role} -Source ${ps(source)} -Root ${ps(root)}\n`);
    else{
      const launcher=path.join(root,'launch-'+role+'.sh');await fs.writeFile(launcher,`#!/bin/sh\nexec bash ${quote(path.join(source,'scripts/dev-install.sh'))} --action launch --role ${role} --source ${quote(source)} --root ${quote(root)}\n`);await fs.chmod(launcher,0o755);
      if(!options['no-shortcuts']){const applications=path.join(os.homedir(),'.local/share/applications');await fs.mkdir(applications,{recursive:true});
      const escaped=launcher.replaceAll('%','%%').replaceAll('"','\\"');await fs.writeFile(path.join(applications,'ultimate-video-tool-dev-'+role+'.desktop'),`[Desktop Entry]\nType=Application\nName=Ultimate Video Tool ${role==='server'?'Server':'Client'} (Development)\nExec="${escaped}"\nIcon=${path.join(source,role,'desktop/build/icon.png')}\nTerminal=false\nCategories=AudioVideo;\n`);}
    }
  }
}
async function launch(){
  for(const role of roles){
    const executable=path.join(source,role,'desktop/node_modules/electron/dist',win?'electron.exe':'electron');if(!await exists(executable))throw new Error('Install '+role+' first.');
    const config={...env,UVT_DEV_HOME:path.join(root,'state'),VT_USE_REPO:'1',VT_PYTHON:python,VT_DATA:path.join(root,'data/server')};
    if(role==='client'){
      const info=await readJSON(path.join(root,'state/server/server-status.json'));
      const address=options['server-url']||(roles.includes('server')?info.url:'');
      if(address){const home=path.join(root,'state/client');await fs.mkdir(home,{recursive:true});await fs.writeFile(path.join(home,'connection.json'),JSON.stringify({server:address}));}
    }
    const child=spawn(executable,[path.join(source,role,'desktop')],{cwd:source,env:config,detached:true,stdio:'ignore',windowsHide:false});child.unref();console.log('Started '+role+' (PID '+child.pid+').');
    if(role==='server'&&roles.includes('client')){
      let ready=false;for(let i=0;i<180;i++){const info=await readJSON(path.join(root,'state/server/server-status.json'));if(info.url){try{const response=await fetch(info.url+'/.well-known/video-tool',{signal:AbortSignal.timeout(1000)});if((await response.json()).app==='video-tool'){ready=true;break;}}catch{}}await new Promise(r=>setTimeout(r,1000));}
      if(!ready)throw new Error('Server did not become ready. Open its manager log in '+path.join(root,'state/server/desktop.log'));
    }
  }
}
async function check(){const state=await readJSON(stateFile);const report={source,root,node:process.version,installedRoles:state.roles||[],clientSource:await exists(path.join(source,'client/studio/package.json')),serverSource:await exists(path.join(source,'server/pyproject.toml')),clientEditorBuilt:await exists(path.join(source,'client/studio/dist/index.html')),serverPython:await exists(python),serverStatus:await readJSON(path.join(root,'state/server/server-status.json'),null)};console.log(JSON.stringify(report,null,2));return report;}
if(options.action==='check'){await check();process.exit(0);}
for(const role of roles){if(!await exists(path.join(source,role,role==='client'?'desktop/package.json':'pyproject.toml')))throw new Error('Source does not contain the selected '+role+' product.');}
await fs.mkdir(root,{recursive:true});const lock=path.join(root,'install.lock');let handle;
try{handle=await fs.open(lock,'wx');}catch(error){
  if(error.code!=='EEXIST')throw error;
  const previous=Number(await fs.readFile(lock,'utf8'));let alive=true;
  if(Number.isInteger(previous)&&previous>0){try{process.kill(previous,0);}catch(e){if(e.code==='ESRCH')alive=false;}}
  if(alive)throw new Error('Another development installer is active: '+lock);
  await fs.unlink(lock);handle=await fs.open(lock,'wx');
}
await handle.writeFile(String(process.pid));
try{
  const state=await readJSON(stateFile);let changed=false;
  const due=!state.updateCheckedAt||Date.now()-Date.parse(state.updateCheckedAt)>4*3600000;
  if(options.action!=='launch'||due){changed=await update();state.updateCheckedAt=new Date().toISOString();await fs.writeFile(stateFile,JSON.stringify(state,null,2));}
  if(options.action!=='launch'||changed||roles.some(role=>!(state.roles||[]).includes(role)))await install();
}finally{await handle.close();await fs.unlink(lock);}
if(options.action==='launch'||!options['no-launch'])await launch();
await check();
