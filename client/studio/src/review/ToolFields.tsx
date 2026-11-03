import { useState } from "react";

type Schema = Record<string, any>;
export function concrete(schema: Schema, defs: Schema): Schema {
  if (schema.$ref) return concrete(defs[schema.$ref.split("/").pop()] ?? {}, defs);
  if (schema.anyOf) return {...concrete(schema.anyOf.find((s: Schema)=>s.type!=="null") ?? {},defs), ...Object.fromEntries(Object.entries(schema).filter(([k])=>k!=="anyOf"))};
  return schema;
}
export function defaults(schema: Schema, defs: Schema): any {
  const s=concrete(schema,defs);
  if(s.default!==undefined) return structuredClone(s.default);
  if(s.type==="object") return Object.fromEntries(Object.entries(s.properties??{}).filter(([,p])=>(p as Schema).default!==undefined).map(([k,p])=>[k,defaults(p as Schema,defs)]));
  return undefined;
}
const label=(s:string)=>s.replace(/_/g," ").replace(/^./,c=>c.toUpperCase());

/** Shared contracts become ordinary labeled controls; no JSON knowledge required. */
export default function ToolFields({schema,defs={},value,onChange,path="Options",depth=0}:{schema:Schema;defs?:Schema;value:any;onChange:(v:any)=>void;path?:string;depth?:number}) {
  const [newKey,setNewKey]=useState("");
  const [newType,setNewType]=useState("string");
  const s=concrete(schema,defs), title=depth===0?"Options":s.title||label(path.split(".").pop()||path);
  const help=s.description && <span className="small muted">{s.description}</span>;
  if(depth>12) return <p className="small muted">This nested value is too deep to edit here.</p>;
  if(s.enum) return <label className="field"><span>{title}</span><select aria-label={path} value={value??""} onChange={e=>onChange(s.enum.find((v:any)=>String(v)===e.target.value))}><option value="" disabled>Choose…</option>{s.enum.map((v:any)=><option key={String(v)} value={String(v)}>{label(String(v))}</option>)}</select>{help}</label>;
  if(s.type==="boolean") return <label className="field"><span><input type="checkbox" checked={value??s.default??false} onChange={e=>onChange(e.target.checked)}/> {title}</span>{help}</label>;
  if(s.type==="number"||s.type==="integer") return <label className="field"><span>{title}</span><input aria-label={path} type="number" step={s.type==="integer"?1:"any"} min={s.minimum} max={s.maximum} value={value??""} onChange={e=>onChange(e.target.value===""?undefined:Number(e.target.value))}/>{help}</label>;
  if(s.type==="array") return <fieldset className="tool-fields"><legend>{title}</legend>{help}{(value??[]).map((item:any,i:number)=><div className="tool-item" key={i}><ToolFields schema={s.items??{type:"string"}} defs={defs} value={item} path={`${path}.${i+1}`} depth={depth+1} onChange={v=>onChange(value.map((x:any,j:number)=>j===i?v:x))}/><button type="button" className="btn sm ghost" onClick={()=>onChange(value.filter((_:any,j:number)=>j!==i))}>Remove item {i+1}</button></div>)}<button type="button" className="btn sm" onClick={()=>onChange([...(value??[]),defaults(s.items??{},defs)??(concrete(s.items??{},defs).type==="object"?{}:"")])}>Add item</button></fieldset>;
  if(s.type==="object") {
    const fields=s.properties??{}, custom=Object.keys(value??{}).filter(k=>!fields[k]);
    return <fieldset className="tool-fields"><legend>{title}</legend>{help}{Object.entries(fields).map(([k,field])=><ToolFields key={k} schema={{...(field as Schema),title:`${(field as Schema).title||label(k)}${s.required?.includes(k)?" *":""}`}} defs={defs} value={value?.[k]} path={`${path}.${k}`} depth={depth+1} onChange={v=>onChange({...value,[k]:v})}/>)}{custom.map(k=><div className="tool-item" key={k}><ToolFields schema={typeof s.additionalProperties==="object"?s.additionalProperties:{type:typeof value[k]==="object"?(Array.isArray(value[k])?"array":"object"):typeof value[k]}} defs={defs} value={value[k]} path={`${path}.${k}`} depth={depth+1} onChange={v=>onChange({...value,[k]:v})}/><button type="button" className="btn sm ghost" onClick={()=>{const next={...value};delete next[k];onChange(next);}}>Remove {label(k)}</button></div>)}{s.additionalProperties!==false && !Object.keys(fields).length && <div className="row wrap"><input aria-label={`${path} new field name`} placeholder="Name of the detail" value={newKey} onChange={e=>setNewKey(e.target.value)}/><select aria-label={`${path} new detail type`} value={newType} onChange={e=>setNewType(e.target.value)}><option value="string">Text</option><option value="number">Number</option><option value="boolean">On / off</option><option value="object">Group of details</option><option value="array">List</option></select><button type="button" className="btn sm" disabled={!newKey.trim()||["__proto__","constructor","prototype"].includes(newKey.trim())} onClick={()=>{const shape=typeof s.additionalProperties==="object"?concrete(s.additionalProperties,defs):{type:newType};const initial=defaults(shape,defs)??({number:0,integer:0,boolean:false,object:{},array:[],string:""} as Record<string,any>)[shape.type]??"";onChange({...value,[newKey.trim()]:initial});setNewKey("");}}>Add detail</button></div>}</fieldset>;
  }
  return <label className="field"><span>{title}</span><textarea aria-label={path} rows={2} maxLength={s.maxLength} value={value??""} onChange={e=>onChange(e.target.value)}/>{help}</label>;
}
