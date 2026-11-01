import { useEffect, useState } from "react";
import { del, get, post } from "../api";
import { useT } from "../i18n";

type Account = { id: string; platform: string; name: string; handle: string; active: number };
type Group = { id: string; name: string; accounts: Account[] };
type Task = { id: string; project_id: string; platform: string; account_name: string; title: string; status: string; progress: number; message: string; error: string; permalink: string };
type Log = { id: number; at: string; status: string; message: string; platform: string; project_id: string; permalink: string };

export default function SocialHub() {
  const tr = useT();
  const [tab, setTab] = useState<"tasks" | "logs" | "accounts">("tasks");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [error, setError] = useState("");
  const [platform, setPlatform] = useState("mock");
  const [name, setName] = useState("");
  const [handle, setHandle] = useState("");
  const [credentials, setCredentials] = useState("{}");
  const [groupName, setGroupName] = useState("");
  const [members, setMembers] = useState<string[]>([]);
  const [metaAppId, setMetaAppId] = useState("");
  const [metaAppSecret, setMetaAppSecret] = useState("");
  const [metaUserToken, setMetaUserToken] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const refresh = async () => {
    try {
      const [a, g, t, l] = await Promise.all([get<Account[]>("/api/social/accounts"), get<Group[]>("/api/social/groups"), get<Task[]>("/api/social/tasks"), get<Log[]>("/api/social/logs")]);
      setAccounts(a); setGroups(g); setTasks(t); setLogs(l); setError("");
    } catch (e: any) { setError(e.message || "Could not load social tasks"); }
  };
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 3000); return () => window.clearInterval(timer); }, []);
  const act = async (action: () => Promise<unknown>) => { try { await action(); await refresh(); } catch (e: any) { setError(e.message || "Request failed"); } };
  const addAccount = () => act(async () => { await post(`/api/social/accounts/connect/${platform}`, { platform, name, handle, credentials: JSON.parse(credentials) }); setName(""); setHandle(""); setCredentials("{}"); });
  const addGroup = () => act(async () => { await post("/api/social/groups", { name: groupName, account_ids: members }); setGroupName(""); setMembers([]); });
  const connectMeta = () => act(async () => { await post("/api/social/accounts/meta/exchange", { app_id: metaAppId, app_secret: metaAppSecret, user_token: metaUserToken }); setMetaAppSecret(""); setMetaUserToken(""); });
  return <div className="page-inner col" style={{ gap: 18 }}>
    <div className="row wrap" style={{ justifyContent: "space-between" }}><div><h1>{tr("social.title")}</h1><p className="muted">{tr("social.subtitle")}</p></div><button className="btn" onClick={refresh}>Refresh</button></div>
    {error && <div className="banner err" role="alert">{error}</div>}
    <div className="row wrap" style={{ gap: 8 }}>{(["tasks", "logs", "accounts"] as const).map(x => <button key={x} className={`btn ${tab === x ? "primary" : ""}`} onClick={() => setTab(x)}>{tr(`social.${x}`)}</button>)}</div>
    {tab === "tasks" && <div className="card card-pad col" style={{ gap: 12 }}>
      <div className="row wrap"><select aria-label="Filter by platform" value={platformFilter} onChange={e => setPlatformFilter(e.target.value)}><option value="">All platforms</option>{["youtube", "facebook", "instagram", "tiktok", "mock"].map(p => <option key={p}>{p}</option>)}</select><select aria-label="Filter by status" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="">All statuses</option>{["queued", "uploading", "published", "failed", "cancelled"].map(s => <option key={s}>{s}</option>)}</select></div>
      {tasks.filter(t => (!platformFilter || t.platform === platformFilter) && (!statusFilter || t.status === statusFilter)).map(t => <div key={t.id} className="card card-pad row wrap" style={{ gap: 12, alignItems: "center" }}><div className="col grow" style={{ gap: 4 }}><strong>{t.title}</strong><span className="small muted">{t.platform} · {t.account_name} · {t.project_id}</span><span className="small">{t.status} {t.message ? `· ${t.message}` : ""}</span>{t.status === "uploading" && <progress value={t.progress} max={1} style={{ width: "100%" }} />}{t.error && <span className="small" style={{ color: "var(--danger, #c33)" }}>{t.error}</span>}</div>{t.permalink && <a className="btn sm" href={t.permalink} target="_blank" rel="noreferrer">View post</a>}{t.status === "failed" && <button className="btn sm" onClick={() => act(() => post(`/api/social/tasks/${t.id}/retry`))}>Retry</button>}{["queued", "uploading"].includes(t.status) && <button className="btn sm" onClick={() => act(() => post(`/api/social/tasks/${t.id}/cancel`))}>Cancel</button>}</div>)}
      {!tasks.length && <p className="muted">No tasks yet. Dispatch a finished export to a group to begin.</p>}
    </div>}
    {tab === "logs" && <div className="card card-pad col" style={{ gap: 8 }}>{logs.map(l => <div key={l.id} className="row wrap small" style={{ gap: 12, borderBottom: "1px solid var(--border, #ddd)", padding: 8 }}><span>{l.at}</span><strong>{l.status}</strong><span>{l.platform} · {l.project_id}</span><span className="grow">{l.message}</span>{l.permalink && <a href={l.permalink} target="_blank" rel="noreferrer">View post</a>}</div>)}{!logs.length && <p className="muted">No execution logs yet.</p>}</div>}
    {tab === "accounts" && <div className="col" style={{ gap: 16 }}>
      <div className="card card-pad col" style={{ gap: 10 }}><h2>Connect Facebook and Instagram</h2><p className="small muted">Exchange a Meta app user token for Page access. Linked Instagram Business accounts are added automatically.</p><input aria-label="Meta app ID" placeholder="Meta app ID" value={metaAppId} onChange={e => setMetaAppId(e.target.value)} /><input type="password" aria-label="Meta app secret" placeholder="Meta app secret" value={metaAppSecret} onChange={e => setMetaAppSecret(e.target.value)} /><input type="password" aria-label="Short-lived user token" placeholder="Short-lived user token" value={metaUserToken} onChange={e => setMetaUserToken(e.target.value)} /><button className="btn primary" disabled={!metaAppId || !metaAppSecret || !metaUserToken} onClick={connectMeta}>Connect managed Pages</button></div>
      <div className="card card-pad col" style={{ gap: 10 }}><h2>Connect account</h2><div className="row wrap" style={{ gap: 8 }}><select aria-label="Platform" value={platform} onChange={e => setPlatform(e.target.value)}>{["mock", "youtube", "facebook", "instagram", "tiktok"].map(p => <option key={p}>{p}</option>)}</select><input placeholder="Account name" aria-label="Account name" value={name} onChange={e => setName(e.target.value)} /><input placeholder="Handle" aria-label="Handle" value={handle} onChange={e => setHandle(e.target.value)} /></div><label className="small">Credentials JSON (stored locally, never returned by the API)<textarea value={credentials} onChange={e => setCredentials(e.target.value)} rows={3} style={{ width: "100%" }} /></label><button className="btn primary" disabled={!name.trim()} onClick={addAccount}>Connect account</button><p className="small muted">Use mock for a dry run. Live accounts need access_token; Facebook also needs page_id, Instagram needs ig_user_id, and YouTube can refresh with client_id, client_secret and refresh_token.</p></div>
      <div className="card card-pad col" style={{ gap: 8 }}><h2>Connected accounts</h2>{accounts.filter(a => a.active).map(a => <div className="row wrap" key={a.id}><span className="grow">{a.platform} · {a.name} {a.handle}</span><button className="btn sm" onClick={() => act(() => del(`/api/social/accounts/${a.id}`))}>Disconnect</button></div>)}</div>
      <div className="card card-pad col" style={{ gap: 10 }}><h2>Create group</h2><input placeholder="Group name" aria-label="Group name" value={groupName} onChange={e => setGroupName(e.target.value)} />{accounts.filter(a => a.active).map(a => <label key={a.id} className="row" style={{ gap: 8 }}><input type="checkbox" checked={members.includes(a.id)} onChange={e => setMembers(e.target.checked ? [...members, a.id] : members.filter(x => x !== a.id))} />{a.platform} · {a.name}</label>)}<button className="btn primary" disabled={!groupName.trim() || !members.length} onClick={addGroup}>Create group</button></div>
      <div className="card card-pad col" style={{ gap: 8 }}><h2>Groups</h2>{groups.map(g => <div className="row wrap" key={g.id}><span className="grow">{g.name} · {g.accounts.map(a => a.name).join(", ")}</span><button className="btn sm" onClick={() => act(() => del(`/api/social/groups/${g.id}`))}>Delete</button></div>)}</div>
    </div>}
  </div>;
}
