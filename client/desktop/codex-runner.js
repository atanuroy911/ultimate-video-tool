/* Codex on the client PC. `run` is a planning session using only this session's processing-server MCP; `ask` is one question answered as JSON.
 * The options come from `codex exec --help` (codex-cli 0.166): the real program is not on this PC's PATH, so `ask` is tested against a stand-in only. */
const {execFile,spawn,spawnSync}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
const {commandFor}=require('./assistant-command');
const {kindOf,modelName}=require('./director-runner');
const OUTPUT_MAX=8*1024*1024;
function interpret(version,auth){
  if(version.error||version.status!==0)return {found:false,logged_in:false,version:'',reason:'Codex CLI is not installed on this computer.'};
  return {found:true,logged_in:auth.status===0,version:String(version.stdout||'').trim().slice(0,80),reason:auth.status===0?'':'Open Codex and sign in on this computer.'};
}
function status(run=spawnSync){
  let command;try{command=run===spawnSync?commandFor('codex'):{file:'codex',prefix:[]};}catch(e){return {found:false,logged_in:false,version:'',reason:e.message};}
  const opts={encoding:'utf8',windowsHide:true,timeout:10000,shell:false,env:{...process.env,...command.env}};
  const version=run(command.file,[...command.prefix,'--version'],opts);if(version.error||version.status!==0)return interpret(version,{});
  return interpret(version,run(command.file,[...command.prefix,'login','status'],opts));
}
function execAsync(file,args,opts){
  return new Promise(resolve=>execFile(file,args,opts,(error,stdout,stderr)=>{
    const exited=error&&typeof error.code==='number';
    resolve({error:error&&!exited?error:null,status:!error?0:exited?error.code:1,stdout,stderr});
  }));
}
async function statusAsync(exec=execAsync){
  let command;try{command=exec===execAsync?commandFor('codex'):{file:'codex',prefix:[]};}catch(e){return {found:false,logged_in:false,version:'',reason:e.message};}
  const opts={encoding:'utf8',windowsHide:true,timeout:10000,env:{...process.env,...command.env}};
  const version=await exec(command.file,[...command.prefix,'--version'],opts);if(version.error||version.status!==0)return interpret(version,{});
  return interpret(version,await exec(command.file,[...command.prefix,'login','status'],opts));
}
function args(server,token,model){
  return ['exec','--json','--ephemeral','--ignore-user-config','--sandbox','read-only','--skip-git-repo-check',...(model?['-m',modelName(model)]:[]),
    '-c','approval_policy="never"','-c',`mcp_servers={video-tool={url=${JSON.stringify(new URL('/mcp',server).href)},default_tools_approval_mode="auto"${token?`,http_headers={Authorization=${JSON.stringify('Bearer '+token)}}`:''}}}`,'-'];
}
function run({prompt,server,token,signal,model},onLog=()=>{}){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'vt-codex-'));
  // Inline TOML preserves the user's normal login, while isolating MCP and config.
  const command=args(server,token,model);
  return new Promise(resolve=>{
    let exe;try{exe=commandFor('codex');}catch(e){fs.rmSync(dir,{recursive:true,force:true});resolve({ok:false,error:e.message,error_kind:'login'});return;}
    const child=spawn(exe.file,[...exe.prefix,...command],{cwd:dir,windowsHide:true,shell:false,env:{...process.env,...exe.env},stdio:['pipe','pipe','pipe']});let error='';
    const stop=()=>child.kill();signal?.addEventListener('abort',stop,{once:true});child.once('close',()=>signal?.removeEventListener('abort',stop));if(signal?.aborted)stop();
    const cleanup=()=>fs.rmSync(dir,{recursive:true,force:true});
    child.stdout.on('data',chunk=>{for(const line of String(chunk).split(/\r?\n/).filter(Boolean))onLog(line.slice(0,500));});
    child.stderr.on('data',chunk=>{error=(error+String(chunk)).slice(-1000);});
    child.on('error',e=>{cleanup();resolve({ok:false,error:e.message,error_kind:'other'});});
    child.on('close',code=>{cleanup();resolve({ok:code===0,error:code===0?'':error,error_kind:code===0?'':kindOf(error),exit_code:code});});child.stdin.end(prompt);
  });
}
/** The options for one question. The schema goes into the prompt, not `--output-schema`: OpenAI's strict mode rejects schemas with optional fields, and ours have them. */
function askArgs({answerFile,imageFiles=[],model}){
  return ['exec',...imageFiles.flatMap(f=>['-i',f]),'--json','--ephemeral','--ignore-user-config','--ignore-rules','--sandbox','read-only','--skip-git-repo-check',
    ...(model?['-m',modelName(model)]:[]),'-c','approval_policy="never"','-o',answerFile,'-'];
}
function ask({system,prompt,schema,images=[],model,timeout=300,signal}={},deps={}){
  return new Promise(resolve=>{
    const began=Date.now();
    const finish=value=>resolve({text:'',error:'',error_kind:'',models:[],seconds:Math.round((Date.now()-began)/100)/10,...value});
    let exe;try{exe=deps.command||commandFor('codex');}catch(e){finish({ok:false,error:e.message,error_kind:'login'});return;}
    const dir=fs.mkdtempSync(path.join(os.tmpdir(),'vt-codex-ask-'));
    const cleanup=()=>fs.rmSync(dir,{recursive:true,force:true});
    try{
      const imageFiles=images.map((image,n)=>{const f=path.join(dir,`frame${n}.png`);fs.writeFileSync(f,Buffer.isBuffer(image)?image:Buffer.from(String(image),'base64'));return f;});
      const answerFile=path.join(dir,'answer.txt');
      const text=(system?system+'\n\n':'')+String(prompt||'')+(schema?'\n\nAnswer with ONE JSON object only (no prose, no code fence) that matches this JSON Schema:\n'+JSON.stringify(schema):'');
      const child=(deps.spawn||spawn)(exe.file,[...exe.prefix,...askArgs({answerFile,imageFiles,model})],{cwd:dir,windowsHide:true,shell:false,env:{...process.env,...exe.env},stdio:['pipe','pipe','pipe']});
      let stdout='',stderr='',timedOut=false;
      const stop=()=>child.kill();
      const timer=setTimeout(()=>{timedOut=true;stop();},(Number(timeout)>0?Number(timeout):300)*1000);
      signal?.addEventListener('abort',stop,{once:true});if(signal?.aborted)stop();
      child.stdout.on('data',b=>{if(stdout.length<OUTPUT_MAX)stdout+=String(b);});
      child.stderr.on('data',b=>{stderr=(stderr+String(b)).slice(-4000);});
      child.on('error',e=>{clearTimeout(timer);cleanup();finish({ok:false,error:`Codex could not be started (${e.message}).`,error_kind:'other'});});
      child.on('close',code=>{
        clearTimeout(timer);signal?.removeEventListener('abort',stop);
        let answer='';try{answer=fs.readFileSync(answerFile,'utf8').trim();}catch{}
        if(!answer)for(const line of stdout.split(/\r?\n/)){try{const m=JSON.parse(line);if(m.item&&m.item.type==='agent_message'&&m.item.text)answer=String(m.item.text);}catch{}}
        cleanup();
        if(timedOut)return finish({ok:false,error:`Codex did not answer within ${Math.round(Number(timeout)>0?Number(timeout):300)} s.`,error_kind:'other'});
        if(code!==0||!answer)return finish({ok:false,error:`Codex gave no answer (exit ${code}): ${(stderr||stdout).slice(0,160)}`,error_kind:kindOf(stderr||stdout)});
        finish({ok:true,text:answer});
      });
      child.stdin.on('error',()=>{});
      child.stdin.end(text);
    }catch(e){cleanup();finish({ok:false,error:e.message,error_kind:'other'});}
  });
}
module.exports={status,statusAsync,args,askArgs,run,ask};
