/* One-click assistants on a client computer (the Python side, vt/assistants.py, does this on the server computer).
 * The Studio page, loaded from a Video Tool server elsewhere, asks the server for a key and hands it here; this registers Video Tool with
 * Claude Code, Codex and Claude Desktop on this computer. Claude Code and Codex speak HTTP to the server; Claude Desktop only starts local
 * programs, so it starts this app as a small bridge (mcp-bridge.js) that relays to the server.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const NAME = "video-tool";
const LABELS = { "claude-code": "Claude Code", codex: "Codex", "claude-desktop": "Claude Desktop" };
const WIN = process.platform === "win32";

function which(name) {
  const r = spawnSync(WIN ? "where" : "which", [name], { encoding: "utf8", windowsHide: true });
  const hit = r.status === 0 && r.stdout.split(/\r?\n/).find(Boolean);
  if (hit) return hit.trim();
  const local = path.join(os.homedir(), ".local", "bin", name + (WIN ? ".exe" : ""));
  return fs.existsSync(local) ? local : null;
}

const files = {
  "claude-code": () => path.join(process.env.CLAUDE_CONFIG_DIR || os.homedir(), ".claude.json"),
  codex: () => path.join(process.env.CODEX_HOME || path.join(os.homedir(), ".codex"), "config.toml"),
  "claude-desktop": () => WIN ? path.join(process.env.APPDATA || os.homedir(), "Claude", "claude_desktop_config.json")
    : process.platform === "darwin" ? path.join(os.homedir(), "Library", "Application Support", "Claude", "claude_desktop_config.json")
      : path.join(os.homedir(), ".config", "Claude", "claude_desktop_config.json"),
};

function readJson(f) {
  if (!fs.existsSync(f)) return {};
  try { return JSON.parse(fs.readFileSync(f, "utf8") || "{}"); } catch { throw new Error(`${f} is not valid JSON, so it was left alone. Fix or remove it, then try again.`); }
}
function writeJson(f, data) {
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f + ".vt-tmp", JSON.stringify(data, null, 2));
  fs.renameSync(f + ".vt-tmp", f);
}
const TOML_BLOCK = /^\[mcp_servers\.(?:"video-tool"|video-tool)(?:\.[^\]]+)?\]\n[\s\S]*?(?=^\[|(?![\s\S]))/gm;

function installed(id) {
  if (id === "claude-code") return !!which("claude") || fs.existsSync(files[id]());
  if (id === "codex") return !!which("codex") || fs.existsSync(path.dirname(files[id]()));
  return fs.existsSync(path.dirname(files[id]()));
}

function connectedTo(id) {
  try {
    if (id === "codex") {
      const f = files.codex();
      const m = fs.existsSync(f) && fs.readFileSync(f, "utf8").match(TOML_BLOCK);
      if (!m) return null;
      const u = m[0].match(/^url = "([^"]+)"/m);
      return u ? u[1] : "here";
    }
    const e = (readJson(files[id]()).mcpServers || {})[NAME];
    if (!e) return null;
    return e.url || (e.env && e.env.VT_SERVER) || (e.command ? "here" : null);
  } catch { return null; }
}

function status() {
  return Object.keys(LABELS).map((id) => {
    const to = connectedTo(id);
    return { id, label: LABELS[id], installed: installed(id), connected: !!to, to, restart: id !== "claude-code" };
  });
}

/** remote = {url, token?}: the server's /mcp, and the server's key only for a server outside the person's own network (none is needed on it). */
function connect(id, remote, bridge) {
  if (!LABELS[id]) throw new Error("unknown assistant " + id);
  if (!remote || !/^https?:\/\//.test(remote.url || "")) throw new Error("No server address.");
  const bearer = remote.token ? `Bearer ${remote.token}` : "";
  if (id === "claude-code") {
    const exe = which("claude");
    if (exe) {
      spawnSync(exe, ["mcp", "remove", "--scope", "user", NAME], { windowsHide: true, shell: WIN });
      const r = spawnSync(exe, ["mcp", "add", "--scope", "user", "--transport", "http", NAME, remote.url, ...(bearer ? ["--header", `Authorization: ${bearer}`] : [])],
        { encoding: "utf8", windowsHide: true, shell: WIN });
      if (r.status !== 0) throw new Error(((r.stderr || r.stdout || "Claude Code refused the connection") + "").trim().slice(0, 300));
    } else {
      const data = readJson(files[id]());
      (data.mcpServers = data.mcpServers || {})[NAME] = { type: "http", url: remote.url, ...(bearer ? { headers: { Authorization: bearer } } : {}) };
      writeJson(files[id](), data);
    }
    return { ok: true, note: "Connected. Start a new Claude Code chat and ask it to make a video." };
  }
  if (id === "codex") {
    const f = files.codex();
    let text = fs.existsSync(f) ? fs.readFileSync(f, "utf8") : "";
    text = text.replace(TOML_BLOCK, "").trimEnd();
    const block = `[mcp_servers.${NAME}]\nurl = ${JSON.stringify(remote.url)}\n${bearer ? `http_headers = { Authorization = ${JSON.stringify(bearer)} }\n` : ""}`;
    fs.mkdirSync(path.dirname(f), { recursive: true });
    fs.writeFileSync(f, (text ? text + "\n\n" : "") + block);
    return { ok: true, note: "Connected. Restart Codex to load the Video Tool tools." };
  }
  const data = readJson(files[id]());
  (data.mcpServers = data.mcpServers || {})[NAME] = {
    command: bridge.command, args: bridge.args,
    env: { ELECTRON_RUN_AS_NODE: "1", VT_SERVER: remote.url, ...(remote.token ? { VT_TOKEN: remote.token } : {}) },
  };
  writeJson(files[id](), data);
  return { ok: true, note: "Connected. Quit and reopen Claude Desktop to load it." };
}

module.exports = { status, connect, files, TOML_BLOCK };
