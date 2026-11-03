import { useState } from "react";
import { Check, Plus, Users, X } from "lucide-react";
import { del, post } from "../api";
import { Modal } from "../ui";
import { platformNames, platformMark, type Account, type Group } from "./types";

const fields:Record<string,{key:string;label:string;secret?:boolean;optional?:boolean}[]>={
  youtube:[{key:'access_token',label:'Access token',secret:true},{key:'client_id',label:'App ID',optional:true},{key:'client_secret',label:'App secret',secret:true,optional:true},{key:'refresh_token',label:'Refresh token',secret:true,optional:true}],
  facebook:[{key:'page_id',label:'Page ID'},{key:'access_token',label:'Page access token',secret:true}],
  instagram:[{key:'ig_user_id',label:'Instagram business account ID'},{key:'access_token',label:'Access token',secret:true}],
  tiktok:[{key:'access_token',label:'Access token',secret:true}],mock:[],
};
export default function Accounts({accounts,groups,onChange}:{accounts:Account[];groups:Group[];onChange:()=>void}) {
  const [platform,setPlatform]=useState<string|null>(null),[name,setName]=useState(''),[handle,setHandle]=useState(''),[values,setValues]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[groupOpen,setGroupOpen]=useState(false),[groupName,setGroupName]=useState(''),[members,setMembers]=useState<string[]>([]);
  const [remove,setRemove]=useState<{id:string;name:string;kind:'account'|'group'}|null>(null),[meta,setMeta]=useState(false);
  const live=accounts.filter(a=>a.active);
  const choose=(p:string)=>{setPlatform(p);setName('');setHandle('');setValues({});setError('');setMeta(false);};
  async function act(fn:()=>Promise<unknown>,done?:()=>void){setBusy(true);setError('');try{await fn();done?.();onChange();}catch(e:any){setError(e.message||'Could not save. Try again.');}finally{setBusy(false);}}
  const connect=()=>act(()=>meta?post('/api/social/accounts/meta/exchange',{app_id:values.app_id,app_secret:values.app_secret,user_token:values.user_token}):post(`/api/social/accounts/connect/${platform}`,{platform,name:name.trim(),handle:handle.trim(),credentials:values}),()=>{setPlatform(null);setValues({});});
  const shown=meta?[{key:'app_id',label:'Meta app ID'},{key:'app_secret',label:'Meta app secret',secret:true},{key:'user_token',label:'User access token',secret:true}]:fields[platform||'mock'];
  const valid=(meta||!!name.trim())&&shown.filter(f=>!('optional'in f&&f.optional)).every(f=>!!values[f.key]?.trim());
  return <div className="accounts-workspace">
    <section className="col"><div className="row wrap"><h2 className="grow">Your accounts</h2><span className="small muted">{live.length} saved</span></div>
      {live.length?<div className="account-grid">{live.map(a=><article className="account-card" key={a.id}><span className={`platform-mark platform-${a.platform}`}>{platformMark[a.platform]}</span><div className="grow"><strong>{a.name}</strong><span className="small muted">{platformNames[a.platform]}{a.handle?` · ${a.handle}`:''}</span><span className="small">{a.platform==='mock'?'Practice only · never posts online':'Available for publishing'}</span></div><button className="btn ghost icon sm" aria-label={`Disconnect ${a.name}`} onClick={()=>setRemove({id:a.id,name:a.name,kind:'account'})}><X size={15}/></button></article>)}</div>:<div className="quiet-empty"><strong>Your channels, together</strong><p>Choose a platform below to add your first account.</p></div>}
      <h3>Add an account</h3><div className="platform-grid">{['youtube','instagram','facebook','tiktok'].map(p=><button className="platform-choice" key={p} onClick={()=>choose(p)}><span className={`platform-mark platform-${p}`}>{platformMark[p]}</span><strong>{platformNames[p]}</strong><Plus size={16}/></button>)}</div>
      <button className="btn ghost sm self-start" onClick={()=>choose('mock')}>Try a practice channel</button>
    </section>
    <section className="col account-groups"><div className="row wrap"><div className="grow"><h2>Saved groups</h2><span className="small muted">A shortcut for accounts you often post to together.</span></div><button className="btn sm" disabled={!live.length} onClick={()=>{setGroupOpen(true);setError('');}}><Plus size={14}/> New group</button></div>
      {!groups.length?<p className="small muted">Choose accounts directly when posting, or save a group here.</p>:groups.map(g=><div className="account-card" key={g.id}><Users size={20}/><div className="grow"><strong>{g.name}</strong><span className="small muted">{g.accounts.filter(a=>a.active).map(a=>a.name).join(', ')||'No accounts'}</span></div><button className="btn ghost icon sm" aria-label={`Remove ${g.name}`} onClick={()=>setRemove({id:g.id,name:g.name,kind:'group'})}><X size={15}/></button></div>)}
    </section>
    {platform&&<Modal title={`Add ${platformNames[platform]}`} onClose={()=>!busy&&setPlatform(null)} footer={<><button className="btn" disabled={busy} onClick={()=>setPlatform(null)}>Cancel</button><button className="btn primary" disabled={busy||!valid} onClick={connect}>{busy?'Saving…':meta?'Import accounts':'Save account'}</button></>}>
      <div className="col">{(platform==='facebook'||platform==='instagram')&&<div className="workflow-tabs compact"><button aria-pressed={!meta} className={!meta?'selected':''} onClick={()=>setMeta(false)}>One account</button><button aria-pressed={meta} className={meta?'selected':''} onClick={()=>setMeta(true)}>Import managed Pages</button></div>}
        {!meta&&<><label className="field">Account name<input value={name} onChange={e=>setName(e.target.value)} placeholder="A name you recognise" autoFocus/></label><label className="field">Handle <span className="small muted">Optional</span><input value={handle} onChange={e=>setHandle(e.target.value)} placeholder="@yourchannel"/></label></>}
        {platform==='mock'?<p className="small muted">Practice the complete posting flow. Nothing is sent to a social platform.</p>:<p className="small muted">Use the publishing credentials from your platform’s developer dashboard. They stay on your server.</p>}
        {shown.filter(f=>!('optional'in f&&f.optional)).map(f=><label className="field" key={f.key}>{f.label}<input type={f.secret?'password':'text'} autoComplete="off" value={values[f.key]||''} onChange={e=>setValues(v=>({...v,[f.key]:e.target.value}))}/></label>)}
        {!meta&&platform==='youtube'&&<details><summary>Keep access up to date automatically</summary><div className="col">{fields.youtube.filter(f=>f.optional).map(f=><label className="field" key={f.key}>{f.label}<input type={f.secret?'password':'text'} autoComplete="off" value={values[f.key]||''} onChange={e=>setValues(v=>({...v,[f.key]:e.target.value}))}/></label>)}</div></details>}
        {error&&<div className="banner err" role="alert">{error}</div>}
      </div></Modal>}
    {groupOpen&&<Modal title="New account group" onClose={()=>!busy&&setGroupOpen(false)} footer={<button className="btn primary" disabled={busy||!groupName.trim()||!members.length} onClick={()=>act(()=>post('/api/social/groups',{name:groupName,account_ids:members}),()=>{setGroupOpen(false);setGroupName('');setMembers([]);})}>Save group</button>}><div className="col"><label className="field">Group name<input value={groupName} onChange={e=>setGroupName(e.target.value)} placeholder="For example, My channels"/></label>{live.map(a=><label className="account-card" key={a.id}><input type="checkbox" checked={members.includes(a.id)} onChange={()=>setMembers(ids=>ids.includes(a.id)?ids.filter(id=>id!==a.id):[...ids,a.id])}/><span className="grow">{a.name}</span><span className="small muted">{platformNames[a.platform]}</span></label>)}{error&&<p role="alert">{error}</p>}</div></Modal>}
    {remove&&<Modal title={`${remove.kind==='account'?'Disconnect':'Remove'} ${remove.name}?`} onClose={()=>!busy&&setRemove(null)} footer={<><button className="btn" disabled={busy} onClick={()=>setRemove(null)}>Keep it</button><button className="btn danger" disabled={busy} onClick={()=>act(()=>remove.kind==='account'?del(`/api/social/accounts/${remove.id}`):del(`/api/social/groups/${remove.id}`),()=>setRemove(null))}>{remove.kind==='account'?'Disconnect':'Remove group'}</button></>}><p>{remove.kind==='account'?'You can add this account again. Existing posts stay online.':'The accounts stay connected.'}</p>{error&&<p role="alert">{error}</p>}</Modal>}
  </div>;
}
