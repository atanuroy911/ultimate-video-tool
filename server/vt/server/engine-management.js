const $=id=>document.getElementById(id);let setup=null,reviewed=null,picture=null,job=null;
if(new URLSearchParams(location.search).has('embedded')){document.querySelector('a[href="/"]').hidden=true;document.querySelector('h1').hidden=true;}
// Icons: lucide's shapes, the same as the Studio's
const ICONS={pen:'<path d="M13 21h8"/><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/>',image:'<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
 zap:'<path d="M15.914 4a1.5 1.5 0 00-2.474-1.561l-9 9A1.5 1.5 0 005.5 14h4.002a.5.5 0 01.471.666L8.086 20a1.5 1.5 0 002.475 1.56l9-9A1.5 1.5 0 0018.5 10h-3.997a.5.5 0 01-.472-.667z"/>',hourglass:'<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
 ban:'<circle cx="12" cy="12" r="10"/><path d="M4.929 4.929 19.07 19.071"/>',sparkles:'<path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/><path d="M20 2v4"/><path d="M22 4h-4"/><circle cx="4" cy="20" r="2"/>',
 download:'<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>'};
function icon(name){const t=document.createElement('template');t.innerHTML='<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+ICONS[name]+'</svg>';return t.content.firstChild;}
for(const t of document.querySelectorAll('[data-icon]'))t.append(icon(t.dataset.icon));
const gb=n=>(n>=100?String(Math.round(n)):n>0?n.toFixed(1).replace(/\.0$/,''):'0')+' GB';
const message=(text,error=false)=>{$('message').textContent=text;$('message').classList.toggle('error',error);};
async function api(route,method='GET',body){const r=await fetch(route,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:d.detail?.errors?.[0]||'That didn\'t work. Try again.');return d;}
async function perform(fn){message('');try{await fn();}catch(e){message(e.message,true);}}
function element(tag,text){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;}
function button(text,fn){const b=element('button',text);b.onclick=()=>perform(async()=>{b.disabled=true;try{await fn();}finally{b.disabled=false;}});return b;}
async function engines(){const data=await api('/api/engines');$('engines').replaceChildren();for(const engine of data.filter(e=>['comfy','ollama'].includes(e.id))){
 const comfy=engine.id==='comfy',mode=engine.endpoint?.mode||'off',ok=!!engine.health?.ok;
 const card=element('section'),row=element('div');row.className='row';const h=element('h2');const tile=element('span');tile.className='tile '+engine.id;tile.append(icon(comfy?'image':'pen'));h.append(tile,comfy?'Picture AI (ComfyUI)':'Writing AI (Ollama)');row.append(h);
 const state=ok?['Ready','ready']:mode==='off'?['Not set up','']:mode==='local'?['Not running','warn']:['Not answering','warn'];
 const badge=element('span',state[0]);badge.className='badge'+(state[1]?' '+state[1]:'');row.append(badge);card.append(row);
 const what=element('p',ok?(comfy?'Draws the pictures.':'Plans each video and writes its script.')
  :mode==='off'?(comfy?'Not installed yet. Without it, each picture becomes a card with the key words.':'Not installed yet. Without it, videos are planned by simple rules or by Claude or Codex.')
  :mode==='local'?'Video Tool installed it and starts it when a video needs it. If it stays off, restart the server.'
  :'Check that it is running on that computer and that the address is right.');what.className='small';card.append(what);
 const actions=element('div');actions.className='actions';
 if(mode==='off'&&!ok){const go=element('button');go.className='primary';go.type='button';go.append(icon('download'),'Install');go.onclick=()=>{document.querySelector('[data-tab="install"]').click();document.querySelector(`[data-engine="${engine.id}"]`)?.click();};actions.append(go);}
 const label=element('label','Address'),input=element('input');input.value=engine.endpoint.url||engine.default_url;input.spellCheck=false;label.append(input);
 const connect=button(mode==='off'?'Use this address':'Connect',async()=>{const t=await api('/api/engines/'+engine.id+'/test','POST',{mode:'remote',url:input.value});if(!t.ok)throw new Error(t.why_not||'It didn\'t answer. Check that it is running and the address is right.');await api('/api/engines/'+engine.id,'PUT',{mode:'remote',url:input.value});message('Connected. It is ready.');await engines();});
 if(mode==='off'&&!ok){const more=element('details');more.append(element('summary','I already have it running'),label);const a2=element('div');a2.className='actions';a2.append(connect);more.append(a2);card.append(actions,more);}
 else{card.append(label);actions.append(connect);
  if(comfy)actions.append(button('Check models',async()=>{picture=await api('/api/discover/prepare?url='+encodeURIComponent(input.value));showPicture();}));
  if(!comfy&&ok&&!engine.health?.models?.length)actions.append(button('Download recommended model',async()=>follow(await api('/api/setup/ollama-model','POST',{}))));
  card.append(actions);}
 $('engines').append(card);
}}
function showPicture(){const p=picture;$('prepare').hidden=false;$('model-name').textContent=p.label;$('model-folder').replaceChildren(new Option('Where ComfyUI keeps them now',''),...(p.model_locations||[]).map(v=>new Option(v,v)));$('model-folder').value=p.models_dir||'';$('model-plan').textContent=p.files.map(f=>(f.have?'Have · ':'Needs download · ')+f.file+(f.have?'':' · '+f.gb+' GB')).concat(p.problems||[]).join('\n');$('prepare-go').textContent=p.download_gb?'Download missing models · '+p.download_gb+' GB':'Use these models';$('prepare-go').disabled=!!p.problems?.length;}
$('model-folder').onchange=()=>perform(async()=>{picture=await api('/api/discover/prepare?url='+encodeURIComponent(picture.url)+'&recipe='+encodeURIComponent(picture.recipe)+'&models_dir='+encodeURIComponent($('model-folder').value));showPicture();});
$('prepare-go').onclick=()=>perform(async()=>follow(await api('/api/discover/prepare','POST',{url:picture.url,recipe:picture.recipe,models_dir:picture.models_dir||''})));
let model='',showAll=false,plans=null,planTimer=0;
function config(){const engine=$('install-engine').value;return {engines:[engine],bundles:['pictures'],models_dir:$('models').value,install_dir:$('programs').value,picture_model:engine==='comfy'?model:undefined,language_model:engine==='ollama'?model:undefined};}
// The models for the chosen program as cards, each marked against this server's graphics card (GET /api/setup -> models): what runs well first, the rest on request
function fitText(m,gb){return !m.fits?m.why:m.speed==='fast'?(gb?'Runs well on the '+gb+' GB card':'Runs well here'):(m.why||(gb?'Works on the '+gb+' GB card, but slowly':'Works here, but slowly'));}
function showModels(){const m=setup?.models;if(!m)return;const engine=$('install-engine').value,list=engine==='comfy'?m.pictures:m.language,saved=engine==='comfy'?(setup.picture_model||m.picture_default):(setup.language_model||m.language_default);
 if(!list.some(x=>x.id===model&&x.fits)){const s=list.find(x=>x.id===saved&&x.fits);model=(s&&(s.speed==='fast'||!list.some(x=>x.recommended&&x.speed==='fast'))?s:(list.find(x=>x.recommended)||list.find(x=>x.fits)||{})).id||'';}
 const good=list.filter(x=>x.fits&&x.speed==='fast'),shown=showAll||!good.length?list:list.filter(x=>(x.fits&&x.speed==='fast')||x.id===model);
 const box=$('install-models');box.replaceChildren();
 for(const x of shown){const l=element('label');l.className=(x.id===model?'on ':'')+(x.fits?'':'off');const r=element('input');r.type='radio';r.name='install-model';r.value=x.id;r.checked=x.id===model;r.disabled=!x.fits;r.onchange=()=>{model=x.id;showModels();refreshPlan();};
  const g=element('span');g.className='grow';const b=element('b',x.label);if(x.recommended){const c=element('span');c.className='chip';c.append(icon('sparkles'),'Best for this card');b.append(c);}
  const f=element('span');f.className='small '+(!x.fits?'fit-no':x.speed==='fast'?'fit-fast':'fit-slow');f.append(icon(!x.fits?'ban':x.speed==='fast'?'zap':'hourglass'),' '+fitText(x,m.card.gb));g.append(b,f);
  const z=element('span',gb(x.download_gb));z.className='size';l.append(r,g,z);box.append(l);}
 const more=list.length-shown.length;if(more>0){const b=element('button','Show '+more+' bigger model'+(more>1?'s':'')+' (slow or too big for this card)');b.type='button';b.className='more';b.onclick=()=>{showAll=true;showModels();};box.append(b);}}
// What would download, worked out by itself whenever a choice changes; the button says the size
function refreshPlan(){clearTimeout(planTimer);plans=null;$('install-go').disabled=true;$('install-go').replaceChildren('Working out the size…');planTimer=setTimeout(()=>perform(async()=>{const c=config();const params=new URLSearchParams({engines:c.engines.join(','),bundles:'pictures',models_dir:c.models_dir,install_dir:c.install_dir});if(c.picture_model)params.set('picture_model',c.picture_model);if(c.language_model)params.set('language_model',c.language_model);
 plans=await api('/api/setup/plan?'+params);const total=plans.reduce((a,p)=>a+p.total_gb,0),problems=plans.flatMap(p=>p.problems);$('install-plan').replaceChildren();
 const d=element('details');d.append(element('summary','What downloads ('+gb(total)+')'));for(const plan of plans)d.append(element('pre',plan.items.map(i=>(i.done?'✓ Already there · ':'↓ ')+i.name+(i.done?'':' · '+gb(i.size_gb))).concat(plan.notes||[]).join('\n')));$('install-plan').append(d);
 for(const p of problems){const e=element('p',p);e.className='error';$('install-plan').append(e);}
 $('install-go').replaceChildren(icon('download'),total>0?'Install · '+gb(total):'Install');$('install-go').disabled=problems.length>0;}),250);}
for(const b of document.querySelectorAll('[data-engine]'))b.onclick=()=>{for(const o of document.querySelectorAll('[data-engine]'))o.setAttribute('aria-checked',String(o===b));$('install-engine').value=b.dataset.engine;model='';showAll=false;showModels();refreshPlan();};
for(const id of ['programs','models'])$(id).onchange=refreshPlan;
// Browse: folders on this server (the window may be on another computer), names only
async function browse(box,input,path){const d=await api('/api/setup/folders?path='+encodeURIComponent(path));box.replaceChildren();
 const drives=element('div');drives.className='drives';for(const r of d.roots){const b=element('button',r.name+' · '+Math.round(r.free_gb)+' GB free');b.type='button';b.onclick=()=>perform(()=>browse(box,input,r.path));drives.append(b);}box.append(drives);
 if(d.path){const here=element('div');here.className='here';const up=element('button','‹');up.type='button';up.disabled=!d.parent;up.setAttribute('aria-label','Up one folder');up.onclick=()=>perform(()=>browse(box,input,d.parent));here.append(up,element('span',d.path));box.append(here);
  const ul=element('ul');if(!d.folders.length)ul.append(element('li','No folders in here.'));for(const f of d.folders){const li=element('li'),b=element('button','📁 '+f.name);b.type='button';b.onclick=()=>perform(()=>browse(box,input,f.path));li.append(b);ul.append(li);}box.append(ul);
  const row=element('div');row.className='actions';const use=element('button',d.writable?'Use this folder':'Video Tool can’t save here');use.className='primary';use.type='button';use.disabled=!d.writable;use.onclick=()=>{input.value=d.path;box.hidden=true;input.onchange?.();};row.append(use);box.append(row);}}
for(const b of document.querySelectorAll('[data-browse]'))b.onclick=()=>perform(async()=>{const input=$(b.dataset.browse),box=document.querySelector('.browser[data-for="'+b.dataset.browse+'"]');box.hidden=!box.hidden;if(!box.hidden)await browse(box,input,input.value||input.placeholder.replace(/^Default folder$/,'')||(setup?.server?.data_dir||''));});
$('install-go').onclick=()=>perform(async()=>{$('install-go').disabled=true;follow(await api('/api/setup/install','POST',config()));});
async function follow(value){job=value;$('job').hidden=false;$('job-status').textContent=job.msg||job.status;$('job').scrollIntoView({block:'nearest'});}
setInterval(async()=>{if(!job||!['queued','running'].includes(job.status))return;try{job=await api('/api/jobs/'+job.id);$('job-status').textContent=job.status==='error'?job.error:Math.round(job.frac*100)+'% · '+(job.msg||job.status);$('job-cancel').hidden=!['queued','running'].includes(job.status);if(job.status==='done')engines();}catch{}},1500);
$('job-cancel').onclick=()=>perform(()=>api('/api/jobs/'+job.id+'/cancel','POST',{}));
addEventListener('hashchange',()=>{if(location.hash==='#cards')document.querySelector('[data-tab="cards"]').click();});
const tabs=[...document.querySelectorAll('[data-tab]')];
for(const tab of tabs){tab.onclick=()=>{for(const other of tabs){other.setAttribute('aria-selected',String(other===tab));other.tabIndex=other===tab?0:-1;}for(const panel of document.querySelectorAll('.tab-panel'))panel.hidden=panel.id!==tab.dataset.tab;};
 tab.tabIndex=tab.getAttribute('aria-selected')==='true'?0:-1;
 tab.onkeydown=e=>{const i=tabs.indexOf(tab),to={ArrowRight:i+1,ArrowLeft:i-1,Home:0,End:tabs.length-1}[e.key];if(to===undefined)return;e.preventDefault();const t=tabs[(to+tabs.length)%tabs.length];t.focus();t.click();};}
for(const b of document.querySelectorAll('[data-engine]'))b.onkeydown=e=>{const all=[...document.querySelectorAll('[data-engine]')],i=all.indexOf(b);if(!['ArrowRight','ArrowLeft','ArrowDown','ArrowUp'].includes(e.key))return;e.preventDefault();const t=all[(i+(e.key==='ArrowRight'||e.key==='ArrowDown'?1:-1)+all.length)%all.length];t.focus();t.click();};
perform(async()=>{setup=await api('/api/setup');$('computer').textContent=setup.server.name;$('programs').value=setup.install_dir||'';$('models').value=setup.models_dir||'';showModels();refreshPlan();await engines();const cards=await api('/api/system/gpus').catch(()=>null);if(location.hash==='#cards'||cards?.needs_choice)document.querySelector('[data-tab="cards"]').click();});
