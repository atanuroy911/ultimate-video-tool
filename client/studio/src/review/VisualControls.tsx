import type { El } from "../types";
import TimeRangeFields from "./TimeRangeFields";
import TransformControls from "./TransformControls.tsx";
import { repositionMotion } from "./motionMath";
import { measuredFor, useHandleMode } from "./transformUi";
const PLACING=["x","y","scale","rotation","transform"];
export default function VisualControls({value,start,end,total,onChange,section,at}:{section?:"position"|"timing";value:El;start:number;end:number;total:number;onChange:(v:El)=>void;at?:{scene:string;index:number}}) {
  // the first placing edit of an element automatic layout put there takes it over where it is and at the size it is (as a drag does), then applies the edit
  const takeover=(patch:Record<string,any>)=>{
    const m=at?measuredFor(at.scene,at.index):null;
    if(!m||m.free||!PLACING.some(k=>k in patch))return {};
    return {...(value.x==null&&m.cx!=null?{x:Math.round(m.cx*1e4)/1e4}:{}),...(value.y==null&&m.cy!=null?{y:Math.round(m.cy*1e4)/1e4}:{}),...(!("scale" in patch)&&(value.scale??1)===1&&m.fit!=null?{scale:m.fit}:{})};
  };
  const edit=(patch:Record<string,any>)=>onChange({...value,start:value.start??start,end:value.end??end,...repositionMotion(value,{...takeover(patch),...patch},.45)});
  const [mode,setMode]=useHandleMode();
  return <div className="col visual-controls">
    {section!=="position"&&<><TimeRangeFields start={value.start??start} end={value.end??end} total={total} label="Visual" onChange={edit}/>
    </>}
    {section!=="timing"&&<TransformControls value={value} bounds={{start:value.start??start,end:value.end??end}} patch={edit} pinning={mode==="warp"} onPin={on=>setMode(on?"warp":"move")}/>}
    <button className="btn ghost sm" onClick={()=>onChange({...value,start:null,end:null,x:null,y:null,scale:1,rotation:0,opacity:1,transform:null,keyframes:[]})}>Reset timing, position & motion</button>
  </div>;
}
