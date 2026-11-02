export default function TimeRangeFields({start,end,total,onChange,label="Clip",fixedStart=false,fixedEnd=false}:{start:number;end:number;total:number;onChange:(range:{start:number;end:number})=>void;label?:string;fixedStart?:boolean;fixedEnd?:boolean}) {
  return <div className="ed-time-fields">{(["start","end"] as const).map(side=><label key={side}>{side==="start"?"Start":"End"} (seconds)
    <input key={`${side}-${start}-${end}`} aria-label={`${label} ${side}`} readOnly={side==="start"?fixedStart:fixedEnd} title={(side==="start"?fixedStart:fixedEnd)?"This edge follows the video length. Trim the voice track to change it.":undefined} type="number" step={.001} min={side==="start"?0:start+.02} max={side==="start"?end-.02:total} defaultValue={(side==="start"?start:end).toFixed(3)}
      onKeyDown={e=>{if(e.key==="Enter") e.currentTarget.blur();}}
      onBlur={e=>{const v=Number(e.currentTarget.value);if(!e.currentTarget.value.trim() || !Number.isFinite(v)) {e.currentTarget.value=(side==="start"?start:end).toFixed(3);return;}
        const next={start,end,[side]:Math.max(side==="start"?0:start+.02,Math.min(v,side==="start"?end-.02:total))};
        e.currentTarget.value=next[side].toFixed(3);if(next.start!==start || next.end!==end) onChange(next);}}/>
  </label>)}</div>;
}
