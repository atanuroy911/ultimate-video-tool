import { Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { post } from "../api";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Spinner } from "../ui";
import StyleChoices from "./StyleChoices";
import { DirectorChoices, type OptionsCtx } from "../pages/NewOptions";

export interface RedoModalProps {
  id: string;
  title?: string;
  open: boolean;
  onClose: () => void;
  defaultScope?: "plan" | "preprocess";
}

export default function RedoModal({ id, title, open, onClose, defaultScope = "plan" }: RedoModalProps) {
  const nav = useNavigate();
  const directors = useFetch<{directors:OptionsCtx["directors"]}>(open ? "/api/directors" : null);
  const project = useFetch<{video_kind:string;options:{look?:string;director?:string}}>(open ? `/api/projects/${id}` : null);
  const [director,setDirector]=useState("best"),[style,setStyle]=useState("auto");
  const [scope,setScope]=useState<"plan"|"preprocess">(defaultScope);
  const [exportAfter,setExportAfter]=useState(true),[busy,setBusy]=useState(false);
  useEffect(()=>{
    if(!project.data) return;
    setDirector(project.data.options.director || "best");
    const look=project.data.options.look;
    setStyle(look==="story"||look==="reel"?look:project.data.video_kind || "auto");
  },[project.data]);
  useEffect(()=>{if(open){setScope(defaultScope);setBusy(false);}},[open,defaultScope]);
  useEffect(()=>{
    if(!open) return;
    const key=(e:KeyboardEvent)=>{if(e.key==="Escape"&&!busy)onClose();};
    window.addEventListener("keydown",key);return()=>window.removeEventListener("keydown",key);
  },[open,busy,onClose]);
  if(!open) return null;
  const run=async()=>{
    setBusy(true);
    try {
      await post(`/api/projects/${id}/run`,{from_stage:scope,force:true,rerender:exportAfter,director,video_kind:style});
      toast("The director is making a new cut.","ok");onClose();nav(`/p/${id}/progress`);
    }catch(e:any){toast(e.message || "Could not start. Try again.","err");setBusy(false);}
  };
  return <div className="modal-back" onClick={e=>e.target===e.currentTarget&&!busy&&onClose()}>
    <div className="modal" style={{maxWidth:820}} role="dialog" aria-modal="true" aria-labelledby="redo-title">
      <div className="modal-head">
        <div className="col grow"><strong id="redo-title">Direct again</strong>{title&&<span className="small muted">{title}</span>}</div>
        <button className="btn icon ghost" aria-label="Close" disabled={busy} onClick={onClose}><X size={16}/></button>
      </div>
      <div className="modal-body col">
        <p>Choose who directs this video and how it is drawn. Your original recording stays available.</p>
        <fieldset disabled={busy} style={{border:0,padding:0,margin:0,minWidth:0}}>
          <legend>Director</legend>
          {directors.error ? <div role="alert">{directors.error}<button className="btn" onClick={directors.refetch}>Try again</button></div> :
           directors.loading ? <Spinner/> : <DirectorChoices value={director} onChange={setDirector} directors={directors.data?.directors || []}/>}
          <p className="small muted">Models are chosen in <Link to="/settings?s=directors">Settings, Directors</Link>.</p>
          <h3>Style</h3><StyleChoices value={style} onChange={setStyle}/>
          <h3>Where to start</h3>
          <label className="row"><input type="radio" name="redo-scope" checked={scope==="plan"} onChange={()=>setScope("plan")}/>Direct the scenes again, keeping the sound and cuts</label>
          <label className="row"><input type="radio" name="redo-scope" checked={scope==="preprocess"} onChange={()=>setScope("preprocess")}/>Start again from the sound</label>
          <label className="row"><input type="checkbox" checked={exportAfter} onChange={e=>setExportAfter(e.target.checked)}/>Export the finished video automatically</label>
        </fieldset>
      </div>
      <div className="modal-foot">
        <button className="btn ghost" disabled={busy} onClick={onClose}>Cancel</button>
        <button className="btn primary" disabled={busy||directors.loading||!!directors.error} onClick={run}>{busy?<Spinner/>:<Sparkles size={15}/>}Direct again</button>
      </div>
    </div>
  </div>;
}
