import { Suspense } from "react";
import { Film, Moon, MoreHorizontal, Palette, Play, Scissors, Server as ServerIcon, Settings as Cog, Share2, Sun, X } from "lucide-react";
import { Sheet } from "./ds";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { EXPECTED_API, get } from "./api";
import { useT } from "./i18n";
import { connStore, settingsStore, startRealtime, useStore } from "./store";
import { BusyLayer } from "./busy";
import { ChoiceDot, ServerDot, SystemPill } from "./components/SystemStats";
import { Toasts } from "./ui";
import { installRadioKeys } from "./radioKeys";
import { useLink } from "./connection";
import SetupWizard from './components/SetupWizard';

function useDark() {
  const [dark, setDark] = useState<boolean>(() => {
    const s = localStorage.getItem("vt-theme");
    return s ? s === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    localStorage.setItem("vt-theme", dark ? "dark" : "light");
  }, [dark]);
  return [dark, setDark] as const;
}

export default function Shell() {
  const t = useT();
  const nav = useNavigate();
  const location = useLocation();
  const editing = /^\/p\/[^/]+\/?$/.test(location.pathname);
  const link = useLink();
  const [menuOpen, setMenuOpen] = useState(false);
  const [phoneMore,setPhoneMore]=useState(false);
  useEffect(() => setMenuOpen(false), [location.pathname]);
  useEffect(() => installRadioKeys(), []);                                        // arrow keys move through every radio group
  useEffect(() => {
    const toggle = () => setMenuOpen(v => !v);
    window.addEventListener("vt-app-menu", toggle);
    return () => window.removeEventListener("vt-app-menu", toggle);
  }, []);
  const conn = useStore(connStore);
  const [dirs, setDirs] = useState<{ order?: string[]; directors: { kind: string; label: string; available: boolean }[] } | null>(null);
  useEffect(() => {                                                // who will direct the next video: the first available one in the person's order
    const read = () => get<{ order?: string[]; directors: { kind: string; label: string; available: boolean }[] }>("/api/directors").then(setDirs).catch(() => {});
    read();
    const t = window.setInterval(() => { if (!document.hidden) read(); }, 15000);
    return () => window.clearInterval(t);
  }, []);
  const firstDirector = dirs ? (dirs.order || []).map((k) => dirs.directors.find((d) => d.kind === k && d.available)).find(Boolean) : null;
  // Subscribe to settings changes — used for lang and to re-fetch AI status so the pill stays in sync
  const settings = useStore(settingsStore);
  const [dark, setDark] = useDark();
  useEffect(() => {
    startRealtime();
  }, []);

  const [stale, setStale] = useState<string | null>(null);
  const [serverSetup,setServerSetup]=useState<{done:boolean;server:{name:string};existing:Record<string,string[]>}|null>(null);
  const [setupOpen,setSetupOpen]=useState(false),[setupLater,setSetupLater]=useState(false);
  useEffect(()=>{get<any>('/api/setup').then(setServerSetup).catch(()=>{});},[]);
  useEffect(() => {                                   // a page newer than its server calls endpoints the server does not have (they answer 404/405)
    get<{ api_version?: number }>("/api/health").then((h) => setStale(!h.api_version || h.api_version < EXPECTED_API ? "older" : null)).catch(() => {});
  }, []);
  const mcp = conn.mcp;
  // which brain makes the decisions: shown to everyone, because with the logged-in Claude CLI or Ollama nothing has to "connect"
  const [ai, setAi] = useState<{ provider: string; model: string; available: boolean } | null>(null);
  // Re-fetch AI status whenever settings change so the header pill stays in sync
  useEffect(() => {
    get<{ provider: string; model: string; available: boolean }>("/api/ai/status").then(setAi).catch(() => setAi(null));
  }, [settings]);
  const aiName = !ai || ai.provider === "off" || !ai.available ? "rules only" : ai.provider.startsWith("claude") || ai.provider === "anthropic" ? "Claude" : ai.model || ai.provider;
  return (
    <div className={`shell ${editing ? "shell-editor" : ""} ${menuOpen ? "menu-open" : ""}`}>
      {editing && menuOpen && <button className="shell-menu-backdrop" aria-label="Close app navigation" onClick={() => setMenuOpen(false)} />}
      <header className="topbar">
        {editing && <button className="btn ghost" onClick={() => setMenuOpen(false)}><X size={16} /> Back to editing</button>}
        <button className="brand" onClick={() => nav("/")} aria-label="Ultimate Video Tool home">
          <span className="brand-mark">
            <Play size={15} fill="currentColor" />
          </span>
          Ultimate Video Tool
        </button>
        <button className="btn primary shell-create" onClick={() => nav("/new")}>New video</button>
        <nav className="nav" aria-label="Main">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            <Film size={18} /> Your videos
          </NavLink>
          <NavLink to="/themes" className={({ isActive }) => (isActive ? "active" : "")}>
            <Palette size={18} /> Look
          </NavLink>
          <NavLink to="/shorts" className={({ isActive }) => (isActive ? "active" : "")}>
            <Scissors size={18} /> Make short clips
          </NavLink>
          <NavLink to="/social" className={({ isActive }) => (isActive ? "active" : "")}><Share2 size={18} /> Share videos</NavLink>
          <NavLink to="/server" className={({ isActive }) => (isActive ? "active" : "")}><ServerIcon size={18} /> Server <ServerDot /><ChoiceDot /></NavLink>
          <NavLink to="/settings" className={({ isActive }) => (isActive ? "active" : "")}>
            <Cog size={18} /> Settings
          </NavLink>
        </nav>
        <div className="spacer" />
        <SystemPill />
        <button
          className="pill"
          style={{ cursor: "pointer" }}
          onClick={() => nav("/settings?s=directors")}
          title={`Decisions are made by: ${aiName}.${mcp?.connected ? ` Claude Code also connected (${mcp.seconds_ago}s ago).` : ""} Change it in Settings.`}
        >
          <span className={`dot ${ai?.available ? "ok" : ""}`} />
          <span className="hide-sm">Director: </span>{firstDirector?.label ?? aiName}
          {mcp && mcp.pending > 0 ? ` · ${mcp.pending} waiting` : ""}
        </button>
        {!conn.ws && (
          <span className="pill" title="Reconnecting to the Studio server…">
            <span className="dot err" />
            Offline
          </span>
        )}
        <button className="btn ghost icon" onClick={() => setDark(!dark)} aria-label="Toggle dark mode">
          {dark ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </header>
      {stale && (
        <div className="banner err" role="alert" style={{ margin: "8px 18px 0" }}>
          <div className="grow"><strong>This Studio server is older than the page you are looking at.</strong>
            <div className="small muted">Some buttons (Check, Check and fix, voice editing, duplicate...) would fail with “405 Method Not Allowed”. Close the Studio and start it again with <code>vt studio</code>, then reload this page.</div></div>
        </div>
      )}
      {link === "lost" && (
        <div className={`banner warn`} role="alert" style={{ margin: "8px 18px 0" }} data-testid="link-lost">
          <div className="grow"><strong>Lost the connection to the server.</strong>
            <div className="small muted">Trying again every few seconds. Check that the server computer is on and on the same network. Nothing you made is lost.</div></div>
        </div>
      )}
      {link === "back" && (
        <div className="banner ok" role="status" style={{ margin: "8px 18px 0" }} data-testid="link-back"><div className="grow"><strong>Connected again.</strong></div></div>
      )}
      <main className="page" id="main">
        {!editing&&serverSetup&&!serverSetup.done&&!setupLater&&<div className="banner" style={{margin:'12px 18px'}} role="status"><div className="grow"><strong>Processing server: {serverSetup.server?.name||'Connected server'}</strong><div className="small muted">{Object.values(serverSetup.existing||{}).some(urls=>urls.length)?'Existing engines found on this server. Reuse them and check the models you need.':'Choose folders on this server, then install or connect the engines you need.'}</div></div><button className="btn sm primary" onClick={()=>setSetupOpen(true)}>Set up server</button><button className="btn ghost sm" onClick={()=>setSetupLater(true)}>Later</button></div>}
        <Suspense fallback={<div className="page-inner muted">Loading…</div>}>
          <Outlet />
        </Suspense>
        {setupOpen&&<SetupWizard onClose={()=>{setSetupOpen(false);get<any>('/api/setup').then(setServerSetup).catch(()=>{});}}/>}
      </main>
      <nav className="tabbar" aria-label="Main (phone)">
        {([["/", t("nav.projects"), Film, true], ["/shorts", t("nav.shorts"), Scissors, false], ["/social", t("nav.social"), Share2, false], ["/server", "Server", ServerIcon, false]] as const).map(([to, label, Icon, end]) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}><Icon size={22} strokeWidth={1.8} />{to === "/server" && <ChoiceDot className="on-tab" />}<span>{label}</span></NavLink>
        ))}
        <button className="phone-more" aria-label="More pages" aria-expanded={phoneMore} onClick={()=>setPhoneMore(true)}><MoreHorizontal size={22}/><span>More</span></button>
      </nav>
      {phoneMore&&<Sheet title="More pages" onClose={()=>setPhoneMore(false)}><nav className="col" aria-label="More pages">
        <NavLink className="btn" to="/themes" onClick={()=>setPhoneMore(false)}><Palette size={18}/>Looks</NavLink>
        <NavLink className="btn" to="/settings" onClick={()=>setPhoneMore(false)}><Cog size={18}/>Settings</NavLink>
      </nav></Sheet>}
      <BusyLayer />
      <Toasts />
    </div>
  );
}
