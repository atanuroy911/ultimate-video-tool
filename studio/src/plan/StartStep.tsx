import { useT } from "../i18n";
import { Group, Row } from "../ds";
import CostMeter from "./CostMeter";
import type { Plan } from "./types";

/* Step 4: time and cost, then Start. "How many to make" re-plans the moments that would need a picture; the time changes at once. */
export default function StartStep({ plan, busy, edit, checks, later, setLater }: {
  plan: Plan; busy: boolean; edit: (op: Record<string, unknown>) => void; checks: string[]; later: boolean; setLater: (v: boolean) => void;
}) {
  const tt = useT();
  const total = plan.moments.length;
  const made = plan.estimate.made;
  return (
    <>
      <CostMeter plan={plan} />
      <Group title={tt("pl.howmany")} note={tt("pl.howmany.note")}>
        <Row label={tt("pl.cnt").replace("{made}", String(made)).replace("{total}", String(total))}>
          <button className="btn sm" type="button" aria-label={tt("pl.fewer")} disabled={busy || made <= 1} onClick={() => edit({ op: "set_budget", n: made - 1 })} data-testid="fewer">−</button>
          <button className="btn sm" type="button" aria-label={tt("pl.morep")} disabled={busy || made >= total} onClick={() => edit({ op: "set_budget", n: made + 1 })} data-testid="more">+</button>
        </Row>
      </Group>
      {checks.length > 0 && (
        <Group title={tt("pl.worth")} note={tt("pl.worth.note")}>
          {checks.slice(0, 5).map((c) => <Row key={c} label={<span className="small">{c}</span>} />)}
        </Group>
      )}
      <label className="row small" style={{ gap: 8 }}><input type="checkbox" checked={later} onChange={(e) => setLater(e.target.checked)} /> {tt("pl.dontshow")}</label>
    </>
  );
}
