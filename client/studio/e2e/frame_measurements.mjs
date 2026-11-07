// C6/C7: production DOM measurement function in software Chrome; no video render.
import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
import {chromePath} from './common.mjs';
import {measureFrame} from '../../../server/renderer/scripts/measure-frame.mjs';
import path from 'node:path';

const browser=await chromium.launch({executablePath:chromePath(),args:['--disable-gpu']});
try{
 const page=await browser.newPage({viewport:{width:1080,height:1920}});
 const reset=async html=>{
  await page.setContent(`<style>body{margin:0;background:white}.scene{width:1080px;height:1920px;position:relative}.el{position:absolute}.el-tag{background:#fff;color:#000;font-size:50px}</style><div class="scene" data-scene="s1">${html}</div>`);
  await page.evaluate(()=>{window.__vt={seek:()=>{}};window.__guard=[];});
 };
 for(const kind of ['stick','story']){
  await reset(`<svg width="1080" height="1920"><g class="stk-ch" data-person="${kind}" data-name="Maya" transform="translate(100 200)"><circle data-face="${kind}" cx="60" cy="60" r="50"/><rect y="120" width="100" height="200"/></g></svg><div class="el el-tag" data-el="1" style="left:100px;top:200px;width:120px;height:120px">Hello</div>`);
  const facts=await page.evaluate(measureFrame,1,{});
  assert(facts.some(f=>f.includes("Maya's face")&&f.includes('100%')),facts.join('\n'));
  await page.locator('.el-tag').evaluate(node=>node.style.left='500px');
  assert(!(await page.evaluate(measureFrame,1,{})).some(f=>f.includes("Maya's face")));
  console.log(kind+': face coverage detected; clear face has no warning PASS');
 }
 await reset(`<div class="el el-media_frame" data-el="0" style="width:400px;height:400px"><img data-faces="[[0.4,0.2,0.2,0.2]]" data-person-name="Photo person" data-source-width="800" data-source-height="400" style="width:400px;height:400px;object-fit:cover;object-position:50% 50%"></div><div class="el el-tag" data-el="1" style="left:120px;top:80px;width:160px;height:80px">Picture</div>`);
 const photo=await page.evaluate(measureFrame,1,{});
 assert(photo.some(f=>f.includes("Photo person's face")&&f.startsWith('element 1')),photo.join('\n'));
 assert(!photo.some(f=>f.startsWith('element 0')&&f.includes("Photo person's face")),'photo never covers its own face');
 console.log('photo: cover crop mapping and own-container exclusion PASS');
 await reset(`<div class="el el-tag" data-el="2" style="left:970px;top:1650px;font-size:20px;color:rgb(180,180,180);background:white;opacity:.5">Small faint text</div>`);
 const facts=await page.evaluate(measureFrame,1,{});
 for(const needle of ['phone reading target','low text contrast','platform button','partly transparent'])assert(facts.some(f=>f.includes(needle)),needle+' missing: '+facts.join('\n'));
 assert.equal(await page.locator('.el-tag').getAttribute('style'),'left:970px;top:1650px;font-size:20px;color:rgb(180,180,180);background:white;opacity:.5','measuring changes nothing');
 await page.locator('.el-tag').evaluate(node=>node.style.display='none');
 assert.deepEqual(await page.evaluate(measureFrame,1,{}),[],'hidden scenes have no text warnings');
 console.log('text: size, solid contrast, platform zones, opacity and hidden-node exclusion PASS');
 // The real Story cartoon bundle, not just a marker fixture.
 await reset('');
 await page.addScriptTag({path:path.resolve('../../server/renderer/node_modules/gsap/dist/gsap.min.js')});
 await page.evaluate(()=>window.VTX={});
 await page.addScriptTag({path:path.resolve('../../server/renderer/runtime/vt-story.js')});
 await page.evaluate(()=>{
  const tl=gsap.timeline({paused:true});
  VTX.story(document.querySelector('.scene'),{id:'s1',start:0,end:4,story:{bg:{type:'plain',color:'#fff'},push:0,items:[{type:'person',char:'maya',x:270,y:560,pose:'stand',enter:'none'}]}},tl,{format:{width:1080,height:1920},story_cast:{maya:{name:'Maya',skin:'#A0663A',ear:'#9a6238',shirt:'#599875',pants:'#243450',hair:'#201710'}}});
  tl.seek(2);window.__vt={seek:t=>{tl.seek(t);}};
 });
 const head=await page.locator('[data-face="story"]').boundingBox();assert(head&&head.width>0);
 await page.evaluate(head=>{
  const overlay=document.createElement('div');overlay.className='el el-tag';overlay.dataset.el='9';
  Object.assign(overlay.style,{left:head.x+'px',top:head.y+'px',width:head.width+'px',height:head.height+'px',background:'red',zIndex:'30'});document.querySelector('.scene').appendChild(overlay);
 },head);
 assert((await page.evaluate(measureFrame,2,{})).some(f=>f.includes("Maya's face")),'actual Story cartoon face is measured');
 console.log('actual rebuilt Story cartoon bundle: sticker on named face detected PASS');
 await reset('');
 await page.evaluate(()=>window.VTX={});
 await page.addScriptTag({path:path.resolve('../../server/renderer/runtime/vt-stick.js')});
 await page.evaluate(()=>{
  const tl=gsap.timeline({paused:true});
  VTX.stick(document.querySelector('.scene'),{id:'s1',start:0,end:4,elements:[],stick:{t0:0,t1:4,set:{kind:'plain'},camera:{shot:'wide',move:'still'},cast:[{id:'maya',name:'Maya',role:'hero',style:{}}],actions:[]}},tl,{format:{width:1080,height:1920,aspect:'9:16'}});
  tl.seek(2);window.__vt={seek:t=>{tl.seek(t);}};
 });
 const stickHead=await page.locator('[data-face="stick"]').boundingBox();assert(stickHead&&stickHead.width>0);
 await page.evaluate(head=>{
  const overlay=document.createElement('div');overlay.className='el el-tag';overlay.dataset.el='8';
  Object.assign(overlay.style,{left:head.x+'px',top:head.y+'px',width:head.width+'px',height:head.height+'px',background:'red',zIndex:'30'});document.querySelector('.scene').appendChild(overlay);
 },stickHead);
 assert((await page.evaluate(measureFrame,2,{})).some(f=>f.includes("Maya's face")),'actual stick face is measured');
 console.log('actual stick runtime: sticker on named face detected PASS');
 // Read a photo through the actual media factory: detector metadata must make
 // it to the DOM, rather than only existing in Python's media document.
 await reset('');await page.evaluate(()=>window.VTX={});
 await page.addScriptTag({path:path.resolve('../../server/renderer/runtime/vt-media.js')});
 await page.evaluate(()=>{
  const media=VTX.mediaNode({media:{photo:{kind:'image',faces:[[.4,.2,.2,.2]],w:800,h:400,fx:.5,fy:.5,src:''}}},'photo');
  Object.assign(media.node.style,{width:'400px',height:'400px',objectFit:'cover'});document.querySelector('.scene').appendChild(media.node);
  const cover=document.createElement('div');cover.className='el el-tag';cover.dataset.el='7';Object.assign(cover.style,{left:'120px',top:'80px',width:'160px',height:'80px'});document.querySelector('.scene').appendChild(cover);
 });
 assert((await page.evaluate(measureFrame,1,{})).some(f=>f.includes("photo's face")),'actual photo factory propagates detector metadata');
 console.log('actual media factory: detector metadata reaches frame measurement PASS');
 await browser.close();
}finally{await browser.close();}
