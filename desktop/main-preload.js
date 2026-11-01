// The Studio window: only the one-click assistant connection is offered to the page (desktop/assistants.js).
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("vtDesktop", {
  assistants: {
    status: () => ipcRenderer.invoke("assistants-status"),
    connect: (id, remote) => ipcRenderer.invoke("assistants-connect", id, remote),
  },
});
