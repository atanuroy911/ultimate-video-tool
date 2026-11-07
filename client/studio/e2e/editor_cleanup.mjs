// E6: actual editor controls in a software-only browser, with an in-memory review.
// This fixture never starts a Video Tool server or requests renders/thumbnails.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createServer } from 'vite';
import { chromium } from 'playwright-core';
import { chromePath } from './common.mjs';

const out = path.resolve('e2e/out/editor-cleanup');
fs.mkdirSync(out, { recursive: true });
const server = await createServer({ server: { host: '127.0.0.1', port: 0 }, logLevel: 'error', plugins: [{ name: 'editor-cleanup-fixture', configureServer(s) { s.middlewares.use('/__editor', fixture); } }] });
async function fixture(req, res) {
  res.setHeader('Content-Type', 'text/html');
  res.end(await server.transformIndexHtml('/__editor', `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">
import React,{useState} from 'react';import {createRoot} from 'react-dom/client';
import Inspector from '/src/review/Inspector.tsx';import ScenesPanel from '/src/review/ScenesPanel.tsx';import Timeline from '/src/review/Timeline.tsx';
import '/src/styles.css';import '/src/ds/ds.css';import '/src/social/social.css';
const member={type:'object',properties:{who:{enum:['man','woman','girl','old_woman']},name:{type:'string',maxLength:14},pose:{enum:['stand','point','think','wave','celebrate','sad','shrug','walk','sit','idle','run','laugh','count','confused','ride']},expression:{enum:['neutral','happy','sad','laugh','confused']},x:{type:'number',minimum:0,maximum:1},y:{anyOf:[{type:'number',minimum:0,maximum:1},{type:'null'}]},arrive:{anyOf:[{type:'number',minimum:0,maximum:30},{type:'null'}]},flip:{type:'boolean'},hair:{type:'string',default:'',pattern:'^(?:|#[0-9a-fA-F]{6})$'},clothes:{type:'string',default:'',pattern:'^(?:|#[0-9a-fA-F]{6})$'}}};
const cat={elements:[{type:'cartoon',name:'Cartoon',defs:{},fields:{character_style:{enum:['classic','ink','paper']},cast:{type:'array',minItems:1,maxItems:3,items:member},at_word:{type:'string'}}}],layouts:{},transitions:[],motion:{entrances:[]}};
const scene={id:'s1',beats:['b1'],layout:'hero',transition_in:'cut',caption:{highlight_words:[]},elements:[{type:'cartoon',at_word:'w1',character_style:'classic',cast:[{who:'girl',name:'Maya',pose:'stand',expression:'happy',x:.5,y:null,arrive:null,flip:false}],start:0,end:4},{type:'big_number',value:'3',at_word:'w1',start:3.95,end:4}]};
const noop=()=>{};window.saved=[];
function App(){const [sc,setSc]=useState(scene);const [thumbs,setThumbs]=useState({});const [video,setVideo]=useState(true);const [selectedEl,setSelectedEl]=useState(null);
const r={id:'fixture',plan:{planner:'manual',scenes:[sc]},aspect:'9:16',beats:[{id:'b1',text:'Maya waves hello.'}],words:[{id:'w1',text:'Maya',start:0,end:1}],timing:{duration:4,scenes:[{id:'s1',start:0,end:4}]},th:{data:{scenes:thumbs}},sc:{data:{elements:{}}},project:{data:{id:'fixture',media:[]}},audio:null,audioSaving:false,patchScene:async(id,patch)=>{window.saved.push(patch);setSc(s=>({...s,...patch}));},patchElement:async()=>{},reloadAll:noop};
window.setThumb=src=>setThumbs({s1:src});const layers={doc:{v:1,tracks:[],clips:[]},saving:false,commit:noop};
return React.createElement('main',{style:{padding:12,maxWidth:1200,margin:'auto'}},
React.createElement('div',{className:'ed-workspace-bar'},React.createElement('strong',null,'Editor controls'),React.createElement('button',{className:'btn sm '+(video?'primary':''),'aria-pressed':video,onClick:()=>setVideo(!video)},'Video settings')),
React.createElement('div',{style:{display:'grid',alignItems:'start',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,300px),1fr))',gap:16,marginTop:16}},React.createElement(ScenesPanel,{r,selected:'s1',onSelect:noop,seek:noop}),React.createElement(Inspector,{r,scene:sc,index:0,time:r.timing.scenes[0],words:r.words,playheadWord:'w1',cat,icons:{}})),
React.createElement('div',{style:{marginTop:16}},React.createElement(Timeline,{r,duration:4,seek:noop,selected:'s1',onSelect:noop,selectedEl,onSelectEl:(scene,index)=>setSelectedEl({scene,index}),tool:'select',setTool:noop,snap:true,setSnap:noop,sel:null,setSel:noop,layers,media:new Map(),selLayer:null,onSelectLayer:noop,onAddMedia:noop})));
}createRoot(document.getElementById('root')).render(React.createElement(App));</script>`));
}
let browser;
try {
  await server.listen();
  browser = await chromium.launch({ executablePath: chromePath(), args: ['--disable-gpu'] });
  for (const [width, theme] of [[1280, 'light'], [1280, 'dark'], [400, 'light'], [400, 'dark']]) {
    const ctx = await browser.newContext({ viewport: { width, height: 1050 }, colorScheme: theme });
    await ctx.route('**/api/**', route => route.abort('blockedbyclient'));
    const page = await ctx.newPage(); page.setDefaultTimeout(10000);
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:' + server.httpServer.address().port + '/__editor');
    await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
    const settings = page.getByRole('button', { name: 'Video settings', exact: true });
    await settings.hover();
    await page.waitForTimeout(250); // finish the shared button's colour transition
    await page.screenshot({ path: path.join(out, width + '-' + theme + '-settings.png') });
    const colours = await settings.evaluate(b => ({ text: getComputedStyle(b).color, background: getComputedStyle(b).backgroundColor }));
    console.log(width, theme, 'selected hover colours', colours);
    assert.equal(colours.text, 'rgb(255, 255, 255)', 'selected Video settings keeps white text on hover');
    assert.equal(await page.getByRole('button', { name: 'JSON', exact: true }).count(), 0, 'JSON is outside everyday tabs');
    const inspector = page.locator('.inspector');
    assert.equal(await inspector.locator('select').first().locator('option:checked').textContent(), 'Classic colour');
    await page.getByRole('group', { name: 'Horizontal position' }).getByRole('slider').fill('67');
    await page.getByRole('group', { name: 'Height of the feet' }).getByRole('slider').fill('62');
    await page.getByLabel('Arrives after (seconds)', { exact: true }).fill('1.4');
    await page.getByRole('radio', { name: 'Wave', exact: true }).click();
    await page.getByLabel('Face the other way').check();
    await page.waitForFunction(() => window.saved.at(-1)?.elements?.[0].cast[0].flip === true);
    const member = await page.evaluate(() => window.saved.at(-1).elements[0].cast[0]);
    assert.deepEqual([member.x, member.y, member.arrive, member.pose, member.flip], [.67, .62, 1.4, 'wave', true]);
    assert.equal(await page.getByRole('radiogroup', { name: 'Pose' }).locator('.picture-choice-visual svg').count(), 15, 'each pose has a picture, including the new C3 actions');
    await page.getByLabel('Hair colour', { exact: true }).fill('#123456');
    await page.getByLabel('Clothes colour', { exact: true }).fill('#789abc');
    await page.waitForFunction(() => window.saved.at(-1)?.elements?.[0].cast[0].clothes === '#789abc');
    assert.equal(await page.evaluate(() => window.saved.at(-1).elements[0].cast[0].hair), '#123456');
    await page.getByRole('button', { name: 'Reset hair colour to automatic', exact: true }).click();
    await page.getByRole('button', { name: 'Reset clothes colour to automatic', exact: true }).click();
    await page.waitForFunction(() => window.saved.at(-1)?.elements?.[0].cast[0].clothes === '');
    assert.equal(await page.evaluate(() => window.saved.at(-1).elements[0].cast[0].hair), '', 'automatic colour stays empty rather than saving the picker fallback');
    await page.getByRole('button', { name: 'Use floor', exact: true }).click();
    await page.getByLabel('Arrives after (seconds)', { exact: true }).fill('');
    await page.waitForFunction(() => window.saved.at(-1)?.elements?.[0].cast[0].arrive === null);
    assert.equal(await page.evaluate(() => window.saved.at(-1).elements[0].cast[0].y), null, 'automatic floor stays null');
    assert(await page.locator('.scene-card .scene-thumbnail-skeleton').isVisible(), 'missing thumbnail has a loading skeleton');
    await page.screenshot({ path: path.join(out, width + '-' + theme + '-loading.png'), animations: 'disabled', fullPage: true });
    await page.evaluate(() => window.setThumb('data:image/svg+xml,invalid'));
    await page.getByRole('img', { name: 'Scene 1 preview unavailable', exact: true }).first().waitFor();
    assert.equal(await page.locator('.scene-card .scene-thumbnail').getAttribute('aria-busy'), 'false', 'failed image stops loading and names its fallback');
    await page.evaluate(() => window.setThumb('data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="54" height="96"><rect width="54" height="96" fill="#568ab0"/></svg>')));
    await page.waitForFunction(() => document.querySelector('.scene-card .scene-thumbnail img')?.complete);
    assert.equal(await page.locator('.scene-card .scene-thumbnail-skeleton').count(), 0, 'skeleton ends when image loads');
    const chip = page.getByRole('button', { name: 'Edit Cartoon visual', exact: true });
    assert(await chip.locator('svg').isVisible(), 'timeline chip has a recognisable icon');
    const short = page.getByRole('button', { name: 'Edit Number visual', exact: true });
    assert(await short.locator('svg').isVisible());
    assert(await short.evaluate(el => el.classList.contains('narrow')), 'short clips use icons instead of clipped words');
    await chip.focus(); await page.keyboard.press('Enter');
    assert.equal(await chip.getAttribute('aria-pressed'), 'true');
    await page.locator('.editor-advanced > summary').first().click();
    assert(await page.getByLabel('Everything about this visual (checked when saved)').isVisible());
    await page.locator('.editor-advanced > summary').first().click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(out, width + '-' + theme + '.png'), animations: 'disabled', fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'page fits viewport');
    assert.deepEqual(errors, []);
    console.log(width + ' ' + theme + ': labels, character saves, Advanced, thumbnail loading and timeline icon PASS');
    await ctx.close();
  }
} finally { await browser?.close(); await server.close(); }
