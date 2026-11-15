/* Claude on this computer. Two jobs, both through the person's own Claude Code login:
 *   run  a planning session that can use only this Video Tool server's MCP tools (no shell, no files);
 *   ask  one question answered as JSON, with pictures if any (the twin of ClaudeCLIProvider.complete in server/vt/ai/providers.py). */
const { execFile, spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {commandFor}=require('./assistant-command');

const DEFAULT_MODEL = "sonnet";
const SCHEMA_ARG_MAX = 6000;                       // a longer schema goes into the prompt: a Windows command line is limited to about 32,000 characters
const OUTPUT_MAX = 8 * 1024 * 1024;
const LIMIT = /usage limit|limit reached|hit your (?:\w+ )?limit|5-hour limit|weekly limit|rate.?limit|too many requests|quota|\b429\b/i;
const LOGIN = /not logged in|not signed in|\/login|invalid api key|authenticat|unauthori[sz]ed|oauth token|log ?in required|\b401\b/i;

/** A model name or alias for --model. Only letters, digits, dots and dashes get through, so nothing else reaches the command line. */
function modelName(model) { return /^[a-z0-9][a-z0-9.-]*$/i.test(String(model || "")) ? String(model) : DEFAULT_MODEL; }

/** What went wrong, in the three kinds the server understands: the plan's usage limit, a missing login, anything else. */
function kindOf(text, apiStatus) {
  const t = String(text || "");
  if (apiStatus === 429 || LIMIT.test(t)) return "limit";
  if (apiStatus === 401 || LOGIN.test(t)) return "login";
  return "other";
}

/** The program's own login is used: an API key left in the environment would silently switch it to per-token billing. */
function cleanEnv(extra) {
  const env = { ...process.env, ...extra };
  for (const k of ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"]) delete env[k];
  return env;
}

function interpret(ver, auth) {
  if (ver.error || ver.status !== 0) return { found: false, logged_in: false, version: "", reason: "Claude Code is not installed on this computer." };
  const text = `${auth.stdout || ""}\n${auth.stderr || ""}`;
  let logged = false;
  try { const data = JSON.parse(auth.stdout || "{}"); logged = !!(data.loggedIn ?? data.logged_in); } catch { logged = auth.status === 0 && /logged.?in|authenticated/i.test(text); }
  return { found: true, logged_in: logged, version: String(ver.stdout || ver.stderr || "").trim().slice(0, 80), reason: logged ? "" : "Open Claude Code once and log in." };
}

function status(run = spawnSync) {
  let command;try{command=run===spawnSync?commandFor('claude'):{file:'claude',prefix:[]};}catch(e){return {found:false,logged_in:false,version:'',reason:e.message};}
  const opts = { encoding: "utf8", windowsHide: true, timeout: 10000, shell:false,env:cleanEnv(command.env) };
  const ver = run(command.file, [...command.prefix,"--version"], opts);
  if (ver.error || ver.status !== 0) return interpret(ver, {});
  return interpret(ver, run(command.file, [...command.prefix,"auth", "status"], opts));
}

/** The same check without stopping the helper's other work while Claude Code starts. */
function execAsync(file, args, opts) {
  return new Promise((resolve) => execFile(file, args, opts, (error, stdout, stderr) => {
    const exited = error && typeof error.code === "number";                  // it ran and returned a code: that is an answer, not a failure to run
    resolve({ error: error && !exited ? error : null, status: !error ? 0 : exited ? error.code : 1, stdout, stderr });
  }));
}
async function statusAsync(exec = execAsync) {
  let command;try{command=exec===execAsync?commandFor('claude'):{file:'claude',prefix:[]};}catch(e){return {found:false,logged_in:false,version:'',reason:e.message};}
  const opts = { encoding: "utf8", windowsHide: true, timeout: 10000, env: cleanEnv(command.env) };
  const ver = await exec(command.file, [...command.prefix, "--version"], opts);
  if (ver.error || ver.status !== 0) return interpret(ver, {});
  return interpret(ver, await exec(command.file, [...command.prefix, "auth", "status"], opts));
}

const MCP_ANSWER_TOKENS = "200000";          // the largest tool answer a directing session takes whole (Claude Code's MAX_MCP_OUTPUT_TOKENS)

/** The planning session: the Video Tool MCP tools and nothing else. `--tools ""` removes every built-in tool (shell, file reading, searching), which an ordinary
 *  `--allowedTools` does not (checked against the real program on 2026-11-05: `echo` ran and the folder could be read). */
function args(configPath, model) {
  return ["-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--disable-slash-commands",
    "--strict-mcp-config", "--mcp-config", configPath, "--tools", "", "--allowedTools", "mcp__video-tool__*", "--model", modelName(model)];
}

function definition({ mcp, server, token, directorToken }) {
  if (directorToken) return { type: "http", url: new URL("/mcp/director", server).href, headers: { "X-VT-Director-Token": directorToken } };
  if (mcp && mcp.command) return { command: mcp.command, args: mcp.args || [], env: mcp.env || {} };
  return { type: "http", url: `${server.replace(/\/$/, "")}/mcp`, ...(token ? { headers: { Authorization: `Bearer ${token}` } } : {}) };       // a server on the person's own network needs no key
}

function run({ prompt, mcp, server, token, directorToken, signal, model }, onLog = () => {}, deps = {}) {
  return new Promise((resolve) => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vt-director-"));
    const work = path.join(dir, "work"), config = path.join(dir, "mcp.json");     // the key sits beside the working folder, not in it
    fs.mkdirSync(work);
    fs.writeFileSync(config, JSON.stringify({ mcpServers: { "video-tool": definition({ mcp, server, token, directorToken }) } }), { mode: 0o600 });
    const cleanup = () => fs.rmSync(dir, { recursive: true, force: true });
    let command;try{command=deps.command||commandFor('claude');}catch(e){cleanup();resolve({ok:false,error:e.message,error_kind:'login'});return;}
    // A long video's script task is larger than Claude Code's usual limit for one tool answer (25,000 tokens). Over it, Claude Code saves the answer to a
    // file and asks for it to be read, but this session has no file tools (--tools ""): the director gave up without a script. 2026-11-15, a 4.5 min interview.
    const child = (deps.spawn||spawn)(command.file, [...command.prefix,...args(config, model)], { cwd: work, windowsHide: true, shell:false,env:cleanEnv({ ...command.env, MAX_MCP_OUTPUT_TOKENS: MCP_ANSWER_TOKENS }), stdio: ["pipe", "pipe", "pipe"] });
    const stop=()=>child.kill();signal?.addEventListener('abort',stop,{once:true});
    child.once('close',()=>signal?.removeEventListener('abort',stop));
    if(signal?.aborted)stop();
    let stdout = "", stderr = "", carry = "", result = null, used = "", builtin = [];
    const calls = [], names = {};
    const note = (line) => {                                              // a whole line of the program's event stream
      onLog(line.slice(0, 500));
      if (line[0] !== "{") return;
      let m;
      try { m = JSON.parse(line); } catch { return; }
      if (deps.onEvent) deps.onEvent(m);                                  // the whole event, for the playground (playground.js)
      if (m.type === "result") result = m;
      else if (m.type === "system" && m.subtype === "init") { used = String(m.model || ""); builtin = (m.tools || []).filter((x) => !String(x).startsWith("mcp__")); }
      else if (m.type === "assistant") for (const b of m.message.content || []) { if (b.type === "tool_use") names[b.id] = b.name; }
      else if (m.type === "user" && Array.isArray(m.message.content)) for (const b of m.message.content) { if (b.type === "tool_result" && names[b.tool_use_id] && calls.length < 200) calls.push({ tool: names[b.tool_use_id], refused: !!b.is_error }); }
    };
    child.stdout.on("data", (b) => {
      const text = String(b);
      stdout = (stdout + text).slice(-OUTPUT_MAX);
      carry += text;
      const parts = carry.split(/\r?\n/);
      carry = parts.pop();                                               // the last piece may be half a line: it waits for the rest
      for (const line of parts) if (line) note(line);
    });
    child.stderr.on("data", (b) => {
      const text = String(b); stderr = (stderr + text).slice(-OUTPUT_MAX);
      for (const line of text.split(/\r?\n/).filter(Boolean)) onLog(line.slice(0, 500));
    });
    child.on("error", (e) => { cleanup(); resolve({ ok: false, error: e.message, error_kind: "other" }); });
    child.on("close", (code) => {
      cleanup();
      if (carry) note(carry);
      const failed = code !== 0 || (result && result.is_error);
      const why = result && result.is_error ? String(result.result || result.subtype || "") : (stderr || stdout).slice(-500);
      resolve({ ok: !failed, error: failed ? why.slice(-500) : "", error_kind: failed ? kindOf(why, result && result.api_error_status) : "", exit_code: code, model: used, builtin_tools: builtin, calls });
    });
    child.stdin.end(prompt);
  });
}

/** One question, answered as JSON. Runs in an empty temporary folder with no tool but (for pictures) Read limited to that folder, so it can only answer. */
function ask({ system, prompt, schema, images = [], model, timeout = 300, signal } = {}, deps = {}) {
  return new Promise((resolve) => {
    const began = Date.now();
    const finish = (value) => resolve({ text: "", error: "", error_kind: "", models: [], seconds: Math.round((Date.now() - began) / 100) / 10, ...value });
    let command;try{command=deps.command||commandFor('claude');}catch(e){finish({ ok: false, error: e.message, error_kind: "login" });return;}
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vt-ask-"));
    const cleanup = () => fs.rmSync(dir, { recursive: true, force: true });
    try {
      const systemFile = path.join(dir, "system.txt");
      fs.writeFileSync(systemFile, system || "You answer only with the requested JSON, no other text.");
      const names = images.map((image, n) => { fs.writeFileSync(path.join(dir, `frame${n}.png`), Buffer.isBuffer(image) ? image : Buffer.from(String(image), "base64")); return `frame${n}.png`; });
      const schemaJson = schema ? JSON.stringify(schema) : "";
      const inline = schemaJson.length > SCHEMA_ARG_MAX;
      const list = ["-p", "--output-format", "json", "--no-session-persistence", "--tools", names.length ? "Read" : "", "--disable-slash-commands", "--strict-mcp-config",
        "--model", modelName(model), "--system-prompt-file", systemFile];
      if (names.length) list.push("--allowedTools", "Read(./**)");           // only this folder: a path outside it is refused (checked against the real program)
      if (schemaJson && !inline) list.push("--json-schema", schemaJson);
      const stdin = (names.length ? `First open and look at these image files with the Read tool: ${names.join(", ")}\n\n` : "") + String(prompt || "")
        + (inline ? `\n\nAnswer with ONE JSON object only (no prose, no code fence) that matches this JSON Schema:\n${schemaJson}` : "");
      const child = (deps.spawn || spawn)(command.file, [...command.prefix, ...list], { cwd: dir, windowsHide: true, shell: false, env: cleanEnv(command.env), stdio: ["pipe", "pipe", "pipe"] });
      let stdout = "", stderr = "", timedOut = false, over = false;
      const stop = () => child.kill();
      const timer = setTimeout(() => { timedOut = true; stop(); }, (Number(timeout) > 0 ? Number(timeout) : 300) * 1000);
      signal?.addEventListener("abort", stop, { once: true });
      if (signal?.aborted) stop();
      child.stdout.on("data", (b) => { if (stdout.length < OUTPUT_MAX) stdout += String(b); else over = true; });
      child.stderr.on("data", (b) => { stderr = (stderr + String(b)).slice(-4000); });
      child.on("error", (e) => { clearTimeout(timer); cleanup(); finish({ ok: false, error: `Claude Code could not be started (${e.message}).`, error_kind: "other" }); });
      child.on("close", (code) => {
        clearTimeout(timer); signal?.removeEventListener("abort", stop); cleanup();
        if (timedOut) return finish({ ok: false, error: `Claude did not answer within ${Math.round(Number(timeout) > 0 ? Number(timeout) : 300)} s.`, error_kind: "other" });
        let d;
        try { if (over) throw new Error("too long"); d = JSON.parse(stdout); } catch { return finish({ ok: false, error: `Claude Code gave no JSON answer (exit ${code}): ${(stderr || stdout).slice(0, 160)}`, error_kind: kindOf(stderr || stdout) }); }
        const models = Object.keys(d.modelUsage || {});
        if (d.is_error) { const why = String(d.result || d.subtype || "error"); return finish({ ok: false, error: `Claude said: ${why.slice(0, 200)}`, error_kind: kindOf(why, d.api_error_status), models }); }
        finish({ ok: true, text: d.structured_output !== undefined && d.structured_output !== null ? JSON.stringify(d.structured_output) : String(d.result || ""), models, cost_usd: Number(d.total_cost_usd) || 0 });
      });
      child.stdin.on("error", () => {});
      child.stdin.end(stdin);
    } catch (e) { cleanup(); finish({ ok: false, error: e.message, error_kind: "other" }); }
  });
}

module.exports = { status, statusAsync, args, definition, run, ask, kindOf, modelName, cleanEnv, DEFAULT_MODEL, MCP_ANSWER_TOKENS };
