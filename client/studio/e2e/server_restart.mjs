// E15 restart card: fake supervisor responses, never an actual restart.
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
import {createServer} from 'vite';import {chromium} from 'playwright-core';import {chromePath} from './common.mjs';
const out=path.resolve('e2e/out/server-restart');fs.mkdirSync(out,{recursive:true});
const server=await createServer({server:{host:'127.0.0.1',port:0},logLevel:'error',plugins:[{name:'restart-fixture',configureServer(s){s.middlewares.use('/__restart',fixture);}}]});
async function fixture(req,res){res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml('/__restart',`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">
import React from 'react';import {createRoot} from 'react-dom/client';import ServerRestart from '/src/components/ServerRestart.tsx';import '/src/styles.css';createRoot(document.getElementById('root')).render(React.createElement('main',{style:{padding:20,maxWidth:700,margin:'auto'}},React.createElement(ServerRestart)));
</script>`));}
let browser;
try{await server.listen();browser=await chromium.launch({executablePath:chromePath(),args:['--disable-gpu']});
for(const [width,theme] of [[1280,'light'],[400,'dark']])for(const state of ['ready','busy','unavailable']){
 const ctx=await browser.newContext({viewport:{width,height:600},colorScheme:theme});let calls=0;
 await ctx.route('**/api/system/restart',r=>{
  if(r.request().method()==='POST'){calls++;return r.fulfill({json:{restarting:true}});}
  return r.fulfill({json:{available:state!=='unavailable',busy:state==='busy',restarting:false,note:state==='unavailable'?'Restart using the server manager.':'Apps reconnect automatically.'}});
 });
 const page=await ctx.newPage();await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/__restart');await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
 await page.getByTestId('server-restart').waitFor();const button=page.getByRole('button',{name:'Restart server',exact:true});
 if(state==='unavailable')assert.equal(await button.count(),0);else if(state==='busy')assert(await button.isDisabled());else{await button.click();await page.getByRole('button',{name:'Restarting…',exact:true}).waitFor();assert.equal(calls,1);}
 await page.screenshot({path:path.join(out,width+'-'+theme+'-'+state+'.png'),animations:'disabled'});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await ctx.close();console.log(width+' '+theme+' '+state+' PASS');
}
}finally{await browser?.close();await server.close();}
