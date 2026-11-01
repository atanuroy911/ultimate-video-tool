const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("vtDesktop", {
  onStatus: (cb) => ipcRenderer.on("status", (_e, m) => cb(m)),
  retry: () => ipcRenderer.send("retry"),
  openLog: () => ipcRenderer.send("open-log"),
  quit: () => ipcRenderer.send("quit"),
  // connect.html
  find: () => ipcRenderer.invoke("find-servers"),
  connect: (address) => ipcRenderer.invoke("connect", address),
  useThisComputer: () => ipcRenderer.send("use-this-computer"),
});
