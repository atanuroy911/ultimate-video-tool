import { Check, MessageSquare, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { get, post } from "../api";
import { Button, Panel, Sheet } from "../ds";
import { useFetch } from "../hooks";
import { toast, useChanged } from "../store";
import { Spinner } from "../ui";
import type { Scene } from "../types";
import type { Review } from "./useReview";
import RedoModal from "../components/RedoModal";
import PlanSheet from "../plan/PlanSheet";

interface QA {
  at?: string;
  model: string;
  bad: string[];
  scenes: { id: string; ok: boolean; problems: string[]; fix_hint: string; source: string; frame?: string }[];
}

/** The AI slide-over: what directed this video, one-click improvements, a self-check of the rendered frames, and the way back (undo). */
export default function AIPanel({ r, id, scene, kind, onClose, onChat, onTools, goProgress }: { r: Review; id: string; scene: Scene | null; kind: string; onClose: () => void; onChat: () => void; onTools: () => void; goProgress: () => void }) {
  const ai = useFetch<{ provider: string; model: string; available: boolean; images: boolean }>("/api/ai/status");
  const qa = useFetch<QA>(`/api/projects/${id}/qa`);
  const script = useFetch<{ script: any; kind: string }>(`/api/projects/${id}/script`);
  const polish = useFetch<{ suggestions: { id: string; old: string; text: string; why: string; status: string }[] }>(`/api/projects/${id}/polish`);
  const pending = (polish.data?.suggestions ?? []).filter((x) => x.status === "pending");
  const decide = async (accept: string[], reject: string[]) => {
    try {
      await post(`/api/projects/${id}/polish/decide`, { accept, reject });
      polish.refetch();
      r.reloadAll();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const [hint, setHint] = useState("");
  const [busy, setBusy] = useState<string>("");
  const [redoOpen, setRedoOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const isReel = (r.project.data as any)?.options?.look === "reel";
  /* a picture video: change its look, pictures or pace as a plan first, then it is made again (the same plan as before it was made) */
  const openPlan = async () => {
    try {
      const cur = await get<{ plan: { state: string } | null }>(`/api/projects/${id}/plan`);
      if (!cur.plan || cur.plan.state !== "draft") await post(`/api/projects/${id}/plan/make`);
      setPlanOpen(true);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const planner = r.plan?.planner;
  const chosenDirector = r.project.data?.director;
  const how = chosenDirector?.who ? (chosenDirector.who === "local" ? "Local AI" : chosenDirector.who === "claude-server" ? "Claude on the server" : chosenDirector.who.startsWith("claude@") ? "Claude on this PC" : chosenDirector.who === "rules" ? "Built-in rules" : chosenDirector.who) : planner === "claude" ? "Claude (through MCP or API)" : planner === "assistant" ? "Codex or connected assistant" : planner === "llm" ? `The AI (${ai.data?.model || "local model"})` : planner === "manual" ? "You (edited by hand)" : "The built-in rules";

  /* the server keeps the plan as it was before each save (POST /api/projects/{id}/scenes/undo; a second press puts the change back) */
  const planBackup = useFetch<{ available: boolean; at: string | null }>(`/api/projects/${id}/scenes/undo`);
  useChanged(id, () => planBackup.refetch());
  const undoPlan = async () => {
    setBusy("undo-plan");
    try {
      await post(`/api/projects/${id}/scenes/undo`);
      r.reloadAll();
      planBackup.refetch();
      toast("The plan is back as it was. Press again to put the change back.", "ok");
    } catch (e: any) {
      toast(e.message, "err");
    } finally {
      setBusy("");
    }
  };
  const job = async (what: string, url: string, after?: () => void) => {
    setBusy(what);
    try {
      await post(url);
      goProgress();
      after?.();
    } catch (e: any) {
      toast(e.message, "err", 6000);
    } finally {
      setBusy("");
    }
  };

  return (
    <Sheet title="AI" onClose={onClose}>
      <Panel title="Who directed this video">
        <div className="row"><span className="chip accent">{how}</span>{script.data?.script?.planner && <span className="small muted">script: {script.data.script.planner}</span>}</div>
        {chosenDirector?.fallback_reason && <span className="small muted">Fallback: {chosenDirector.fallback_reason}</span>}
        <div className="row small muted">
          {ai.data ? <><span className={`dot ${ai.data.available ? "ok" : "warn"}`} /> {ai.data.provider}{ai.data.model ? ` · ${ai.data.model}` : ""}{ai.data.available ? "" : " · not available"}{ai.data.images ? " · can look at pictures" : ""}</> : <Spinner size={12} />}
          <span className="grow" /><Link to="/settings" onClick={onClose}>Settings</Link>
        </div>
      </Panel>

      <Panel title="All video tools">
        <Button onClick={onTools}>Browse everything the app can do</Button>
        <span className="small muted">Search tools for voice, visuals, pacing, quality checks and more. See what your Director can use.</span>
      </Panel>

      <Panel title="Make it better">
        <Button variant="primary" onClick={() => setRedoOpen(true)}><Wand2 size={15} /> Direct this video again…</Button>
        {isReel && <Button data-testid="reel-plan" onClick={openPlan}><Sparkles size={15} /> Change the look, pictures or pace</Button>}
        <span className="small muted">Choose a director (Local AI, Claude, Codex) to completely re-plan the scenes, visuals and story graphics.</span>
        <Button onClick={() => r.askClaude("full", null, "", 1).then((x) => x && toast("Request queued for your assistant", "ok"))}><Sparkles size={15} /> Ask Claude or Codex to plan it</Button>
        <Button onClick={() => { onClose(); onChat(); }}><MessageSquare size={15} /> Ask a chat assistant</Button>
        <Button onClick={r.undo} disabled={!r.canUndo}>Undo my last edit</Button>
        {planBackup.data?.available && (
          <>
            <Button onClick={undoPlan} disabled={!!busy} data-testid="undo-plan">{busy === "undo-plan" ? <Spinner /> : null} Undo the last plan change</Button>
            <span className="small muted">Brings back the plan as it was before its latest change{planBackup.data.at ? ` (${planBackup.data.at.slice(11, 16)})` : ""}, also one made by a director or an assistant. Press it again to put the change back.</span>
          </>
        )}
      </Panel>

      <Panel title="Redo this scene" defaultOpen={!!scene}>
        {scene ? (
          <>
            <textarea rows={2} value={hint} onChange={(e) => setHint(e.target.value)} placeholder="Optional hint, e.g. “make it a comparison”" aria-label="Hint for the scene" />
            <Button onClick={() => r.askClaude("scene", scene.id, hint, 1).then((x) => x && toast("Request queued for your assistant", "ok"))}><Sparkles size={15} /> Ask for a new version of scene {r.plan ? r.plan.scenes.findIndex((s) => s.id === scene.id) + 1 : ""}</Button>
          </>
        ) : <span className="small muted">Select a scene first.</span>}
      </Panel>

      <Panel title="Check the transcript">
        <span className="small muted">The AI reads the words with their context and suggests fixes for recognition mistakes. Nothing changes until you accept it; timings never change.</span>
        <Button onClick={() => job("polish", `/api/projects/${id}/polish`, () => polish.refetch())} disabled={!!busy}>{busy === "polish" ? <Spinner /> : <Check size={15} />} Look for mistakes</Button>
        {pending.length > 0 && (
          <div className="col" style={{ gap: 6 }} aria-label="Transcript suggestions">
            <div className="row"><span className="small muted grow">{pending.length} suggestion{pending.length === 1 ? "" : "s"}</span><Button size="sm" onClick={() => decide(pending.map((x) => x.id), [])}>Accept all</Button></div>
            {pending.map((x) => (
              <div key={x.id} className="row small" style={{ gap: 6 }}>
                <span className="bn grow"><s>{x.old}</s> → <strong>{x.text}</strong>{x.why ? <span className="muted"> · {x.why}</span> : null}</span>
                <Button size="sm" onClick={() => decide([x.id], [])} aria-label={`Accept ${x.text}`}>Accept</Button>
                <Button size="sm" variant="ghost" onClick={() => decide([], [x.id])} aria-label={`Reject ${x.text}`}>Reject</Button>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Check the frames">
        <span className="small muted">Looks at one frame per scene for cut-off or overlapping text, empty screens and unrelated pictures{ai.data?.images ? " (with the vision model)" : " (pixel checks only: no vision model is set up)"}.</span>
        <div className="row wrap">
          <Button onClick={() => job("qa", `/api/projects/${id}/qa`, () => qa.refetch())} disabled={!!busy}>{busy === "qa" ? <Spinner /> : <Check size={15} />} Check</Button>
          <Button onClick={() => job("qafix", `/api/projects/${id}/qa?fix=true`, () => qa.refetch())} disabled={!!busy}>Check and fix</Button>
          <Button className="magic" onClick={() => job("autofix", `/api/projects/${id}/autofix`, () => { qa.refetch(); r.reloadAll(); })} disabled={!!busy}><Sparkles size={14} /> Auto-fix suggestions</Button>
          <Button onClick={() => job("pics", `/api/projects/${id}/qa?pictures=true`, () => qa.refetch())} disabled={!!busy || !ai.data?.images} title="The vision model looks at the candidate pictures and picks the best one">Judge pictures</Button>
        </div>
        {qa.data && qa.data.scenes.length > 0 && (
          <div className="col" style={{ gap: 4 }} aria-label="Frame check results">
            <span className="small muted">{qa.data.bad.length === 0 ? "No problems found." : `${qa.data.bad.length} of ${qa.data.scenes.length} scenes need a look`}{qa.data.model ? ` · ${qa.data.model}` : ""}</span>
            {qa.data.scenes.filter((s) => !s.ok).map((s) => (
              <button key={s.id} className="banner warn small qa-bad" style={{ textAlign: "left" }} onClick={() => { r.reloadAll(); onClose(); window.dispatchEvent(new CustomEvent("vt-select-scene", { detail: s.id })); }}>
                {s.frame && <img className="qa-frame" src={`/api/projects/${id}/qa/frame/${encodeURIComponent(s.frame)}?v=${encodeURIComponent(qa.data!.at || "")}`} alt={`The frame checked in scene ${(r.plan?.scenes.findIndex((x) => x.id === s.id) ?? 0) + 1}`} loading="lazy" />}
                <span><strong>Scene {(r.plan?.scenes.findIndex((x) => x.id === s.id) ?? 0) + 1}</strong>: {s.problems.join(", ").replace(/_/g, " ")}{s.fix_hint ? ` · ${s.fix_hint}` : ""}</span>
              </button>
            ))}
          </div>
        )}
      </Panel>
      <RedoModal id={id} open={redoOpen} onClose={() => setRedoOpen(false)} />
      {planOpen && <PlanSheet pid={id} onClose={() => setPlanOpen(false)} onStarted={() => { setPlanOpen(false); goProgress(); }} />}
    </Sheet>
  );
}

export async function fetchQA(id: string) {
  return get(`/api/projects/${id}/qa`);
}
