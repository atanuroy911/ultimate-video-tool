/* Claude Desktop starts local programs only. On a client computer it starts the Video Tool app as plain Node (ELECTRON_RUN_AS_NODE=1)
 * with this file: each JSON-RPC line from Claude goes to the server's /mcp (VT_SERVER, key in VT_TOKEN) and every answer comes back as a line.
 * The server may answer with JSON or with an event stream; both are handled. Its session id is kept for the following requests.
 */
const http = require("http");
const https = require("https");
const readline = require("readline");

const url = new URL(process.env.VT_SERVER || "");
const token = process.env.VT_TOKEN || "";
const lib = url.protocol === "https:" ? https : http;
let session = "";
const out = (obj) => process.stdout.write(JSON.stringify(obj) + "\n");

function send(line) {
  let msg;
  try { msg = JSON.parse(line); } catch { return; }
  const body = Buffer.from(JSON.stringify(msg));
  const headers = { "Content-Type": "application/json", Accept: "application/json, text/event-stream", Authorization: `Bearer ${token}`, "Content-Length": body.length };
  if (session) headers["Mcp-Session-Id"] = session;
  const req = lib.request(url, { method: "POST", headers }, (res) => {
    if (res.headers["mcp-session-id"]) session = res.headers["mcp-session-id"];
    let buf = "";
    res.setEncoding("utf8");
    const sse = /text\/event-stream/.test(res.headers["content-type"] || "");
    res.on("data", (chunk) => {
      buf += chunk;
      if (!sse) return;
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {                     // one event at a time: its data lines are one message
        const event = buf.slice(0, i);
        buf = buf.slice(i + 2);
        const data = event.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("");
        if (data) try { out(JSON.parse(data)); } catch { /* not JSON */ }
      }
    });
    res.on("end", () => {
      if (res.statusCode >= 400 && msg.id !== undefined) {
        out({ jsonrpc: "2.0", id: msg.id, error: { code: -32000, message: res.statusCode === 401 ? "The Video Tool server does not accept this key any more. Connect again in the Video Tool app." : `The Video Tool server answered ${res.statusCode}.` } });
        return;
      }
      if (!sse && buf.trim()) try { out(JSON.parse(buf)); } catch { /* empty 202 for notifications */ }
    });
  });
  req.on("error", (e) => { if (msg.id !== undefined) out({ jsonrpc: "2.0", id: msg.id, error: { code: -32000, message: "Could not reach the Video Tool server: " + e.message } }); });
  req.end(body);
}

readline.createInterface({ input: process.stdin }).on("line", (l) => { if (l.trim()) send(l); });
