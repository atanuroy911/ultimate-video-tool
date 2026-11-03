const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('serverManager',{
  state:()=>ipcRenderer.invoke('server-manager:state'),
  act:action=>ipcRenderer.invoke('server-manager:act',action),
  onProgress:callback=>ipcRenderer.on('server-manager:progress',(_event,value)=>callback(value)),
});
