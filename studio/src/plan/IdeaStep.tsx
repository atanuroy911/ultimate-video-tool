import { useT } from "../i18n";
import { useEffect, useState } from "react";
import { Group, Row } from "../ds";
import { Seg } from "../ui";
import { STYLES, type Plan } from "./types";

/* Step 1: what the director understood. Every line can be changed; the pictures that depend on a change are redrawn only if they were already drawn. */
export default function IdeaStep({ plan, busy, edit, ask }: { plan: Plan; busy: boolean; edit: (op: Record<string, unknown>) => void; ask: (text: string) => Promise<string | undefined> }) {
  const tt = useT();
  const [goal, setGoal] = useState(plan.idea.goal);
  const [text, setText] = useState("");
  const [said, setSaid] = useState("");
  useEffect(() => setGoal(plan.idea.goal), [plan.idea.goal]);
  const style = STYLES.find((s) => s.value === plan.idea.style);
  const end = plan.moments.length ? plan.moments[plan.moments.length - 1].end : 0;
  return (
    <>
      <Group title={tt("pl.goal")}>
        <Row label="" stack>
          <textarea className="bn" rows={2} value={goal} onChange={(e) => setGoal(e.target.value)} onBlur={() => goal !== plan.idea.goal && edit({ op: "set_goal", text: goal })} aria-label={tt("pl.goal")} data-testid="goal" />
        </Row>
      </Group>
      <Group>
        <Row label={tt("pl.who")}><input type="text" defaultValue={plan.idea.audience} key={plan.idea.audience} aria-label={tt("pl.who")} onBlur={(e) => e.target.value !== plan.idea.audience && edit({ op: "set_idea", field: "audience", value: e.target.value })} /></Row>
        <Row label={tt("pl.tone")}><input type="text" defaultValue={plan.idea.tone} key={plan.idea.tone} aria-label={tt("pl.tone")} onBlur={(e) => e.target.value !== plan.idea.tone && edit({ op: "set_idea", field: "tone", value: e.target.value })} /></Row>
        <Row label={tt("pl.look")} stack>
          <Seg label={tt("pl.look")} wrap value={plan.idea.style} onChange={(v) => edit({ op: "set_style", value: v })} options={STYLES.map((s) => ({ value: s.value, label: s.label }))} />
          <span className="small muted">{plan.idea.style_why || `Every picture is drawn as ${style?.label.toLowerCase()}.`}{plan.idea.character ? ` The same figure throughout: ${plan.idea.character}.` : ""}</span>
        </Row>
        <Row label={tt("pl.pace")} stack>
          <Seg label={tt("pl.pace")} value={plan.idea.pace} onChange={(v) => edit({ op: "set_pace", value: v })} options={[{ value: "punchy", label: tt("pl.punchy") }, { value: "balanced", label: tt("pl.balanced") }, { value: "calm", label: tt("pl.calm") }]} />
          <span className="small muted">{plan.moments.length} pictures over {end.toFixed(0)} s: about one every {plan.moments.length ? (end / plan.moments.length).toFixed(1) : 0} s.</span>
        </Row>
      </Group>
      <Group title={tt("pl.ask")} note={said || tt("pl.ask.note")}>
        <Row label="" stack>
          <form className="row" style={{ gap: 8 }} onSubmit={async (e) => { e.preventDefault(); if (!text.trim()) return; setSaid((await ask(text)) || ""); setText(""); }}>
            <input type="text" className="grow" value={text} placeholder={tt("pl.ask.ph")} onChange={(e) => setText(e.target.value)} aria-label={tt("pl.ask.aria")} data-testid="ask-director" disabled={busy} style={{ maxWidth: "none" }} />
            <button className="btn sm primary" type="submit" disabled={busy || !text.trim()}>{tt("pl.ask.btn")}</button>
          </form>
        </Row>
      </Group>
    </>
  );
}
