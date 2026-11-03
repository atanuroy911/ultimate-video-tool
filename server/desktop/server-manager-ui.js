const api=window.serverManager;
const $=id=>document.getElementById(id);
let pending=false,refreshing=false,current=null;
function showError(message){$('error').textContent=message;$('error').hidden=!message;}
function overview(){$('engine-screen').hidden=true;$('log-screen').hidden=true;$('overview').hidden=false;}
async function refresh(){
  if(refreshing)return;refreshing=true;
  try{current=await api.state();const running=current.running;
    $('computer').textContent=current.computer;
    $('status').textContent=current.operation|| (running?'Running':'Stopped');$('status').classList.toggle('on',running&&!current.operation);
    $('description').textContent=running?'Ready to make videos for your connected clients.':'Your clients can reconnect after you start the server.';
    $('address').textContent=current.addresses?.length?current.addresses.join('\n'):'Start the server to see its address.';
    for(const id of ['workspace','connect','copy','stop','restart'])$(id).disabled=pending||!!current.operation||!running;
    $('start').hidden=running;$('stop').hidden=!running;$('restart').hidden=!running;$('start').disabled=pending||!!current.operation;
    $('autostart').checked=current.autostart;$('autostart').disabled=pending;
    $('tray-note').textContent=current.tray?'Close this window to keep the server in the tray.':'This desktop does not show a tray icon. Keep this window open while using the server.';
    $('progress').textContent=current.progress?.error?current.progress.step||'':current.operation?current.progress?.step||'Please wait…':'';
    if(current.error)showError(current.error);
    if(!$('engine-screen').hidden){if(!running)overview();else {const url=current.url+'/manage?embedded=1';if($('engine-frame').src!==url)$('engine-frame').src=url;}}
  }catch(e){showError(e.message);}finally{refreshing=false;}
}
async function act(action){
  if(pending)return;pending=true;showError('');
  for(const b of document.querySelectorAll('button'))b.disabled=true;
  try{const result=await api.act(action);if(action==='connect-client'){$('code').textContent=result.code;$('pairing').hidden=false;$('connect').textContent='New connection code';}
    if(action==='engine-settings'){$('engine-frame').src=result.url;$('overview').hidden=true;$('log-screen').hidden=true;$('engine-screen').hidden=false;}
    if(action==='open-log'){$('log-content').textContent=result.log||'No log entries yet.';$('overview').hidden=true;$('engine-screen').hidden=true;$('log-screen').hidden=false;}}
  catch(e){showError(e.message.replace(/^Error invoking remote method '[^']+': (?:Error: )?/,''));}
  finally{pending=false;for(const b of document.querySelectorAll('button'))b.disabled=false;await refresh();}
}
for(const [id,action] of Object.entries({workspace:'engine-settings',start:'start',stop:'stop',restart:'restart',connect:'connect-client',copy:'copy-address',log:'open-log',quit:'quit'}))$(id).onclick=()=>act(action);
$('refresh').onclick=refresh;
$('autostart').onchange=()=>act($('autostart').checked?'autostart-on':'autostart-off');
$('engine-back').onclick=overview;$('log-back').onclick=overview;$('log-refresh').onclick=()=>act('open-log');
api.onProgress(value=>{if(value.engines){act('engine-settings');return;}if(value.connect){overview();act('connect-client');return;}if(value.step)$('progress').textContent=value.step;refresh();});
refresh();setInterval(refresh,4000);
