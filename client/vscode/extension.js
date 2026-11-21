// A small preview of a Video Tool shot beside the code. It only reads from the server (the shot's page and the list of shots); the person's edits and the
// agent's writes go through Video Tool as before. No key is stored here: a server on this computer needs none.
const vscode = require("vscode");

const clean = (s) => String(s || "").replace(/[^A-Za-z0-9._-]/g, "");

async function listShots(server, project) {
  const r = await fetch(`${server}/api/projects/${encodeURIComponent(project)}/shots`);
  if (!r.ok) throw new Error(`The server answered ${r.status}.`);
  const j = await r.json();
  return Array.isArray(j) ? j : j.shots || [];
}

function page(url) {
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src ${new URL(url).origin}; style-src 'unsafe-inline'"></head>
<body style="margin:0;background:#111"><iframe src="${url}" sandbox="allow-scripts" style="border:0;width:100vw;height:100vh"></iframe></body></html>`;
}

function activate(context) {
  context.subscriptions.push(vscode.commands.registerCommand("videoTool.previewShot", async () => {
    const cfg = vscode.workspace.getConfiguration("videoTool");
    const server = String(cfg.get("server") || "").replace(/\/$/, "");
    const project = clean(cfg.get("project") || (vscode.workspace.workspaceFolders?.[0]?.name ?? ""));
    if (!project) return vscode.window.showWarningMessage("Open the video's folder first, or set videoTool.project.");
    let shots;
    try { shots = await listShots(server, project); }
    catch (e) { return vscode.window.showErrorMessage(`Video Tool is not reachable at ${server}. ${e.message}`); }
    if (!shots.length) return vscode.window.showInformationMessage("This video has no shots yet. Ask Claude Code to write one.");
    const pick = await vscode.window.showQuickPick(shots.map((s) => ({ label: s.id, description: s.title || "" })), { placeHolder: "Which shot?" });
    if (!pick) return;
    const panel = vscode.window.createWebviewPanel("videoToolShot", `Shot ${pick.label}`, vscode.ViewColumn.Beside, { enableScripts: true });
    panel.webview.html = page(`${server}/api/projects/${encodeURIComponent(project)}/shots/${encodeURIComponent(clean(pick.label))}/page/index.html?editor=1`);
  }));
}
function deactivate() {}
module.exports = { activate, deactivate, clean, page };
