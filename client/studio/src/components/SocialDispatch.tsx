import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, Clock3, Send } from "lucide-react";
import { get, post } from "../api";
import { Modal } from "../ui";
import { platformNames, platformMark, type Account, type Group } from "../social/types";
import "../social/social.css";

export default function SocialDispatch({projectId,videoFilename,defaultTitle,defaultDescription,defaultTags,onSent,onAccounts}: {
  projectId:string;videoFilename:string;defaultTitle:string;defaultDescription:string;defaultTags:string[];onSent?:()=>void;onAccounts?:()=>void;
}) {
  const [accounts,setAccounts]=useState<Account[]>([]),[groups,setGroups]=useState<Group[]>([]),[selected,setSelected]=useState<string[]>([]);
  const [title,setTitle]=useState(defaultTitle),[description,setDescription]=useState(defaultDescription),[tags,setTags]=useState(defaultTags.join(" "));
  const [schedule,setSchedule]=useState(""),[later,setLater]=useState(false),[section,setSection]=useState<"post"|"timing"|"platforms">("post");
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(""),[sent,setSent]=useState(""),[review,setReview]=useState(false);
  const [overrides,setOverrides]=useState<Record<string,{title:string;description:string;hashtags:string}>>({});
  const load=()=>{setLoading(true);setError("");Promise.all([get<Account[]>("/api/social/accounts"),get<Group[]>("/api/social/groups")]).then(([a,g])=>{setAccounts(a.filter(x=>x.active));setGroups(g);setSelected(ids=>ids.filter(id=>a.some(x=>x.id===id&&x.active)));}).catch(e=>setError(e.message)).finally(()=>setLoading(false));};
  useEffect(load,[]);
  useEffect(()=>{setSent("");setReview(false);},[videoFilename,description,tags,later,schedule,overrides,selected]);
  useEffect(()=>{setTitle(defaultTitle);setDescription(defaultDescription);setTags(defaultTags.join(" "));setSent("");setOverrides({});setReview(false);},[projectId,defaultTitle,defaultDescription,defaultTags.join(" ")]);
  const chosen=accounts.filter(a=>selected.includes(a.id)), platforms=[...new Set(chosen.map(a=>a.platform))];
  const ready=!!chosen.length && !!title.trim() && !!videoFilename && (!later || !!schedule);
  const edit=(p:string,k:"title"|"description"|"hashtags",v:string)=>setOverrides(old=>({...old,[p]:{...(old[p]??{title:"",description:"",hashtags:""}),[k]:v}}));
  const parseTags=(s:string)=>s.split(/[\s,]+/).map(x=>x.replace(/^#/,"")).filter(Boolean);
  async function dispatch() {
    setBusy(true);setError("");
    try {
      const when=later?new Date(schedule):null;
      if(when && (!Number.isFinite(when.getTime()) || when.getTime()<=Date.now())) throw new Error("Choose a time in the future.");
      const result=await post<{total_tasks:number}>(`/api/projects/${projectId}/social/dispatch`,{
        account_ids:chosen.map(a=>a.id),video_filename:videoFilename,title,description,hashtags:parseTags(tags),scheduled_for:when?.toISOString()??null,
        platform_overrides:Object.fromEntries(Object.entries(overrides).filter(([p])=>platforms.includes(p)).map(([p,v])=>[p,{title:v.title||undefined,description:v.description||undefined,hashtags:v.hashtags?parseTags(v.hashtags):undefined}]))});
      setSent(`${result.total_tasks} ${result.total_tasks===1?"post":"posts"} ${later?"scheduled":"queued"}.`);setReview(false);onSent?.();
    } catch(e:any){setError(e.message||"Could not queue your post.");} finally {setBusy(false);}
  }
  return <section className="post-composer col" aria-label="Prepare your post">
    <div className="row wrap"><h2 className="grow">Where to?</h2>{onAccounts?<button className="btn sm ghost" onClick={onAccounts}>Manage accounts</button>:<Link className="btn sm ghost" to="/social?tab=accounts">Manage accounts</Link>}</div>
    {loading?<p role="status">Loading accounts…</p>:accounts.length?<>
      <div className="account-choices">{accounts.map(a=><button key={a.id} className={`account-choice ${selected.includes(a.id)?"on":""}`} aria-pressed={selected.includes(a.id)} onClick={()=>{setSent("");setSelected(ids=>ids.includes(a.id)?ids.filter(id=>id!==a.id):[...ids,a.id]);}}>
        <span className={`platform-mark platform-${a.platform}`}>{platformMark[a.platform]||"●"}</span><span><strong>{a.name}</strong><small>{platformNames[a.platform]||a.platform}</small></span>{selected.includes(a.id)&&<Check size={16}/>}</button>)}</div>
      {!!groups.length&&<label className="field small">Use a saved group<select aria-label="Choose accounts from a saved group" value="" onChange={e=>{const g=groups.find(g=>g.id===e.target.value);if(g)setSelected(g.accounts.filter(a=>a.active).map(a=>a.id));}}><option value="">Choose a group…</option>{groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label>}
    </>:<div className="quiet-empty"><strong>Add an account to post directly</strong><p>You can still download the video and share it yourself.</p>{onAccounts?<button className="btn" onClick={onAccounts}>Add account</button>:<Link className="btn" to="/social?tab=accounts">Add account</Link>}<button className="btn ghost sm" onClick={load}>Refresh accounts</button></div>}
    <nav className="workflow-tabs compact" aria-label="Post options">{([['post','Post'],['timing','When'],['platforms','Per platform']] as const).map(([v,label])=><button key={v} aria-pressed={section===v} className={section===v?'selected':''} onClick={()=>setSection(v)}>{label}</button>)}</nav>
    {section==='post'&&<div className="col"><label className="field">Title<input value={title} onChange={e=>{setTitle(e.target.value);setSent("");}}/></label><label className="field">Description<textarea rows={3} value={description} onChange={e=>setDescription(e.target.value)} placeholder="What should viewers know?"/></label><label className="field">Hashtags<input value={tags} onChange={e=>setTags(e.target.value)} placeholder="#yourtopic"/></label></div>}
    {section==='timing'&&<div className="col"><div className="row"><button className={`btn ${!later?'selected':''}`} aria-pressed={!later} onClick={()=>setLater(false)}>Post now</button><button className={`btn ${later?'selected':''}`} aria-pressed={later} onClick={()=>setLater(true)}><Clock3 size={15}/> Schedule</button></div>{later&&<label className="field">Your local date and time<input type="datetime-local" value={schedule} onChange={e=>setSchedule(e.target.value)}/></label>}<p className="small muted">{later?'Keep the server running until your post is sent.':'The video uploads after you review and confirm.'}</p></div>}
    {section==='platforms'&&<div className="col">{!platforms.length?<p className="small muted">Choose an account above first.</p>:platforms.map(p=><fieldset className="post-platform" key={p}><legend>{platformNames[p]||p}</legend><label className="field">Title<input value={overrides[p]?.title||''} placeholder={title} onChange={e=>edit(p,'title',e.target.value)}/></label><label className="field">Description<textarea value={overrides[p]?.description||''} placeholder={description||'Use the main description'} onChange={e=>edit(p,'description',e.target.value)}/></label><label className="field">Hashtags<input value={overrides[p]?.hashtags||''} placeholder={tags||'Use the main hashtags'} onChange={e=>edit(p,'hashtags',e.target.value)}/></label></fieldset>)}</div>}
    {error&&<div className="banner err" role="alert">{error}</div>}{sent&&<div className="banner ok" role="status">{sent} <Link to="/social?tab=activity">View progress</Link></div>}
    <div className="post-submit"><span className="small muted">{chosen.length?`${chosen.length} ${chosen.length===1?'account':'accounts'} selected`:'Choose accounts above'}</span><button className="btn primary" disabled={!ready||busy||!!sent} onClick={()=>{setError("");setReview(true);}}><Send size={15}/> Review post</button></div>
    {review&&<Modal title={chosen.every(a=>a.platform==='mock')?'Review practice post':'Ready to share?'} onClose={()=>!busy&&setReview(false)} footer={<><button className="btn" disabled={busy} onClick={()=>setReview(false)}>Keep editing</button><button className="btn primary" disabled={busy} onClick={dispatch}>{busy?'Queuing…':later?'Schedule post':'Publish now'}</button></>}><h3>{title}</h3><p>{chosen.map(a=>`${a.name} (${platformNames[a.platform]||a.platform})`).join(', ')}</p><p>{later?new Date(schedule).toLocaleString():'Upload and publish now'}</p>{error&&<p role="alert">{error}</p>}</Modal>}
  </section>;
}
