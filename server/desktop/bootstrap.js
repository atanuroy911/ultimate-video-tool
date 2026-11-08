/* First-run (and after-update) setup of the engine the app runs on, entirely inside the user's own folder:
 *   - portable `uv` (installs Python 3.11 and the Python packages) and portable Node (installs the video renderer)
 *   - ffmpeg / ffprobe come bundled with the installer (ffmpeg-static / ffprobe-static)
 * Nothing is installed system-wide and no administrator rights are needed. Every step is skipped when already done, so the
 * next start opens in seconds. */
const fs = require("fs");
const path = require("path");
const https = require("https");
const { spawn, spawnSync } = require("child_process");

const WIN = process.platform === "win32";
const MAC = process.platform === "darwin";
const ARCH = process.arch === "arm64" ? "arm64" : "x64";
const NODE_VERSION = "22.22.1";

const UV_ASSET = WIN ? "uv-x86_64-pc-windows-msvc.zip"
  : MAC ? (ARCH === "arm64" ? "uv-aarch64-apple-darwin.tar.gz" : "uv-x86_64-apple-darwin.tar.gz")
  : (ARCH === "arm64" ? "uv-aarch64-unknown-linux-gnu.tar.gz" : "uv-x86_64-unknown-linux-gnu.tar.gz");
const NODE_ASSET = WIN ? `node-v${NODE_VERSION}-win-x64.zip`
  : MAC ? `node-v${NODE_VERSION}-darwin-${ARCH}.tar.gz` : `node-v${NODE_VERSION}-linux-${ARCH}.tar.xz`;

function download(url, dest, onProgress, redirects = 6) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { "User-Agent": "video-tool-desktop" } }, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location && redirects > 0) {
        res.resume();
        return resolve(download(new URL(res.headers.location, url).toString(), dest, onProgress, redirects - 1));
      }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`download failed (${res.statusCode}): ${url}`)); }
      const total = Number(res.headers["content-length"] || 0);
      let got = 0;
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      const out = fs.createWriteStream(dest);
      res.on("data", (c) => { got += c.length; if (total && onProgress) onProgress(got / total); });
      res.pipe(out);
      out.on("finish", () => out.close(() => resolve(dest)));
      out.on("error", reject);
    }).on("error", reject);
  });
}

function sh(cmd, args, opts, onLine) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { ...opts, windowsHide: true, shell: false });
    let tail = "";
    const feed = (b) => String(b).split(/\r?\n/).forEach((l) => { if (l.trim()) { tail = (tail + "\n" + l).slice(-1500); onLine && onLine(l); } });
    p.stdout.on("data", feed);
    p.stderr.on("data", feed);
    p.on("error", reject);
    p.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`${path.basename(cmd)} ${args.slice(0, 3).join(" ")} failed (exit ${code})\n${tail}`))));
  });
}

function extract(archive, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  // bsdtar ships with Windows 10+ (System32, used by full path because Git's GNU tar can shadow it), macOS and Linux desktops;
  // it reads zip, tar.gz and tar.xz
  const tar = WIN ? path.join(process.env.SystemRoot || "C:\Windows", "System32", "tar.exe") : "tar";
  let r = spawnSync(tar, ["-xf", archive, "-C", destDir], { windowsHide: true });
  if (r.status !== 0 && WIN && /\.zip$/i.test(archive)) {
    r = spawnSync("powershell.exe", ["-NoProfile", "-Command", `Expand-Archive -LiteralPath '${archive}' -DestinationPath '${destDir}' -Force`], { windowsHide: true });
  }
  if (r.status !== 0) throw new Error("could not unpack " + path.basename(archive) + ": " + String(r.stderr || r.error || ""));
}

function findFirst(dir, name) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isFile() && e.name === name) return p;
    if (e.isDirectory()) { const f = findFirst(p, name); if (f) return f; }
  }
  return null;
}

// Use the real interpreter directory, not uv's Windows minor-version junction.
// Interrupted installs can leave that junction dangling even after extraction succeeds.
function installedPython(dir) {
  if (!fs.existsSync(dir)) return null;
  for (const e of fs.readdirSync(dir, { withFileTypes: true }).sort((a,b)=>b.name.localeCompare(a.name,undefined,{numeric:true}))) {
    if (!e.isDirectory() || e.isSymbolicLink() || !/^cpython-3\.11\.\d+-/.test(e.name)) continue;
    const p = path.join(dir, e.name, WIN ? "python.exe" : "bin/python3.11");
    const r = spawnSync(p, ["-c", "import sys; assert sys.version_info[:2] == (3,11)"], {windowsHide:true,timeout:15000});
    if (r.status === 0) return p;
  }
  return null;
}

/** Resolve every path the app needs. `home` is the user's per-app folder (userData). */
function layout(home, srcDir, version) {
  const runtime = path.join(home, "runtime");
  const tools = path.join(home, "tools");
  const venv = path.join(runtime, ".venv");
  return {
    home, srcDir, version, runtime, tools, venv,
    data: path.join(home, "data"),
    python: WIN ? path.join(venv, "Scripts", "python.exe") : path.join(venv, "bin", "python"),
    uv: path.join(tools, "uv", WIN ? "uv.exe" : "uv"),
    nodeDir: path.join(tools, "node"),
    binDir: path.join(tools, "bin"),
    stamp: path.join(runtime, ".installed.json"),
  };
}

function nodeBinDir(L) {
  const exe = WIN ? "node.exe" : "node";
  const dir = path.join(L.nodeDir, `node-v${NODE_VERSION}-${WIN ? "win-x64" : MAC ? "darwin-" + ARCH : "linux-" + ARCH}`);
  const f = fs.existsSync(dir) ? findFirst(dir, exe) : null;
  return f ? path.dirname(f) : null;
}

function readStamp(L) {
  try { return JSON.parse(fs.readFileSync(L.stamp, "utf8")); } catch { return null; }
}

function isReady(L) {
  const s = readStamp(L);
  return !!s && s.version === L.version && s.source_hash===sourceHash(L) && s.done === true && fs.existsSync(L.python);
}

function sourceHash(L){
  if(L.sourceHash)return L.sourceHash;
  const hash=require('crypto').createHash('sha256');
  const walk=(dir)=>{
    if(!fs.existsSync(dir))return;
    const stat=fs.statSync(dir);
    if(stat.isFile()){hash.update(path.relative(L.srcDir,dir));hash.update(fs.readFileSync(dir));return;}
    for(const name of fs.readdirSync(dir).sort())if(!['__pycache__','node_modules','.venv','user'].includes(name))walk(path.join(dir,name));
  };
  for(const name of ['vt','design','assets','renderer/runtime','renderer/package-lock.json','pyproject.toml','uv.lock'])walk(path.join(L.srcDir,name));
  L.sourceHash=hash.digest('hex');return L.sourceHash;
}

function copyProgram(L, say) {
  say({ step: "Setting up for the first time. This takes a few minutes.", progress: 0.02 });
  const skip = (src) => {
    const b = path.basename(src);
    return !(b === "__pycache__" || b === "node_modules" || b.endsWith(".pyc") || b === ".venv");
  };
  fs.mkdirSync(L.runtime, { recursive: true });
  fs.cpSync(L.srcDir, L.runtime, { recursive: true, force: true, filter: skip });
}

async function bootstrap(L, say, opts = {}) {
  const line = (l) => say({ line: l });
  const log = (step, progress) => say({ step, progress });

  copyProgram(L, say);

  // ---- ffmpeg / ffprobe (bundled with the installer)
  fs.mkdirSync(L.binDir, { recursive: true });
  for (const [mod, name] of [["ffmpeg-static", "ffmpeg"], ["ffprobe-static", "ffprobe"]]) {
    try {
      let p = require(mod); p = typeof p === "string" ? p : p.path;
      p = p.replace("app.asar" + path.sep, "app.asar.unpacked" + path.sep);
      const dst = path.join(L.binDir, name + (WIN ? ".exe" : ""));
      if (p && fs.existsSync(p) && !fs.existsSync(dst)) { fs.copyFileSync(p, dst); if (!WIN) fs.chmodSync(dst, 0o755); }
    } catch (e) { line("note: " + name + " not bundled (" + e.message + "); using the system one if present"); }
  }

  // ---- uv
  if (!fs.existsSync(L.uv)) {
    log("Downloading tools (step 1 of 5)", 0.06);
    const tmp = path.join(L.tools, "dl", UV_ASSET);
    await download(`https://github.com/astral-sh/uv/releases/latest/download/${UV_ASSET}`, tmp, (f) => say({ progress: 0.06 + f * 0.04 }));
    const x = path.join(L.tools, "uv-x");
    fs.rmSync(x, { recursive: true, force: true });
    extract(tmp, x);
    const found = findFirst(x, WIN ? "uv.exe" : "uv");
    if (!found) throw new Error("uv was not found in the downloaded archive");
    fs.mkdirSync(path.dirname(L.uv), { recursive: true });
    fs.copyFileSync(found, L.uv);
    if (!WIN) fs.chmodSync(L.uv, 0o755);
    fs.rmSync(x, { recursive: true, force: true });
  }

  const env = { ...process.env, UV_CACHE_DIR: path.join(L.tools, "uv-cache"), UV_PYTHON_INSTALL_DIR: path.join(L.tools, "python"), HF_HUB_DISABLE_XET: "1", PYTHONIOENCODING: "utf-8" };

  // ---- Python 3.11 + packages
  if (!fs.existsSync(L.python)) {
    log("Installing tools (step 2 of 5)", 0.12);
    let interpreter = installedPython(env.UV_PYTHON_INSTALL_DIR);
    if (!interpreter) {
      try {
        await sh(L.uv, ["python", "install", "3.11", "--no-bin", "--no-registry"], { env, cwd: L.runtime }, line);
      } catch (error) {
        if (!WIN || !String(error).includes("Missing expected target directory for Python minor version link") || !installedPython(env.UV_PYTHON_INSTALL_DIR)) throw error;
        line("Python is ready; using its verified executable directly.");
      }
      interpreter = installedPython(env.UV_PYTHON_INSTALL_DIR);
    }
    if (!interpreter) throw new Error("Python downloaded but could not start. Try setup again.");
    await sh(L.uv, ["venv", "--python", interpreter, "--no-managed-python", L.venv], { env, cwd: L.runtime }, line);
  }
  // One locked environment, including dependency overrides (not an independent pip resolver).
  let flavour = "cpu";
  if (!opts.cpuOnly) {
    const r = spawnSync(L.python, [path.join(L.runtime, "vt", "gpu_detect.py")], {encoding:"utf8",windowsHide:true,timeout:60000});
    if (r.status === 0 && /^(cu128|cu124|cu118|cpu)\s*$/.test(r.stdout)) flavour = r.stdout.trim();
  }
  log("Installing video and voice tools (step 3 of 5)", 0.3);
  await sh(L.uv, ["sync", "--frozen", "--no-dev", "--extra", flavour, "--python", L.python],
    {env:{...env,UV_PROJECT_ENVIRONMENT:L.venv},cwd:L.runtime},line);

  // ---- Node + video renderer
  if (!nodeBinDir(L)) {
    log("Downloading the video renderer (step 4 of 5)", 0.62);
    const tmp = path.join(L.tools, "dl", NODE_ASSET);
    await download(`https://nodejs.org/dist/v${NODE_VERSION}/${NODE_ASSET}`, tmp, (f) => say({ progress: 0.62 + f * 0.06 }));
    fs.rmSync(L.nodeDir, { recursive: true, force: true });
    extract(tmp, L.nodeDir);
  }
  const nb = nodeBinDir(L);
  if (!nb) throw new Error("Node.js could not be unpacked");
  const nenv = { ...process.env, PATH: nb + path.delimiter + process.env.PATH, HYPERFRAMES_NO_TELEMETRY: "1", DO_NOT_TRACK: "1" };
  const rdir = path.join(L.runtime, "renderer");
  const node = WIN ? path.join(nb, "node.exe") : path.join(nb, "node");
  if (!fs.existsSync(path.join(rdir, "node_modules", "hyperframes"))) {
    log("Installing the video renderer (step 5 of 5)", 0.7);
    // run npm through node itself: no .cmd shim, no shell, same on every platform
    const cli = [path.join(nb, "node_modules", "npm", "bin", "npm-cli.js"), path.join(nb, "..", "lib", "node_modules", "npm", "bin", "npm-cli.js")].find((f) => fs.existsSync(f));
    if (!cli) throw new Error("npm was not found in the downloaded Node.js");
    await sh(node, [cli, "ci", "--no-audit", "--no-fund"], { env: nenv, cwd: rdir }, line);
  }
  if (!fs.existsSync(path.join(L.runtime, "design", "fonts", "fonts.css"))) await sh(node, ["scripts/build-fonts.mjs"], { env: nenv, cwd: rdir }, line);
  if (!fs.existsSync(path.join(L.runtime, "design", "icons", "lucide.json"))) await sh(node, ["scripts/build-icons.mjs"], { env: nenv, cwd: rdir }, line);

  fs.writeFileSync(L.stamp, JSON.stringify({ version: L.version, source_hash:sourceHash(L), done: true, at: new Date().toISOString() }));
  say({ step: "Ready", progress: 1 });
}

/** Environment for the Python server process. */
function serverEnv(L) {
  const nb = nodeBinDir(L);
  const extra = [L.binDir, nb].filter(Boolean).join(path.delimiter);
  return {
    ...process.env,
    PATH: extra + path.delimiter + process.env.PATH,
    VT_DATA: L.data,
    PYTHONIOENCODING: "utf-8",
    HYPERFRAMES_NO_TELEMETRY: "1",
    DO_NOT_TRACK: "1",
    HF_HUB_DISABLE_XET: "1",
    PYTHONUNBUFFERED: "1",
  };
}

module.exports = { layout, bootstrap, isReady, serverEnv, nodeBinDir };
