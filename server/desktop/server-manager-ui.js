const api=window.serverManager;
const $=id=>document.getElementById(id);
let pending=false,refreshing=false,current=null,asked=false;
function showError(message){$('error').textContent=message;$('error').hidden=!message;}
function overview(){$('engine-screen').hidden=true;$('log-screen').hidden=true;$('overview').hidden=false;}
async function refresh(){
  if(refreshing)return;refreshing=true;
  try{current=await api.state();const running=current.running;
    $('computer').textContent=current.computer;
    $('status').textContent=current.operation? current.operation+'…' : (running?'Running':'Stopped');$('status').classList.toggle('on',running&&!current.operation);if($('dot'))$('dot').classList.toggle('on',running&&!current.operation);
    $('description').textContent=running?'Ready to make videos.':'Start it to make videos. Connected computers reconnect by themselves.';
    const lan=(current.addresses||[]).filter(a=>!/\/\/(127\.|localhost|\[::1\])/.test(a)).map(a=>a.replace(/^https?:\/\//,''));$('address').textContent=!running?'Start the server to see its address.':lan.length?lan.join('\n'):'Other computers can\'t reach it yet. Check that this computer is on your network.';
    for(const id of ['workspace','copy','stop','restart'])$(id).disabled=pending||!!current.operation||!running;
    const many=!!(running&&current.gpu&&current.gpu.cards>=2);$('gpu-card').hidden=!many;
    if(many){$('gpu-text').textContent=current.gpu.needs_choice?'Choose which cards Video Tool may use. Until then it uses one.':'Video Tool uses '+(current.gpu.allowed.join(', ')||'no card, only the processor')+'.';$('gpu-choose').disabled=pending||!!current.operation;
      if(current.askGpu&&!asked){asked=true;act('gpu-settings');}}
    $('start').hidden=running;$('stop').hidden=!running;$('restart').hidden=!running;$('start').disabled=pending||!!current.operation;
    $('autostart').checked=current.autostart;$('autostart').disabled=pending;
    $('tray-note').textContent=current.tray?'Closing this window keeps the server running in the tray.':'Keep this window open while you use the server.';
    $('progress').textContent=current.progress?.error?current.progress.step||'':current.operation?current.progress?.step||'':'';
    if(current.error)showError(current.error);
    if(!$('engine-screen').hidden){if(!running)overview();else {const url=current.url+'/manage?embedded=1';if(!$('engine-frame').src.startsWith(url))$('engine-frame').src=url;}}
  }catch(e){showError(e.message);}finally{refreshing=false;}
}
async function act(action){
  if(pending)return;pending=true;showError('');
  for(const b of document.querySelectorAll('button'))b.disabled=true;
  try{const result=await api.act(action);
    if(action==='engine-settings'||action==='gpu-settings'){$('engine-frame').src=result.url;$('overview').hidden=true;$('log-screen').hidden=true;$('engine-screen').hidden=false;}
    if(action==='open-log'){const first=$('log-screen').hidden;showLog(result.log||'',first);$('overview').hidden=true;$('engine-screen').hidden=true;$('log-screen').hidden=false;}}
  catch(e){showError(e.message.replace(/^Error invoking remote method '[^']+': (?:Error: )?/,''));}
  finally{pending=false;for(const b of document.querySelectorAll('button'))b.disabled=false;await refresh();}
}
for(const [id,action] of Object.entries({workspace:'engine-settings','gpu-choose':'gpu-settings',start:'start',stop:'stop',restart:'restart',copy:'copy-address',log:'open-log',quit:'quit'}))$(id).onclick=()=>act(action);
$('refresh').onclick=refresh;
$('autostart').onchange=()=>act($('autostart').checked?'autostart-on':'autostart-off');
$('engine-back').onclick=overview;$('log-back').onclick=overview;

// The log screen: Important (no routine requests, installs folded), Problems, Everything; search; the newest at the bottom, older on request; live while open.
const LOG_STEP=300;let logEntries=[],logView='important',logLimit=LOG_STEP,logRaw='';
function drawLog(scrollToEnd){
  const lv=window.LogView;if(!lv){$('log-content').textContent=logRaw||'No log entries yet.';return;}
  const sel=lv.renderLog($('log-content'),logEntries,{view:logView,query:($('log-search').value||'').trim(),limit:logLimit,step:LOG_STEP,scrollToEnd,onMore:()=>{logLimit+=LOG_STEP;drawLog(false);}});
  const n=$('log-problem-count');n.hidden=!sel.problems;n.textContent=String(sel.problems);
  $('log-note').textContent=logView==='important'&&sel.hiddenRequests?`${sel.hiddenRequests} routine requests are hidden. Choose Everything to see them.`:'';
}
function showLog(raw,first){logRaw=raw;logEntries=window.LogView?window.LogView.parseLog(raw):[];if(first)logLimit=LOG_STEP;drawLog(first);}
function setView(v){logView=v;logLimit=LOG_STEP;for(const [id,name] of [['log-important','important'],['log-problems','problems'],['log-everything','everything']]){const b=$(id);if(!b)continue;b.classList.toggle('on',name===v);b.setAttribute&&b.setAttribute('aria-selected',String(name===v));}drawLog(true);}
if($('log-important')){$('log-important').onclick=()=>setView('important');$('log-problems').onclick=()=>setView('problems');$('log-everything').onclick=()=>setView('everything');
  $('log-search').oninput=()=>{logLimit=LOG_STEP;drawLog(true);};
  $('log-copy').onclick=async()=>{try{await navigator.clipboard.writeText(logRaw);$('log-copy').textContent='Copied';setTimeout(()=>{$('log-copy').textContent='Copy';},1500);}catch{}};}
setInterval(async()=>{if($('log-screen').hidden||pending)return;try{const r=await api.act('open-log');if((r.log||'')!==logRaw)showLog(r.log||'',false);}catch{}},3000);
api.onProgress(value=>{if(value.engines){act('engine-settings');return;}if(value.gpu){act('gpu-settings');return;}if(value.step)$('progress').textContent=value.step;refresh();});
refresh();setInterval(refresh,4000);
