// E5: actual Details sheet and conversation components, fake server responses.
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
import {createServer} from 'vite';import {chromium} from 'playwright-core';import {chromePath} from './common.mjs';
const out=path.resolve('e2e/out/details-readability');fs.mkdirSync(out,{recursive:true});
const server=await createServer({server:{host:'127.0.0.1',port:0},logLevel:'error',plugins:[{name:'details-fixture',configureServer(s){s.middlewares.use('/__details',fixture);}}]});
async function fixture(req,res){res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml('/__details',`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">
import React from 'react';import {createRoot} from 'react-dom/client';import {DirectorLog} from '/src/log/DirectorLog.tsx';import '/src/styles.css';createRoot(document.getElementById('root')).render(React.createElement(DirectorLog,{pid:'video',onClose:()=>{}}));
</script>`));}
let browser;
try{await server.listen();browser=await chromium.launch({executablePath:chromePath(),args:['--disable-gpu']});
for(const [width,theme]of [[1280,'light'],[1280,'dark'],[400,'light'],[400,'dark']]){
 const ctx=await browser.newContext({viewport:{width,height:950},colorScheme:theme});const errors=[];
 await ctx.route('**/api/**',async route=>{
 const url=new URL(route.request().url()),p=url.pathname;
 if(p.includes('/ai-talk-images/'))return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="160"><rect width="120" height="160" fill="coral"/></svg>'});
 if(p.endsWith('/calls'))return route.fulfill({json:{entries:url.searchParams.get('after')==='0'?Array.from({length:35},(_,i)=>({seq:i+1,t:'2026-11-06T10:00:00Z',id:'c'+i,module:'craft.check',plain:'Quality check: 80/100; 2 things to look at.',level:'warn',caller:{kind:'person'},cost:{seconds:1}})):[],running:[]}});
 const rows=[{seq:0,stage:'plan',who:'claude-pc',kind:'ask',model:'sonnet',preview:'Place Maya beside the window',images:1},{seq:1,stage:'check',who:'claude-pc',kind:'ask',model:'sonnet',preview:'Measure the finished frame',images:0}].map(r=>({...r,at:'now',seconds:1,error:'',cached:false,size:60}));
 if(p.endsWith('/ai-talk'))return route.fulfill({json:{rows}});
 return route.fulfill({json:{...rows[0],system:'Keep every spoken fact.',prompt:'Place Maya beside the window',answer:'The label stays clear of her face.',image_files:['picture.png']}});
 });
 const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/__details');
 await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
 await page.getByTestId('log-row').first().waitFor();
 const tabs=page.getByRole('button',{name:'AI conversations',exact:true});assert(await tabs.isVisible());
 assert((await tabs.boundingBox()).y>=0,'opening does not scroll tabs out of view');
 await tabs.click();await page.getByText('Place Maya beside the window',{exact:true}).waitFor();
 assert(await page.getByRole('heading',{name:'Planning the scenes',exact:true}).isVisible());
 await page.getByRole('button',{name:/Place Maya beside the window/}).click();
 await page.getByText('The label stays clear of her face.',{exact:true}).waitFor();
 const image=page.getByRole('img',{name:'Picture 1 sent to the director',exact:true});await image.waitFor();
 assert(await image.evaluate(img=>img.complete&&img.naturalWidth>0));
 await page.screenshot({path:path.join(out,width+'-'+theme+'.png'),animations:'disabled'});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);await ctx.close();console.log(width+' '+theme+': tabs visible on opening, grouped question previews, full text and pictures PASS');
}
}finally{await browser?.close();await server.close();}
