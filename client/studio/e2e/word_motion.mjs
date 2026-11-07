// C5: real GSAP recipes and CSS in software Chrome, on text fixtures only.
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
import {chromium} from 'playwright-core';import {chromePath} from './common.mjs';
const runtime=path.resolve('../../server/renderer/runtime'),out=path.resolve('e2e/out/word-motion');fs.mkdirSync(out,{recursive:true});
const executable=chromePath();console.log('Word-motion browser located');
const browser=await chromium.launch({executablePath:executable,args:['--disable-gpu'],timeout:15000});
try{for(const [lang,text] of [['en','Every word stays together and wraps at a space.'],['bn','প্রতিটি শব্দ নিজের জায়গায় থাকে এবং সুন্দর করে নড়ে।']]){
for(const recipe of ['blur-slide','word-relay-geometry']){
const page=await browser.newPage({viewport:{width:540,height:500}});
page.setDefaultTimeout(10000);
await page.setContent('<style>body{background:#fff;color:#111;padding:20px}#words{width:260px;font:32px sans-serif;line-height:1.5}</style><p id="words"></p>');
await page.addStyleTag({content:process.env.VT_WORD_BASELINE ? fs.readFileSync(path.join(runtime,'vt.css'),'utf8').replace('.mw, .mc { display: inline-block; white-space: pre; }','') : fs.readFileSync(path.join(runtime,'vt.css'),'utf8')});
await page.addStyleTag({content:'body{background:#fff;color:#111;padding:20px}'});
await page.addScriptTag({path:path.resolve('../../server/renderer/node_modules/gsap/dist/gsap.min.js')});
await page.evaluate(()=>window.VTX={});await page.addScriptTag({path:path.join(runtime,'vt-motion.js')});
const report=await page.evaluate(({text,recipe})=>{
 const root=document.querySelector('#words');root.textContent=text;
 const tl=gsap.timeline({paused:true});window.wordTimeline=tl;VTX.motionEnter(recipe,tl,root,0,'test');
 tl.seek(.16);const first=root.querySelector('.mw'),mid=first.getBoundingClientRect(),transform=getComputedStyle(first).transform;
 const display=getComputedStyle(first).display;tl.seek(10);const rest=first.getBoundingClientRect();
 return {display,transform,mid:[mid.x,mid.y,mid.width,mid.height],rest:[rest.x,rest.y,rest.width,rest.height],text:root.textContent,rows:new Set([...root.querySelectorAll('.mw')].map(n=>Math.round(n.getBoundingClientRect().top))).size};
},{text,recipe});
assert.equal(report.display,'inline-block');assert.equal(report.text,text);assert(report.rows>1,'words wrap');
assert.notDeepEqual(report.mid,report.rest,'mid-motion has a different measured box');
await page.screenshot({path:path.join(out,lang+'-'+recipe+'-rest.png'),timeout:10000});
await page.evaluate(()=>{window.wordTimeline.seek(.16);});
await page.screenshot({path:path.join(out,lang+'-'+recipe+'-moving.png'),timeout:10000});await page.close();console.log(lang+' '+recipe+': words move, wrap and preserve spaces PASS');
}}
}finally{await browser.close();}
