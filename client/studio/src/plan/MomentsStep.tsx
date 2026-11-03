import { useT } from "../i18n";
import { useState } from "react";
import { Seg } from "../ui";
import MomentCard from "./MomentCard";
import { type Plan } from "./types";

/* Step 3: what you see in each moment, in time order. */
export default function MomentsStep({ plan, urls, busy, edit, preview, notes }: {
  plan: Plan; urls: Record<string, string>; busy: boolean; edit: (op: Record<string, unknown>) => void; preview: (id: string, still: boolean) => void; notes: string[];
}) {
  const tt = useT();
  const [filter, setFilter] = useState<"all" | "made" | "look">("all");
  const flagged = (id: string) => notes.some((n) => n.startsWith(`Moment ${id.slice(1)}`));
  const shown = plan.moments.map((m, i) => ({ m, i })).filter(({ m }) => filter === "all" || (filter === "made" ? m.medium === "made" : flagged(m.id) || m.status === "failed"));
  return (
    <>
      <Seg<"all" | "made" | "look"> label={tt("pl.show")} value={filter} onChange={setFilter} options={[{ value: "all", label: tt("pl.all").replace("{n}", String(plan.moments.length)) }, { value: "made", label: tt("pl.m.made") }, { value: "look", label: tt("pl.needslook") }]} />
      <div className="col" style={{ gap: 12 }}>
        {shown.length === 0 && <p className="muted">{tt("pl.nothing")}</p>}
        {shown.map(({ m, i }) => (
          <MomentCard key={m.id} m={m} index={i} index0={i === 0} last={i === plan.moments.length - 1} urls={urls} busy={busy} notes={notes} onEdit={edit} onPreview={(s) => preview(m.id, s)} />
        ))}
      </div>
    </>
  );
}
