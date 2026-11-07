// E4: real Result page, intercepted API. No render, model, social post or real project request.
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';
import {createServer} from 'vite';import {chromium} from 'playwright-core';import {chromePath} from './common.mjs';
const out=path.resolve('e2e/out/result-cleanup');fs.mkdirSync(out,{recursive:true});
const server=await createServer({server:{host:'127.0.0.1',port:0},logLevel:'error',plugins:[{name:'result-fixture',configureServer(s){s.middlewares.use('/__result',fixture);}}]});
async function fixture(req,res){res.setHeader('Content-Type','text/html');res.end(await server.transformIndexHtml('/__result',`<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script type="module">import React from 'react';import {createRoot} from 'react-dom/client';import {MemoryRouter,Routes,Route} from 'react-router-dom';import Result from '/src/pages/Result.tsx';import '/src/styles.css';import '/src/ds/ds.css';createRoot(document.getElementById('root')).render(React.createElement(MemoryRouter,{initialEntries:['/p/video/result']},React.createElement(Routes,null,React.createElement(Route,{path:'/p/:id/result',element:React.createElement(Result)}))));</script>`));}
const poster='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="420" height="747"><rect width="420" height="747" fill="#d9e8e7"/><circle cx="320" cy="150" r="140" fill="#b9d5d1"/><rect x="42" y="215" width="336" height="310" rx="26" fill="#fff"/><text x="70" y="285" font-family="Arial" font-size="27" fill="#233d3a">A little saved today.</text><text x="70" y="325" font-family="Arial" font-size="20" fill="#52716b">More choices tomorrow.</text><path d="M90 460L150 410L210 430L300 370" stroke="#2d806d" stroke-width="10" fill="none"/></svg>');
let browser;
try{await server.listen();browser=await chromium.launch({executablePath:chromePath(),args:['--disable-gpu']});
for(const [width,theme]of [[1280,'light'],[1280,'dark'],[400,'light'],[400,'dark']]){
 const ctx=await browser.newContext({viewport:{width,height:1050},colorScheme:theme});const calls=[],errors=[];let craftError=false,score=82,projectError=false;
 await ctx.route('**/video.mp4',r=>r.fulfill({status:204}));
 await ctx.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;
 if(req.method()!=='GET'){calls.push({path:p,body:req.postDataJSON()});return route.fulfill({json:{id:'fake-job'}});}
 if(p==='/api/projects/video')return route.fulfill(projectError?{status:404,json:{detail:'This video could not be found.'}}:{json:{id:'video',title:'A little saved today',aspect:'9:16',theme:'paper',video_kind:'cartoon',options:{},media:[]}});
 if(p.endsWith('/exports'))return route.fulfill({json:[{name:'cut-9x16-final.mp4',url:'/video.mp4',size:1024,retention:{verdict:'A few slow moments',risk:47,worst:[]},judges:{passed:true,failed:[],skipped:[],says:[],at:'now'}}]});
 if(p.endsWith('/craft'))return route.fulfill(craftError?{status:503,json:{detail:'The quality check is temporarily unavailable.'}}:{json:{score,violations:score===100?[]:[{rule:'hook.frame0',t0:0,t1:1,says:'The opening picture arrives late.',fix:'Bring the opening picture forward.'},{rule:'text.contrast',t0:2,t1:3,says:'A label is hard to read.',fix:'Make the label clearer.'}],passed:[],skipped:[]}});
 if(p.endsWith('/publish'))return route.fulfill({json:{kit:{title:'A little saved today',description:'An easy habit.',hashtags:['saving'],cover_url:poster}}});
 if(p.endsWith('/decisions'))return route.fulfill({json:{retakes:[],tighten:{target:null,cuts:[]},revise:{before:47,after:11,kept:true}}});
 if(p.endsWith('/director'))return route.fulfill({json:{report:null,messages:[{from:'viewer test',text:'Viewer test: at 2-3 s: the picture stays too long.'}]}});
 if(p.endsWith('/look-at'))return route.fulfill({json:{planner:'claude',looked:true,current:true,left:[],changed:[],guard_current:true}});
 if(p==='/api/themes')return route.fulfill({json:[{name:'paper',label:'Paper',color:{bg:'#fff',accent:'#0071e3',accent2:'#34c759',ink:'#111'}}]});
 if(p==='/api/directors')return route.fulfill({json:{directors:[]}});
 if(p==='/api/social/accounts'||p==='/api/social/groups')return route.fulfill({json:[]});
 return route.fulfill({json:{entries:[],running:[]}});
 });
 const page=await ctx.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/__result');await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
 await page.getByRole('link',{name:'Download',exact:true}).waitFor();
 // This is a layout fixture with a synthetic poster, never a playback test.
 await page.locator('video').evaluate(video=>{video.pause();video.removeAttribute('src');video.load();});
 await page.screenshot({path:path.join(out,width+'-'+theme+'-initial.png'),fullPage:true,animations:'disabled'});
 assert.equal(await page.locator('.btn.magic').count(),1,'one gradient action');
 const summary=page.getByText('Quality check: 82/100 · 2 things to look at',{exact:true});await summary.waitFor();
 const actions=page.getByRole('group',{name:'Change this video',exact:true});
 assert.deepEqual(await actions.locator('button,a').allTextContents(),[' Direct again',' Change the look',' Fix a word',' Edit everything']);
 assert.equal(await page.getByRole('link',{name:'Fix a word',exact:true}).getAttribute('href'),'/p/video?tab=words');
 await summary.click();await page.getByText(/The opening picture arrives late\./).waitFor();
 await page.getByRole('button',{name:'Auto-fix suggestions',exact:true}).click();await page.getByRole('button',{name:'Auto-fix suggestions',exact:true}).waitFor();assert.deepEqual(calls,[{path:'/api/projects/video/autofix',body:{}}]);
 assert.equal(await page.getByRole('button',{name:/Auto-fix|Fix the risky moments/}).count(),1,'only one autofix button');
 await page.getByText('What changed in this cut',{exact:true}).click();assert(!/risk 47|47\s*→\s*11/.test(await page.locator('body').innerText()));
 await page.getByText('What changed in this cut',{exact:true}).click();await summary.click();
 await page.getByRole('button',{name:'Change the look',exact:true}).click();assert(await page.getByRole('button',{name:'Paper',exact:true}).isVisible());await page.getByRole('button',{name:'Change the look',exact:true}).click();
 await page.locator('video').evaluate(video=>{video.removeAttribute('autoplay');video.pause();video.removeAttribute('src');video.load();});
 await page.evaluate(async()=>{window.scrollTo(0,0);await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});await page.screenshot({path:path.join(out,width+'-'+theme+'.png'),fullPage:true,animations:'disabled'});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no horizontal overflow');assert.deepEqual(errors,[]);
 if(width===1280&&theme==='light'){
   craftError=true;await page.reload();await page.getByText('Quality check unavailable',{exact:true}).waitFor();assert.equal(await page.getByText('82/100',{exact:false}).count(),0,'no invented fallback score');
   await page.getByText('Quality check unavailable',{exact:true}).click();craftError=false;score=100;await page.getByRole('button',{name:'Try again',exact:true}).click();await page.getByText('Quality check: 100/100 · Nothing to look at',{exact:true}).waitFor();
   projectError=true;await page.reload();await page.getByRole('heading',{name:'Could not open this video',exact:true}).waitFor();
   assert(await page.getByText('This video could not be found.',{exact:true}).isVisible());assert.equal(await page.getByRole('link',{name:'Back to your videos',exact:true}).getAttribute('href'),'/');
   await page.screenshot({path:path.join(out,'project-error.png'),animations:'disabled'});projectError=false;await page.getByRole('button',{name:'Try again',exact:true}).click();await page.getByRole('link',{name:'Download',exact:true}).waitFor();
 }
 console.log(width+' '+theme+': score, action order, one autofix, details, overflow PASS');await ctx.close();
}
}finally{await browser?.close();await server.close();}
