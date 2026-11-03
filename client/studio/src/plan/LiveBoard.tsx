import { useT } from "../i18n";
import { AlertTriangle, Check, Clock, Sparkles } from "lucide-react";
import { useMemo } from "react";
import { useProject } from "../hooks";
import { usePlan } from "./usePlan";
import { MEDIUM, range, type Moment } from "./types";

/* After Start, the same moments as a board: waiting, making, ready, or needs a look. A picture that cannot be drawn never stops the video: the card says what was used instead. */
const KEY: Record<Moment["status"], string> = { planned: "pl.st.waiting", waiting: "pl.st.waiting", making: "pl.st.making", ready: "pl.st.ready", replaced: "pl.st.replaced", failed: "pl.needslook" };

export default function LiveBoard({ pid }: { pid: string }) {
  const tt = useT();
  const { plan } = usePlan(pid);
  const { data: project } = useProject(pid);
  const urls = useMemo(() => Object.fromEntries((project?.media ?? []).map((m: any) => [m.id, m.url])), [project?.media]);
  if (!plan || !["running", "done", "approved"].includes(plan.state)) return null;
  const ready = plan.moments.filter((m) => m.status === "ready").length;
  return (
    <section className="pl-board" aria-label={tt("pl.board.aria")} data-testid="live-board">
      <h2 className="pl-board-h"><Sparkles size={15} aria-hidden /> {tt("pl.board").replace("{n}", String(ready)).replace("{m}", String(plan.moments.length))}</h2>
      <ul className="pl-board-grid">
        {plan.moments.map((m, i) => (
          <li key={m.id} className={`pl-tile ${m.status} pl-m-${m.medium}`} data-status={m.status} data-testid={`tile-${m.id}`}>
            <div className="pl-tile-pic">
              {urls[m.media] ? <img src={urls[m.media]} alt="" loading="lazy" /> : <span className="pl-tile-word bn">{m.words.find((w) => w.id === m.beat.word_id)?.text ?? ""}</span>}
              {m.status === "making" && <span className="pl-spin" aria-hidden />}
            </div>
            <div className="pl-tile-foot">
              <span className="small"><strong>{i + 1}</strong> · {range(m)}</span>
              <span className={`chip ${m.status === "ready" ? "ok" : m.status === "failed" ? "warn" : ""}`}>
                {m.status === "ready" ? <Check size={11} aria-hidden /> : m.status === "failed" ? <AlertTriangle size={11} aria-hidden /> : <Clock size={11} aria-hidden />} {tt(KEY[m.status])}
              </span>
            </div>
            <span className="small muted">{tt("pl.m." + m.medium)}</span>
            {m.status === "failed" && <span className="small pl-note" role="status">{m.problem || tt("pl.nodrawn")} {tt("pl.cardinstead")}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
