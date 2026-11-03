import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Download, Film, RefreshCw, Search, Send, Users, Clock3, ArrowRight } from "lucide-react";
import { get, post, fmtTime } from "../api";
import { useFetch } from "../hooks";
import type { ProjectSummary } from "../types";
import SocialDispatch from "../components/SocialDispatch";
import Accounts from "../social/Accounts";
import { platformNames, platformMark, type Account, type Group } from "../social/types";

type Task={id:string;project_id:string;platform:string;account_name:string;title:string;status:string;progress:number;message:string;error:string;permalink:string;scheduled_for?:string};
type Log={id:number;at:string;status:string;message:string;platform:string;account_name:string;permalink:string};
type Export={name:string;url:string;size:number};
const states:Record<string,string>={queued:'Waiting',uploading:'Uploading',published:'Published',failed:'Needs attention',cancelled:'Cancelled'};

export default function SocialHub() {
  const [params,setParams]=useSearchParams();
  const tab=params.get('tab')==='accounts'?'accounts':params.get('tab')==='activity'?'activity':'videos';
  const [videos,setVideos]=useState<ProjectSummary[]>([]),[accounts,setAccounts]=useState<Account[]>([]),[groups,setGroups]=useState<Group[]>([]),[tasks,setTasks]=useState<Task[]>([]),[logs,setLogs]=useState<Log[]>([]);
  const [query,setQuery]=useState(''),[onlyReady,setOnlyReady]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[actionBusy,setActionBusy]=useState<string|null>(null);
  const [activity,setActivity]=useState<'active'|'history'|'log'>('active');
  const refreshing=useRef(false);
  const selected=videos.find(v=>v.id===params.get('video'))??videos.find(v=>v.export_count>0)??videos[0];
  const exports=useFetch<Export[]>(selected?`/api/projects/${selected.id}/exports`:null);
  const [exportName,setExportName]=useState('');
  useEffect(()=>setExportName(''),[selected?.id]);
  const file=exports.data?.find(f=>f.name===exportName)??exports.data?.[0];
  const setTab=(next:string)=>setParams(p=>{p.set('tab',next);return p;});
  async function refresh(){
    if(refreshing.current)return;refreshing.current=true;
    try {
      const results=await Promise.allSettled([get<ProjectSummary[]>('/api/projects').then(setVideos),get<Account[]>('/api/social/accounts').then(setAccounts),get<Group[]>('/api/social/groups').then(setGroups),get<Task[]>('/api/social/tasks').then(setTasks),get<Log[]>('/api/social/logs').then(setLogs)]);
      const failure=results.find(r=>r.status==='rejected') as PromiseRejectedResult|undefined;
      setError(failure?.reason?.message||'');
    } finally {refreshing.current=false;setLoading(false);}
  }
  useEffect(()=>{refresh();const timer=window.setInterval(refresh,4000);return()=>window.clearInterval(timer);},[]);
  async function taskAction(id:string,action:string){setActionBusy(id);setError('');try{await post(`/api/social/tasks/${id}/${action}`);await refresh();}catch(e:any){setError(e.message);}finally{setActionBusy(null);}}
  const visible=videos.filter(v=>(!onlyReady||v.export_count>0)&&v.title.toLowerCase().includes(query.toLowerCase()));
  const pending=tasks.filter(t=>['queued','uploading'].includes(t.status));
  const shownTasks=tasks.filter(t=>activity==='active'?['queued','uploading','failed'].includes(t.status):['published','cancelled'].includes(t.status));
  return <div className="page-inner workflow-page">
    <header className="workflow-header"><div><h1>Share videos</h1><p>Choose a video. Make it a post.</p></div><button className="btn ghost icon" aria-label="Refresh sharing" onClick={refresh}><RefreshCw size={17}/></button></header>
    <nav className="workflow-tabs" aria-label="Sharing"><button className={tab==='videos'?'selected':''} aria-current={tab==='videos'?'page':undefined} onClick={()=>setTab('videos')}><Send size={16}/> New post</button><button className={tab==='activity'?'selected':''} aria-current={tab==='activity'?'page':undefined} onClick={()=>setTab('activity')}><Clock3 size={16}/> Activity {pending.length>0&&<span className="count-badge">{pending.length}</span>}</button><button className={tab==='accounts'?'selected':''} aria-current={tab==='accounts'?'page':undefined} onClick={()=>setTab('accounts')}><Users size={16}/> Accounts</button></nav>
    {error&&<div className="banner err" role="alert">{error}<button className="btn sm" onClick={refresh}>Try again</button></div>}
    {tab==='videos'&&<div className="share-workspace">
      <section className="share-picker" aria-label="Choose a video"><div className="row"><h2 className="grow">Your videos</h2><span className="small muted">{videos.length}</span></div><label className="search-field"><Search size={16}/><input aria-label="Find a video" placeholder="Find a video…" value={query} onChange={e=>setQuery(e.target.value)}/></label><div className="workflow-tabs compact"><button aria-pressed={!onlyReady} className={!onlyReady?'selected':''} onClick={()=>setOnlyReady(false)}>All videos</button><button aria-pressed={onlyReady} className={onlyReady?'selected':''} onClick={()=>setOnlyReady(true)}>Ready to post</button></div>
        <div className="share-picker-list">{visible.map(v=><button className={`share-pick ${selected?.id===v.id?'on':''}`} aria-pressed={selected?.id===v.id} key={v.id} onClick={()=>setParams(p=>{p.set('video',v.id);return p;})}><span className="share-pick-thumb">{v.cover_url||v.thumb?<img src={v.cover_url||v.thumb||''} alt="" loading="lazy"/>:<Film size={23}/>}</span><span className="grow"><strong>{v.title}</strong><small>{fmtTime(v.duration||0)} · {v.aspect}</small><span className={`small ${v.export_count?'text-success':'muted'}`}>{v.export_count?'Ready to post':v.scene_count?'Export first':'Still being made'}</span></span><ArrowRight size={15}/></button>)}</div>
        {loading&&<p role="status">Loading videos…</p>}{!loading&&!visible.length&&<div className="quiet-empty"><p>{videos.length?'No videos match. Try All videos or another name.':'Your videos will appear here.'}</p>{!videos.length&&<Link className="btn" to="/new">Make a video</Link>}</div>}
      </section>
      {selected?<section className="share-compose" key={selected.id} aria-label={`Share ${selected.title}`}><div className="share-video-heading"><div><h2>{selected.title}</h2><span className="small muted">{selected.aspect} · {fmtTime(selected.duration||0)}</span></div><Link className="btn sm ghost" to={`/p/${selected.id}`}>Edit video</Link></div>
        <div className="share-preview-row"><div className="share-film">{file?<video key={file.url} src={file.url} poster={selected.cover_url||selected.thumb||undefined} controls preload="metadata" playsInline/>:selected.thumb?<img src={selected.thumb} alt={`${selected.title} preview`}/>:<Film size={32}/>}</div><div className="col">{exports.loading?<p role="status">Loading exports…</p>:file?<><span className="chip ok">Ready to share</span>{(exports.data?.length||0)>1&&<label className="field">Video version<select value={file.name} onChange={e=>setExportName(e.target.value)}>{exports.data?.map(f=><option key={f.name} value={f.name}>{f.name}</option>)}</select></label>}<a className="btn" href={file.url} download><Download size={15}/> Download</a><span className="small muted">Or post directly below.</span></>:<><h3>{selected.scene_count?'One step before sharing':'Finish your video'}</h3><p className="small muted">{selected.scene_count?'Create the final video file, then return here to post it.':'Open the video to finish preparing it.'}</p><Link className="btn primary" to={`/p/${selected.id}${selected.scene_count?'/export':''}`}>{selected.scene_count?'Export video':'Open video'}<ArrowRight size={15}/></Link></>}{exports.error&&<p role="alert">{exports.error}</p>}</div></div>
        {file&&<SocialDispatch key={`${selected.id}:${file.name}`} projectId={selected.id} videoFilename={file.name} defaultTitle={selected.title} defaultDescription="" defaultTags={[]} onAccounts={()=>setTab('accounts')} onSent={()=>{setTab('activity');refresh();}}/>}
      </section>:<div className="quiet-empty"><Film size={36}/><h2>Pick a video to get started</h2></div>}
    </div>}
    {tab==='accounts'&&<Accounts accounts={accounts} groups={groups} onChange={refresh}/>}
    {tab==='activity'&&<section className="col"><div className="workflow-tabs compact" aria-label="Activity view">{([['active','In progress'],['history','Past posts'],['log','Details']] as const).map(([v,label])=><button key={v} aria-pressed={activity===v} className={activity===v?'selected':''} onClick={()=>setActivity(v)}>{label}</button>)}</div>
      {activity==='log'?<div className="activity-log">{logs.map(l=><article key={l.id}><span className="small muted">{l.at}</span><strong>{l.account_name||platformNames[l.platform]||'Publishing'}</strong><span>{l.message}</span>{l.permalink&&<a href={l.permalink} target="_blank" rel="noreferrer">View post</a>}</article>)}{!logs.length&&<p className="muted">No activity yet.</p>}</div>:<>{shownTasks.map(t=><article className="publish-task" key={t.id}><span className={`platform-mark platform-${t.platform}`}>{platformMark[t.platform]}</span><div className="grow"><strong>{t.title}</strong><div className="small muted">{t.account_name} · {platformNames[t.platform]}</div><div className="small">{t.scheduled_for&&t.status==='queued'?`Scheduled · ${new Date(t.scheduled_for).toLocaleString()}`:states[t.status]||t.status}</div>{t.status==='uploading'&&<progress value={t.progress} max={100} aria-label={`${t.account_name} upload progress`}/>}<p className={`small ${t.error?'text-danger':'muted'}`}>{t.error||t.message}</p></div><div className="row wrap">{t.permalink&&<a className="btn sm" href={t.permalink} target="_blank" rel="noreferrer">View post</a>}{t.status==='failed'&&<button className="btn sm" disabled={actionBusy===t.id} onClick={()=>taskAction(t.id,'retry')}>Try again</button>}{['queued','uploading'].includes(t.status)&&<button className="btn ghost sm" disabled={actionBusy===t.id} onClick={()=>taskAction(t.id,'cancel')}>Cancel</button>}</div></article>)}{!shownTasks.length&&<div className="quiet-empty"><h2>{activity==='active'?'Nothing waiting':'Your published videos will appear here'}</h2><button className="btn" onClick={()=>setTab('videos')}>Choose a video</button></div>}</>}
    </section>}
  </div>;
}
