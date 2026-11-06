import { useState } from "react";
import { Diamond, Plus, Trash2 } from "lucide-react";
import { timeStore } from "./timeStore";
import type { MotionPoint } from "../types";
import { sampleMotion } from "./motionMath";
import { Value } from "./TransformControls.tsx";
import { POINT_KEYS } from "./transformMath.ts";

type Pose = {x?:number|null;y?:number|null;scale?:number;rotation?:number;opacity?:number;keyframes?:MotionPoint[]};
export default function MotionEditor({value,start,end,onChange,seek}:{value:Pose;start:number;end:number;onChange:(frames:MotionPoint[])=>void;seek?:(t:number)=>void}) {
  const points=value.keyframes??[];
  const [selected,setSelected]=useState(0);
  const index=Math.min(selected,Math.max(0,points.length-1)), point=points[index];
  const pose=(time:number):MotionPoint=>({time,x:value.x??.5,y:value.y??.5,scale:value.scale??1,rotation:value.rotation??0,opacity:value.opacity??1,ease:"smooth"});
  const pick=(i:number)=>{setSelected(i);seek?.(points[i].time);};
  const patch=(data:Partial<MotionPoint>)=>onChange(points.map((p,i)=>i===index?{...p,...data}:p));
  function preset(name:string) {
    const a=pose(start),b=pose(end);
    if(name==="slide") a.x=Math.max(-.5,b.x-.35);
    if(name==="rise") {a.y=Math.min(1.5,b.y+.25);a.opacity=0;}
    if(name==="zoom") b.scale=Math.min(5,a.scale*1.25);
    if(name==="fade") a.opacity=0;
    onChange([a,b]);setSelected(0);seek?.(start);
  }
  function add() {
    const at=Math.round(Math.min(end,Math.max(start,timeStore.t))*1000)/1000;
    const existing=points.findIndex(p=>Math.abs(p.time-at)<.001);
    if(existing>=0) {pick(existing);return;}
    const next=[...points,sampleMotion(points,at,pose(at))].sort((a,b)=>a.time-b.time);
    onChange(next);setSelected(next.findIndex(p=>p.time===at));seek?.(at);
  }
  return <div className="col motion-editor">
    <div className="motion-presets" aria-label="Motion presets">{[["slide","Slide"],["rise","Rise"],["zoom","Zoom"],["fade","Fade"]].map(([id,label])=><button key={id} className={`motion-preset motion-${id}`} onClick={()=>preset(id)}><span aria-hidden="true">Aa</span>{label}</button>)}</div>
    <div className="row wrap"><button className="btn sm" onClick={add} disabled={points.length>=100}><Plus size={14}/>Save a point here</button>{points.length>0&&<button className="btn ghost sm" onClick={()=>onChange([])}>Clear motion</button>}</div>
    {!points.length&&<p className="small muted">Choose a move, or move the playhead and save a point.</p>}
    {!!points.length&&<>
      <div className="motion-points" aria-label="Animation points">{points.map((p,i)=><button key={i} className={`btn sm ${i===index?'primary':''}`} aria-pressed={i===index} onClick={()=>pick(i)}><Diamond size={12}/>{p.time.toFixed(2)}s</button>)}</div>
      <div className="row"><label className="field grow"><span>At video time</span><input type="number" aria-label="Animation point time" min={index>0?points[index-1].time+.001:-36000} max={index+1<points.length?points[index+1].time-.001:36000} step={.01} value={point.time} onChange={e=>{
        const t=Number(e.target.value);if(!Number.isFinite(t)||t< -36000||t>36000||index>0&&t<=points[index-1].time||index+1<points.length&&t>=points[index+1].time)return;
        patch({time:t});seek?.(t);
      }}/></label><button className="btn ghost icon" aria-label="Remove animation point" onClick={()=>{onChange(points.filter((_,i)=>i!==index));setSelected(Math.max(0,index-1));}}><Trash2 size={15}/></button></div>
      {([["x","Left ↔ right",-.5,1.5,100,"%"],["y","Top ↔ bottom",-.5,1.5,100,"%"],["scale","Size",.05,5,100,"%"],["rotation","Rotate",-360,360,1,"°"],["opacity","Opacity",0,1,100,"%"],
         ["stretch_x","Stretch across",.1,5,100,"%"],["stretch_y","Stretch up and down",.1,5,100,"%"],["skew_x","Slant sideways",-60,60,1,"°"],["skew_y","Slant up and down",-60,60,1,"°"],
         ["tilt_x","Lean back or forward",-80,80,1,"°"],["tilt_y","Turn left or right",-80,80,1,"°"],["blur","Blur",0,60,1,"px"]] as const).map(([key,label,min,max,shown,unit])=>
        <Value key={key} label={label} aria={`Motion ${label}`} value={(point as any)[key]??POINT_KEYS[key][2]} def={POINT_KEYS[key][2]} min={min} max={max} step={1} unit={unit} shown={shown} onChange={v=>{seek?.(point.time);patch({[key]:v});}}/>)}
      <label className="field"><span>Movement</span><select value={point.ease} onChange={e=>patch({ease:e.target.value as MotionPoint['ease']})}>{[["smooth","Smooth"],["linear","Steady"],["in","Speed up"],["out","Slow down"],["hold","Hold, then jump"]].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
    </>}
  </div>;
}
