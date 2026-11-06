// The Studio window: the one-click assistant connection (desktop/assistants.js), the helper that keeps Claude and Codex ready (desktop/helper.js),
// and choosing another server. Nothing else of the desktop is offered to the page.
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("vtDesktop", {
  assistants: {
    status: () => ipcRenderer.invoke("assistants-status"),
    connect: (id, remote) => ipcRenderer.invoke("assistants-connect", id, remote),
  },
  helper: {
    status: () => ipcRenderer.invoke("helper-status"),
    start: () => ipcRenderer.invoke("helper-start"),
    stop: () => ipcRenderer.invoke("helper-stop"),
    refresh: () => ipcRenderer.invoke("helper-refresh"),
    removeServer: (address) => ipcRenderer.invoke("helper-remove-server", address),
    setAutostart: (on) => ipcRenderer.invoke("helper-autostart", !!on),
  },
  server: { choose: () => ipcRenderer.invoke("choose-processing-server") },
});
