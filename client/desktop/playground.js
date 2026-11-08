#!/usr/bin/env node
/* A playground for the director path: run the same Claude call the helper makes, and watch it happen with a clock on every line.
 *
 *   node playground.js ping                         Claude answers one plain question (the "ask" path every quick check uses)
 *   node playground.js tools [server]               Claude lists the Video Tool tools it can reach (proves the MCP connection)
 *   node playground.js direct <project> [server]    the real planning task for a project: every event, every tool call, when it submits
 *
 * Options: --model sonnet|opus|haiku|<id>   --wait <seconds> (default 300)   --json (print every raw event line)
 * Nothing here changes a video unless `direct` ends with Claude submitting the plan (that is what it is for: use a throw-away project).
 * It uses the helper's own director-runner.js, so what works here is what the helper does.
 */
const runner = require("./director-runner.js");

const argv = process.argv.slice(2);
const flag = (name, fallback) => { const i = argv.indexOf(name); if (i < 0) return fallback; const v = argv[i + 1]; argv.splice(i, 2); return v; };
const raw = argv.includes("--json"); if (raw) argv.splice(argv.indexOf("--json"), 1);
const model = flag("--model", "sonnet");
const wait = Number(flag("--wait", "300"));
const [mode = "ping", a, b] = argv;
const t0 = Date.now();
const clock = () => ((Date.now() - t0) / 1000).toFixed(1).padStart(6) + " s";
const say = (...x) => console.log(clock(), ...x);

function describe(m) {                          // one event of Claude's stream, in a few words
  if (m.type === "system" && m.subtype === "init") return `started: model ${m.model}, tools ${(m.tools || []).length} (${(m.tools || []).filter((t) => !String(t).startsWith("mcp__")).length} built in), mcp ${JSON.stringify((m.mcp_servers || []).map((s) => s.name + ":" + s.status))}`;
  if (m.type === "assistant") return (m.message.content || []).map((c) => c.type === "tool_use" ? `CALLS ${c.name}(${JSON.stringify(c.input).slice(0, 90)}${JSON.stringify(c.input).length > 90 ? "... " + JSON.stringify(c.input).length + " chars" : ""})` : c.type === "text" ? `says: ${c.text.slice(0, 140).replace(/\s+/g, " ")}` : c.type === "thinking" ? "thinking..." : c.type).join(" | ");
  if (m.type === "user") return (m.message.content || []).map((c) => c.type === "tool_result" ? `TOOL ANSWERED ${String(typeof c.content === "string" ? c.content : JSON.stringify(c.content)).length} chars${c.is_error ? " (ERROR)" : ""}` : c.type).join(" | ");
  if (m.type === "rate_limit_event") return `usage: ${m.rate_limit_info?.rateLimitType} ${Math.round((m.rate_limit_info?.utilization || 0) * 100)}% used (${m.rate_limit_info?.status})`;
  if (m.type === "result") return `finished: ${m.subtype}${m.is_error ? " (ERROR)" : ""}, ${m.num_turns} turns, ${(m.duration_ms / 1000).toFixed(1)} s, cost $${(m.total_cost_usd || 0).toFixed(3)}${m.result ? ", result: " + String(m.result).slice(0, 120).replace(/\s+/g, " ") : ""}`;
  return `${m.type}${m.subtype ? "/" + m.subtype : ""}`;
}

async function main() {
  const st = await runner.status();
  say(`Claude on this computer: ${st.found ? st.version : "not found"}${st.logged_in ? ", signed in" : ", NOT signed in"}${st.reason ? " (" + st.reason + ")" : ""}`);
  if (!st.found || !st.logged_in) process.exit(2);

  if (mode === "ping") {
    const r = await runner.ask({ system: "Answer in JSON.", prompt: 'Reply with {"ok": true}.', schema: { type: "object", properties: { ok: { type: "boolean" } }, required: ["ok"] }, model, timeout: wait });
    say(r.ok ? "answered" : "FAILED", JSON.stringify(r).slice(0, 300));
    return process.exit(r.ok ? 0 : 1);
  }

  const server = (mode === "tools" ? a : b) || "http://192.168.123.47:8790";
  const prompt = mode === "tools"
    ? "List the names of the Video Tool tools you can use, one per line, then stop. Do not call any tool."
    : `Direct Video Tool project ${a}. Use only the Video Tool MCP tools. First call module_catalog_tool to discover the system's capabilities; use module_describe_tool for exact inputs instead of guessing. Call get_script_task for this project, read its timed transcript, craft rules, styles and choices, and submit the Video Script with submit_script.`;
  if (mode === "direct" && !a) { console.log("direct needs a project id"); process.exit(2); }
  say(`MCP server ${server}, model ${model}, waiting up to ${wait} s`);
  const ctl = new AbortController(); const timer = setTimeout(() => { say(`gave up after ${wait} s`); ctl.abort(); }, wait * 1000);
  const r = await runner.run({ prompt, server, signal: ctl.signal, model }, (line) => { if (raw || line[0] !== "{") say(line.slice(0, 400)); }, { onEvent: (m) => { if (!raw) say(describe(m)); } });
  clearTimeout(timer);
  say(r.ok ? "DONE" : "FAILED", r.error ? `: ${r.error}` : "", `model ${r.model || "?"}, tools it called: ${(r.calls || []).map((c) => c.tool + (c.refused ? "(refused)" : "")).join(", ") || "none"}`);
  process.exit(r.ok ? 0 : 1);
}
main().catch((e) => { console.error(e); process.exit(1); });
