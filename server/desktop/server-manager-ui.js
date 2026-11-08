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
    if(action==='open-log'){$('log-content').textContent=result.log||'No log entries yet.';$('overview').hidden=true;$('engine-screen').hidden=true;$('log-screen').hidden=false;}}
  catch(e){showError(e.message.replace(/^Error invoking remote method '[^']+': (?:Error: )?/,''));}
  finally{pending=false;for(const b of document.querySelectorAll('button'))b.disabled=false;await refresh();}
}
for(const [id,action] of Object.entries({workspace:'engine-settings','gpu-choose':'gpu-settings',start:'start',stop:'stop',restart:'restart',copy:'copy-address',log:'open-log',quit:'quit'}))$(id).onclick=()=>act(action);
$('refresh').onclick=refresh;
$('autostart').onchange=()=>act($('autostart').checked?'autostart-on':'autostart-off');
$('engine-back').onclick=overview;$('log-back').onclick=overview;$('log-refresh').onclick=()=>act('open-log');
api.onProgress(value=>{if(value.engines){act('engine-settings');return;}if(value.gpu){act('gpu-settings');return;}if(value.step)$('progress').textContent=value.step;refresh();});
refresh();setInterval(refresh,4000);
