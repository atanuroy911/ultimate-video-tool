// The Studio window: only the one-click assistant connection is offered to the page (desktop/assistants.js).
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("vtDesktop", {
  assistants: {
    status: () => ipcRenderer.invoke("assistants-status"),
    connect: (id, remote) => ipcRenderer.invoke("assistants-connect", id, remote),
  },
  director: {
    managed: true,
    status: () => ipcRenderer.invoke("director-status"),
    run: (task) => ipcRenderer.invoke("director-run", task),
    onLog: (fn) => { const listener = (_event, value) => fn(value); ipcRenderer.on("director-log", listener); return () => ipcRenderer.removeListener("director-log", listener); },
  },
  companion:{status:()=>ipcRenderer.invoke('companion-status'),chooseServer:()=>ipcRenderer.invoke('choose-processing-server'),codexStatus:()=>ipcRenderer.invoke('codex-status')},
});
