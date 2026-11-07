// E7/E9: real Shell and video list; fake API and placeholder destinations.
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
import {createServer} from 'vite';import {chromium} from 'playwright-core';import {chromePath} from './common.mjs';
const out=path.resolve('e2e/out/navigation-dashboard');fs.mkdirSync(out,{recursive:true});
const server=await createServer({server:{host:'127.0.0.1',port:0},logLevel:'error',plugins:[{name:'nav-fixture',configureServer(s){s.middlewares.use('/__nav',fixture);}}]});
async function fixture(req,res){res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml('/__nav',`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">
 import React from 'react';import {createRoot} from 'react-dom/client';import {BrowserRouter,Routes,Route} from 'react-router-dom';import Shell from '/src/Shell.tsx';import Projects from '/src/pages/Projects.tsx';import '/src/styles.css';
 history.replaceState(null,'','/');const h=React.createElement;
 createRoot(document.getElementById('root')).render(h(BrowserRouter,null,h(Routes,null,h(Route,{element:h(Shell)},h(Route,{path:'/',element:h(Projects)}),...['themes','settings','server','social','shorts'].map(p=>h(Route,{key:p,path:'/'+p,element:h('h1',null,p)}))))));
 </script>`));}
let browser;
try{await server.listen();browser=await chromium.launch({executablePath:chromePath(),args:['--disable-gpu']});
for(const [width,theme] of [[1280,'light'],[1280,'dark'],[400,'light'],[400,'dark']]){
const ctx=await browser.newContext({viewport:{width,height:950},colorScheme:theme});
await ctx.routeWebSocket('**/ws',ws=>ws.send(JSON.stringify({type:'hello',jobs:[]})));
await ctx.route('**/api/**',r=>{const p=new URL(r.request().url()).pathname;
 if(p==='/api/system/stats')return r.fulfill({status:503,json:{detail:'No hardware in this test'}});
 const data=p==='/api/projects'?[1,2].map(i=>({id:'video'+i,title:'Video '+i,status:'draft',duration:12,scene_count:0,export_count:0,pending_requests:0,aspect:'9:16',created_at:'2026-11-06T10:00:00Z',updated_at:'2026-11-06T10:00:00Z',options:{}})):p==='/api/directors'?{order:[],directors:[]}:p==='/api/setup'?{done:true}:p==='/api/health'?{ok:true,api_version:999}:{};
 return r.fulfill({json:data});});
const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/__nav');await page.getByText('Video 1',{exact:true}).waitFor();
assert.equal(await page.getByRole('button',{name:'New',exact:true}).count(),0);
const filters=page.getByRole('group',{name:'Filter by status',exact:true});
if(width===400){assert(!(await filters.isVisible()));await page.getByRole('button',{name:'Filters',exact:true}).click();assert(await filters.isVisible());await page.getByRole('button',{name:'Filters',exact:true}).click();}
else assert(await filters.isVisible());
await page.screenshot({path:path.join(out,width+'-'+theme+'.png'),animations:'disabled'});
assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
if(width===400){const nav=page.getByRole('navigation',{name:'Main (phone)',exact:true});assert.equal(await nav.locator(':scope > a,:scope > button').count(),5);
 for(const destination of ['shorts','social','server']){await nav.locator('a[href="/'+destination+'"]').click();assert(new URL(page.url()).pathname==='/'+destination);}
 for(const [label,to] of [['Looks','themes'],['Settings','settings']]){await page.getByRole('button',{name:'More pages',exact:true}).click();await page.getByRole('navigation',{name:'More pages',exact:true}).getByRole('link',{name:label,exact:true}).click();assert(new URL(page.url()).pathname==='/'+to);}
 const targets=await nav.locator(':scope > a,:scope > button').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().height));assert(targets.every(h=>h>=44));
}
assert.deepEqual(errors,[]);await ctx.close();console.log(width+' '+theme+': dashboard actions/filters, five phone tabs and every destination reachable PASS');
}
}finally{await browser?.close();await server.close();}
