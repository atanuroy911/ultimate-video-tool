import { useEffect, useState } from 'react';
import { get, post } from '../api';
import { Spinner } from '../ui';

interface Plan {
  recipe:string; label:string; models_dir:string; model_locations:string[];
  files:{file:string;have:boolean;to:string;gb:number}[];
  download_gb:number; problems:string[];
}
interface Job {id:string;status:string;frac:number;msg:string;error:string}

/** The same server-side missing-model plan used by engine discovery. Never downloads without a click. */
export default function PrepareComfy({url}:{url:string}) {
  const [plan,setPlan]=useState<Plan|null>(null),[error,setError]=useState('');
  const [folder,setFolder]=useState(''),[job,setJob]=useState<Job|null>(null),[busy,setBusy]=useState(false);
  useEffect(()=>{
    let current=true;setBusy(true);setError('');setPlan(null);
    get<Plan>(`/api/discover/prepare?url=${encodeURIComponent(url)}&models_dir=${encodeURIComponent(folder)}`)
      .then(p=>{if(current)setPlan(p);}).catch(e=>{if(current)setError(e.message);}).finally(()=>{if(current)setBusy(false);});
    return()=>{current=false;};
  },[url,folder]);
  useEffect(()=>{
    if(!job||!['queued','running'].includes(job.status))return;
    const timer=setInterval(()=>get<Job>(`/api/jobs/${job.id}`).then(setJob).catch(()=>{}),1500);
    return()=>clearInterval(timer);
  },[job?.id,job?.status]);
  const running=!!job&&['queued','running'].includes(job.status);
  const start=async()=>{
    if(!plan)return;setBusy(true);setError('');
    try{setJob(await post<Job>('/api/discover/prepare',{url,recipe:plan.recipe,models_dir:folder}));}
    catch(e:any){setError(e.message);}finally{setBusy(false);}
  };
  return <div className="ios-row stack prep">
    <h4 className="prep-title">Picture models</h4>
    {busy&&!plan&&<span className="prep-line"><Spinner/> Checking what this server already has…</span>}
    {error&&<p className="small" role="alert">{error}</p>}
    {plan&&<>
      <p className="prep-line">Recommended for this engine: <b>{plan.label}</b></p>
      {plan.download_gb>0?<>
        <label className="field">Model folder on the processing server<select value={folder} disabled={busy||running} onChange={e=>setFolder(e.target.value)}><option value="">Use this ComfyUI’s current folders</option>{plan.model_locations.map(p=><option key={p} value={p}>{p}</option>)}</select></label>
        <span className="small muted">These folders are already read by this ComfyUI. Choose a new folder in a separate managed installation.</span>
        {plan.files.map(f=><span key={f.file} className="small">{f.have?'Already installed':'Missing'} · {f.file}{!f.have?` · ${f.gb} GB`:''}</span>)}
      </>:<p className="status-line ok"><i aria-hidden />All required picture models are already installed.</p>}
      {plan.problems.map(p=><span key={p} className="small" role="alert">{p}</span>)}
      {job?.status==='done'?<p className="status-line ok" role="status"><i aria-hidden />Picture models and workflow are ready.</p>:<button className="btn sm prep-action" disabled={busy||running||plan.problems.length>0} onClick={start}>{running?'Preparing models…':plan.download_gb?`Download missing models · ${plan.download_gb} GB`:'Use recommended models'}</button>}
      {job&&job.status!=='done'&&<span className="small" role="status">{job.status==='error'?job.error:job.status==='cancelled'?'Preparation cancelled.':`${Math.round(job.frac*100)}% · ${job.msg||job.status}`}</span>}
    </>}
  </div>;
}
