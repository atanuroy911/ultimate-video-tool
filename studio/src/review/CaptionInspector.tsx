import type { Word } from "../types";
import type { Review } from "./useReview";
import { clearPreview, previewWord } from "./previewEdits";
import TimeRangeFields from "./TimeRangeFields";

/** Keep the canvas visible while editing the words it displays. */
export default function CaptionInspector({word,r,total,seek}:{word:Word;r:Review;total:number;seek:(time:number)=>void}) {
  const start=word.caption_start??word.start, end=word.caption_end??word.end;
  return <div className="col" style={{padding:14,gap:14}}>
    <label className="field">Caption text
      <input key={word.id+word.text} aria-label="Caption text" autoFocus defaultValue={word.text}
        onFocus={e=>e.currentTarget.select()}
        onChange={e=>previewWord(word.id,start,end,e.currentTarget.value)}
        onBlur={e=>{const text=e.currentTarget.value.trim();if(text && text!==word.text) r.editWord(word.id,{text});else {e.currentTarget.value=word.text;clearPreview();}}}
        onKeyDown={e=>{if(e.key==="Enter") {e.preventDefault();e.currentTarget.blur();} if(e.key==="Escape") {e.stopPropagation();e.currentTarget.value=word.text;clearPreview();e.currentTarget.blur();}}}/>
    </label>
    <p className="small muted" style={{margin:0}}>See your text change as you type. Press Enter or click away to save. Escape cancels the text draft.</p>
    <TimeRangeFields label="Caption" start={start} end={end} total={total} onChange={range=>r.editWord(word.id,range)}/>
    <button className="btn" onClick={()=>seek(Math.min(total,start+Math.min(.1,(end-start)/2)))}>Show this word</button>
    <button className="btn" onClick={()=>r.editWord(word.id,{reset_timing:true})}>Match the spoken word again</button>
    <button className="btn" onClick={()=>r.editWord(word.id,{cut:!word.cut})}>{word.cut?"Show caption":"Hide caption"}</button>
    <p className="small muted" style={{margin:0}}>These changes affect the words on screen. The recorded voice stays in place.</p>
  </div>;
}
