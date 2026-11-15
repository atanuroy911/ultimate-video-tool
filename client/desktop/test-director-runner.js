const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const runner = require("./director-runner");
const codex = require("./codex-runner");

// the planning session: the Video Tool MCP tools and no built-in tool at all (a shell, file reading and searching ran with the old flags)
const command = runner.args("C:/tmp/mcp.json");
assert.strictEqual(command[command.indexOf("--allowedTools") + 1], "mcp__video-tool__*");
assert.strictEqual(command[command.indexOf("--tools") + 1], "", "no built-in tool");
assert.strictEqual(command[command.indexOf("--model") + 1], "sonnet", "Sonnet unless another is chosen");
assert(command.includes("--strict-mcp-config"));
assert(!command.includes("Bash") && !command.includes("Read") && !command.includes("Write"));
assert.strictEqual(runner.args("x", "opus")[runner.args("x", "opus").indexOf("--model") + 1], "opus");
assert.deepStrictEqual(runner.definition({ server: "http://box:8765/", token: "secret" }), {
  type: "http", url: "http://box:8765/mcp", headers: { Authorization: "Bearer secret" },
});
assert.deepStrictEqual(runner.definition({ server: "http://box:8765/" }), { type: "http", url: "http://box:8765/mcp" }, "no key on the server's own network");
assert.deepStrictEqual(runner.definition({ mcp: { command: "python", args: ["-m", "vt.mcp.server"], env: { VT_DATA: "data" } } }), {
  command: "python", args: ["-m", "vt.mcp.server"], env: { VT_DATA: "data" },
});

// a model name reaches the command line only when it is letters, digits, dots and dashes
for (const good of ["sonnet", "opus", "claude-sonnet-5-5", "claude-opus-5.5"]) assert.strictEqual(runner.modelName(good), good);
for (const bad of ["", undefined, "sonnet; calc", "--tools", "a b", "../x", "$(id)"]) assert.strictEqual(runner.modelName(bad), "sonnet");

// what went wrong, in the three kinds the server understands
for (const text of ["Claude AI usage limit reached|1730000000", "5-hour limit reached ∙ resets 3am", "You've hit your limit", "weekly limit reached", "429 Too Many Requests"]) assert.strictEqual(runner.kindOf(text), "limit", text);
for (const text of ["Invalid API key · Please run /login", "Not logged in", "OAuth token has expired"]) assert.strictEqual(runner.kindOf(text), "login", text);
assert.strictEqual(runner.kindOf("", 429), "limit");
assert.strictEqual(runner.kindOf("", 401), "login");
assert.strictEqual(runner.kindOf("the network dropped"), "other");
assert.strictEqual(runner.kindOf("overloaded, try again"), "other");

// a program's own login is used: an API key in the environment must not reach it
process.env.ANTHROPIC_API_KEY = "sk-test"; process.env.CLAUDE_CODE_USE_BEDROCK = "1";
const env = runner.cleanEnv({ EXTRA: "1" });
assert(!("ANTHROPIC_API_KEY" in env) && !("CLAUDE_CODE_USE_BEDROCK" in env) && env.EXTRA === "1");
delete process.env.ANTHROPIC_API_KEY; delete process.env.CLAUDE_CODE_USE_BEDROCK;

const fake = (exe, args) => args[0] === "--version"
  ? { status: 0, stdout: "2.1.0", stderr: "" }
  : { status: 0, stdout: JSON.stringify({ loggedIn: true }), stderr: "" };
assert.deepStrictEqual(runner.status(fake), { found: true, logged_in: true, version: "2.1.0", reason: "" });
const fakeAsync = async (exe, args) => fake(exe, args);
const asyncStatus = runner.statusAsync(fakeAsync);
const missing = runner.statusAsync(async () => ({ error: new Error("ENOENT"), status: 1, stdout: "", stderr: "" }));

// a stand-in for the program: it records what it was given and answers like `claude -p --output-format json`
const standIn = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "vt-standin-")), "claude.js");
fs.writeFileSync(standIn, `
const fs = require("fs");
let stdin = "";
process.stdin.on("data", (b) => { stdin += b; });
process.stdin.on("end", () => {
  const a = process.argv.slice(2), at = (flag) => a[a.indexOf(flag) + 1];
  const mode = process.env.STAND_IN;
  if (mode === "hang") return setTimeout(() => {}, 60000);
  if (mode === "garbage") return process.stdout.write("not json at all");
  if (mode === "limit") return process.stdout.write(JSON.stringify({ type: "result", is_error: true, result: "Claude AI usage limit reached|1730000000", modelUsage: {} }));
  const seen = { args: a, cwd: process.cwd(), files: fs.readdirSync(process.cwd()).sort(), stdin, system: fs.readFileSync(at("--system-prompt-file"), "utf8"), key: process.env.ANTHROPIC_API_KEY || "" };
  process.stdout.write(JSON.stringify(mode === "plain" ? { type: "result", is_error: false, result: "just words", total_cost_usd: 0.002, modelUsage: { "claude-sonnet-5-5": {} } }
    : { type: "result", is_error: false, result: "{}", structured_output: seen, total_cost_usd: 0.001, modelUsage: { "claude-sonnet-5-5": {}, "claude-haiku-5-5": {} } }));
});
`);
const stand = (mode) => ({ file: process.execPath, prefix: [standIn], env: { STAND_IN: mode } });

(async () => {
  assert.deepStrictEqual(await asyncStatus, { found: true, logged_in: true, version: "2.1.0", reason: "" });
  assert.strictEqual((await missing).found, false);

  // a question without pictures: no tool at all, the system prompt in a file, the schema on the command line
  process.env.ANTHROPIC_API_KEY = "sk-test";
  const schema = { type: "object", properties: { answer: { type: "string" } }, required: ["answer"] };
  const plain = await runner.ask({ system: "Be exact.", prompt: "What is 2+2?", schema, model: "sonnet", timeout: 20 }, { command: stand("echo") });
  delete process.env.ANTHROPIC_API_KEY;
  assert.strictEqual(plain.ok, true);
  const seen = JSON.parse(plain.text);
  assert.strictEqual(seen.args[seen.args.indexOf("--tools") + 1], "", "no tool without pictures");
  assert(!seen.args.includes("--allowedTools"));
  assert.strictEqual(seen.args[seen.args.indexOf("--json-schema") + 1], JSON.stringify(schema));
  assert.strictEqual(seen.args[seen.args.indexOf("--output-format") + 1], "json");
  assert.strictEqual(seen.system, "Be exact.");
  assert.strictEqual(seen.stdin, "What is 2+2?");
  assert.strictEqual(seen.key, "", "the API key stayed out");
  assert(seen.cwd.includes("vt-ask-") && !seen.cwd.startsWith(process.cwd()), "its own empty folder");
  assert.deepStrictEqual(seen.files, ["system.txt"]);
  assert.deepStrictEqual(plain.models, ["claude-sonnet-5-5", "claude-haiku-5-5"]);
  assert(!fs.existsSync(seen.cwd), "the folder is removed afterwards");

  // with pictures: only Read, and only inside that folder; the pictures are named in the prompt
  const withPictures = await runner.ask({ prompt: "Which word?", schema, images: [Buffer.from("png-one").toString("base64"), Buffer.from("png-two")], model: "opus" }, { command: stand("echo") });
  const picked = JSON.parse(withPictures.text);
  assert.strictEqual(picked.args[picked.args.indexOf("--tools") + 1], "Read");
  assert.strictEqual(picked.args[picked.args.indexOf("--allowedTools") + 1], "Read(./**)");
  assert.strictEqual(picked.args[picked.args.indexOf("--model") + 1], "opus");
  assert.deepStrictEqual(picked.files, ["frame0.png", "frame1.png", "system.txt"]);
  assert(picked.stdin.startsWith("First open and look at these image files with the Read tool: frame0.png, frame1.png\n\nWhich word?"));
  assert.strictEqual(picked.system, "You answer only with the requested JSON, no other text.");

  // a long schema goes into the prompt instead of the command line
  const long = { type: "object", properties: Object.fromEntries(Array.from({ length: 400 }, (_, i) => ["field_" + i, { type: "string" }])) };
  const inline = JSON.parse((await runner.ask({ prompt: "Q", schema: long }, { command: stand("echo") })).text);
  assert(!inline.args.includes("--json-schema"));
  assert(inline.stdin.includes("Answer with ONE JSON object only") && inline.stdin.includes("field_399"));

  // a plain-text answer comes back as it is
  assert.strictEqual((await runner.ask({ prompt: "Q" }, { command: stand("plain") })).text, "just words");

  // failures say what kind they are
  const limited = await runner.ask({ prompt: "Q" }, { command: stand("limit") });
  assert.deepStrictEqual([limited.ok, limited.error_kind], [false, "limit"]);
  assert.match(limited.error, /usage limit/);
  const garbage = await runner.ask({ prompt: "Q" }, { command: stand("garbage") });
  assert.deepStrictEqual([garbage.ok, garbage.error_kind], [false, "other"]);
  assert.match(garbage.error, /no JSON answer/);
  const slow = await runner.ask({ prompt: "Q", timeout: 0.4 }, { command: stand("hang") });
  assert.deepStrictEqual([slow.ok, slow.error_kind], [false, "other"]);
  assert.match(slow.error, /did not answer within/);
  const controller = new AbortController();
  const stopped = runner.ask({ prompt: "Q", timeout: 30, signal: controller.signal }, { command: stand("hang") });
  setTimeout(() => controller.abort(), 300);
  assert.strictEqual((await stopped).ok, false);

  // Codex: the same question, with its pictures attached by option and the schema in the prompt
  const cx = codex.askArgs({ answerFile: "/tmp/a.txt", imageFiles: ["/tmp/f0.png", "/tmp/f1.png"], model: "gpt-5" });
  assert.deepStrictEqual(cx.slice(0, 5), ["exec", "-i", "/tmp/f0.png", "-i", "/tmp/f1.png"]);
  assert.strictEqual(cx[cx.length - 1], "-", "the prompt is read from stdin after the last option");
  assert(["--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check"].every((f) => cx.includes(f)));
  assert.strictEqual(cx[cx.indexOf("--sandbox") + 1], "read-only");
  assert(!cx.includes("--dangerously-bypass-approvals-and-sandbox") && !cx.some((x) => /mcp_servers/.test(x)), "no tool server, no bypass");
  assert.strictEqual(cx[cx.indexOf("-m") + 1], "gpt-5");
  const noKey = codex.args("http://box:8790", "", "sonnet").find((x) => /mcp_servers/.test(x));
  assert(noKey.includes('url="http://box:8790/mcp"') && !noKey.includes("http_headers") && !noKey.includes(",}"), noKey);
  assert(codex.args("http://box:8790", "tok").find((x) => /mcp_servers/.test(x)).includes('"auto",http_headers={Authorization="Bearer tok"}'));
  const cxArgs = codex.args("http://box:8790", "tok", "sonnet");
  assert(cxArgs.includes("--ignore-user-config") && cxArgs.includes("read-only") && !cxArgs.includes("--dangerously-bypass-approvals-and-sandbox"));
  // the server asks Codex for no model (the Claude setting names a Claude model): no -m, so Codex uses the one it is set up with
  assert(!codex.args("http://box:8790", "tok", "").includes("-m") && !codex.askArgs({ answerFile: "/tmp/a.txt", model: "" }).includes("-m"), "no model, no -m");
  const codexStandIn = path.join(path.dirname(standIn), "codex.js");
  fs.writeFileSync(codexStandIn, `
const fs = require("fs");
let stdin = ""; process.stdin.on("data", (b) => { stdin += b; });
process.stdin.on("end", () => { const a = process.argv.slice(2); fs.writeFileSync(a[a.indexOf("-o") + 1], JSON.stringify({ seen: stdin.length, pictures: a.filter((x) => x === "-i").length })); });
`);
  const answered = await codex.ask({ system: "Be brief.", prompt: "Q", schema, images: [Buffer.from("x")] }, { command: { file: process.execPath, prefix: [codexStandIn], env: {} } });
  assert.strictEqual(answered.ok, true);
  assert.strictEqual(JSON.parse(answered.text).pictures, 1);
  // the planning session, against a stand-in that streams events like `claude -p --output-format stream-json`
  const streamer = path.join(path.dirname(standIn), "stream.js");
  fs.writeFileSync(streamer, `
const fs = require("fs");
const a = process.argv.slice(2), mode = process.env.STREAM;
fs.writeFileSync(process.env.RECORD, JSON.stringify({ args: a, cwd: process.cwd(), files: fs.readdirSync(process.cwd()), config: fs.readFileSync(a[a.indexOf("--mcp-config") + 1], "utf8"), key: process.env.ANTHROPIC_API_KEY || "" }));
process.stdin.resume();
process.stdin.on("end", () => {
  const say = (o) => process.stdout.write(JSON.stringify(o) + "\\n");
  const init = JSON.stringify({ type: "system", subtype: "init", model: "claude-sonnet-5-5", tools: ["mcp__video-tool__list_projects", "mcp__video-tool__get_script_task"] }) + "\\n";
  process.stdout.write(init.slice(0, 40));                                  // one line, arriving in two pieces
  setTimeout(() => {
    process.stdout.write(init.slice(40));
    say({ type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "mcp__video-tool__list_projects", input: {} }, { type: "tool_use", id: "t2", name: "Bash", input: { command: "echo hi" } }] } });
    say({ type: "user", message: { content: [{ type: "tool_result", tool_use_id: "t1", content: "[]" }, { type: "tool_result", tool_use_id: "t2", is_error: true, content: "No such tool" }] } });
    if (mode === "limit") { say({ type: "result", subtype: "success", is_error: true, result: "5-hour limit reached ∙ resets 3am" }); process.exit(0); }
    if (mode === "crash") { process.stderr.write("boom"); process.exit(3); }
    say({ type: "result", subtype: "success", is_error: false, result: "done" });
  }, 40);
});
`);
  const record = path.join(path.dirname(standIn), "record.json");
  const streamIn = (mode) => ({ file: process.execPath, prefix: [streamer], env: { STREAM: mode, RECORD: record } });
  process.env.ANTHROPIC_API_KEY = "sk-test";
  const logged = [];
  const planned = await runner.run({ prompt: "Direct project p1.", server: "http://box:8790", token: "secret", model: "opus" }, (line) => logged.push(line), { command: streamIn("ok") });
  delete process.env.ANTHROPIC_API_KEY;
  assert.strictEqual(planned.ok, true);
  assert.strictEqual(planned.model, "claude-sonnet-5-5", "the model is read from the init line, even when it arrives in two pieces");
  assert.deepStrictEqual(planned.builtin_tools, []);
  assert.deepStrictEqual(planned.calls, [{ tool: "mcp__video-tool__list_projects", refused: false }, { tool: "Bash", refused: true }]);
  assert.strictEqual(logged.length, 4, "four whole lines are passed on");
  assert.strictEqual(JSON.parse(logged[0]).subtype, "init", "the line that arrived in two pieces is passed on whole");
  const given = JSON.parse(fs.readFileSync(record, "utf8"));
  assert.strictEqual(given.args[given.args.indexOf("--tools") + 1], "");
  assert.strictEqual(given.args[given.args.indexOf("--model") + 1], "opus");
  assert(given.cwd.endsWith("work") && given.files.length === 0, "it works in an empty folder");
  assert(!given.config.includes("work") && JSON.parse(given.config).mcpServers["video-tool"].headers.Authorization === "Bearer secret", "the key sits beside that folder, not in it");
  assert.strictEqual(given.key, "");
  assert(!fs.existsSync(path.dirname(given.args[given.args.indexOf("--mcp-config") + 1])), "its temporary folder is removed afterwards");
  // a usage limit arrives as a result with is_error, and the program still exits with 0
  const limit = await runner.run({ prompt: "p", server: "http://box:8790", token: "t" }, () => {}, { command: streamIn("limit") });
  assert.deepStrictEqual([limit.ok, limit.error_kind, limit.exit_code], [false, "limit", 0]);
  assert.match(limit.error, /5-hour limit/);
  const crashed = await runner.run({ prompt: "p", server: "http://box:8790", token: "t" }, () => {}, { command: streamIn("crash") });
  assert.deepStrictEqual([crashed.ok, crashed.error_kind, crashed.exit_code], [false, "other", 3]);
  assert.match(crashed.error, /boom/);
  // a long video's whole task arrives as one tool answer: the session has no file tools to read a saved copy (2026-11-15)
  const { EventEmitter } = require("events");
  let env = null;
  const fake = (file, args, opts) => { env = opts.env; const c = new EventEmitter(); c.stdout = new EventEmitter(); c.stderr = new EventEmitter();
    c.stdin = { end: () => setImmediate(() => c.emit("close", 0)) }; c.kill = () => {}; return c; };
  await runner.run({ prompt: "p", server: "http://box:8790", token: "t" }, () => {}, { command: { file: "claude", prefix: [] }, spawn: fake });
  assert(Number(env.MAX_MCP_OUTPUT_TOKENS) >= 100000, "a long video's task is not cut into a file the director cannot read");
  console.log("director runner: ok");
})().catch((e) => { console.error(e); process.exit(1); });
