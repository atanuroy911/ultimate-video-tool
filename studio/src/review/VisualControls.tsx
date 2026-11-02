import type { El } from "../types";
import TimeRangeFields from "./TimeRangeFields";
export default function VisualControls({value,start,end,total,onChange}:{value:El;start:number;end:number;total:number;onChange:(v:El)=>void}) {
  const edit=(patch:Record<string,any>)=>onChange({...value,start:value.start??start,end:value.end??end,...patch});
  return <div className="col visual-controls">
    <h3>Timing</h3><TimeRangeFields start={value.start??start} end={value.end??end} total={total} label="Visual" onChange={edit}/>
    <span className="small muted">Move or trim this visual freely, including across scene changes.</span>
    <h3>Position & appearance</h3>
    {([ ["x","Left ↔ right",.5,0,1,.01], ["y","Top ↔ bottom",.45,0,1,.01], ["scale","Size",1,.05,3,.01], ["rotation","Rotation",0,-180,180,1], ["opacity","Opacity",1,0,1,.01] ] as const).map(([key,label,fallback,min,max,step])=>
      <label key={key} className="field"><span>{label} · {key==="rotation"?`${value[key]??fallback}°`:`${Math.round((value[key]??fallback)*100)}%`}</span><input aria-label={label} type="range" min={min} max={max} step={step} value={value[key]??fallback} onChange={e=>edit({[key]:Number(e.target.value)})}/></label>)}
    <button className="btn ghost sm" onClick={()=>onChange({...value,start:null,end:null,x:null,y:null,scale:1,rotation:0,opacity:1})}>Reset to generated timing & layout</button>
  </div>;
}
