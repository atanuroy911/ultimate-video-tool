import { useT } from "../i18n";
import { fmt, type Plan } from "./types";

/* Time and cost in plain lines. The total is the honest sum of the lines. */
export default function CostMeter({ plan }: { plan: Plan }) {
  const tt = useT();
  const e = plan.estimate;
  return (
    <div className="pl-cost" data-testid="cost-meter">
      <div className="pl-cost-total"><strong>{tt("cm.about")} {fmt(e.total_seconds)}</strong><span className="muted small">{tt("cm.made").replace("{n}", String(e.made))}</span></div>
      <dl>
        {e.lines.filter((l) => l.count > 0 || l.seconds > 0 || l.where === "done").map((l) => (
          <div key={l.label} className="pl-cost-line"><dt>{l.label}{l.count > 1 ? ` · ${l.count}` : ""}</dt><dd>{l.where === "done" ? tt("cm.done") : l.seconds > 0 ? `${fmt(l.seconds)}${l.where ? ` · ${l.where}` : ""}` : tt("cm.nowait")}</dd></div>
        ))}
      </dl>
    </div>
  );
}
