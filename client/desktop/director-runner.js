/* Claude on this computer, constrained to this Video Tool server's MCP tools. */
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {commandFor}=require('./assistant-command');

function status(run = spawnSync) {
  let command;try{command=run===spawnSync?commandFor('claude'):{file:'claude',prefix:[]};}catch(e){return {found:false,logged_in:false,version:'',reason:e.message};}
  const opts = { encoding: "utf8", windowsHide: true, timeout: 10000, shell:false,env:{...process.env,...command.env} };
  const ver = run(command.file, [...command.prefix,"--version"], opts);
  if (ver.error || ver.status !== 0) return { found: false, logged_in: false, version: "", reason: "Claude Code is not installed on this computer." };
  const auth = run(command.file, [...command.prefix,"auth", "status"], opts);
  const text = `${auth.stdout || ""}\n${auth.stderr || ""}`;
  let logged = false;
  try { const data = JSON.parse(auth.stdout || "{}"); logged = !!(data.loggedIn ?? data.logged_in); } catch { logged = auth.status === 0 && /logged.?in|authenticated/i.test(text); }
  return { found: true, logged_in: logged, version: String(ver.stdout || ver.stderr || "").trim().slice(0, 80), reason: logged ? "" : "Open Claude Code once and log in." };
}

function args(configPath) {
  return ["-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--disable-slash-commands",
    "--strict-mcp-config", "--mcp-config", configPath, "--allowedTools", "mcp__video-tool__*"];
}

function definition({ mcp, server, token }) {
  if (mcp && mcp.command) return { command: mcp.command, args: mcp.args || [], env: mcp.env || {} };
  return { type: "http", url: `${server.replace(/\/$/, "")}/mcp`, headers: { Authorization: `Bearer ${token}` } };
}

function run({ prompt, mcp, server, token, signal }, onLog = () => {}) {
  return new Promise((resolve) => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vt-director-"));
    const config = path.join(dir, "mcp.json");
    fs.writeFileSync(config, JSON.stringify({ mcpServers: { "video-tool": definition({ mcp, server, token }) } }));
    let command;try{command=commandFor('claude');}catch(e){fs.rmSync(dir,{recursive:true,force:true});resolve({ok:false,error:e.message});return;}
    const child = spawn(command.file, [...command.prefix,...args(config)], { windowsHide: true, shell:false,env:{...process.env,...command.env}, stdio: ["pipe", "pipe", "pipe"] });
    const stop=()=>child.kill();signal?.addEventListener('abort',stop,{once:true});
    child.once('close',()=>signal?.removeEventListener('abort',stop));
    if(signal?.aborted)stop();
    let stdout = "", stderr = "";
    const take = (kind, chunk) => {
      const text = String(chunk); if (kind === "out") stdout += text; else stderr += text;
      for (const line of text.split(/\r?\n/).filter(Boolean)) onLog(line.slice(0, 500));
    };
    child.stdout.on("data", (b) => take("out", b));
    child.stderr.on("data", (b) => take("err", b));
    child.on("error", (e) => { fs.rmSync(dir, { recursive: true, force: true }); resolve({ ok: false, error: e.message }); });
    child.on("close", (code) => { fs.rmSync(dir, { recursive: true, force: true }); resolve({ ok: code === 0, error: code === 0 ? "" : (stderr || stdout).slice(-500), exit_code: code }); });
    child.stdin.end(prompt);
  });
}

module.exports = { status, args, definition, run };
