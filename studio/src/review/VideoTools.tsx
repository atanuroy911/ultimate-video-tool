import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { get, post } from "../api";
import { Button, Sheet } from "../ds";
import { useFetch } from "../hooks";
import ToolFields, {defaults} from "./ToolFields";

interface Tool {id:string;plain_name:string;summary:string;cost:string;effects:string;toolboxes:string[];requires:string[];inputs?:Record<string,any>;when_to_use?:string;when_not_to_use?:string}
const groups:Record<string,string>={audio:"Voice & sound",voice:"Voices",asr:"Transcription",text:"Words & captions",timeline:"Editing",fill:"Visuals",gen:"AI pictures & clips",understand:"Find the story",direct:"Direction",plan:"Plan the video",cut:"Pacing",judge:"Quality checks",craft:"Quality checks",render:"Preview & export",publish:"Sharing",project:"Project & files",meta:"Utilities",pipeline:"Build the video",shorts:"Short clips"};
const costs:Record<string,string>={instant:"Almost instant",fast:"A few seconds",slow:"About a minute",heavy:"Can take several minutes"};
export default function VideoTools({id,onClose,onChanged}:{id:string;onClose:()=>void;onChanged:()=>void}) {
  const list=useFetch<Tool[]>("/api/modules");
  const [query,setQuery]=useState(""),[group,setGroup]=useState("");
  const [tool,setTool]=useState<Tool|null>(null),[values,setValues]=useState<Record<string,any>>({});
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[result,setResult]=useState<any>(null);
  const categories=useMemo(()=>[...new Set((list.data??[]).map(t=>groups[t.id.split(".")[0]]||"Other"))].sort(),[list.data]);
  const visible=(list.data??[]).filter(t=>(!group||(groups[t.id.split(".")[0]]||"Other")===group)&&query.toLowerCase().split(/\s+/).every(w=>(t.plain_name+" "+t.summary+" "+t.id).toLowerCase().includes(w)));
  async function choose(t:Tool) {setBusy(true);setError("");setResult(null);try {const detail=await get<Tool>(`/api/modules/${t.id}`);setTool(detail);setValues(defaults(detail.inputs!,detail.inputs!.$defs??{})??{});}catch(e:any){setError(e.message);}finally{setBusy(false);}}
  async function run(check:boolean) {if(!tool)return;setBusy(true);setError("");setResult(null);try {const r=await post(`/api/projects/${id}/modules/${tool.id}/call`,{inputs:values,dry_run:check,why:`Selected ${tool.plain_name.toLowerCase()} in Video tools.`});setResult(r);if(!check&&r.ok)onChanged();}catch(e:any){setError(e.message);}finally{setBusy(false);}}
  return <Sheet title="Video tools" onClose={onClose}>
    <p className="small muted">Everything the app can do, from the same catalogue your Director uses. Choose a task, set its options, then run it.</p>
    {(error||list.error)&&<div role="alert" className="banner err">{error||list.error}<Button size="sm" onClick={()=>list.refetch()}>Retry list</Button></div>}
    {tool?<><Button disabled={busy} onClick={()=>{setTool(null);setResult(null);}}>← All tools</Button><h3>{tool.plain_name}</h3><p>{tool.summary}</p><p className="small muted">{tool.when_to_use} · {costs[tool.cost]}</p>
      <span className="chip">{tool.toolboxes.includes("autonomous")?"Your Director can use this":"You choose when to use this"}</span>
      {tool.effects==="external_post"?<><p>Choose accounts, review the post and publish from Share videos.</p><Link to="/social" onClick={onClose}>Open Share videos</Link></>:tool.toolboxes.includes("studio")?<>
        <ToolFields schema={tool.inputs!} defs={tool.inputs!.$defs??{}} value={values} onChange={v=>{setValues(v);setResult(null);}}/>
        <div className="row wrap"><Button disabled={busy} onClick={()=>run(true)}>Check what’s needed</Button><Button variant="primary" disabled={busy} onClick={()=>run(false)}>{busy?"Working…":"Run this tool"}</Button></div>
        {result&&<div role="status" className={`banner ${result.ok?"ok":"warn"}`}><strong>{result.summary}</strong>{result.fix&&<p>{result.fix}</p>}{result.missing?.length>0&&<p>First prepare: {result.missing.map((x:string)=>x.replace(/\./g," ").replace(/_/g," ")).join(", ")}. These steps are in the tool list.</p>}{result.warnings?.map((w:string,i:number)=><p key={i}>{w}</p>)}{result.output!=null&&<ToolResult value={result.output}/>}</div>}
      </>:<p>This operation is available through a connected assistant. It is listed here so you can see the complete catalogue.</p>}
    </>:<><label className="field"><span>What do you want to do?</span><input autoFocus type="search" placeholder="Find repeated takes, check facts, add visuals…" value={query} onChange={e=>setQuery(e.target.value)}/></label><label className="field"><span>Category</span><select value={group} onChange={e=>setGroup(e.target.value)}><option value="">All categories</option>{categories.map(g=><option key={g}>{g}</option>)}</select></label><span className="small muted">{visible.length} tools</span>{list.loading&&<p role="status">Loading tools…</p>}{!list.loading&&!visible.length&&<p>No matching tools. Try a shorter phrase or another category.</p>}<div className="video-tool-list">{visible.map(t=><button key={t.id} className="video-tool-card" disabled={busy} onClick={()=>choose(t)}><strong>{t.plain_name}</strong><span>{t.summary}</span><small>{costs[t.cost]} · {t.toolboxes.includes("autonomous")?"Director ready":"You control this"}</small></button>)}</div></>}
  </Sheet>;
}
function ToolResult({value,depth=0}:{value:any;depth?:number}) {
  if(value==null)return null;
  if(typeof value!=="object")return <span>{String(value)}</span>;
  if(depth>5)return <span>More nested details are saved in the Director log.</span>;
  if(Array.isArray(value))return <ul>{value.slice(0,100).map((v,i)=><li key={i}><ToolResult value={v} depth={depth+1}/></li>)}{value.length>100&&<li>{value.length-100} more items in the Director log.</li>}</ul>;
  return <dl className="tool-result">{Object.entries(value).map(([k,v])=><div key={k}><dt>{k.replace(/_/g," ")}</dt><dd><ToolResult value={v} depth={depth+1}/></dd></div>)}</dl>;
}
