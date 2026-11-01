/* Video Tool desktop shell: opens the Studio in its own window, from a Video Tool server (docs/plans/PLAN-CLIENT-SERVER.MD CS4).
 *   first start  : asks where to run (connect.html): this computer, a server found on the network, or a typed address; remembered
 *   this computer: sets up the engine in the user's folder on first start (see bootstrap.js), then runs it
 *   another one  : just opens its Studio; the page asks for the pairing code once (studio/src/Pair.tsx)
 *   VT_USE_REPO=1: this computer uses the repository checkout and its .venv (development, no setup)
 */
const { app, BrowserWindow, Menu, ipcMain, shell, session, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const net = require("net");
const http = require("http");
const { spawn, spawnSync } = require("child_process");
const B = require("./bootstrap");
const discover = require("./discover");
const assistants = require("./assistants");

const WIN = process.platform === "win32";
const REPO = path.resolve(__dirname, "..");
const USE_REPO = process.env.VT_USE_REPO === "1";

let splash = null;
let win = null;
let server = null;
let quitting = false;
let logFile = null;
let origin = null;                 // where the Studio comes from: http://127.0.0.1:<port> here, or the server's address
let connFile = null;               // the remembered choice: {"server": "here"} or {"server": "http://..."}

if (!app.requestSingleInstanceLock()) { app.quit(); process.exit(0); }
app.on("second-instance", () => { const w = win || splash; if (w) { if (w.isMinimized()) w.restore(); w.focus(); } });

function log(msg) {
  try { if (logFile) fs.appendFileSync(logFile, `[${new Date().toISOString()}] ${msg}\n`); } catch { /* ignore */ }
}
function say(m) {
  if (m.line) log(m.line);
  if (splash && !splash.isDestroyed()) splash.webContents.send("status", m);
}

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => resolve(p)); });
    s.on("error", reject);
  });
}

function ping(port) {
  return new Promise((resolve) => {
    const r = http.get({ host: "127.0.0.1", port, path: "/api/health", timeout: 1500 }, (res) => { res.resume(); resolve(res.statusCode === 200); });
    r.on("error", () => resolve(false));
    r.on("timeout", () => { r.destroy(); resolve(false); });
  });
}

async function waitForServer(port, ms = 90000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (!server || server.exitCode !== null) throw new Error("The engine stopped while starting. See the log for details.");
    if (await ping(port)) return;
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error("The engine did not start in time.");
}

function killServer() {
  if (!server || server.exitCode !== null) return;
  try {
    if (WIN) spawnSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], { windowsHide: true });
    else server.kill("SIGTERM");
  } catch { /* already gone */ }
}

/** The small window: the setup progress (splash.html) or the connect screen (connect.html). */
function createSplash(page = "splash.html") {
  const height = page === "connect.html" ? 660 : 440;
  if (splash && !splash.isDestroyed()) {
    splash.setSize(560, height);
    splash.loadFile(path.join(__dirname, page));
    splash.show();
    splash.focus();
    return;
  }
  splash = new BrowserWindow({
    width: 560, height, resizable: false, maximizable: false, minimizable: true, show: false, title: "Video Tool",
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true },
  });
  splash.setMenu(null);
  splash.loadFile(path.join(__dirname, page));
  splash.once("ready-to-show", () => splash.show());
  splash.on("closed", () => { splash = null; if (!win) app.quit(); });
}

function remembered() {
  try { return JSON.parse(fs.readFileSync(connFile, "utf8")).server || ""; } catch { return ""; }
}
function remember(choice) {
  try { fs.writeFileSync(connFile, JSON.stringify({ server: choice })); } catch (e) { log("could not save the connection: " + e); }
}
const isHere = () => !!origin && origin.startsWith("http://127.0.0.1:");

function createMain() {
  win = new BrowserWindow({
    width: 1360, height: 880, minWidth: 980, minHeight: 640, show: false, title: "Video Tool",
    backgroundColor: "#f5f5f7",
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    webPreferences: { contextIsolation: true, sandbox: true, preload: path.join(__dirname, "main-preload.js") },
  });
  // the recorder needs the microphone; only the Studio's own pages get it
  session.defaultSession.setPermissionRequestHandler((wc, permission, cb) => cb(wc.getURL().startsWith(origin) && ["media", "audioCapture", "fullscreen", "clipboard-sanitized-write"].includes(permission)));
  win.webContents.setWindowOpenHandler(({ url }) => { if (/^https?:/.test(url) && !url.startsWith(origin)) shell.openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e, url) => { if (!url.startsWith(origin)) { e.preventDefault(); shell.openExternal(url); } });
  win.once("ready-to-show", () => { win.show(); if (splash && !splash.isDestroyed()) splash.close(); });
  const w = win;
  w.on("closed", () => { if (win === w) win = null; });
  win.loadURL(`${origin}/`);
}

function closeMain() {
  if (win && !win.isDestroyed()) { const w = win; win = null; w.destroy(); }
}

function buildMenu() {
  const here = isHere();
  const tpl = [
    ...(process.platform === "darwin" ? [{ role: "appMenu" }] : []),
    { label: "File", submenu: [
      { label: "New video", accelerator: "CmdOrCtrl+N", click: () => win && win.loadURL(`${origin}/new`) },
      ...(here ? [{ label: "Open projects folder", click: () => shell.openPath(path.join(layoutRef.data, "projects")) }] : []),
      { label: "Connect to another server…", click: chooseServer },
      { type: "separator" }, process.platform === "darwin" ? { role: "close" } : { role: "quit" } ] },
    { role: "editMenu" },
    { label: "View", submenu: [{ role: "reload" }, { role: "forceReload" }, { type: "separator" }, { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" }, { type: "separator" }, { role: "togglefullscreen" }, { role: "toggleDevTools" }] },
    { role: "windowMenu" },
    { label: "AI", submenu: [
      { label: "Settings: AI and assistants", click: () => win && win.loadURL(`${origin}/settings#ai`) },
      { label: "Command palette", accelerator: "CmdOrCtrl+K", click: () => win && win.webContents.sendInputEvent({ type: "keyDown", keyCode: "K", modifiers: ["control"] }) },
    ] },
    { label: "Help", submenu: [
      { label: "Open log", click: () => logFile && shell.showItemInFolder(logFile) },
      ...(here ? [{ label: "Open data folder", click: () => shell.openPath(layoutRef.data) }] : []) ] },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(tpl));
}

let layoutRef = null;

/** The connect screen, also behind File > Connect to another server…; the open Studio stays until a new choice is made. */
function chooseServer() {
  createSplash("connect.html");
}

function openRemote(url) {
  log("using the server at " + url);
  closeMain();
  killServer();
  origin = url;
  buildMenu();
  createMain();
}

async function start() {
  const home = app.getPath("userData");
  fs.mkdirSync(home, { recursive: true });
  logFile = path.join(home, "desktop.log");
  connFile = path.join(home, "connection.json");
  try { fs.writeFileSync(logFile, ""); } catch { /* ignore */ }
  const saved = remembered();
  if (saved && saved !== "here") {
    const s = await discover.probe(saved);
    if (s) return openRemote(s.url);
    log("the saved server does not answer: " + saved);
  }
  if (saved !== "here") return chooseServer();
  return startHere();
}

async function startHere() {
  const home = app.getPath("userData");
  createSplash();
  say({ title: "Video Tool", sub: "Starting…", busy: true });

  let python, cwd, env;
  if (USE_REPO) {
    const py = WIN ? path.join(REPO, ".venv", "Scripts", "python.exe") : path.join(REPO, ".venv", "bin", "python");
    layoutRef = { data: process.env.VT_DATA || path.join(home, "data-dev") };
    python = py; cwd = REPO;
    env = { ...process.env, VT_DATA: layoutRef.data, PYTHONIOENCODING: "utf-8", HYPERFRAMES_NO_TELEMETRY: "1", DO_NOT_TRACK: "1", HF_HUB_DISABLE_XET: "1" };
  } else {
    const srcDir = app.isPackaged ? path.join(process.resourcesPath, "app-src") : REPO;
    const L = B.layout(home, srcDir, app.getVersion());
    layoutRef = L;
    if (!B.isReady(L)) {
      say({ sub: "Setting up for the first time. This needs the internet and can take 10 to 20 minutes; it only happens once.", step: "Starting setup", progress: 0.01 });
      await B.bootstrap(L, say);
    }
    python = L.python; cwd = L.runtime; env = B.serverEnv(L);
  }
  fs.mkdirSync(layoutRef.data, { recursive: true });

  say({ sub: "Starting the engine…", step: "", busy: true });
  const port = await freePort();
  log(`starting engine on ${port}: ${python}`);
  server = spawn(python, ["-m", "vt.cli", "studio", "--port", String(port), "--no-open"], { cwd, env, windowsHide: true });
  server.stdout.on("data", (b) => log(String(b).trimEnd()));
  server.stderr.on("data", (b) => log(String(b).trimEnd()));
  server.on("exit", (code) => { log("engine exited " + code); if (!quitting && win && isHere()) dialog.showErrorBox("Video Tool", "The engine stopped unexpectedly. Reopen the app; details are in the log (Help > Open log)."); });
  await waitForServer(port);
  closeMain();
  origin = `http://127.0.0.1:${port}`;
  buildMenu();
  createMain();
}

function fail(e) {
  log("FATAL " + (e && e.stack || e));
  say({ title: "Setup could not finish", sub: "Check your internet connection and try again. Nothing was changed on your computer outside the app's own folder.", step: String(e.message || e).split("\n")[0], error: true });
  killServer();
}

async function startSafely() {
  try { await start(); } catch (e) { fail(e); }
}

ipcMain.on("retry", () => { startSafely(); });
ipcMain.on("open-log", () => { if (logFile) shell.showItemInFolder(logFile); });
ipcMain.on("quit", () => app.quit());
ipcMain.handle("find-servers", () => discover.find(2000));
ipcMain.handle("assistants-status", () => assistants.status());
ipcMain.handle("assistants-connect", (e, id, remote) => {
  // only for the server this window shows: a page cannot point the assistants anywhere else
  if (!origin || !win || e.sender !== win.webContents || !remote || !String(remote.url || "").startsWith(origin + "/")) throw new Error("That server is not the one this window shows.");
  const bridge = { command: process.execPath, args: [path.join(__dirname, "mcp-bridge.js").replace("app.asar" + path.sep, "app.asar.unpacked" + path.sep)] };
  return assistants.connect(id, remote, bridge);
});
ipcMain.handle("connect", async (_e, address) => {
  const s = await discover.probe(address);
  if (!s) return { error: "No Video Tool server answers at that address. Check it, and that the server is running on the same network." };
  remember(s.url);
  openRemote(s.url);
  return { ok: true };
});
ipcMain.on("use-this-computer", () => {
  remember("here");
  if (isHere() && win && server && server.exitCode === null) { if (splash && !splash.isDestroyed()) splash.close(); return; }
  closeMain();
  startHere().catch(fail);
});

app.whenReady().then(startSafely);
app.on("before-quit", () => { quitting = true; killServer(); });
app.on("window-all-closed", () => { if (process.platform !== "darwin" || quitting) app.quit(); });
app.on("activate", () => { if (!win && !splash && layoutRef) startSafely(); });
