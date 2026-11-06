"""Settings, coherent: six sections that each answer one question. Nine sections became six; the three pages that configured the same two engines are one;
the two legacy "run this in a terminal" cards are gone (the one-click assistants replace them); the page no longer repeats its own section title."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "client/studio/src"


def cut(s: str, start: str, end: str) -> str:
    a = s.index(start)
    b = s.index(end, a) + len(end)
    return s[:a] + s[b:]


p = ROOT / "pages/Settings.tsx"
s = p.read_text(encoding="utf-8")

a = s.index("  const sections = [")
b = s.index("  ];", a) + len("  ];")
s = s[:a] + '''  const sections = [
    ["general", "Preferences", "Default shape, pace, music, theme and language for new videos."],
    ["voice", "Voice & speech", "The voices that read your script, and the models that understand speech."],
    ["server", "Server & engines", "The computer that does the work: how busy it is, and the programs it uses to make pictures, voices and plans."],
    ["directors", "Directors & assistants", "Who plans each scene, and connecting Claude or Codex."],
    ["libraries", "Picture libraries", "Free photo and video libraries."],
    ["help", "Help & checks", "See what is working and what needs attention."],
  ];''' + s[b:]

s = cut(s, '      <section className="card card-pad settings-simple">', "      </section>\n")                      # a summary card the stylesheet always hid
s = cut(s, '      <div className="settings-all-title">', "</div>\n")                                                  # the section title, said a second time
s = s.replace('      <p className="muted settings-lead">Make Video Tool work your way. Choose a category to see its controls.</p>\n', "")
s = s.replace("<strong>{l}</strong><span>{description}</span>", "<strong>{l}</strong>")
s = s.replace('<button type="button" key={k} aria-current', '<button type="button" key={k} title={description} aria-current')

s = s.replace('      <div id="local-ai"><LocalAI /></div>\n', "").replace('      <div id="pictures"><ComfySettings /></div>\n', "")
s = s.replace("      <Engines />\n      </div>", '''      <Engines />
      <details className="card card-pad settings-more">
        <summary><strong>Language AI settings</strong> <span className="small muted">address, model version, test</span></summary>
        <LocalAI />
      </details>
      <details className="card card-pad settings-more">
        <summary><strong>Pictures & clips settings</strong> <span className="small muted">address, connection check, clip models</span></summary>
        <ComfySettings />
      </details>
      </div>''')

s = cut(s, '      <section id="claude"', "      </section>\n")                                                         # "run this in a terminal": replaced by one-click connecting
s = cut(s, '      <section id="codex"', "      </section>\n")

for dead in ('  const pending = (mcp as McpStatus | null)?.pending ?? 0;\n',
             '  const readyDirectors = directors.data?.directors.filter((d) => d.id !== "best" && d.available).length ?? 0;\n',
             '  const comfyUrl = (settings as Settings & { comfy_url?: string }).comfy_url || "";\n',
             '  const remoteGpu = !!comfyUrl && !/(localhost|127\\.0\\.0\\.1)/.test(comfyUrl);\n',
             '  const mcp = useStore(connStore).mcp;\n'):
    s = s.replace(dead, "")
s = s.replace("import { Check, Copy, Download, RefreshCw, X } from \"lucide-react\";", "import { Check, Download, RefreshCw, X } from \"lucide-react\";")
s = s.replace("import { Field, ProgressBar, Seg, Spinner, copyText } from \"../ui\";", "import { Field, ProgressBar, Seg, Spinner } from \"../ui\";")
s = s.replace("import { connStore, jobsStore, settingsStore, toast, useStore } from \"../store\";", "import { jobsStore, settingsStore, toast, useStore } from \"../store\";")
s = s.replace("import type { DoctorRow, McpStatus, ModelInfo, Settings } from \"../types\";", "import type { DoctorRow, ModelInfo, Settings } from \"../types\";")
s = s.replace('<h2>Who plans each scene</h2>', '<h2>Who directs your videos</h2>')
s = s.replace('<h2>Understand spoken words</h2>', '<h2>Speech recognition</h2>')
s = s.replace('<h2 className="grow">Is everything working?</h2>', '<h2 className="grow">Is everything working?</h2>')
s = s.replace("setSection(\"general\")", "setSection(\"general\")")
p.write_text(s, encoding="utf-8")

# the legacy provider card says what it is: the server's own AI services
p = ROOT / "pages/AIAssistants.tsx"
s = p.read_text(encoding="utf-8")
s = s.replace('title: "Free AI on a computer",\n      subtitle: "Private; can use this computer or your GPU server",', 'title: "Local AI (Ollama)",\n      subtitle: "Private; runs on the server or your GPU server",')
s = s.replace('title: "Claude on this computer",\n      subtitle: "Uses your Claude login — no key to paste",', 'title: "Claude on the server",\n      subtitle: "Uses a Claude login on the server computer. Claude on your own PC is set in the list above",')
s = s.replace('<h2 className="grow">AI that directs your videos</h2>', '<h2 className="grow">AI services the server can call</h2>')
s = s.replace("The AI writes the whole plan — scenes, characters, actions, on-screen graphics. Built-in rules always back it up, so a video is made even when AI is off.",
              "Used by the server itself, after the directors above. Built-in rules always back it up, so a video is made even when AI is off.")
p.write_text(s, encoding="utf-8")

css = ROOT / "styles.css"
c = css.read_text(encoding="utf-8")
a = c.index('.settings-organized[data-section="general"] #general,')
b = c.index("{ display: flex; flex-direction: column; }", a) + len("{ display: flex; flex-direction: column; }")
c = c[:a] + '''.settings-organized[data-section="general"] #general,
.settings-organized[data-section="voice"] #speech,
.settings-organized[data-section="voice"] #voices,
.settings-organized[data-section="server"] #engines,
.settings-organized[data-section="directors"] #ai,
.settings-organized[data-section="libraries"] #stock,
.settings-organized[data-section="help"] #system { display: flex; flex-direction: column; }
.settings-more > summary { cursor: pointer; display: flex; gap: 10px; align-items: baseline; list-style: none; }
.settings-more > summary::-webkit-details-marker { display: none; }
.settings-more[open] > summary { margin-bottom: 12px; }
.settings-more .card { border: 0; box-shadow: none; padding: 0; background: transparent; }''' + c[b:]
c = c.replace(".settings-organized .settings-layout { grid-template-columns: 240px minmax(0, 1fr); }", ".settings-organized .settings-layout { grid-template-columns: 210px minmax(0, 1fr); }")
c = c.replace("border-radius: 12px; padding: 13px; cursor: pointer; }", "border-radius: 12px; padding: 11px 14px; cursor: pointer; }")
css.write_text(c, encoding="utf-8")
print("ok")
