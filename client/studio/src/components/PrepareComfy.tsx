import { CircleCheck, Download } from 'lucide-react';
import { useEffect, useState } from 'react';
import { get, post } from '../api';
import { Spinner } from '../ui';
import ModelList, { type ModelOption } from './ModelList';

interface Plan {
  recipe:string; label:string; models_dir:string; model_locations:string[];
  files:{file:string;have:boolean;to:string;gb:number}[];
  download_gb:number; problems:string[]; choices?:(ModelOption&{addon?:boolean})[]; instance?:{gpu:string;vram_gb:number};
}
interface Job {id:string;status:string;frac:number;msg:string;error:string}

/** Picture models for a ComfyUI the person already has: the best one for its card is picked; one button gets what is missing.
 *  The same server-side plan engine discovery uses. Never downloads without a click. */
export default function PrepareComfy({url,onReady}:{url:string;onReady?:()=>void}) {
  const [plan,setPlan]=useState<Plan|null>(null),[error,setError]=useState('');
  const [recipe,setRecipe]=useState('');
  const [folder,setFolder]=useState(''),[job,setJob]=useState<Job|null>(null),[busy,setBusy]=useState(false);
  useEffect(()=>{
    let current=true;setBusy(true);setError('');
    get<Plan>(`/api/discover/prepare?url=${encodeURIComponent(url)}&recipe=${encodeURIComponent(recipe)}&models_dir=${encodeURIComponent(folder)}`)
      .then(p=>{if(current){setPlan(p);if(!recipe)setRecipe(p.recipe);}}).catch(e=>{if(current)setError(e.message);}).finally(()=>{if(current)setBusy(false);});
    return()=>{current=false;};
  },[url,folder,recipe]);
  useEffect(()=>{
    if(!job||!['queued','running'].includes(job.status))return;
    const timer=setInterval(()=>get<Job>(`/api/jobs/${job.id}`).then(j=>{setJob(j);if(j.status==='done')onReady?.();}).catch(()=>{}),1500);
    return()=>clearInterval(timer);
  },[job?.id,job?.status]);
  const running=!!job&&['queued','running'].includes(job.status);
  const start=async()=>{
    if(!plan)return;setBusy(true);setError('');
    try{setJob(await post<Job>('/api/discover/prepare',{url,recipe:plan.recipe,models_dir:folder}));}
    catch(e:any){setError(e.message);}finally{setBusy(false);}
  };
  const cardGb=Math.round((plan?.instance?.vram_gb||0)*1e9/2**30);
  return <div className="ios-row stack prep">
    <h4 className="prep-title">Picture model</h4>
    {busy&&!plan&&<span className="prep-line"><Spinner/> Checking which models it already has…</span>}
    {error&&<p className="small status-line bad" role="alert"><i aria-hidden />{error}</p>}
    {plan&&<>
      {plan.choices?.length?<ModelList name={`prep-${url}`} options={plan.choices} value={recipe||plan.recipe} onChange={setRecipe} cardGb={cardGb}/>:<p className="prep-line">Best for its card: <b>{plan.label}</b></p>}
      {plan.download_gb>0?<>
        {plan.model_locations.length>1&&<label className="field">Save the models in<select value={folder} disabled={busy||running} onChange={e=>setFolder(e.target.value)}><option value="">The folders this ComfyUI uses now</option>{plan.model_locations.map(p=><option key={p} value={p}>{p}</option>)}</select></label>}
        <details className="setup-more"><summary className="small">What downloads ({plan.download_gb} GB)</summary>
          {plan.files.map(f=><span key={f.file} className="small row" style={{gap:6}}>{f.have?<CircleCheck size={14} className="ok-icon" aria-hidden/>:<Download size={14} aria-hidden/>}{f.file}{f.have?' · already there':` · ${f.gb} GB`}</span>)}
        </details>
      </>:<p className="status-line ok"><i aria-hidden />It already has every file this model needs.</p>}
      {plan.problems.map(p=><p key={p} className="small status-line bad" role="alert"><i aria-hidden />{p}</p>)}
      {job?.status==='done'?<p className="status-line ok" role="status"><i aria-hidden />Ready. Pictures will use {plan.label}.</p>
        :<button className="btn primary prep-action" data-testid="prepare-go" disabled={busy||running||plan.problems.length>0} onClick={start}>{running?<><Spinner size={14}/> Getting it ready…</>:plan.download_gb?<><Download size={16} aria-hidden/> Download · {plan.download_gb} GB</>:'Use this model'}</button>}
      {job&&job.status!=='done'&&<span className="small" role="status">{job.status==='error'?job.error:job.status==='cancelled'?'Stopped.':`${Math.round(job.frac*100)}% · ${job.msg||job.status}`}</span>}
    </>}
  </div>;
}
