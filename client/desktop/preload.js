const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("vtDesktop", {
  // connect.html: every entry here has a handler in main.js
  find: () => ipcRenderer.invoke("find-servers"),
  connect: (address) => ipcRenderer.invoke("connect", address),
  useThisComputer: () => ipcRenderer.send("use-this-computer"),
});
