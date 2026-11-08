// E3: actual Settings page; software browser, in-memory server responses only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createServer} from 'vite';
import {chromium} from 'playwright-core';
import {chromePath} from './common.mjs';
const out=path.resolve('e2e/out/settings-clarity');fs.mkdirSync(out,{recursive:true});
const server=await createServer({server:{host:'127.0.0.1',port:0},logLevel:'error',plugins:[{name:'settings-fixture',configureServer(s){s.middlewares.use('/__settings',fixture);}}]});
async function fixture(req,res){res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml('/__settings',`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">
import React from 'react';import {createRoot} from 'react-dom/client';import {BrowserRouter} from 'react-router-dom';import Settings from '/src/pages/Settings.tsx';import '/src/styles.css';
createRoot(document.getElementById('root')).render(React.createElement(BrowserRouter,null,React.createElement(Settings)));
</script>`));}
let browser;
try {
 await server.listen();browser=await chromium.launch({executablePath:chromePath(),args:['--disable-gpu']});
 for(const [width,theme] of [[1280,'light'],[1280,'dark'],[400,'light'],[400,'dark']]) {
  const ctx=await browser.newContext({viewport:{width,height:980}}),errors=[],patches=[];ctx.setDefaultTimeout(8000);
  let readyPC=false;
  let settings={default_theme:'auto',default_aspect:'9:16',default_pace:'normal',default_music:'auto',director_order:['claude-client','codex-client','claude-server','local'],director_model:'sonnet'};
  await ctx.route('**/api/**',async route=>{
   const p=new URL(route.request().url()).pathname;
   let body={};
   if(p==='/api/settings') {
    if(route.request().method()==='PUT'){const patch=route.request().postDataJSON();patches.push(patch);settings={...settings,...patch};}body=settings;
   }else if(p==='/api/directors')body={directors:[{id:'best',kind:'best',label:'Best available',available:true,note:''},{id:'claude@pc',kind:'claude-client',label:'Claude on Desk PC',available:readyPC,note:'offline'},{id:'local',kind:'local',label:'Local AI',available:true,note:'ready'},{id:'claude-server',kind:'claude-server',label:'Claude on the server',available:false,note:'not signed in'}],claude_usage_today:{calls:0,seconds:0}};
   else if(p==='/api/doctor')body=[{name:'Python 3.11',ok:true,detail:'3.11.9',fix:''},{name:'ASR model',ok:false,detail:'none downloaded yet',fix:'vt models pull bn-medium'},{name:'Local AI (scene planner)',ok:true,detail:'gemma at http://localhost:11434',fix:''},{name:'FFmpeg NVENC',ok:false,detail:'GPU video encoding',fix:'optional CPU'}];
   else if(p==='/api/ai/status')body={provider:'auto',available:true,model:'local-model',claude:{found:true,logged_in:false,reason:'Sign in',model:'sonnet',daily_cap:200,calls_today:0,cost_usd_today:0},settings:{ai_provider:settings.ai_provider||'best',ai_script:true}};
   else if(p==='/api/llm/status')body={reachable:true,model_ready:true,llm_mode:'auto',models:['local-model'],model:'local-model',ollama_model:'',ollama_url:'http://localhost:11434'};
   else if(p==='/api/my-voices')body={voices:[],available:true};
   else if(p==='/api/assistants')body={assistants:[]};
   else if(p==='/api/server')body={exposed:false};
   else if(p==='/api/mcp/connect')body={};
   else if(['/api/themes','/api/music','/api/models'].includes(p))body=[];
   await route.fulfill({json:body});
  });
  const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
  const url='http://127.0.0.1:'+server.httpServer.address().port+'/__settings';
  await page.goto(url+'?s=directors');await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
  await page.getByText('Local AI directs your next video',{exact:true}).waitFor();
  assert.equal(await page.getByRole('heading',{name:'Who directs your videos',exact:true}).count(),1);
  assert(!await page.getByLabel('Ollama address',{exact:true}).isVisible(),'addresses stay inside closed disclosure');
  await page.screenshot({path:path.join(out,width+'-'+theme+'-directors.png'),animations:'disabled'});
  await page.getByLabel('Which Claude directs',{exact:true}).selectOption('opus');
  await page.waitForFunction(()=>document.querySelector('[data-testid=director-model]')?.value==='opus');
  await page.getByText('Language AI on the server',{exact:true}).click();
  const automatic=page.locator('#provider-best');assert(await automatic.getByText('Ready',{exact:true}).isVisible(),'Automatic includes the ready local provider');
  await page.locator('#provider-auto [role=radio]').click();
  await page.getByLabel('Ollama address',{exact:true}).waitFor();
  await page.getByLabel('Ollama address',{exact:true}).fill('http://fixture:11434');await page.getByLabel('Ollama address',{exact:true}).press('Tab');
  await page.waitForTimeout(100);
  assert(patches.some(p=>p.director_model==='opus'));
  assert(patches.some(p=>p.ollama_url==='http://fixture:11434'));
  assert(patches.every(p=>Object.keys(p).length<=2),'saves send only the changed fields');
  await page.getByRole('button',{name:'Preferences',exact:true}).click();
  if(width===1280){const labels=['Look','Shape','Pace'];const tops=await page.evaluate(labels=>labels.map(label=>Array.from(document.querySelectorAll('#general label > span, #general .small')).find(el=>el.textContent===label)?.getBoundingClientRect().top),labels);assert(tops.every(top=>Math.abs(top-tops[0])<=2),'Theme, Shape and Pace labels align');}
  await page.screenshot({path:path.join(out,width+'-'+theme+'-preferences.png'),animations:'disabled'});
  await page.getByRole('button',{name:'Help & checks',exact:true}).click();
  await page.getByText('Open Voice & speech and download a speech reader.',{exact:true}).waitFor();
  assert(!await page.getByText('vt models pull bn-medium',{exact:true}).isVisible());
  await page.screenshot({path:path.join(out,width+'-'+theme+'-help.png'),animations:'disabled'});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'page fits viewport');
  readyPC=true;await page.goto(url+'?s=directors');await page.getByText('Claude on Desk PC directs your next video',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);await ctx.close();console.log(width+' '+theme+': fallback summary, collapsed connections, model saves, plain checks PASS');
 }
} finally {await browser?.close();await server.close();}
