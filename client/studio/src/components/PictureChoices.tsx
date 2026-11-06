import type { ReactNode } from "react";
import { Check } from "lucide-react";

/** A choice that is seen before it is picked: each option is a card with a real picture of what it makes (an ElementExample drawn by the
 *  video runtime, a caption frame ...). One radio group; arrow keys move between the cards. Use it for every option that changes a look. */
export interface PictureChoice { value: string; title: string; about?: string; visual: ReactNode }

export default function PictureChoices({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: PictureChoice[] }) {
  const move = (e: React.KeyboardEvent, i: number) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = options[(i + step + options.length) % options.length];
    onChange(next.value);
    (e.currentTarget.parentElement?.children[(i + step + options.length) % options.length] as HTMLElement | undefined)?.focus();
  };
  return (
    <div className="picture-choices" role="radiogroup" aria-label={label}>
      {options.map((o, i) => {
        const on = o.value === value;
        return (
          <button key={o.value} type="button" role="radio" aria-checked={on} tabIndex={on || (!options.some((x) => x.value === value) && i === 0) ? 0 : -1}
            className={`picture-choice${on ? " on" : ""}`} onClick={() => onChange(o.value)} onKeyDown={(e) => move(e, i)}>
            <span className="picture-choice-visual" aria-hidden="true">{o.visual}</span>
            <span className="picture-choice-text">
              <strong>{o.title}{on && <Check size={15} aria-hidden="true" />}</strong>
              {o.about && <span>{o.about}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
