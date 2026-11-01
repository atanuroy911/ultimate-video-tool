import { useT } from "../i18n";
import { Sparkles } from "lucide-react";
import { MEDIUM, type Medium } from "./types";

/* What you see in a moment. Colour is never the only signal: each choice has its words, and "made for you" carries the sparkle. */
export default function MediumPicker({ value, onChange, disabled, first }: { value: Medium; onChange: (m: Medium) => void; disabled?: boolean; first?: boolean }) {
  const tt = useT();
  return (
    <div className="pl-medium" role="radiogroup" aria-label={tt("pl.whatsee")}>
      {(Object.keys(MEDIUM) as Medium[]).map((m) => {
        const off = disabled || (m === "repeat" && first);
        return (
          <button key={m} type="button" role="radio" aria-checked={value === m} className={`pl-m pl-m-${m} ${value === m ? "on" : ""}`} disabled={off} title={off && first && m === "repeat" ? "The first moment has no picture before it." : MEDIUM[m].about}
            onClick={() => value !== m && onChange(m)} data-medium={m}>
            {m === "made" && <Sparkles size={12} aria-hidden />} {tt("pl.m." + m)}
          </button>
        );
      })}
    </div>
  );
}
