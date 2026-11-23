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
  // Claude Code and Codex in the Assistant pane (acp-agents.js); every value is checked again in the main process
  agents: {
    status: (kind) => ipcRenderer.invoke("vt-agent:status", kind),
    open: (kind, projectId, options) => ipcRenderer.invoke("vt-agent:open", kind, projectId, options),
    send: (id, text, refs, images) => ipcRenderer.invoke("vt-agent:send", id, text, refs, images),
    stop: (id) => ipcRenderer.invoke("vt-agent:stop", id),
    permission: (id, requestId, choice) => ipcRenderer.invoke("vt-agent:permission", id, requestId, choice),
    list: (projectId) => ipcRenderer.invoke("vt-agent:list", projectId),
    openInCode: (projectId) => ipcRenderer.invoke("vt-agent:open-in-code", projectId),
    signIn: (kind) => ipcRenderer.invoke("vt-agent:signin", kind),
    onEvent: (cb) => { const on = (_e, m) => cb(m); ipcRenderer.on("vt-agent:event", on); return () => ipcRenderer.removeListener("vt-agent:event", on); },
  },
});
