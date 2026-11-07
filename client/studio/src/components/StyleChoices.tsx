import { Check } from "lucide-react";
import { useT } from "../i18n";
import type { VideoStyle } from "../types";
import { STYLE_DEFINITIONS } from "../pages/StyleThumbnails";

/** One visual style catalogue for new videos and directing an existing video again. */
export default function StyleChoices({value,onChange,onShortcut}:{value:string;onChange:(v:VideoStyle)=>void;onShortcut?:(pick:()=>void)=>string}) {
 const t=useT();
 return <div className="style-cards-grid" role="radiogroup" aria-label="Style">{STYLE_DEFINITIONS.map(def=>{
  const letter=onShortcut?.(()=>onChange(def.value)),selected=value===def.value;
  return <button key={def.value} type="button" role="radio" aria-checked={selected} className={`style-card ${selected?"sel":""}`} onClick={()=>onChange(def.value)}>
   <div className="style-card-head">{letter&&<span className="style-card-kbd">{letter}</span>}<span className="style-card-badge">{def.badge}</span>{selected&&<Check size={16} className="style-card-check"/>}</div>
   <div className="style-card-thumb">{def.thumbnail}</div>
   <div className="style-card-title"><span>{t(def.titleKey)}</span></div><div className="style-card-about">{t(def.aboutKey)}</div>
   <div className="style-card-details"><div className="style-card-detail-item"><strong>Best for:</strong><span>{def.idealFor}</span></div><div className="style-card-detail-item"><strong>Visuals:</strong><span>{def.howItWorks}</span></div></div>
  </button>;
 })}</div>;
}
