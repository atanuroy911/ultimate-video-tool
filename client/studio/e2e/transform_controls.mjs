// E17 controls in the real React components, with an in-memory layer document.
// No processing server, model, speech recognition or video render is started.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createServer } from "vite";
import { chromium } from "playwright-core";
import { chromePath } from "./common.mjs";

const out=path.resolve("e2e/out/transform-controls");fs.mkdirSync(out,{recursive:true});
const server=await createServer({server:{host:"127.0.0.1",port:0},logLevel:"error",plugins:[{name:"transform-fixture",configureServer(s){s.middlewares.use("/__controls",fixture);}}]});
async function fixture(req,res){
 res.setHeader("Content-Type","text/html");res.end(await server.transformIndexHtml('/__controls',`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">
 import React,{useState} from 'react';
 import {createRoot} from 'react-dom/client';
 import LayerInspector from '/src/review/LayerInspector.tsx';
 import {timeStore} from '/src/review/timeStore.ts';
 import '/src/styles.css';
 timeStore.set(1);
 const first={v:1,tracks:[{id:'track',name:'Picture',kind:'visual'}],clips:[{id:'clip',track:'track',type:'media',media:'photo',start:0,dur:4,fade_in:0,fade_out:0,x:.5,y:.5}]};
 function Fixture(){const [doc,setDoc]=useState(first);window.doc=doc;
 const layers={doc,setLocal:setDoc,commit:setDoc};
 return React.createElement('main',{style:{maxWidth:480,margin:'auto',padding:12}},React.createElement(LayerInspector,{layers,clip:doc.clips[0],media:new Map([['photo',{id:'photo',kind:'image',caption:'Test picture'}]]),total:4,onSelect:()=>{},seek:t=>timeStore.set(t),time:1}));}
 createRoot(document.getElementById('root')).render(React.createElement(Fixture));
 </script>`));
}
let browser;
try {
 await server.listen();
 browser=await chromium.launch({executablePath:chromePath(),args:["--disable-gpu"]});
 const base=`http://127.0.0.1:${server.httpServer.address().port}`;
 for(const [width,theme] of [[1280,'light'],[1280,'dark'],[400,'light'],[400,'dark']]) {
  const ctx=await browser.newContext({viewport:{width,height:950},colorScheme:theme});
  const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/__controls');
  await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
  await page.getByRole('tab',{name:'Position',exact:true}).click({timeout:10000}).catch(async e=>{console.error(errors,await page.locator('body').innerText());throw e;});
  await page.getByTestId('group-stretch-slant-and-flip').locator('summary').click();
  await page.getByRole('spinbutton',{name:'Stretch across, as a number',exact:true}).fill('180');
  assert.equal(await page.evaluate(()=>window.doc.clips[0].transform.stretch_x),1.8);
  await page.getByRole('button',{name:'Keyframe Stretch across',exact:true}).click();
  const points=await page.evaluate(()=>window.doc.clips[0].keyframes);
  assert.deepEqual(points.map(p=>p.time),[0,1]);assert(points.every(p=>p.stretch_x===1.8));
  assert.equal(await page.getByRole('button',{name:/^Keyframe /,includeHidden:true}).count(),12);
  await page.screenshot({path:path.join(out,width+'-'+theme+'.png'),animations:'disabled'});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);await ctx.close();
  console.log(width+' '+theme+': static media effects, value diamonds, full pose saved, no overflow/errors PASS');
 }
}finally {await browser?.close();await server.close();}
