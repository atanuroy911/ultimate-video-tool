// C3/C4: production SVG cartoon rigs in software Chrome; no app server, model or video renderer.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright-core';
import {chromePath} from './common.mjs';

const out=path.resolve('e2e/out/cartoon-vocabulary');
const python=process.env.VT_PYTHON||path.resolve('../../.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const fixture=JSON.parse(execFileSync(python,[path.resolve('../../scripts/lab/cartoon_vocabulary_fixture.py')],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}));
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:chromePath(),args:['--disable-gpu']});
try{
 const context=await browser.newContext({viewport:{width:2000,height:1540},deviceScaleFactor:1});
 await context.setOffline(true);
 const page=await context.newPage();
 await page.setContent(`<style>
 :root{--accent:#e87943;--accent2:#43a9b8;--bg:#fff9ee;--ink:#263044;--card:#fff;--s:.5;--radius:12px;--stroke:0;--card-border:transparent;--sh-x:0;--sh-y:0;--sh-color:transparent;--tag-bg:#fff;--tag-ink:#263044}
 *{box-sizing:border-box}body{margin:0;padding:18px;background:#f0eee8;color:#263044;font-family:Arial,sans-serif}h1{font-size:23px;margin:0 0 12px}.grid{display:grid;grid-template-columns:repeat(10,190px);gap:7px}.tile{background:white;border:1px solid #d5d7da;border-radius:10px;overflow:hidden}.label{text-align:center;font-size:15px;font-weight:bold;padding:7px}.tile .cn-stage{width:100%;height:265px;aspect-ratio:auto;border:0;border-radius:0;box-shadow:none}.tile .cn-actor{width:calc(65% * var(--k,1));bottom:6%}.tile .cn-name{display:none}.tile .cn{border-radius:0}.zoom{grid-template-columns:repeat(3,470px)}.zoom .cn-stage{height:470px}.zoom .cn-actor{width:calc(48% * var(--k,1));bottom:6%}
 </style><h1 id="title"></h1><div id="grid" class="grid"></div>`);
 await page.addStyleTag({path:path.resolve('../../server/renderer/runtime/vt-media.css')});
 // Our contact-sheet sizing follows the production CSS, so override only the fixed card dimensions after loading it.
 await page.addStyleTag({content:'.tile .cn-stage{width:100%;height:265px;aspect-ratio:auto;border:0;border-radius:0;box-shadow:none}.tile .cn-actor{width:calc(55% * var(--k,1));bottom:6%}.tile .cn-name{display:none}.zoom .cn-stage{height:470px}.zoom .cn-actor{width:calc(48% * var(--k,1));bottom:6%}'});
 await page.addScriptTag({path:path.resolve('../../server/renderer/node_modules/gsap/dist/gsap.min.js')});
 await page.evaluate(()=>{
  window.VTX={C:{},h:(tag,cls,text)=>{const el=document.createElement(tag);el.className=cls||'';if(text)el.textContent=text;return el;},rt:(tag,cls,text)=>{const el=document.createElement(tag);el.className=cls;el.textContent=text;return el;},fit:()=>{},idle:()=>{}};
 });
 await page.addScriptTag({path:path.resolve('../../server/renderer/runtime/vt-cartoon.js')});
 await page.evaluate(()=>{
  window.make=(member,pose,label,cues=[])=>{
   const tile=document.createElement('div');tile.className='tile';
   const title=document.createElement('div');title.className='label';title.textContent=label;tile.appendChild(title);
   const d={set:'plain',camera:'still',cast:[{...member,pose,x:.5,arrive:0}],cues};
   const rendered=VTX.C.cartoon(d,{D:{format:{width:1000,height:700}}});tile.appendChild(rendered.el);document.querySelector('#grid').appendChild(tile);
   const rig=tile.querySelector('.ch'),identity=rig.outerHTML;
   const timeline=gsap.timeline({paused:true});rendered.enter(timeline,0,{dur:.3,ease:'none'},null,{start:0,end:4});timeline.seek(3.2);
   return{tile,rig,timeline,identity};
  };
 });
 const {who,poses}=fixture;
 for(let group=0;group<Math.ceil(poses.length/5);group++){
  const selected=poses.slice(group*5,group*5+5);
  await page.evaluate(({who,poses})=>{document.querySelector('#grid').replaceChildren();document.querySelector('#grid').className='grid';document.querySelector('#title').textContent='Production cartoon rigs — '+poses.join(', ');for(const pose of poses)for(const person of who)make({who:person,name:'Maya',expression:'neutral'},pose,`${person} · ${pose}`);},{who,poses:selected});
  await page.screenshot({path:path.join(out,`all-people-poses-${group+1}.png`),fullPage:true});
 }
 const results=await page.evaluate(()=>{
  document.querySelector('#grid').replaceChildren();document.querySelector('#grid').className='grid zoom';document.querySelector('#title').textContent='New poses — actual articulated rigs';
  const newer=['idle','run','laugh','count','confused','ride'];
  const drawn=newer.map(pose=>make({who:'woman',name:'Maya',expression:'neutral'},pose,pose));
  const signatures=drawn.map(({rig})=>[...rig.querySelectorAll('.ch-body,.ch-legL,.ch-legR,.ch-shin,.ch-armL,.ch-armR,.ch-forearm,.ch-head,.ch-bike')].map(el=>el.getAttribute('transform')+'|'+el.getAttribute('opacity')).join(';'));
  const laugh=drawn[2],count=drawn[3],ride=drawn[5];
  const bikeVisible=+getComputedStyle(ride.rig.querySelector('.ch-bike')).opacity===1;
  const fingers=[...count.rig.querySelectorAll('.ch-count-finger')].filter(el=>+getComputedStyle(el).opacity===1).length;
  const laughingEyes=+getComputedStyle(laugh.rig.querySelector('.ch-laugh-eyes')).opacity===1;
  const motion={};for(const i of [0,1,2,5]){const item=drawn[i];item.timeline.seek(.7);const before=item.rig.outerHTML;item.timeline.seek(1.03);motion[newer[i]]=before!==item.rig.outerHTML;item.timeline.seek(3.2);}
  return{distinct:new Set(signatures).size,bikeVisible,fingers,laughingEyes,motion};
 });
 assert.equal(results.distinct,6);assert(results.bikeVisible);assert.equal(results.fingers,3);assert(results.laughingEyes);for(const [pose,moving]of Object.entries(results.motion))assert(moving,pose+' must move');
 await page.screenshot({path:path.join(out,'new-poses-detail.png'),fullPage:true});
 const identity=await page.evaluate(()=>{
  document.querySelector('#grid').replaceChildren();document.querySelector('#grid').className='grid zoom';document.querySelector('#title').textContent='Named identity across scenes and explicit colours';
  const first=make({who:'old_woman',name:'Maya'},'stand','Maya · scene one · automatic');
  const second=make({who:'old_woman',name:'Maya'},'wave','Maya · scene two · automatic');
  const colored=make({who:'old_woman',name:'Maya',hair:'#ded0c4',clothes:'#8758ab'},'stand','Maya · chosen hair and clothes');
  const next=make({who:'old_woman',name:'Maya',hair:'#ded0c4',clothes:'#8758ab'},'count','Maya · same chosen colours');
  const other=make({who:'woman',name:'Riya',hair:'#252525',clothes:'#23776c'},'stand','Riya · different adult');
  const another=make({who:'woman',name:'Sam',hair:'#8e4324',clothes:'#c05b6f'},'stand','Sam · different adult');
  return{autoSame:first.identity===second.identity,explicitSame:colored.identity===next.identity,hair:colored.rig.dataset.hair,clothes:colored.rig.dataset.clothes,adultsDiffer:other.identity!==another.identity};
 });
 assert(identity.autoSame);assert(identity.explicitSame);assert.equal(identity.hair,'#ded0c4');assert.equal(identity.clothes,'#8758ab');assert(identity.adultsDiffer);
 await page.screenshot({path:path.join(out,'identity-and-colours.png'),fullPage:true});
 const expressions=await page.evaluate(()=>{
  document.querySelector('#grid').replaceChildren();document.querySelector('#title').textContent='New face expressions, independent of the body pose';
  const values=[];for(const expression of ['laugh','confused'])for(const who of ['woman','old_woman','robot']){
   const item=make({who,name:'Maya',expression},'stand',`${who} · ${expression} face`);
   values.push({who,expression,laugh:+getComputedStyle(item.rig.querySelector('.ch-laugh-eyes')).opacity,question:+getComputedStyle(item.rig.querySelector('.ch-question')).opacity});
  }return values;
 });
 for(const face of expressions){assert.equal(face.laugh,face.expression==='laugh'?1:0);assert.equal(face.question,face.expression==='confused'?1:0);}
 await page.screenshot({path:path.join(out,'new-expressions.png'),fullPage:true});
 const counting=await page.evaluate(fixture=>{
  document.querySelector('#grid').replaceChildren();document.querySelector('#title').textContent='Requested counts one to five, including the production Story kit cue';
  const visible=rig=>[...rig.querySelectorAll('.ch-count-finger')].filter(el=>+getComputedStyle(el).opacity===1).length;
  const counts=[];for(let count=1;count<=5;count++){const item=make({who:'woman',name:'Maya',count},'count',`${count} fingers`);counts.push(visible(item.rig));}
  const actual=make(fixture.cast[0],fixture.cast[0].pose,'Script director requested five',fixture.cues);actual.timeline.seek(1.35);
  return{counts,directorCue:fixture.cues[0].count,directorVisible:visible(actual.rig)};
 },fixture.count5);
 assert.deepEqual(counting.counts,[1,2,3,4,5]);assert.equal(counting.directorCue,5);assert.equal(counting.directorVisible,5);
 await page.screenshot({path:path.join(out,'count-one-to-five.png'),fullPage:true});
 const transitions=await page.evaluate(()=>{
  document.querySelector('#grid').replaceChildren();
  const item=make({who:'man',name:'Sam'},'stand','Cue reset',[{actor:0,start:0,end:1,pose:'ride',expression:'neutral'},{actor:0,start:1,end:2,pose:'stand',expression:'neutral'},{actor:0,start:2,end:3,pose:'count',expression:'neutral'},{actor:0,start:3,end:4,pose:'idle',expression:'neutral'}]);
  const snapshots=[];for(const t of [.5,1.5,2.8,3.5,.5,3.5]){item.timeline.seek(t);snapshots.push({t,bike:+getComputedStyle(item.rig.querySelector('.ch-bike')).opacity,fingers:[...item.rig.querySelectorAll('.ch-count-finger')].filter(el=>+getComputedStyle(el).opacity===1).length,armY:+gsap.getProperty(item.rig.querySelector('.ch-armR'),'y')});}return snapshots;
 });
 assert.equal(transitions[0].bike,1);assert.equal(transitions[1].bike,0);assert.equal(transitions[1].armY,0);assert.equal(transitions[2].fingers,3);assert.equal(transitions[3].fingers,0);assert.equal(transitions[4].bike,1);assert.equal(transitions[5].bike,0);
 await fs.writeFile(path.join(out,'checks.json'),JSON.stringify({people:who.length,poses:poses.length,combinations:who.length*poses.length,results,identity,expressions,counting,transitions},null,2));
 console.log('PASS: 150 who/pose combinations, six distinct animated poses, bicycle, counting fingers, laughing face, automatic/explicit identity, forward/backward cue resets.');
}finally{await browser.close();}
