import { useT } from "../i18n";
import { useEffect, useState } from "react";
import { Group, Row } from "../ds";
import TimelineStrip from "./TimelineStrip";
import WordChips from "./WordChips";
import { type Plan } from "./types";

/* Step 2: where the picture changes. The strip shows every change; tap one to see the sentence and move the change to another word. */
export default function ChangesStep({ plan, busy, edit }: { plan: Plan; busy: boolean; edit: (op: Record<string, unknown>) => void }) {
  const tt = useT();
  const [sel, setSel] = useState(plan.moments[0]?.id ?? "");
  useEffect(() => { if (!plan.moments.some((m) => m.id === sel)) setSel(plan.moments[0]?.id ?? ""); }, [plan.moments, sel]);
  const i = plan.moments.findIndex((m) => m.id === sel);
  const m = plan.moments[i];
  const lens = plan.moments.map((x) => x.end - x.start);
  const short = Math.min(...lens), long = Math.max(...lens);
  const first = plan.moments[0]?.beat.time ?? 0;
  return (
    <>
      <TimelineStrip moments={plan.moments} selected={sel} onSelect={setSel} />
      <p className="small muted" role="status" data-testid="change-summary">
        First change at {first.toFixed(1)} s {first <= 1.5 ? "✓" : "· a little late"} · {plan.moments.length} changes · shortest {short.toFixed(1)} s, longest {long.toFixed(1)} s {long <= 3.2 ? "✓" : "· one holds a while"}
      </p>
      {m && (
        <Group title={`Change ${i + 1} · ${m.start.toFixed(1)} s`}>
          <Row label="" stack>
            <WordChips moment={m} disabled={busy || m.locked} onPick={(w) => edit({ op: "set_beat", moment: m.id, word: w })} />
            <span className="small muted">{tt("pl.why")}: {m.beat.why}</span>
            <div className="row wrap" style={{ gap: 8 }}>
              <button className="btn sm" type="button" disabled={busy || m.locked || i === 0} onClick={() => edit({ op: "merge", moment: plan.moments[i - 1].id })}>{tt("pl.remove")}</button>
              <button className="btn sm" type="button" disabled={busy || m.locked || m.sentence_ids.length < 2} onClick={() => edit({ op: "split", moment: m.id, sentence: m.sentence_ids[Math.ceil(m.sentence_ids.length / 2)] })}>{tt("pl.addmid")}</button>
              <button className="btn sm" type="button" disabled={busy || m.locked || i === plan.moments.length - 1} onClick={() => edit({ op: "merge", moment: m.id })}>{tt("pl.joinnext")}</button>
            </div>
          </Row>
        </Group>
      )}
      <ol className="sr-only" aria-label={tt("pl.allchanges")}>{plan.moments.map((x, k) => <li key={x.id}>{k + 1}: {x.start.toFixed(1)} seconds, {x.text}</li>)}</ol>
    </>
  );
}
