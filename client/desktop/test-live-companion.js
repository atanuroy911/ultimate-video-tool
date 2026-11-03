const fs=require('fs');
const {ClientCompanion}=require('./client-companion');
const claude=require('./director-runner'),codex=require('./codex-runner');
const target=JSON.parse(fs.readFileSync(0,'utf8'));
(async()=>{
 const companion=new ClientCompanion({runner:claude,codex});
 try{
  await companion.start();companion.select(target);
  let found=[];
  for(let i=0;i<100;i++){
   await new Promise(r=>setTimeout(r,500));
   const response=await fetch(target.server+'/api/directors',{headers:{Authorization:'Bearer '+target.token}});
   const body=await response.json();found=body.directors.filter(d=>d.kind==='claude-client'||d.kind==='codex-client');
   if(found.some(d=>d.kind==='codex-client'))break;
  }
  if(!found.some(d=>d.kind==='codex-client'&&d.available))throw new Error('Codex on this PC was not registered as ready.');
  if(target.verifyRun){
   let called=false;
   const result=await codex.run({...target,prompt:'Use only the video-tool MCP server. Call list_projects once and report the number of projects. Do not modify anything, render, publish, or use shell commands.'},line=>{
    try{const event=JSON.parse(line);if(event.item?.type==='mcp_tool_call'&&event.item?.tool==='list_projects')called=true;}catch{}
   });
   if(!result.ok)throw new Error('Codex MCP check failed: '+result.error);
   if(!called)throw new Error('Codex did not call the requested MCP tool.');
   console.log('Real Codex MCP read-only call passed.');
  }
  console.log(JSON.stringify({role:companion.info().role,connected:companion.info().connected,server:target.server,directors:found.map(d=>({kind:d.kind,available:d.available,label:d.label}))},null,2));
 }finally{companion.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
