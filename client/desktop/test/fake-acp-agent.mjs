// A stand-in ACP agent for tests (docs/plans/PLAN-WORKBENCH.MD W12.5): speaks the real protocol over stdio with scripted behaviour.
//   a normal message  -> "Hello" in 3 chunks, one video-tool tool call, one Bash call that asks permission, then "Done" (or "Denied")
//   "slow"            -> waits until the turn is cancelled
//   "limit"           -> fails the way Claude does at its usage limit
// FAKE_RECORD=<file> gets what session/new, session/resume and the prompts carried.
import fs from "node:fs";
import { Readable, Writable } from "node:stream";
import * as acp from "@agentclientprotocol/sdk";

const record = (obj) => { if (process.env.FAKE_RECORD) fs.appendFileSync(process.env.FAKE_RECORD, JSON.stringify(obj) + "\n"); };
const cancelled = new Set();
let n = 0;

class Fake {
  constructor(conn) { this.conn = conn; }
  async initialize() {
    return { protocolVersion: acp.PROTOCOL_VERSION, agentCapabilities: { loadSession: false, promptCapabilities: { image: true }, sessionCapabilities: { resume: {} } }, authMethods: [] };
  }
  async newSession(p) { record({ method: "new", cwd: p.cwd, mcpServers: p.mcpServers, meta: p._meta }); return { sessionId: `s${++n}`, models: { currentModelId: "sonnet", availableModels: [{ modelId: "sonnet", name: "Sonnet" }, { modelId: "opus", name: "Opus" }] } }; }
  async resumeSession(p) { record({ method: "resume", sessionId: p.sessionId, mcpServers: p.mcpServers }); return {}; }
  async cancel(p) { cancelled.add(p.sessionId); }
  async prompt(p) {
    const text = p.prompt.filter((b) => b.type === "text").map((b) => b.text).join("\n");
    record({ method: "prompt", text, images: p.prompt.filter((b) => b.type === "image").length });
    const say = (t) => this.conn.sessionUpdate({ sessionId: p.sessionId, update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: t } } });
    if (/limit/.test(text)) { const e = new Error("Claude usage limit reached"); throw e; }
    if (/slow/.test(text)) { await say("Working"); while (!cancelled.has(p.sessionId)) await new Promise((r) => setTimeout(r, 20)); cancelled.delete(p.sessionId); return { stopReason: "cancelled" }; }
    for (const t of ["Hel", "lo ", "there"]) await say(t);
    await this.conn.sessionUpdate({ sessionId: p.sessionId, update: { sessionUpdate: "tool_call", toolCallId: "t1", title: "mcp__video-tool__set_caption_style", kind: "other", status: "in_progress", _meta: { claudeCode: { toolName: "mcp__video-tool__set_caption_style" } } } });
    const own = await this.conn.requestPermission({ sessionId: p.sessionId, toolCall: { toolCallId: "t1", title: "mcp__video-tool__set_caption_style", _meta: { claudeCode: { toolName: "mcp__video-tool__set_caption_style" } } },
      options: [{ optionId: "allow", name: "Allow", kind: "allow_once" }, { optionId: "reject", name: "Reject", kind: "reject_once" }] });
    record({ method: "own-tool-permission", outcome: own.outcome });
    await this.conn.sessionUpdate({ sessionId: p.sessionId, update: { sessionUpdate: "tool_call_update", toolCallId: "t1", status: "completed" } });
    await this.conn.sessionUpdate({ sessionId: p.sessionId, update: { sessionUpdate: "tool_call", toolCallId: "t2", title: "Run: dir C:\Users", kind: "execute", status: "pending", rawInput: { command: "dir C:\Users" }, _meta: { claudeCode: { toolName: "Bash" } } } });
    const res = await this.conn.requestPermission({ sessionId: p.sessionId, toolCall: { toolCallId: "t2", title: "Run: dir C:\Users", kind: "execute", rawInput: { command: "dir C:\Users" }, _meta: { claudeCode: { toolName: "Bash" } } },
      options: [{ optionId: "allow", name: "Allow once", kind: "allow_once" }, { optionId: "always", name: "Allow always", kind: "allow_always" }, { optionId: "reject", name: "Reject", kind: "reject_once" }] });
    record({ method: "bash-permission", outcome: res.outcome });
    await say(res.outcome.outcome === "selected" && res.outcome.optionId !== "reject" ? " Done." : " Denied.");
    return { stopReason: "end_turn" };
  }
}

const stream = acp.ndJsonStream(Writable.toWeb(process.stdout), Readable.toWeb(process.stdin));
new acp.AgentSideConnection((conn) => new Fake(conn), stream);
