// E2: actual Direct again dialog, fake API; no video job is started.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createServer} from 'vite';
import {chromium} from 'playwright-core';
import {chromePath} from './common.mjs';
const out=path.resolve('e2e/out/redo-choices');fs.mkdirSync(out,{recursive:true});
const server=await createServer({server:{host:'127.0.0.1',port:0},logLevel:'error',plugins:[{name:'redo-fixture',configureServer(s){s.middlewares.use('/__redo',fixture);}}]});
async function fixture(req,res){res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml('/__redo',`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">
 import React from 'react';import {createRoot} from 'react-dom/client';import {BrowserRouter} from 'react-router-dom';import RedoModal from '/src/components/RedoModal.tsx';import '/src/styles.css';
 createRoot(document.getElementById('root')).render(React.createElement(BrowserRouter,null,React.createElement(RedoModal,{id:'video',title:'My recording',open:true,onClose:()=>{window.closedDialog=true;}})));
 </script>`));}
let browser;
try{
 await server.listen();browser=await chromium.launch({executablePath:chromePath(),args:['--disable-gpu']});
 const base='http://127.0.0.1:'+server.httpServer.address().port;
 const directors=[['best','Best available'],['local','Local AI'],['claude@pc','Claude on this PC'],['codex@pc','Codex on this PC'],['claude-server','Claude on the server'],['rules','Built-in rules']];
 for(const [width,theme] of [[1280,'light'],[1280,'dark'],[400,'light'],[400,'dark']]){
  const ctx=await browser.newContext({viewport:{width,height:950},colorScheme:theme});const runs=[],errors=[];
  await ctx.route('**/api/**',route=>{
   const p=new URL(route.request().url()).pathname;
   if(p.endsWith('/run')){runs.push(route.request().postDataJSON());return route.fulfill({json:{id:'fake-job'}});}
   if(p==='/api/directors')return route.fulfill({json:{directors:directors.map(([id,label])=>({id,label,available:true,note:'Ready'}))}});
   return route.fulfill({json:{video_kind:'explainer',options:{director:'best',look:'classic'}}});
  });
  const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
  for(const [i,[id,label]] of directors.entries()){
   await page.goto(base+'/__redo');await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
   const group=page.getByRole('radiogroup',{name:'Director',exact:true});await group.getByRole('radio',{name:new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'))}).click();
   const styles=page.getByRole('radiogroup',{name:'Style',exact:true}).getByRole('radio');assert.equal(await styles.count(),9);
   await styles.nth(i%9).click();
   const chosen=await styles.nth(i%9).getAttribute('aria-checked');assert.equal(chosen,'true');
   assert.equal(await page.getByText('AI Provider',{exact:true}).count(),0);assert.equal(await page.getByText('Ollama Model',{exact:true}).count(),0);
   if(i===0){await page.screenshot({path:path.join(out,width+'-'+theme+'.png'),animations:'disabled'});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
   await page.getByRole('button',{name:'Direct again',exact:true}).click();
   await page.waitForFunction(()=>window.closedDialog===true);
   assert.equal(runs.at(-1).director,id);assert.equal(runs.at(-1).from_stage,'plan');assert(!('ai_provider' in runs.at(-1)));assert(!('ai_model' in runs.at(-1)));
  }
  assert.deepEqual(errors,[]);await ctx.close();console.log(width+' '+theme+': all six directors, all nine styles offered, project-only request, no errors/overflow PASS');
 }
}finally{await browser?.close();await server.close();}
