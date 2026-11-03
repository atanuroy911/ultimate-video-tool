import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Modal, Spinner } from "../ui";
import type { Review } from "./useReview";
import { DirectionDrafts, type Direction } from "./directionDrafts";

type Info = {revision:number;direction:Direction;director:Record<string,any>;source_script:any;source_notes:any[];source_plan:any;components:any[];history:any[];original_voice:Record<string,any>;pictures:{id:string;label:string}[];videos:{id:string;label:string}[]};

export default function DirectionPanel({r,sid,onElement}:{r:Review;sid:string;onElement:(index:number)=>void}) {
  const base=`/api/projects/${r.id}/scenes/${sid}`;
  const [info,setInfo]=useState<Info|null>(null),[draft,setDraft]=useState<Direction|null>(null);
  const [section,setSection]=useState('plan'),[busy,setBusy]=useState(false),[job,setJob]=useState<string|null>(null),[error,setError]=useState('');
  const [document,setDocument]=useState<string|null>(null);
  const [recovery,setRecovery]=useState<DirectionDrafts|null>(null),[recovered,setRecovered]=useState(false);
  const voices=useFetch<any[]>(section==='voice'?'/api/voices':null);
  const scene=r.plan?.scenes.find(s=>s.id===sid), timing=r.timing.scenes.find(s=>s.id===sid);
  useEffect(()=>{let live=true;
    Promise.all([get<Info>(`${base}/direction`),get<{server:string}>('/__client/connection').catch(()=>({server:location.origin}))]).then(([d,connection])=>{
      if(!live)return;let storage:Storage|null=null;try{storage=sessionStorage;}catch{/* Storage can be disabled. */}
      const cache=new DirectionDrafts(connection.server,storage),stored=cache.draft(base),cached=stored&&JSON.stringify(stored.direction)!==JSON.stringify(d.direction)?stored:null,active=cache.job(base);
      if(stored&&!cached)cache.save(base,null);
      setRecovery(cache);setInfo(cached?{...d,revision:cached.revision}:d);setDraft(cached?.direction??d.direction);setRecovered(!!cached);
      if(active){setJob(active);setBusy(true);}
      if(cached&&cached.revision!==d.revision)setError('Saved instructions changed while you were away. Your draft is kept; reload the saved version to discard it.');
    }).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[base]);
  useEffect(()=>{if(!info||!draft||!recovery)return;const dirty=JSON.stringify(info.direction)!==JSON.stringify(draft);recovery.save(base,dirty?{revision:info.revision,direction:draft}:null);if(!dirty)setRecovered(false);},[base,draft,info,recovery]);
  useEffect(()=>{
    if(!job)return;let live=true,checking=false;
    const timer=setInterval(async()=>{if(checking)return;checking=true;try{
      const state=await get<any>(`/api/jobs/${job}`);if(!live)return;
      if(['done','error','cancelled'].includes(state.status)){
        recovery?.track(base,null);setJob(null);setBusy(false);
        if(state.status!=='done')setError(state.error||'Generation cancelled');
        else{await r.reloadAll();const fresh=await get<Info>(`${base}/direction`);if(live){setInfo(fresh);setDraft(fresh.direction);toast('Scene updated','ok');}}
      }
    }catch(e:any){if(live){setError(e.status===404?'This generation is no longer available. Your instructions are kept; you can try again.':e.message);if(e.status===404){recovery?.track(base,null);setJob(null);setBusy(false);}}}finally{checking=false;}},1200);
    return()=>{live=false;clearInterval(timer);};
  },[job,base,recovery]);
  const change=(key:keyof Direction,value:string)=>setDraft(d=>d?{...d,[key]:value}:d);
  const save=async()=>{if(!info||!draft)throw new Error('Direction is still loading');const result=await put<Info>(`${base}/direction`,{revision:info.revision,direction:draft});setInfo(result);return result;};
  const run=async(kind:'picture'|'video'|'voice'|'rebuild')=>{
    if(busy||!draft||!timing)return;setBusy(true);setError('');
    try{await save();let result:{id:string};
      if(kind==='picture')result=await post(`${base}/redraw`,{draw:draft.picture_prompt,recipe:draft.picture_recipe});
      else if(kind==='voice')result=await post(`/api/projects/${r.id}/voice/overdub`,{text:draft.narration,engine:draft.voice_engine,voice:draft.voice,start:timing.start,end:timing.end,scene:sid});
      else result=await post(`${base}/direction/${kind}`);
      recovery?.track(base,result.id);setJob(result.id);
    }catch(e:any){setError(e.errors?.join(' · ')||e.message);setBusy(false);}
  };
  if(!info||!draft)return <div className="direction-panel">{error?<p role="alert">{error}</p>:<Spinner/>}</div>;
  const field=(key:keyof Direction,label:string,max=4000)=><label className="field"><span>{label}</span><textarea rows={4} maxLength={max} value={draft[key]} onChange={e=>change(key,e.target.value)}/></label>;
  const select=(key:keyof Direction,label:string,options:{id:string;label:string}[])=><label className="field"><span>{label}</span><select value={draft[key]} onChange={e=>change(key,e.target.value)}>{options.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></label>;
  const engine=voices.data?.find(e=>e.id===draft.voice_engine);
  const dirty=JSON.stringify(info.direction)!==JSON.stringify(draft);
  return <div className="direction-panel col">
    <div><h3>Scene direction</h3><p className="small muted">Directed by {info.director.who||'Not recorded'}{info.director.model?` · ${info.director.model}`:''}</p></div>
    <div className="direction-tabs" role="tablist" aria-label="Scene direction sections">{[['plan','Plan'],['picture','Picture'],['video','Video'],['voice','Voice'],['history','History']].map(([id,label])=><button className={`btn sm ${section===id?'primary':'ghost'}`} role="tab" aria-selected={section===id} key={id} onClick={()=>setSection(id)}>{label}</button>)}</div>
    {error&&<p className="banner err" role="alert">{error}</p>}
    {recovered&&!error&&<p className="small muted" role="status">Your unsaved instructions were restored.</p>}
    <fieldset disabled={busy} className="direction-fields col">
    {section==='plan'&&<>
      {field('instructions','What should happen in this scene?')}
      {select('director','Director for the next version',[{id:'configured',label:'Use my AI settings'},{id:'local',label:'Local AI'},{id:'claude-server',label:'Claude on this server'}])}
      {draft.director!=='configured'&&<label className="field"><span>Model</span><input value={draft.director_model} placeholder="Use the configured model" onChange={e=>change('director_model',e.target.value)}/></label>}
      <div className="col"><span className="small muted">Components in this scene</span>{scene?.elements.map((el,i)=><button className="btn sm" key={i} onClick={()=>onElement(i)}>{String(el.type).replace(/_/g,' ')}{el.text?` · ${String(el.text).slice(0,40)}`:''}</button>)}{!scene?.elements.length&&<span className="small muted">No added components. Add one from Elements.</span>}</div>
      <button className="btn primary" onClick={()=>run('rebuild')}>Rebuild this scene</button>
      <button className="btn ghost sm" onClick={()=>setDocument(JSON.stringify(scene,null,2))}>Edit complete scene instructions</button>
    </>}
    {section==='picture'&&<>
      {field('picture_prompt','What should the picture show?',300)}
      {select('picture_recipe','Picture model',[{id:'',label:'Use my picture settings'},...info.pictures])}
      <button className="btn primary" onClick={()=>run('picture')}>Generate a new picture</button>
      <p className="small muted">Replaces this scene’s background. Earlier versions stay in Pictures.</p>
    </>}
    {section==='video'&&<>
      {select('source_image','Starting picture',[{id:'',label:'Choose a picture'},...(r.project.data?.media??[]).filter(m=>m.kind==='image').map(m=>({id:m.id,label:m.caption||m.id}))])}
      {field('video_prompt','How should it move?',600)}
      {select('video_workflow','Video model',info.videos)}
      <button className="btn primary" onClick={()=>run('video')} disabled={!draft.source_image||!draft.video_prompt.trim()}>Generate a new video</button>
    </>}
    {section==='voice'&&<>
      {field('narration','Words to speak',600)}
      <label className="field"><span>Voice engine</span><select value={draft.voice_engine} onChange={e=>{const next=voices.data?.find(x=>x.id===e.target.value);setDraft({...draft,voice_engine:e.target.value,voice:next?.voices?.find((v:any)=>v.lang==='en')?.id||next?.voices?.[0]?.id||''});}}>{(voices.data??[]).map(e=><option key={e.id} value={e.id}>{e.label}</option>)}</select></label>
      {select('voice','Voice',(engine?.voices??[]).map((v:any)=>({id:v.id,label:v.label})))}
      <button className="btn primary" disabled={!draft.voice||!draft.narration.trim()} onClick={()=>run('voice')}>Regenerate this scene’s voice</button>
      <p className="small muted">Updates the voice and caption wording, keeping the scene length. If the words will not fit naturally, shorten the line or extend the scene.</p>
      <button className="btn ghost sm" onClick={async()=>{try{await post(`${base}/direction/voice/undo`);await r.reloadAll();toast('Voice and captions restored','ok');}catch(e:any){setError(e.message);}}}>Undo voice replacement</button>
    </>}
    {section==='history'&&<>
      <h4>Recorded generation details</h4>
      {Object.keys(info.original_voice).length>0&&<p className="small">Original voice: {info.original_voice.engine} · {info.original_voice.voice}</p>}
      {!info.history.length&&<p className="small muted">No generation record was saved for this scene’s media.</p>}
      {info.history.slice().reverse().map((item,i)=><details key={i}><summary>{item.kind} · {item.model_label||item.workflow||item.engine||'Model not recorded'}</summary><p className="small">{item.prompt}</p><p className="small muted">{item.voice||item.models?.join(', ')}{item.seed!=null?` · Seed ${item.seed}`:''}</p></details>)}
      {(info.source_script||info.source_plan||info.source_notes.length>0)&&<details><summary>Original director’s plan</summary><pre className="direction-source">{JSON.stringify(info.source_script||info.source_plan||info.source_notes,null,2)}</pre></details>}
    </>}
    </fieldset>
    {busy&&<p className="row small" role="status"><Spinner/>{job?'Generating this scene…':'Saving instructions…'}</p>}
    {dirty&&!busy&&<div className="row wrap"><button className="btn" onClick={async()=>{setBusy(true);try{await save();toast('Direction saved','ok');setError('');}catch(e:any){setError(e.message);}finally{setBusy(false);}}}>Save instructions</button><button className="btn ghost sm" onClick={async()=>{try{const fresh=await get<Info>(`${base}/direction`);recovery?.save(base,null);setInfo(fresh);setDraft(fresh.direction);setError('');setRecovered(false);}catch(e:any){setError(e.message);}}}>Reload saved version</button></div>}
    {document!==null&&<Modal title="Complete scene instructions" onClose={()=>setDocument(null)} wide footer={<button className="btn primary" onClick={async()=>{try{const parsed=JSON.parse(document);if(parsed.id!==sid)throw new Error('Keep this scene’s id unchanged.');await r.patchScene(sid,parsed);setDocument(null);}catch(e:any){toast(e.message,'err');}}}>Apply scene changes</button>}><p className="small muted">The editable scene document includes components, character actions, camera, timing, and media references. Invalid changes are rejected before saving.</p><textarea aria-label="Complete scene instructions" rows={18} className="direction-source" value={document} onChange={e=>setDocument(e.target.value)}/></Modal>}
  </div>;
}
