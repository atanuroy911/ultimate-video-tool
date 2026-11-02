import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Search, Plus, Eye } from "lucide-react";
import { Modal } from "../ui";
import ElementExample from "./ElementExample";
import type { Catalogue, ComponentSpec } from "../types";

function Sample({spec}: {spec:ComponentSpec}) {
  const category=spec.category, kind=spec.type;
  return <div className={`component-sample sample-${kind}`} aria-hidden="true">
    {category === "Numbers & charts" ? <svg viewBox="0 0 120 60"><rect x="22" y="32" width="18" height="20" rx="3"/><rect x="51" y="19" width="18" height="33" rx="3"/><rect x="80" y="6" width="18" height="46" rx="3"/></svg>
      : category === "Lists & diagrams" ? <svg viewBox="0 0 120 60"><path d="M30 30H90" stroke="currentColor" strokeWidth="3"/><rect x="6" y="16" width="30" height="28" rx="6"/><rect x="45" y="16" width="30" height="28" rx="6"/><rect x="84" y="16" width="30" height="28" rx="6"/></svg>
      : category === "Shapes" ? <svg viewBox="0 0 120 60"><rect x="12" y="14" width="40" height="36" rx="8"/><circle cx="86" cy="32" r="21"/></svg>
      : category === "Pictures & characters" ? <span>{kind === "sticker" ? "✦" : kind === "cartoon" || kind === "speaker_card" ? "☺" : "▧"}</span>
      : <span>{kind === "quote" ? "“Your words”" : kind === "question" ? "What if?" : kind === "cta" ? "Start here →" : "Your story"}</span>}
  </div>;
}

export default function ComponentLibrary({catalogue,onAdd,disabled,reason}: {
  catalogue:Catalogue|null; onAdd:(spec:ComponentSpec)=>void; disabled?:boolean; reason?:string;
}) {
  const [query,setQuery]=useState(""); const [category,setCategory]=useState("All");
  const [example,setExample]=useState<ComponentSpec|null>(null);
  const [hover,setHover]=useState<{spec:ComponentSpec;left:number;top:number}|null>(null);
  const timer=useRef(0);
  const hide=()=>{window.clearTimeout(timer.current);setHover(null);};
  useEffect(()=>{const close=()=>hide();window.addEventListener("scroll",close,true);window.addEventListener("resize",close);return()=>{window.clearTimeout(timer.current);window.removeEventListener("scroll",close,true);window.removeEventListener("resize",close);};},[]);
  const show=(spec:ComponentSpec,target:HTMLElement)=>{hide();const b=target.getBoundingClientRect();timer.current=window.setTimeout(()=>setHover({spec,left:Math.max(8,Math.min(b.right+12,window.innerWidth-290)),top:Math.max(8,Math.min(b.top,window.innerHeight-345))}),300);};
  const categories=useMemo(()=>["All",...new Set(catalogue?.elements.map(s=>s.category || "More") ?? [])],[catalogue]);
  const choices=(catalogue?.elements ?? []).filter(s=>(category === "All" || s.category === category) &&
    `${s.name} ${s.type} ${s.category} ${s.use_when}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="component-library">
    <label className="component-search"><Search size={16}/><input type="search" aria-label="Search elements" placeholder="Search text, shapes, charts…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
    <div className="component-categories" role="group" aria-label="Element categories">{categories.map(c=><button key={c} className={c===category?"on":""} aria-pressed={c===category} onClick={()=>setCategory(c)}>{c}</button>)}</div>
    <p className="small muted">Hover for an animated example, or tap Preview. Add it, then make it yours in Details.</p>
    {reason && <p className="banner small" role="status">{reason}</p>}
    {!catalogue ? <p role="status">Loading elements…</p> : !choices.length ? <p role="status">No matches. Try another word or choose All.</p> :
      <div className="component-grid">{choices.map(spec=><div key={spec.type} className="component-card" onMouseEnter={e=>show(spec,e.currentTarget)} onMouseLeave={hide}>
        <button className="component-add" disabled={disabled} onClick={()=>{hide();onAdd(spec);}} onFocus={e=>show(spec,e.currentTarget)} onBlur={hide} aria-label={`Add ${spec.name || spec.type}`}>
          <Sample spec={spec}/><span className="component-name">{spec.name || spec.type.replace(/_/g," ")}<Plus size={14}/></span>
        </button><button className="component-preview-btn" aria-label={`Preview ${spec.name || spec.type}`} onClick={()=>{hide();setExample(spec);}}><Eye size={12}/> Preview</button>
      </div>)}</div>}
    {hover && createPortal(<div role="tooltip" className="component-hover" style={{left:hover.left,top:hover.top}}><strong>{hover.spec.name}</strong><ElementExample key={hover.spec.type} kind={hover.spec.type}/><p>{hover.spec.use_when}</p></div>,document.body)}
    {example && <Modal title={example.name || example.type} onClose={()=>setExample(null)} footer={<button className="btn primary" disabled={disabled} onClick={()=>{onAdd(example);setExample(null);}}>Add to scene</button>}><div className="component-demo"><ElementExample kind={example.type}/><p>{example.use_when}</p><p className="small muted">Starter text and numbers are examples. Replace them with your content.</p></div></Modal>}
  </div>;
}
