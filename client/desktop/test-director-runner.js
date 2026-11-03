const assert = require("assert");
const runner = require("./director-runner");

const command = runner.args("C:/tmp/mcp.json");
assert.strictEqual(command[command.indexOf("--allowedTools") + 1], "mcp__video-tool__*");
assert(command.includes("--strict-mcp-config"));
assert(!command.includes("Bash") && !command.includes("Read") && !command.includes("Write"));
assert.deepStrictEqual(runner.definition({ server: "http://box:8765/", token: "secret" }), {
  type: "http", url: "http://box:8765/mcp", headers: { Authorization: "Bearer secret" },
});
assert.deepStrictEqual(runner.definition({ mcp: { command: "python", args: ["-m", "vt.mcp.server"], env: { VT_DATA: "data" } } }), {
  command: "python", args: ["-m", "vt.mcp.server"], env: { VT_DATA: "data" },
});

const fake = (exe, args) => args[0] === "--version"
  ? { status: 0, stdout: "2.1.0", stderr: "" }
  : { status: 0, stdout: JSON.stringify({ loggedIn: true }), stderr: "" };
assert.deepStrictEqual(runner.status(fake), { found: true, logged_in: true, version: "2.1.0", reason: "" });
console.log("director runner: ok");
