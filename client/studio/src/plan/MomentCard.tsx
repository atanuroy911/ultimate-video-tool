import { useT } from "../i18n";
import { ImageIcon, Lock, Sparkles, Unlock } from "lucide-react";
import { useEffect, useState } from "react";
import { MenuItem, Popover } from "../ds";
import MediumPicker from "./MediumPicker";
import { MEDIUM, range, type Medium, type Moment } from "./types";

/* One moment, as a person reads it: when, what is said, where the picture changes, what you see, why, and what it costs. */
export default function MomentCard({ m, index, urls, busy, onEdit, onPreview, index0, last, notes }: {
  m: Moment; index: number; urls: Record<string, string>; busy: boolean; onEdit: (op: Record<string, unknown>) => void; onPreview: (still: boolean) => void; index0: boolean; last: boolean; notes: string[];
}) {
  const tt = useT();
  const [draw, setDraw] = useState(m.draw);
  useEffect(() => setDraw(m.draw), [m.draw]);
  const picture = urls[m.media] || urls[m.preview];
  const beatWord = m.words.find((w) => w.id === m.beat.word_id)?.text;
  const mine = notes.filter((n) => n.startsWith(`Moment ${m.id.slice(1)}`));
  const locked = m.locked;
  return (
    <article className={`pl-card pl-m-${m.medium} ${m.status}`} data-testid={`moment-${m.id}`} data-medium={m.medium} aria-label={`Moment ${index + 1}`}>
      <header className="pl-card-head">
        <strong className="pl-card-n">{index + 1}</strong>
        <span className="small muted">{range(m)}</span>
        <span className="grow" />
        <span className="chip" title={tt("pl.howlong")}>{(m.end - m.start).toFixed(1)} s</span>
        <button type="button" className="btn sm ghost icon" aria-pressed={locked} aria-label={locked ? tt("pl.unlock") : tt("pl.keep")} title={locked ? tt("pl.locked.t") : tt("pl.keep.t")}
          onClick={() => onEdit({ op: locked ? "unlock" : "lock", moment: m.id })} data-testid={`lock-${m.id}`}>{locked ? <Lock size={14} /> : <Unlock size={14} />}</button>
        <Popover label={tt("pl.more")} align="right" trigger={<span role="img" aria-label={tt("pl.more")}>⋯</span>}>
          <MenuItem disabled={last || locked} onClick={() => onEdit({ op: "merge", moment: m.id })}>{tt("pl.joinmoment")}</MenuItem>
          <MenuItem disabled={m.sentence_ids.length < 2 || locked} onClick={() => onEdit({ op: "split", moment: m.id, sentence: m.sentence_ids[Math.ceil(m.sentence_ids.length / 2)] })}>{tt("pl.splitmid")}</MenuItem>
        </Popover>
      </header>
      <div className="pl-card-body">
        <div className="pl-frame">
          {picture ? <img src={picture} alt={`Picture for moment ${index + 1}`} loading="lazy" />
            : m.medium === "card" || m.medium === "repeat" ? <span className="pl-frame-word bn">{beatWord || m.text.split(" ")[0]}</span>
            : <span className="pl-frame-empty"><ImageIcon size={22} aria-hidden /><small>{tt("pl.notdrawn")}</small></span>}
        </div>
        <div className="col grow" style={{ gap: 8, minWidth: 0 }}>
          <p className="pl-said bn">{m.text}</p>
          {beatWord && <span className="small muted">{tt("pl.changeson")} <strong className="bn">{beatWord}</strong> ({m.beat.time.toFixed(1)} s)</span>}
          <MediumPicker value={m.medium} first={index0} disabled={locked || busy} onChange={(to) => onEdit({ op: "set_medium", moment: m.id, medium: to as Medium })} />
          <span className="small muted">{tt("pl.why")}: {m.why}</span>
          {m.medium === "made" && (
            <label className="col" style={{ gap: 4 }}>
              <span className="small"><Sparkles size={12} aria-hidden /> {tt("pl.willshow")}</span>
              <textarea className="bn" rows={2} value={draw} disabled={locked} onChange={(e) => setDraw(e.target.value)} onBlur={() => draw.trim() && draw !== m.draw && onEdit({ op: "set_prompt", moment: m.id, text: draw })}
                aria-label={`What the picture of moment ${index + 1} shows`} data-testid={`draw-${m.id}`} />
            </label>
          )}
          {mine.map((n) => <span key={n} className="small pl-note" role="status">{n}</span>)}
          <div className="row wrap" style={{ gap: 8 }}>
            {m.medium === "made" && <button className="btn sm" type="button" disabled={busy} onClick={() => onPreview(true)} data-testid={`preview-${m.id}`}>{tt("pl.preview")}</button>}
            {m.alternatives.filter((a) => a.medium !== m.medium && !(a.medium === "repeat" && index0)).slice(0, 2).map((a) => (
              <button key={a.medium} className="btn sm ghost" type="button" disabled={locked || busy} title={a.why} onClick={() => onEdit({ op: "choose_alternative", moment: m.id, medium: a.medium })}>
                {tt("pl.instead")}: {tt("pl.m." + a.medium).toLowerCase()}
              </button>
            ))}
            <span className="chip" title={MEDIUM[m.medium].about}>{m.medium === "made" ? (m.media ? tt("pl.drawn") : tt("pl.needsdraw")) : tt("pl.nodraw")}</span>
          </div>
        </div>
      </div>
    </article>
  );
}
