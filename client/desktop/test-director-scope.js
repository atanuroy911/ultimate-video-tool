/* Task tokens reach only the scoped MCP endpoint; assistants receive no server-wide key. */
const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const claude = require("./director-runner");
const codex = require("./codex-runner");
const { Helper } = require("./helper");

const server = "http://box:8790", token = "task-project-credential";
assert.deepStrictEqual(claude.definition({ server, token: "server-wide-key", directorToken: token }), {
  type: "http", url: server + "/mcp/director", headers: { "X-VT-Director-Token": token },
});
const options = codex.args(server, "server-wide-key", "", token).find(value => value.startsWith("mcp_servers="));
assert(options.includes(server + "/mcp/director"));
assert(options.includes('"X-VT-Director-Token"="' + token + '"'));
assert(!options.includes("server-wide-key") && !options.includes("Authorization"));

(async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "vt-scope-"));
  try {
    let task;
    const helper = new Helper({ home, runners: { claude: { run: async value => { task = value; return { ok: true }; } } } });
    helper.assistants.claude = { found: true, logged_in: true, at: Date.now() };
    const controller = new AbortController();
    await helper.perform({ kind: "claude", type: "direct", request: "r1", project: "p1", controller,
      link: { server, token: "server-wide-key" }, task: { prompt: "Direct p1", director_token: token } });
    assert.strictEqual(task.directorToken, token);
    assert.strictEqual(task.token, "");
    assert.strictEqual(task.server, server);
    console.log("director project scope tests passed");
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
