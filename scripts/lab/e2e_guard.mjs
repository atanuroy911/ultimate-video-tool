// A guard between the Studio (Vite) and a scratch server on the owner's Windows PC (PLAN-PERFECT 0.1: no renders, speech recognition or GPU work
// there). Any request that would start heavy work (export/render, speech recognition, a pipeline, a new video, downloads, frame checks, covers) is
// refused with 423 and logged; everything else passes through, WebSockets included. Usage: node scripts/lab/e2e_guard.mjs <listen port> <target port> <log file>
//   scratch server: VT_DATA=<dir> CUDA_VISIBLE_DEVICES=-1 python -m vt.cli server --host 127.0.0.1 --port 8771 --comfy off --ollama off --gpus none
//   then: node scripts/lab/e2e_guard.mjs 8772 8771 guard.log;  cd client/studio && VT_SERVER_URL=http://127.0.0.1:8772 npx vite --port 5179 --strictPort --host 127.0.0.1
//   and:  VT_DATA=<dir> python scripts/lab/run_e2e.py http://127.0.0.1:5179 out.md   (suites that need heavy work fail with "Refused by the test guard")
import http from "node:http";
import net from "node:net";
import fs from "node:fs";

const [listen, target, log] = [Number(process.argv[2] || 8772), Number(process.argv[3] || 8771), process.argv[4] || "guard.log"];
const HEAVY = [
  /\/export(\?|$)/, /\/run(\?|$)/, /\/qa(\?|$)/, /\/publish(\?|$)/, /\/thumbnails/, /\/autofix/, /\/snapshot/, /\/render/, /\/context(\?|$)/,
  /\/polish(\?|$)/, /\/shorts\/detect/, /\/voice\//, /\/api\/projects\/from-/, /^\/api\/projects\/?(\?|$)/, /\/replan/, /\/script\/generate/,
  /\/catalog\/[^/]+\/project/, /\/catalog\/refresh/, /\/catalog\/[^/]+\/check/, /\/catalog\/[^/]+\/music/, /\/models\/[^/]+\/pull/, /\/engines\/.*(install|start|setup)/,
  /\/setup\/(install|run|start)/, /\/sound-events(\?|$)/, /\/sounds\/(detect|listen)/, /\/regenerate/, /\/continue/, /\/my-voices/, /\/comfy\//, /\/shorts(\?|$)/,
];
const heavy = (m, u) => m !== "GET" && m !== "HEAD" && m !== "OPTIONS" && HEAVY.some((rx) => rx.test(u));
const note = (s) => fs.appendFileSync(log, `${new Date().toISOString()} ${s}\n`);

http.createServer((req, res) => {
  if (heavy(req.method, req.url)) {
    note(`REFUSED ${req.method} ${req.url}`);
    res.writeHead(423, { "content-type": "application/json" });
    return res.end(JSON.stringify({ detail: "Refused by the test guard: heavy work does not run on this PC (run this suite on the GPU server's scratch)." }));
  }
  const up = http.request({ host: "127.0.0.1", port: target, method: req.method, path: req.url, headers: req.headers }, (r) => { res.writeHead(r.statusCode, r.headers); r.pipe(res); });
  up.on("error", (e) => { res.writeHead(502); res.end(String(e)); });
  req.pipe(up);
}).on("upgrade", (req, sock, head) => {
  const up = net.connect(target, "127.0.0.1", () => {
    up.write(`${req.method} ${req.url} HTTP/1.1\r\n` + Object.entries(req.headers).map(([k, v]) => `${k}: ${v}`).join("\r\n") + "\r\n\r\n");
    if (head?.length) up.write(head);
    sock.pipe(up).pipe(sock);
  });
  up.on("error", () => sock.destroy());
  sock.on("error", () => up.destroy());
}).listen(listen, "127.0.0.1", () => note(`guard on ${listen} -> ${target}`));
