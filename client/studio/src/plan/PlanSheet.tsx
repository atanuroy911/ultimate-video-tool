import { useT } from "../i18n";
import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { put } from "../api";
import { Steps } from "../ds";
import { useProject } from "../hooks";
import { toast } from "../store";
import { Spinner } from "../ui";
import ChangesStep from "./ChangesStep";
import IdeaStep from "./IdeaStep";
import MomentsStep from "./MomentsStep";
import StartStep from "./StartStep";
import { usePlan } from "./usePlan";
import "./plan.css";

/* The plan review (docs/plans/PLAN-DIRECTOR-MODULES.MD section 8): four steps, then Start. Nothing expensive has run before the last button. */
export default function PlanSheet({ pid, onClose, onStarted }: { pid: string; onClose: () => void; onStarted: () => void }) {
  const tt = useT();
  const { view, plan, busy, call, edit } = usePlan(pid);
  const { data: project } = useProject(pid);
  const [later, setLater] = useState(false);
  const [notes, setNotes] = useState<string[]>([]);
  const urls = useMemo(() => Object.fromEntries((project?.media ?? []).map((m: any) => [m.id, m.url])), [project?.media]);

  useEffect(() => {                                          // a video with no plan yet: write it (no picture is drawn)
    if (view && !view.plan) call("/make");
  }, [view?.plan === null && view !== null]); // eslint-disable-line react-hooks/exhaustive-deps

  const change = async (op: Record<string, unknown>) => {
    const v = await edit(op);
    if (v?.changes) setNotes(v.changes);
  };
  const start = async () => {
    if (later) await put("/api/settings", { plan_review: "never" }).catch(() => {});
    const v = await call("/approve");
    if (v) { toast(tt("pl.making"), "ok", 2500); onStarted(); }
  };
  if (!plan) {
    return (
      <div className="ios-back"><div className="ios-sheet"><div className="ios-body" role="status" aria-live="polite"><Spinner /><p className="ios-sub">{tt("pl.writing")}</p></div></div></div>
    );
  }
  const urgent = plan.state === "running" || plan.state === "done";
  const steps = [
    { title: tt("pl.title"), icon: <Sparkles size={26} />, subtitle: tt("pl.s1.sub"), body: <IdeaStep plan={plan} busy={busy || urgent} edit={change} ask={async (text) => (await call("/ask", { text }))?.said} /> },
    { title: tt("pl.s2"), subtitle: tt("pl.s2.sub"), body: <ChangesStep plan={plan} busy={busy || urgent} edit={change} /> },
    { title: tt("pl.s3"), subtitle: tt("pl.s3.sub").replace("{n}", String(plan.moments.length)), body: <MomentsStep plan={plan} urls={urls} busy={busy || urgent} edit={change} notes={notes} preview={(id, still) => call(`/preview/${id}?still=${still}`)} /> },
    { title: tt("pl.s4"), subtitle: tt("pl.s4.sub"), body: <StartStep plan={plan} busy={busy || urgent} edit={change} checks={view?.checks ?? []} later={later} setLater={setLater} /> },
  ];
  return <Steps label={tt("pl.title")} className="wide" steps={steps} onClose={onClose} onDone={start} doneLabel={tt("pl.start")} headerDone={false} cancelLabel={tt("pl.later")} />;
}
