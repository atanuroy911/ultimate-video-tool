/* Resolve native CLIs without shell interpolation of MCP URLs, tokens or config. */
const {spawnSync}=require('child_process');
const fs=require('fs'),path=require('path'),os=require('os');
function commandFor(name){
 if(process.platform!=='win32')return {file:name,prefix:[]};
 const found=spawnSync('where.exe',[name],{encoding:'utf8',windowsHide:true,shell:false});
 const entries=String(found.stdout||'').split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
 const native=entries.find(p=>p.toLowerCase().endsWith('.exe'));
 if(native)return {file:native,prefix:[]};
 const direct=path.join(os.homedir(),'.local','bin',name+'.exe');
 if(fs.existsSync(direct))return {file:direct,prefix:[]};
 for(const entry of entries){
  const modules=path.join(path.dirname(entry),'node_modules');
  if(name==='claude'){
   const js=path.join(modules,'@anthropic-ai','claude-code','cli.js');
   if(fs.existsSync(js))return {file:process.execPath,prefix:[js],env:{ELECTRON_RUN_AS_NODE:'1'}};
  }
  if(name==='codex')for(const pkg of ['codex','codex-win32-x64','codex-win32-arm64']){
   const arch=process.arch==='arm64'?'aarch64':'x86_64';
   const exe=path.join(modules,'@openai',pkg,'vendor',arch+'-pc-windows-msvc','codex','codex.exe');
   if(fs.existsSync(exe))return {file:exe,prefix:[]};
  }
 }
 throw new Error(`${name} CLI was not found. Install it and sign in on this PC.`);
}
module.exports={commandFor};
