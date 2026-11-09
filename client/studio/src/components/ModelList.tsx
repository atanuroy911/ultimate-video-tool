import { Ban, Hourglass, Sparkles, Zap } from "lucide-react";
import { useState } from "react";

/* A model to download, marked against the graphics card it will run on. */
export interface ModelOption { id: string; label: string; note?: string; download_gb: number; fits: boolean; speed: string; recommended: boolean; why: string }

export function fitWords(x: ModelOption, cardGb: number) {
  return !x.fits ? x.why : x.speed === "fast" ? (cardGb ? `runs well on your ${cardGb} GB card` : "runs well here") : "works, but slowly";
}
export function FitIcon({ x }: { x: ModelOption }) {
  return !x.fits ? <Ban size={14} aria-hidden /> : x.speed === "fast" ? <Zap size={14} aria-hidden /> : <Hourglass size={14} aria-hidden />;
}

/* Every model that can be installed, marked against the card: runs well (lightning), works but slowly (hourglass), or does not fit (greyed, with why). */
export default function ModelList({ name, options, value, onChange, cardGb }: { name: string; options: ModelOption[]; value: string; onChange: (id: string) => void; cardGb: number }) {
  const [all, setAll] = useState(false);
  const good = options.filter((x) => x.fits && x.speed === "fast");
  const shown = all || !good.length ? options : options.filter((x) => (x.fits && x.speed === "fast") || x.id === value);   // what runs well; the rest on request
  const more = options.length - shown.length;
  return (
    <div className="model-list" role="radiogroup" aria-label="Model">
      {shown.map((x) => {
        const cls = !x.fits ? "no" : x.speed === "fast" ? "fast" : "slow";
        const text = !x.fits ? x.why : x.speed === "fast" ? (cardGb ? `Runs well on your ${cardGb} GB card` : "Runs well here") : x.why || "Works, but slowly";
        return (
          <label key={x.id} className={`model-opt ${value === x.id ? "on" : ""} ${x.fits ? "" : "off"}`}>
            <input type="radio" name={name} value={x.id} checked={value === x.id} disabled={!x.fits} onChange={() => onChange(x.id)} />
            <span className="grow">
              <strong>{x.label}{x.recommended && <span className="chip accent" style={{ marginLeft: 8 }}><Sparkles size={12} aria-hidden /> Best for this computer</span>}</strong>
              <span className={`model-fit ${cls}`}><FitIcon x={x} /> {text}</span>
            </span>
            <span className="model-size">{x.download_gb} GB</span>
          </label>
        );
      })}
      {more > 0 && <button type="button" className="btn ghost sm" onClick={() => setAll(true)}>Show {more} bigger model{more > 1 ? "s" : ""} (slow or too big for this card)</button>}
    </div>
  );
}

