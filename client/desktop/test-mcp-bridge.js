/* The MCP bridge (mcp-bridge.js) against a stand-in server: an event stream with CRLF line ends is read, and a session id that comes with a refused request is not kept
   (found 2026-11-21: Claude Code's first probe, server/discover, was refused with a made-up session id, and its real initialize then got 404). */
const assert = require("node:assert/strict");
const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");

const seen = [];
const server = http.createServer((req, res) => {
  let body = "";
  req.on("data", (d) => (body += d));
  req.on("end", () => {
    const msg = JSON.parse(body);
    seen.push({ method: msg.method, session: req.headers["mcp-session-id"] || "" });
    if (msg.method === "server/discover") { res.writeHead(400, { "content-type": "application/json", "mcp-session-id": "ghost" }); res.end("{}"); return; }
    if (req.headers["mcp-session-id"] === "ghost") { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "content-type": "text/event-stream", "mcp-session-id": "real" });
    res.write(`event: message\r\ndata: ${JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: { ok: msg.method } })}\r\n\r\n`);
    res.end();
  });
});
server.listen(0, "127.0.0.1", () => {
  const bridge = spawn(process.execPath, [path.join(__dirname, "mcp-bridge.js")], { env: { ...process.env, VT_SERVER: `http://127.0.0.1:${server.address().port}/mcp` } });
  const lines = [];
  let buf = "";
  bridge.stdout.on("data", (d) => { buf += d; let i; while ((i = buf.indexOf("\n")) >= 0) { lines.push(JSON.parse(buf.slice(0, i))); buf = buf.slice(i + 1); } });
  const send = (o) => bridge.stdin.write(JSON.stringify({ jsonrpc: "2.0", ...o }) + "\n");
  const until = (n) => new Promise((r) => { const t = setInterval(() => { if (lines.length >= n) { clearInterval(t); r(); } }, 20); });
  (async () => {
    send({ id: "probe", method: "server/discover" });
    await until(1);
    assert.equal(lines[0].error.message, "The Video Tool server answered 400.");
    send({ id: 1, method: "initialize" });
    await until(2);
    assert.deepEqual(lines[1], { jsonrpc: "2.0", id: 1, result: { ok: "initialize" } }, "a CRLF event stream is read, and the refused probe's session id was not kept");
    send({ id: 2, method: "tools/list" });
    await until(3);
    assert.equal(seen[2].session, "real", "the session id of the successful answer is used from then on");
    console.log("MCP bridge: CRLF event streams and refused probes are handled.");
    bridge.kill();
    server.close();
  })().catch((e) => { console.error(e); bridge.kill(); process.exit(1); });
});
