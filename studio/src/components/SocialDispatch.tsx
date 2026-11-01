import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, post } from "../api";
import { useT } from "../i18n";

type Group = { id: string; name: string; accounts: { id: string; platform: string; name: string }[] };
export default function SocialDispatch({ projectId, videoFilename, defaultTitle, defaultDescription, defaultTags }: { projectId: string; videoFilename: string; defaultTitle: string; defaultDescription: string; defaultTags: string[] }) {
  const tr = useT();
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupId, setGroupId] = useState("");
  const [title, setTitle] = useState(defaultTitle);
  const [description, setDescription] = useState(defaultDescription);
  const [tags, setTags] = useState(defaultTags.join(" "));
  const [schedule, setSchedule] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState("");
  const [busy, setBusy] = useState(false);
  const [customize, setCustomize] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, { title: string; description: string; hashtags: string }>>({});
  useEffect(() => { get<Group[]>("/api/social/groups").then(setGroups).catch(e => setError(e.message)); }, []);
  useEffect(() => { setTitle(defaultTitle); setDescription(defaultDescription); setTags(defaultTags.join(" ")); }, [defaultTitle, defaultDescription, defaultTags.join(" ")]);
  const selected = groups.find(g => g.id === groupId);
  const platforms = Array.from(new Set((selected?.accounts || []).map(a => a.platform)));
  const edit = (platform: string, key: "title" | "description" | "hashtags", value: string) => setOverrides(current => ({ ...current, [platform]: { title: current[platform]?.title || "", description: current[platform]?.description || "", hashtags: current[platform]?.hashtags || "", [key]: value } }));
  const dispatch = async () => {
    setBusy(true); setError("");
    try {
      const platform_overrides = Object.fromEntries(Object.entries(overrides).map(([platform, value]) => [platform, { title: value.title || undefined, description: value.description || undefined, hashtags: value.hashtags ? value.hashtags.split(/[\s,]+/).map(x => x.replace(/^#/, "")).filter(Boolean) : undefined }]));
      const res = await post<{ batch_id: string; total_tasks: number }>(`/api/projects/${projectId}/social/dispatch`, { group_id: groupId, video_filename: videoFilename, title, description, hashtags: tags.split(/[\s,]+/).map(x => x.replace(/^#/, "")).filter(Boolean), scheduled_for: schedule ? new Date(schedule).toISOString() : null, platform_overrides });
      setSent(`Queued ${res.total_tasks} upload tasks.`);
    } catch (e: any) { setError(e.message || "Dispatch failed"); }
    finally { setBusy(false); }
  };
  return <div className="card card-pad col" style={{ gap: 10 }}><strong>{tr("social.dispatch")}</strong>
    {!groups.length ? <p className="small muted">Create a group of accounts in <Link to="/social">Social publishing</Link> first.</p> : <>
      <label className="small">Target group<select value={groupId} onChange={e => setGroupId(e.target.value)} style={{ width: "100%" }}><option value="">Select a group</option>{groups.map(g => <option key={g.id} value={g.id}>{g.name} ({g.accounts.length} channels)</option>)}</select></label>
      {selected && <span className="small muted">{selected.accounts.map(a => `${a.platform}: ${a.name}`).join(" · ")}</span>}
      <label className="small">Title<input value={title} onChange={e => setTitle(e.target.value)} style={{ width: "100%" }} /></label>
      <label className="small">Description<textarea rows={3} value={description} onChange={e => setDescription(e.target.value)} style={{ width: "100%" }} /></label>
      <label className="small">Hashtags<input value={tags} onChange={e => setTags(e.target.value)} style={{ width: "100%" }} /></label>
      <label className="small">Schedule (leave empty for now)<input type="datetime-local" value={schedule} onChange={e => setSchedule(e.target.value)} /></label>
      <button className="btn sm" onClick={() => setCustomize(!customize)} aria-expanded={customize}>{customize ? "Hide platform text" : "Customize per platform"}</button>
      {customize && platforms.map(platform => <div className="card card-pad col" style={{ gap: 8 }} key={platform}><strong className="small">{platform}</strong><input aria-label={`${platform} title`} placeholder="Use main title" value={overrides[platform]?.title || ""} onChange={e => edit(platform, "title", e.target.value)} /><textarea aria-label={`${platform} description`} placeholder="Use main description" value={overrides[platform]?.description || ""} onChange={e => edit(platform, "description", e.target.value)} /><input aria-label={`${platform} hashtags`} placeholder="Use main hashtags" value={overrides[platform]?.hashtags || ""} onChange={e => edit(platform, "hashtags", e.target.value)} /></div>)}
      <button className="btn primary" disabled={!groupId || !title.trim() || !videoFilename || busy} onClick={dispatch}>{busy ? "Queuing…" : `Dispatch to ${selected?.accounts.length || 0} channels`}</button>
    </>}
    {error && <span className="small" role="alert">{error}</span>}{sent && <span className="small">{sent} <Link to="/social">View task flow</Link></span>}
  </div>;
}
