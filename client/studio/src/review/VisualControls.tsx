import type { El } from "../types";
import TimeRangeFields from "./TimeRangeFields";
import TransformControls from "./TransformControls.tsx";
import { repositionMotion } from "./motionMath";
import { useHandleMode } from "./transformUi";
export default function VisualControls({value,start,end,total,onChange,section}:{section?:"position"|"timing";value:El;start:number;end:number;total:number;onChange:(v:El)=>void}) {
  const edit=(patch:Record<string,any>)=>onChange({...value,start:value.start??start,end:value.end??end,...repositionMotion(value,patch,.45)});
  const [mode,setMode]=useHandleMode();
  return <div className="col visual-controls">
    {section!=="position"&&<><TimeRangeFields start={value.start??start} end={value.end??end} total={total} label="Visual" onChange={edit}/>
    </>}
    {section!=="timing"&&<TransformControls value={value} bounds={{start:value.start??start,end:value.end??end}} patch={edit} pinning={mode==="warp"} onPin={on=>setMode(on?"warp":"move")}/>}
    <button className="btn ghost sm" onClick={()=>onChange({...value,start:null,end:null,x:null,y:null,scale:1,rotation:0,opacity:1,transform:null,keyframes:[]})}>Reset timing, position & motion</button>
  </div>;
}
