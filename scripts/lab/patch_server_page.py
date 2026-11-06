"""Server page in the navigation; Settings down to five sections with deep links; Director wording; the server's own name in the setup banner."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "client/studio/src"


def sub(path: Path, old: str, new: str, count: int = 1):
    s = path.read_text(encoding="utf-8")
    assert old in s, (path.name, old[:80])
    path.write_text(s.replace(old, new, count), encoding="utf-8")


# ---- server: the setup API names the server by its own name, not the computer's hostname
sub(ROOT / "server/vt/engines/setup.py", "'server':{'name':socket.gethostname(),", "'server':{'name':_server_name(),")
sub(ROOT / "server/vt/engines/setup.py", "def overview", '''def _server_name() -> str:
    """The name this server goes by (its --name), the same everywhere; the computer's name only when it has none."""
    try:
        from ..server.serve import STATE

        return STATE.get("name") or socket.gethostname()
    except Exception:
        return socket.gethostname()


def overview''')

# ---- Settings: five sections, deep link ?s=, no engines (they live on the Server page)
p = C / "pages/Settings.tsx"
s = p.read_text(encoding="utf-8")
a, b = s.index('      <div id="engines"'), s.index('      <div id="ai"')
s = s[:a] + s[b:]
s = s.replace('import Engines from "./Engines";\n', "").replace('import LocalAI from "./LocalAI";\n', "").replace('import ComfySettings from "./ComfySettings";\n', "")
s = s.replace('    ["server", "Server & engines", "The computer that does the work: how busy it is, and the programs it uses to make pictures, voices and plans."],\n', "")
s = s.replace('["libraries", "Picture libraries"', '["libraries", "Picture libraries"')
s = s.replace('  const [section, setSection] = useState("general");', '''  const [params, setParams] = useSearchParams();
  const keys = ["general", "voice", "directors", "libraries", "help"];
  const [section, setSectionState] = useState(() => (keys.includes(params.get("s") || "") ? (params.get("s") as string) : "general"));
  const setSection = (k: string) => { setSectionState(k); setParams({ s: k }, { replace: true }); };           // a link such as /settings?s=directors opens that section
  useEffect(() => { const k = params.get("s"); if (k && keys.includes(k)) setSectionState(k); }, [params]);       // eslint-disable-line react-hooks/exhaustive-deps''')
s = s.replace('import { useEffect, useRef, useState } from "react";', 'import { useEffect, useRef, useState } from "react";\nimport { useSearchParams } from "react-router-dom";')
p.write_text(s, encoding="utf-8")

# ---- Engines page: the System panel lives on the Server page now (once)
p = C / "pages/Engines.tsx"
s = p.read_text(encoding="utf-8")
s = s.replace('import SystemPanel from "../components/SystemStats";\n', "").replace("      <SystemPanel />\n", "")
p.write_text(s, encoding="utf-8")

# ---- route
sub(C / "main.tsx", 'const ReviewPage = lazyScreen(() => import("./pages/Review"));', 'const ReviewPage = lazyScreen(() => import("./pages/Review"));\nconst ServerPage = lazyScreen(() => import("./pages/Server"));')
sub(C / "main.tsx", '          <Route path="/settings" element={<SettingsPage />} />', '          <Route path="/server" element={<ServerPage />} />\n          <Route path="/settings" element={<SettingsPage />} />')

# ---- shell: Server in the sidebar and the phone tab bar; "Director" wording; the AI pill opens Settings > Directors
p = C / "Shell.tsx"
s = p.read_text(encoding="utf-8")
s = s.replace('import { Film, Moon, Palette, Play, Scissors, Settings as Cog, Share2, Sun, X } from "lucide-react";',
              'import { Film, Moon, Palette, Play, Scissors, Server as ServerIcon, Settings as Cog, Share2, Sun, X } from "lucide-react";')
s = s.replace('import { SystemPill } from "./components/SystemStats";', 'import { ServerDot, SystemPill } from "./components/SystemStats";')
old = '<NavLink to="/social" className={({ isActive }) => (isActive ? "active" : "")}><Share2 size={18} /> Share videos</NavLink>'
assert old in s
s = s.replace(old, old + '\n          <NavLink to="/server" className={({ isActive }) => (isActive ? "active" : "")}><ServerIcon size={18} /> Server <ServerDot /></NavLink>')
s = s.replace('onClick={() => nav("/settings")}\n          title={`Decisions are made by:', 'onClick={() => nav("/settings?s=directors")}\n          title={`Decisions are made by:')
s = s.replace('<span className="hide-sm">AI: </span>{aiName}', '<span className="hide-sm">Director: </span>{aiName}')
old_tabs = '[["/", t("nav.projects"), Film, true], ["/themes", t("nav.themes"), Palette, false], ["/shorts", t("nav.shorts"), Scissors, false], ["/social", t("nav.social"), Share2, false], ["/settings", t("nav.settings"), Cog, false]] as const'
assert old_tabs in s
s = s.replace(old_tabs, '[["/", t("nav.projects"), Film, true], ["/shorts", t("nav.shorts"), Scissors, false], ["/social", t("nav.social"), Share2, false], ["/server", "Server", ServerIcon, false], ["/settings", t("nav.settings"), Cog, false]] as const')
p.write_text(s, encoding="utf-8")
print("ok")
