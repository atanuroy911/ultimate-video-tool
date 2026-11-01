import CastEditor from "./CastEditor";
import ActionEditor from "./ActionEditor";
import { ChevronDown, ChevronRight, ChevronUp, Plus, Sparkles, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { fmtTime } from "../api";
import { Menu, Seg } from "../ui";
import type { Catalogue, El, Scene, SceneTime, Word } from "../types";
import SchemaForm from "./SchemaForm";
import ShowAs from "./ShowAs";
import type { Review } from "./useReview";

function summary(e: El): string {
  const v = e.text ?? e.value ?? e.label ?? e.name ?? (e.items ? e.items.join(", ") : "") ?? "";
  return String(v).slice(0, 28);
}

type InspectorTab = "elements" | "characters" | "scene";

export default function Inspector(props: {
  r: Review;
  scene: Scene;
  index: number;
  time: SceneTime | undefined;
  words: Word[]; // words belonging to this scene
  playheadWord: string | null;
  cat: Catalogue | null;
  icons: Record<string, string>;
  focusEl?: number | null;
}) {
  const { r, scene, index, cat } = props;
  const [els, setEls] = useState<El[]>(scene.elements);
  const [open, setOpen] = useState<Set<number>>(new Set([0]));
  const [tab, setTab] = useState<InspectorTab>("elements");
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const [hint, setHint] = useState("");
  const [alts, setAlts] = useState<1 | 2 | 3>(1);
  const dirty = useRef(false);
  const cards = useRef<Record<number, HTMLDivElement | null>>({});
  const timer = useRef<number>(0);

  // adopt server changes unless the user is mid-edit
  useEffect(() => {
    if (!dirty.current) setEls(scene.elements);
  }, [scene]);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  // an element picked on the canvas or the timeline opens its card
  useEffect(() => {
    if (props.focusEl == null) return;
    setTab("elements");
    setOpen(new Set([props.focusEl]));
    setTimeout(() => cards.current[props.focusEl!]?.scrollIntoView({ block: "nearest", behavior: "smooth" }), 30);
  }, [props.focusEl]); // eslint-disable-line react-hooks/exhaustive-deps

  const differs = useMemo(() => JSON.stringify(els) !== JSON.stringify(scene.elements), [els, scene.elements]);

  const commit = (next: El[], immediate = false) => {
    setEls(next);
    dirty.current = true;
    window.clearTimeout(timer.current);
    const flush = async () => {
      await r.patchScene(scene.id, { elements: next });
      dirty.current = false;
    };
    if (immediate) flush();
    else timer.current = window.setTimeout(flush, 500);
  };

  const specs = new Map((cat?.elements ?? []).map((c) => [c.type, c]));
  const wordLite = props.words.map((w) => ({ id: w.id, text: w.text, start: w.start }));
  const firstWord = props.words[0]?.id ?? "";
  const hlWords = scene.caption.highlight_words.map((id) => props.words.find((w) => w.id === id)).filter(Boolean) as Word[];

  const addElement = (type: string) => {
    const spec = specs.get(type);
    if (!spec) return;
    const at = props.playheadWord && props.words.some((w) => w.id === props.playheadWord) ? props.playheadWord : firstWord;
    const el = { ...JSON.parse(JSON.stringify(spec.example)), at_word: at } as El;
    commit([...els, el], true);
    setOpen((o) => new Set(o).add(els.length));
  };

  return (
    <div className="inspector">
      <div className="row">
        <div className="col grow" style={{ gap: 2 }}>
          <h2>Scene {index + 1}</h2>
          <span className="small muted">
            {props.time ? `${fmtTime(props.time.start)}–${fmtTime(props.time.end)} · ${(props.time.end - props.time.start).toFixed(1)}s` : ""}
          </span>
        </div>
        <span className={`chip ${r.plan?.planner === "claude" || r.plan?.planner === "assistant" ? "accent" : ""}`}>{r.plan?.planner === "claude" ? "planned by Claude" : r.plan?.planner === "assistant" ? "planned by Codex" : r.plan?.planner === "manual" ? "edited" : "auto draft"}</span>
      </div>

      <Seg<InspectorTab> value={tab} onChange={setTab} label="Edit" options={[{ value: "elements", label: `Elements ${els.length}` }, ...(scene.stick ? [{ value: "characters" as const, label: `Characters ${(scene.stick.cast ?? []).length}` }] : []), { value: "scene", label: "Scene" }]} />

      {tab === "elements" && (
        <>
        <div className="col" style={{ gap: 8 }}>
          <div className="row">
            <h3 className="grow">Elements ({els.length}/5)</h3>
            <button
              className="btn sm"
              disabled={els.length >= 5 || !cat}
              onClick={(e) => {
                const b = (e.currentTarget as HTMLElement).getBoundingClientRect();
                setMenu({ x: b.left - 120, y: b.bottom + 4 });
              }}
            >
              <Plus size={14} /> Add
            </button>
          </div>
          {els.length === 0 && <div className="small muted">No visuals in this scene. The captions carry it. Add an element or ask your assistant below.</div>}
          {differs && !dirty.current && (
            <div className="banner warn small">
              These changes were not saved (see the message above).
              <button className="btn sm" onClick={() => setEls(scene.elements)}>
                Revert
              </button>
            </div>
          )}
          {els.map((e, i) => {
            const spec = specs.get(e.type);
            const isOpen = open.has(i);
            return (
              <div key={i} className={`el-card ${props.focusEl === i ? "picked" : ""}`} ref={(n) => { cards.current[i] = n; }}>
                <div
                  className="el-head"
                  onClick={() =>
                    setOpen((o) => {
                      const n = new Set(o);
                      n.has(i) ? n.delete(i) : n.add(i);
                      return n;
                    })
                  }
                >
                  {isOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                  <strong>{e.type.replace("_", " ")}</strong>
                  <span className="muted small bn grow" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {summary(e)}
                  </span>
                  <button className="btn ghost icon sm" disabled={i === 0} aria-label="Move up" onClick={(ev) => { ev.stopPropagation(); const n = [...els]; [n[i - 1], n[i]] = [n[i], n[i - 1]]; commit(n, true); }}>
                    <ChevronUp size={14} />
                  </button>
                  <button className="btn ghost icon sm" disabled={i === els.length - 1} aria-label="Move down" onClick={(ev) => { ev.stopPropagation(); const n = [...els]; [n[i + 1], n[i]] = [n[i], n[i + 1]]; commit(n, true); }}>
                    <ChevronDown size={14} />
                  </button>
                  <button className="btn ghost icon sm" aria-label="Delete element" onClick={(ev) => { ev.stopPropagation(); commit(els.filter((_, j) => j !== i), true); }}>
                    <Trash2 size={14} />
                  </button>
                </div>
                {isOpen && spec && (
                  <div className="el-body">
                    <span className="small muted">{spec.use_when}</span>
                    <SchemaForm spec={spec} value={e} words={wordLite} icons={props.icons} playheadWord={props.playheadWord} onChange={(v) => commit(els.map((x, j) => (j === i ? v : x)))} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="col card card-pad" style={{ gap: 8 }}>
          <div className="row">
            <Sparkles size={15} color="var(--accent)" />
            <strong>Ask Codex or Claude to redo this scene</strong>
          </div>
          <textarea rows={2} value={hint} onChange={(e) => setHint(e.target.value)} placeholder="Optional hint, e.g. “make it a comparison” or “use the coin icons”" />
          <div className="row">
            <span className="small muted">Options to choose from</span>
            <Seg value={String(alts) as any} onChange={(v) => setAlts(+v as 1 | 2 | 3)} options={[{ value: "1", label: "1" }, { value: "2", label: "2" }, { value: "3", label: "3" }]} />
          </div>
          <button className="btn primary" onClick={() => r.askClaude("scene", scene.id, hint, alts)}>
            <Sparkles size={14} /> Send request
          </button>
          <span className="small muted">Codex or Claude Code picks it up through the connector. Say “plan my pending videos” there.</span>
        </div>

        </>
      )}

      {tab === "characters" && scene.stick && (
        <div className="col" style={{ gap: 14 }} aria-label="Stick figures">
          <CastEditor cast={scene.stick.cast ?? []} onChange={r.patchCast} />
          <ActionEditor
            sceneId={scene.id}
            cast={scene.stick.cast ?? []}
            actions={scene.stick.actions ?? []}
            words={props.words}
            playheadWord={props.playheadWord}
            r={r}
          />
        </div>
      )}

      {tab === "scene" && (
        <>
        <ShowAs r={r} id={r.project.data?.id ?? ""} scene={scene} media={r.project.data?.media ?? []} />

        <div className="col" style={{ gap: 6 }}>
          <h3>Layout</h3>
          <Seg value={scene.layout} onChange={(v) => r.patchScene(scene.id, { layout: v })} options={[{ value: "stack", label: "Stack" }, { value: "split", label: "Split" }, { value: "hero", label: "Hero" }, { value: "grid", label: "Grid" }, { value: "side", label: "Side" }, { value: "lower", label: "Lower" }, { value: "upper", label: "Upper" }]} label="Layout" wrap />
          <span className="small muted">{cat?.layouts[scene.layout]}</span>
        </div>

        <label className="field">
          <span>Transition into this scene</span>
          <select value={scene.transition_in} onChange={(e) => r.patchScene(scene.id, { transition_in: e.target.value })}>
            {(cat?.transitions ?? [scene.transition_in]).map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>

        <div className="col" style={{ gap: 6 }}>
          <h3>Caption highlight</h3>
          <div className="row wrap">
            {hlWords.map((w) => (
              <span key={w.id} className="chip accent bn">
                {w.text}
                <button className="btn ghost icon sm" style={{ width: 18, height: 18 }} aria-label={`Remove highlight ${w.text}`} onClick={() => r.patchScene(scene.id, { caption: { highlight_words: scene.caption.highlight_words.filter((x) => x !== w.id) } })}>
                  <X size={11} />
                </button>
              </span>
            ))}
            {hlWords.length === 0 && <span className="small muted">None</span>}
            <button
              className="btn sm"
              disabled={!props.playheadWord || !props.words.some((w) => w.id === props.playheadWord) || scene.caption.highlight_words.includes(props.playheadWord!)}
              onClick={() => r.patchScene(scene.id, { caption: { highlight_words: [...scene.caption.highlight_words, props.playheadWord].slice(-3) } })}
            >
              + Word at playhead
            </button>
          </div>
        </div>

        </>
      )}

      {menu && (
        <Menu x={menu.x} y={menu.y} onClose={() => setMenu(null)}>
          {(cat?.elements ?? []).map((c) => (
            <button key={c.type} onClick={() => { addElement(c.type); setMenu(null); }} title={c.use_when}>
              {c.type.replace("_", " ")}
            </button>
          ))}
        </Menu>
      )}
    </div>
  );
}
