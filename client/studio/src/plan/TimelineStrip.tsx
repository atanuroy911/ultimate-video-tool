import { useT } from "../i18n";
import { type Moment } from "./types";

/* The video as one strip: a block per moment, a pin where each picture changes. The pins are large enough to tap (44 px) and the list of changes below is the text alternative. */
export default function TimelineStrip({ moments, selected, onSelect }: { moments: Moment[]; selected: string; onSelect: (id: string) => void }) {
  const tt = useT();
  const total = Math.max(0.1, moments.length ? moments[moments.length - 1].end : 0.1);
  return (
    <div className="pl-strip" role="group" aria-label={tt("pl.s2")}>
      <div className="pl-strip-track">
        {moments.map((m, i) => (
          <button key={m.id} type="button" className={`pl-seg pl-m-${m.medium} ${selected === m.id ? "on" : ""}`} style={{ left: `${(m.start / total) * 100}%`, width: `${Math.max(0.8, ((m.end - m.start) / total) * 100)}%` }}
            onClick={() => onSelect(m.id)} aria-pressed={selected === m.id} aria-label={`Change ${i + 1} at ${m.start.toFixed(1)} seconds`} title={`${i + 1} · ${m.start.toFixed(1)} s`}>
            <span className="pl-pin" aria-hidden />
            <span className="pl-seg-n" aria-hidden>{i + 1}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
