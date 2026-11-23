// G1/G4 (docs/plans/PLAN-SCENE-TOOLS.MD): pictures for one scene, three columns like a generation studio: the chosen picture large (left), every
// picture made for the scene (middle: Use, Redraw, Forget), the setup (right: prompt, model, how many, Generate, progress). The pictures are drawn by
// the picture engine the person chose (ComfyUI); each lands in the media bin too. Using one shows the scene with it (undoable like every edit).
import { Check, Clapperboard, ImagePlus, Loader2, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { del, get, post } from "../api";
import { toast } from "../store";

interface Item { media?: string; prompt?: string; seed: number; seconds?: number; error?: string; kind?: "clip"; from?: string }
interface Run { id: string; kind?: "clip"; from?: string; prompt: string; recipe: string; model: string; count: number; made_at: number; items: Item[] }
interface Info { runs: Run[]; prompt: string; words: string; models: { id: string; label: string; note?: string; seconds?: number }[]; clip_models?: { id: string; label: string }[] }
interface Media { id: string; url: string; kind: string; caption?: string }

const COUNTS = [1, 2, 4, 6, 8];
const LENGTHS = [3, 5];

// a picture or (G2) a clip made from one
function Shown({ m, big }: { m: Media; big?: boolean }) {
  return m.kind === "video"
    ? <video src={m.url} muted loop playsInline autoPlay={big} controls={big} onMouseEnter={(e) => !big && e.currentTarget.play().catch(() => {})} onMouseLeave={(e) => !big && e.currentTarget.pause()} />
    : <img src={m.url} alt={big ? m.caption || "picture" : ""} />;
}

export default function ScenePictures({ projectId, sceneId, sceneLabel, onClose, onUsed }: {
  projectId: string; sceneId: string; sceneLabel: string; onClose: () => void; onUsed?: () => void;
}) {
  const base = `/api/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/pictures`;
  const [info, setInfo] = useState<Info | null>(null);
  const [media, setMedia] = useState<Record<string, Media>>({});
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("");
  const [count, setCount] = useState(4);
  const [clipModel, setClipModel] = useState("");
  const [ideas, setIdeas] = useState<{ idea: string; prompt: string }[]>([]);          // G3: prompts written by the AI, edited before drawing
  const [writing, setWriting] = useState(false);
  const [clipLength, setClipLength] = useState(3);
  const [job, setJob] = useState<{ id: string; frac: number; msg: string; clip?: boolean; n?: number } | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [i, m] = await Promise.all([get<Info>(base), get<Media[]>(`/api/projects/${encodeURIComponent(projectId)}/media`)]);
    setInfo(i);
    setMedia(Object.fromEntries(m.map((x) => [x.id, x])));
    setPrompt((p) => p || i.runs[0]?.prompt || i.prompt);
    const first = i.runs.flatMap((r) => r.items).find((x) => x.media)?.media;
    setPicked((p) => p ?? first ?? null);
  }, [base, projectId]);
  useEffect(() => { load().catch((e) => setProblem(e.message)); }, [load]);

  // follow a running job: progress, then the new pictures
  useEffect(() => {
    if (!job) return;
    let stop = false;
    const tick = async () => {
      while (!stop) {
        await new Promise((r) => setTimeout(r, 1000));
        const j = await get<{ status: string; frac?: number; msg?: string; error?: string }>(`/api/jobs/${job.id}`).catch(() => null);
        if (!j || stop) continue;
        setJob((cur) => (cur && cur.id === job.id ? { ...cur, frac: j.frac ?? cur.frac, msg: j.msg ?? cur.msg } : cur));
        await load().catch(() => {});
        if (["done", "error", "cancelled"].includes(j.status)) {
          if (j.status === "error") setProblem(j.error || "The pictures could not be made.");
          setJob(null);
          return;
        }
      }
    };
    tick();
    return () => { stop = true; };
  }, [job?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = async (p = prompt, n = count, seed?: number, many?: string[]) => {
    setProblem(null);
    try {
      const j = await post<{ id: string }>(`${base}?quiet=1`, { prompt: p, count: many ? many.length : n, recipe: model, ...(many ? { prompts: many } : {}), ...(seed != null ? { seed } : {}) });          // the panel shows its own progress
      setJob({ id: j.id, frac: 0, msg: "Starting the picture engine", n: many ? many.length : n });
    } catch (e: any) {
      setProblem(e.message);
    }
  };
  const writePrompts = async () => {
    setProblem(null);
    setWriting(true);
    try {
      const r = await post<{ prompts: { idea: string; prompt: string }[] }>(`${base}/prompts?quiet=1`, { count });
      setIdeas(r.prompts);
    } catch (e: any) {
      setProblem(e.message);
    } finally {
      setWriting(false);
    }
  };
  const move = async (m: string, p: string) => {                          // G2: the picture is the clip's first frame
    setProblem(null);
    try {
      const j = await post<{ id: string }>(`${base}/${encodeURIComponent(m)}/move?quiet=1`, { prompt: p, workflow: clipModel, seconds: clipLength });
      setJob({ id: j.id, frac: 0, msg: "Starting the clip", clip: true });
    } catch (e: any) {
      setProblem(e.message);
    }
  };
  const use = async (m: string) => {
    try {
      await post(`${base}/use`, { media: m });
      toast(`Scene ${sceneLabel} now shows this ${media[m]?.kind === "video" ? "clip" : "picture"}.`);
      onUsed?.();
    } catch (e: any) {
      toast(`The picture was not used: ${e.message}`, "err");
    }
  };
  const forget = async (m: string) => {
    try {
      setInfo(await del<Info>(`${base}/${encodeURIComponent(m)}`));
      if (picked === m) setPicked(null);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  const cards = useMemo(() => (info?.runs ?? []).flatMap((r) => r.items.map((it, k) => ({ run: r, it, key: `${r.id}-${k}` }))), [info]);
  const big = picked ? media[picked] : null;
  const pickedRun = cards.find((c) => c.it.media === picked)?.run;

  return (
    <div className="scene-pics" role="dialog" aria-label={`Pictures for scene ${sceneLabel}`}>
      <header className="scene-pics-head">
        <strong>Pictures for scene {sceneLabel}</strong>
        <span className="small muted scene-pics-words">{info?.words ? `“${info.words}”` : ""}</span>
        <span className="grow" />
        <button className="btn ghost icon sm" aria-label="Close the pictures" onClick={onClose}><X size={16} /></button>
      </header>
      <div className="scene-pics-body">
        <section className="scene-pics-view" aria-label="Chosen picture">
          {big ? <Shown m={big} big /> : <p className="muted small">Pictures you make appear here.</p>}
          {big && picked && (
            <div className="row">
              <button className="btn primary sm" onClick={() => use(picked)}><Check size={14} /> Use for this scene</button>
              {pickedRun && <span className="small muted">{pickedRun.model}</span>}
            </div>
          )}
        </section>
        <section className="scene-pics-grid" aria-label="Pictures">
          <div className="scene-pics-grid-head small muted">{cards.filter((c) => c.it.media && c.it.kind !== "clip").length} picture(s){cards.some((c) => c.it.media && c.it.kind === "clip") ? `, ${cards.filter((c) => c.it.media && c.it.kind === "clip").length} clip(s)` : ""}{job ? ` · ${job.msg}` : ""}</div>
          <div className="scene-pics-cards" role="list" aria-label="Pictures made for this scene">
            {cards.map(({ run, it, key }) => (
              <div key={key} role="listitem" className={`scene-pics-card ${it.media && it.media === picked ? "on" : ""}`}>
                {it.media && media[it.media]
                  ? <button className={`scene-pics-thumb ${it.kind === "clip" ? "clip" : ""}`} aria-label={`Show ${it.kind === "clip" ? "clip" : "picture"} with seed ${it.seed}`} onClick={() => setPicked(it.media!)}><Shown m={media[it.media]} /></button>
                  : <div className="scene-pics-thumb failed small" title={it.error}>{it.error ? "Not made" : <Loader2 className="spin" size={18} />}</div>}
                <div className="scene-pics-meta small muted" title={it.prompt || run.prompt}>{it.kind === "clip" ? "Clip · " : ""}Seed {it.seed}{it.seconds ? ` · ${Math.round(it.seconds)} s` : ""}</div>
                <div className="row">
                  {it.media && <button className="btn sm" onClick={() => use(it.media!)}>Use</button>}
                  {it.kind === "clip"
                    ? <button className="btn ghost sm" disabled={!!job || !it.from} title="Make the clip again from the same picture with a new seed" onClick={() => move(it.from!, run.prompt)}><RefreshCw size={13} /> Again</button>
                    : <button className="btn ghost sm" disabled={!!job} title="Draw this one again with the same prompt and a new seed" onClick={() => { const p = it.prompt || run.prompt; setPrompt(p); generate(p, 1); }}><RefreshCw size={13} /> Redraw</button>}
                  {it.media && it.kind !== "clip" && <button className="btn ghost sm" disabled={!!job} title={`Make a ${clipLength} s clip that starts on this picture`} onClick={() => move(it.media!, it.prompt || run.prompt)}><Clapperboard size={13} /> Make it move</button>}
                  {!it.media && it.error && <button className="btn ghost icon sm" aria-label="Clear the attempts that failed" title={`Not made: ${it.error}`} onClick={() => forget("failed")}><Trash2 size={13} /></button>}
                  {it.media && <button className="btn ghost icon sm" aria-label="Forget this picture" title="Take it out of this list (it stays in the media bin)" onClick={() => forget(it.media!)}><Trash2 size={13} /></button>}
                </div>
              </div>
            ))}
            {job && Array.from({ length: job.clip ? 1 : Math.max(0, (job.n ?? count) - Math.round(job.frac * (job.n ?? count))) }).map((_, i) => (
              <div key={`wait-${i}`} className="scene-pics-card waiting" role="listitem"><div className="scene-pics-thumb"><Loader2 className="spin" size={18} /></div></div>
            ))}
          </div>
        </section>
        <aside className="scene-pics-setup" aria-label="What to make">
          <label className="field">What the picture shows
            <textarea rows={5} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Say what the picture shows, in plain words." /></label>
          <button className="btn sm" disabled={writing || !!job} onClick={writePrompts} title={`The AI chosen in Settings writes ${count} different prompts from what is said in and around this scene`}>
            {writing ? <><Loader2 className="spin" size={13} /> Writing prompts…</> : <><Sparkles size={13} /> Write {count} prompts for me</>}</button>
          {ideas.length > 0 && (
            <div className="scene-pics-ideas">
              <div className="row"><strong className="small">Prompt ideas</strong><span className="grow" />
                <button className="btn primary sm" disabled={!!job || ideas.every((x) => x.prompt.trim().length < 3)} onClick={() => generate(ideas[0].prompt, ideas.length, undefined, ideas.map((x) => x.prompt))}>
                  <ImagePlus size={13} /> Draw all {ideas.length}</button>
                <button className="btn ghost icon sm" aria-label="Clear the prompt ideas" onClick={() => setIdeas([])}><X size={13} /></button></div>
              <div role="list" aria-label="Written prompts">
                {ideas.map((x, i) => (
                  <div key={i} role="listitem" className="scene-pics-idea">
                    <span className="small muted">{x.idea}</span>
                    <textarea rows={3} aria-label={`Prompt: ${x.idea}`} value={x.prompt} onChange={(e) => setIdeas((all) => all.map((y, k) => (k === i ? { ...y, prompt: e.target.value } : y)))} />
                    <div className="row">
                      <button className="btn ghost sm" onClick={() => setPrompt(x.prompt)} title="Put it in the prompt above">Use</button>
                      <button className="btn ghost sm" disabled={!!job || x.prompt.trim().length < 3} onClick={() => generate(x.prompt, 1)}>Draw one</button>
                      <span className="grow" />
                      <button className="btn ghost icon sm" aria-label={`Remove the idea ${x.idea}`} onClick={() => setIdeas((all) => all.filter((_, k) => k !== i))}><Trash2 size={13} /></button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <label className="field">Model
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">The one chosen in Settings</option>
              {(info?.models ?? []).map((m) => <option key={m.id} value={m.id}>{m.label}{m.seconds ? ` · about ${Math.round(m.seconds)} s a picture` : ""}</option>)}
            </select></label>
          <div className="field">How many
            <div className="scene-pics-counts" role="radiogroup" aria-label="How many pictures">
              {COUNTS.map((n) => <button key={n} role="radio" aria-checked={count === n} className={`btn sm ${count === n ? "selected" : "ghost"}`} onClick={() => setCount(n)}>{n}</button>)}
            </div></div>
          <div className="field">Clips: model and length
            <div className="row">
              <select aria-label="Clip model" value={clipModel} onChange={(e) => setClipModel(e.target.value)}>
                <option value="">Any that runs</option>
                {(info?.clip_models ?? []).map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
              <div className="scene-pics-counts" role="radiogroup" aria-label="Clip length">
                {LENGTHS.map((n) => <button key={n} role="radio" aria-checked={clipLength === n} className={`btn sm ${clipLength === n ? "selected" : "ghost"}`} onClick={() => setClipLength(n)}>{n} s</button>)}
              </div>
            </div></div>
          {problem && <p className="small scene-pics-problem" role="alert">{problem}</p>}
          {job && <div className="scene-pics-progress" role="progressbar" aria-valuenow={Math.round(job.frac * 100)} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${Math.round(job.frac * 100)}%` }} /></div>}
          <button className="btn primary" disabled={!!job || prompt.trim().length < 3} onClick={() => generate()}>
            {job ? <><Loader2 className="spin" size={15} /> {job.clip ? "Making a clip…" : "Making pictures…"}</> : <><ImagePlus size={15} /> Generate {count}</>}</button>
          <p className="small muted">Drawn by the picture engine on your computer or server (Settings &gt; Engines). Each picture also goes into the media bin.</p>
        </aside>
      </div>
    </div>
  );
}
