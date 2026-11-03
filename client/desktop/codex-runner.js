/* Codex on the client PC, using only this session's processing-server MCP. */
const {spawn,spawnSync}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
const {commandFor}=require('./assistant-command');
function status(run=spawnSync){
  let command;try{command=run===spawnSync?commandFor('codex'):{file:'codex',prefix:[]};}catch(e){return {found:false,logged_in:false,version:'',reason:e.message};}
  const opts={encoding:'utf8',windowsHide:true,timeout:10000,shell:false,env:{...process.env,...command.env}};
  const version=run(command.file,[...command.prefix,'--version'],opts);if(version.error||version.status!==0)return {found:false,logged_in:false,version:'',reason:'Codex CLI is not installed on this computer.'};
  const auth=run(command.file,[...command.prefix,'login','status'],opts);
  return {found:true,logged_in:auth.status===0,version:String(version.stdout||'').trim().slice(0,80),reason:auth.status===0?'':'Open Codex and sign in on this computer.'};
}
function args(server,token){
  return ['exec','--json','--ephemeral','--ignore-user-config','--sandbox','read-only','--skip-git-repo-check',
    '-c','approval_policy="never"','-c',`mcp_servers={video-tool={url=${JSON.stringify(new URL('/mcp',server).href)},default_tools_approval_mode="auto",http_headers={Authorization=${JSON.stringify('Bearer '+token)}}}}`,'-'];
}
function run({prompt,server,token,signal},onLog=()=>{}){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'vt-codex-'));
  // Inline TOML preserves the user's normal login, while isolating MCP and config.
  const command=args(server,token);
  return new Promise(resolve=>{
    let exe;try{exe=commandFor('codex');}catch(e){fs.rmSync(dir,{recursive:true,force:true});resolve({ok:false,error:e.message});return;}
    const child=spawn(exe.file,[...exe.prefix,...command],{cwd:dir,windowsHide:true,shell:false,env:{...process.env,...exe.env},stdio:['pipe','pipe','pipe']});let error='';
    const stop=()=>child.kill();signal?.addEventListener('abort',stop,{once:true});child.once('close',()=>signal?.removeEventListener('abort',stop));if(signal?.aborted)stop();
    const cleanup=()=>fs.rmSync(dir,{recursive:true,force:true});
    child.stdout.on('data',chunk=>{for(const line of String(chunk).split(/\r?\n/).filter(Boolean))onLog(line.slice(0,500));});
    child.stderr.on('data',chunk=>{error=(error+String(chunk)).slice(-1000);});
    child.on('error',e=>{cleanup();resolve({ok:false,error:e.message});});
    child.on('close',code=>{cleanup();resolve({ok:code===0,error:code===0?'':error,exit_code:code});});child.stdin.end(prompt);
  });
}
module.exports={status,args,run};
