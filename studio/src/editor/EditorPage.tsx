import { ChevronLeft, Download, Film, Image as ImageIcon, MoreHorizontal, Sparkles, Trash2, Type, Wand2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { get, post } from "../api";
import RedoModal from "../components/RedoModal";
import PlanSheet from "../plan/PlanSheet";
import { Button, MenuItem, MenuSep, Popover, Segmented, Sheet } from "../ds";
import { useCatalogue, useFetch } from "../hooks";
import { DirectorLogButton } from "../log/DirectorLog";
import MediaBin from "../review/MediaBin";
import Preview, { PlayerHandle } from "../review/Preview";
import { timeStore } from "../review/timeStore";
import { useReview } from "../review/useReview";
import VideoInspector from "../review/VideoInspector";
import { useT } from "../i18n";
import { toast } from "../store";
import type { UseCase } from "../types";
import { Modal, Spinner } from "../ui";
import HookCard from "./HookCard";
import PictureTools from "./PictureTools";
import SimpleTimeline from "./SimpleTimeline";
import SoundPanel from "./SoundPanel";
import "./editor.css";

type Rail = "story" | "media" | "text" | "ai";
const CAPTION_LOOKS: { id: string; label: string; hint: string }[] = [
  { id: "theme", label: "Automatic", hint: "The director picks the look that suits the content" },
  { id: "pop", label: "Short lines", hint: "Three words at a time, the spoken one lights up" },
  { id: "word", label: "One big word", hint: "One huge word at a time" },
  { id: "keyword", label: "Key word", hint: "A small line where the key word grows" },
  { id: "box", label: "Boxed", hint: "The classic caption box" },
];
const LAYOUTS: { id: string; label: string; hint: string }[] = [
  { id: "stack", label: "Stacked", hint: "Title, picture, caption in a column" },
  { id: "hero", label: "Big picture", hint: "One large picture or number" },
  { id: "split", label: "Two halves", hint: "Two things side by side" },
  { id: "grid", label: "Grid", hint: "Several small pictures" },
  { id: "side", label: "Side note", hint: "Picture with a note beside it" },
  { id: "lower", label: "Bottom", hint: "Content in the lower half" },
  { id: "upper", label: "Top", hint: "Content in the upper half" },
];

/** The everyday editor: pictures, captions and voice on one small timeline, with the few things most people change. The full editor is one click away. */
export default function EditorPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const t = useT();
  const r = useReview(id);
  const cat = useCatalogue();
  const player = useRef<PlayerHandle>(null);
  const [rail, setRail] = useState<Rail>("story");
  const [selected, setSelected] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const lastT = useRef(0);
  const [bin, setBin] = useState(false);
  const [redoOpen, setRedoOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [options, setOptions] = useState(false);
  const [confirmDel, setConfirmDel] = useState(false);
  const [editWord, setEditWord] = useState<string | null>(null);
  const [stamp] = useState(() => String(Date.now()));
  const { data: useCases } = useFetch<UseCase[]>("/api/usecases");

  const p = r.project.data;
  const scenes = r.plan?.scenes ?? [];
  const dur = r.timing.duration || p?.duration || 0;
  const timeOf = useMemo(() => new Map(r.timing.scenes.map((s) => [s.id, s])), [r.timing.scenes]);
  const idx = scenes.findIndex((s) => s.id === selected);
  const scene = idx >= 0 ? scenes[idx] : null;
  const seek = useCallback((t: number) => player.current?.seek(t), []);
  const thumbs = r.th.data?.scenes ?? {};

  useEffect(() => {
    if (p && (p.status === "processing" || p.active_job)) nav(`/p/${id}/progress`, { replace: true });
  }, [p?.status, p?.active_job, id, nav]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (scenes.length && (!selected || !scenes.some((s) => s.id === selected))) setSelected(scenes[0].id);
  }, [scenes, selected]);
  // follow the playhead
  useEffect(() => {
    const cur = r.timing.scenes.find((s) => time >= s.start && time < s.end);
    if (cur && cur.id !== selected) setSelected(cur.id);
  }, [Math.floor(time * 4)]); // eslint-disable-line react-hooks/exhaustive-deps

  const wordsOf = useCallback((sid: string) => {
    const sc = scenes.find((s) => s.id === sid);
    if (!sc) return [];
    const ids = new Set(sc.beats.flatMap((b) => r.beats.find((x) => x.id === b)?.word_ids ?? []));
    return r.words.filter((w) => ids.has(w.id));
  }, [scenes, r.beats, r.words]);
  const sentence = (sid: string) => wordsOf(sid).filter((w) => !w.cut).map((w) => w.text).join(" ");

  const go = (d: number) => {
    const n = scenes[Math.max(0, Math.min(scenes.length - 1, idx + d))];
    if (n) { setSelected(n.id); const t = timeOf.get(n.id); if (t) seek(t.start); }
  };
  /** Split the scene under the playhead at the nearest sentence start inside it. */
  const split = () => {
    const cur = scenes.find((s) => { const t = timeOf.get(s.id); return t && timeStore.t >= t.start && timeStore.t < t.end; });
    if (!cur || cur.beats.length < 2) { toast(t("ed.onesentence"), "info", 3500); return; }
    let best: string | null = null, gap = Infinity;
    cur.beats.slice(1).forEach((bid) => {
      const first = r.words.find((w) => w.id === r.beats.find((b) => b.id === bid)?.word_ids[0]);
      if (first && Math.abs(first.start - timeStore.t) < gap) { gap = Math.abs(first.start - timeStore.t); best = bid; }
    });
    if (best) r.splitScene(cur.id, best);
  };
  const remove = () => { if (scene) { r.removeScene(scene.id); setConfirmDel(false); } };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? r.redo() : r.undo(); }
      else if (mod && e.key === "Enter") { e.preventDefault(); nav(`/p/${id}/export`); }
      else if (mod || e.altKey) return;
      else if (e.key === " ") { e.preventDefault(); player.current?.toggle(); }
      else if (e.key.toLowerCase() === "s") split();
      else if (e.key === "Delete" || e.key === "Backspace") { if (scenes.length > 1) setConfirmDel(true); }
      else if (e.key.toLowerCase() === "j") go(-1);
      else if (e.key.toLowerCase() === "k") go(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (r.project.error) return <div className="page-inner"><div className="banner err">{t("ed.cantopen")}: {r.project.error}. <Link to="/">{t("ed.back")}</Link></div></div>;
  if (!p || r.sc.loading) return <div className="page-inner"><div className="row muted"><Spinner /> {t("ed.loading")}</div></div>;
  if (!r.plan) return <div className="page-inner"><div className="banner warn">{t("ed.noplan")} <button className="btn sm" onClick={() => post(`/api/projects/${id}/run`, {}).then(() => nav(`/p/${id}/progress`))}>{t("ed.makenow")}</button></div></div>;

  const RAIL: { id: Rail; label: string; icon: React.ReactNode }[] = [
    { id: "story", label: t("ed.story"), icon: <Film size={20} /> },
    { id: "media", label: t("ed.media"), icon: <ImageIcon size={20} /> },
    { id: "text", label: t("ed.text"), icon: <Type size={20} /> },
    { id: "ai", label: t("ed.ai"), icon: <Sparkles size={20} /> },
  ];
  const selWords = scene ? wordsOf(scene.id) : [];

  return (
    <div className="ce" data-testid="simple-editor">
      <h1 className="sr-only">{p.title}</h1>
      <header className="ce-top">
        <Link to="/" className="ce-icon" aria-label={t("ed.allprojects")}><ChevronLeft size={20} /></Link>
        <input type="text" className="ce-title bn" defaultValue={p.title} key={p.title} aria-label={t("ed.title")}
          onBlur={(e) => e.target.value.trim() && e.target.value !== p.title && r.patchProject({ title: e.target.value })} />
        <span className="grow" />
        <Segmented value={p.aspect} onChange={(a) => r.patchProject({ aspect: a })} options={[{ value: "9:16", label: "9:16" }, { value: "1:1", label: "1:1" }, { value: "16:9", label: "16:9" }]} label={t("ed.shape")} />
        <Popover label={t("ed.more")} align="right" trigger={<span role="img" aria-label={t("ed.more")}><MoreHorizontal size={18} /></span>}>
          <MenuItem onClick={() => setOptions(true)}>{t("ed.videooptions")}</MenuItem>
          <MenuItem onClick={() => nav(`/p/${id}/shorts`)}>{t("ed.findshorts")}</MenuItem>
          <MenuItem onClick={() => nav(`/p/${id}/pro`)}>{t("ed.fulleditor")}</MenuItem>
          <MenuSep />
          <MenuItem onClick={() => nav("/")}>{t("ed.allprojects")}</MenuItem>
        </Popover>
        <DirectorLogButton pid={p.id} label={t("ed.details")} />
        <Button variant="primary" onClick={() => nav(`/p/${id}/export`)}><Download size={15} /> {t("ed.export")}</Button>
      </header>

      <nav className="ce-rail" aria-label={t("ed.tools")}>
        {RAIL.map((x) => (
          <button key={x.id} className={rail === x.id ? "on" : ""} onClick={() => setRail(x.id)} aria-pressed={rail === x.id}>
            {x.icon}<span>{x.label}</span>
          </button>
        ))}
      </nav>

      <aside className="ce-panel" aria-label={RAIL.find((x) => x.id === rail)?.label}>
        {rail === "story" && (
          <>
            <h2>{t("ed.story")}</h2>
            <p className="ce-help">{t("ed.story.help")}</p>
            <ol className="ce-scenes">
              {scenes.map((s, i) => (
                <li key={s.id}>
                  <button className={selected === s.id ? "on" : ""} onClick={() => { setSelected(s.id); const t = timeOf.get(s.id); if (t) seek(t.start); }}>
                    <span className="ce-thumb">{thumbs[s.id] ? <img src={thumbs[s.id]} alt="" /> : <i>{i + 1}</i>}</span>
                    <span className="ce-line bn"><b>{i + 1}</b> {sentence(s.id) || "…"}</span>
                  </button>
                </li>
              ))}
            </ol>
          </>
        )}
        {rail === "media" && (
          <>
            <h2>{t("ed.media")}</h2>
            <p className="ce-help">{t("ed.media.help")}</p>
            <Button variant="primary" onClick={() => setBin(true)}><ImageIcon size={15} /> {t("ed.addmedia")}</Button>
            <div className="ce-media">
              {(p.media ?? []).slice(0, 24).map((m: any) => <img key={m.id} src={m.url} alt={m.caption || m.id} title={m.caption || m.id} />)}
              {!(p.media ?? []).length && <span className="muted small">{t("ed.nothingadded")}</span>}
            </div>
            <SoundPanel r={r} />
          </>
        )}
        {rail === "text" && (
          <>
            <h2>{t("ed.text")}</h2>
            <p className="ce-help">{t("ed.text.help").replace("{n}", String(idx + 1))}</p>
            <div className="ce-words bn">
              {selWords.map((w) => editWord === w.id ? (
                <input key={w.id} autoFocus defaultValue={w.text} aria-label={t("ed.fixword")} onBlur={(e) => { if (e.target.value.trim() && e.target.value !== w.text) r.editWord(w.id, { text: e.target.value.trim() }); setEditWord(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") setEditWord(null); }} />
              ) : (
                <button key={w.id} className={w.cut ? "cut" : ""} onClick={() => setEditWord(w.id)} title={w.cut ? t("ed.removed") : t("ed.clickfix")}>{w.text}</button>
              ))}
            </div>
            <h3>{t("ed.captionlook")}</h3>
            <div className="ce-layouts" role="group" aria-label={t("ed.captionlook")} data-testid="caption-looks">
              {CAPTION_LOOKS.map((l) => (
                <button key={l.id} className={(p.options?.caption_style ?? "theme") === l.id ? "on" : ""} aria-pressed={(p.options?.caption_style ?? "theme") === l.id} title={t("ed.look." + l.id + ".h")}
                  onClick={() => r.patchProject({ options: { caption_style: l.id } })}>{t("ed.look." + l.id)}</button>
              ))}
            </div>
            {scene && (
              <>
                <h3>{t("ed.highlight")}</h3>
                <p className="ce-help">{t("ed.highlight.help")}</p>
                <div className="ce-words bn">
                  {selWords.filter((w) => !w.cut).map((w) => {
                    const on = scene.caption.highlight_words.includes(w.id);
                    return <button key={w.id} className={on ? "hl" : ""} aria-pressed={on} onClick={() => r.patchScene(scene.id, { caption: { highlight_words: on ? scene.caption.highlight_words.filter((x) => x !== w.id) : [...scene.caption.highlight_words, w.id].slice(-3) } })}>{w.text}</button>;
                  })}
                </div>
              </>
            )}
          </>
        )}
        {rail === "ai" && (
          <>
            <h2>{t("ed.ai")}</h2>
            <p className="ce-help">{t("ed.ai.help")}</p>
            <div className="ce-actions">
              <Button onClick={() => setRedoOpen(true)}><Wand2 size={15} /> {t("ed.redoall")}</Button>
              {p.options?.look === "reel" && (
                <Button data-testid="reel-plan" onClick={async () => {                      // a reel: change the look, the pictures or the pace, seen as a plan first, then made again
                  try {
                    const cur = await get<{ plan: { state: string } | null }>(`/api/projects/${id}/plan`);
                    if (!cur.plan || cur.plan.state !== "draft") await post(`/api/projects/${id}/plan/make`);
                    setPlanOpen(true);
                  } catch (e: any) { toast(e.message, "err"); }
                }}><Sparkles size={15} /> {t("ed.reelplan")}</Button>
              )}
              <Button disabled={!scene} onClick={() => scene && r.askClaude("scene", scene.id, "", 1).then(() => toast(t("ed.asked").replace("{n}", String(idx + 1)), "ok"))}><Sparkles size={15} /> {t("ed.redoscene")}</Button>
              <Button onClick={() => post(`/api/projects/${id}/qa`).then(() => nav(`/p/${id}/progress`)).catch((e: any) => toast(e.message, "err"))}>{t("ed.watch")}</Button>
            </div>
            <HookCard pid={id} onApplied={() => nav(`/p/${id}/progress`)} />
          </>
        )}
      </aside>

      <section className="ce-stage" aria-label={t("ed.preview")}>
        <Preview
          ref={player}
          projectId={id}
          aspect={p.aspect}
          audioUrl={p.audio_url ? `${p.audio_url}${p.audio_url.includes("?") ? "&" : "?"}v=${r.audioRev}` : null}
          duration={dur}
          scenes={r.timing.scenes}
          selected={selected}
          onSelectScene={setSelected}
          onTime={(t) => { timeStore.set(t); if (Math.abs(t - lastT.current) >= 0.07 || t === 0) { lastT.current = t; setTime(t); } }}
          onPlaying={(pl) => { timeStore.playing = pl; setPlaying(pl); }}
          rev={r.rev}
          reloadKey={`${stamp}-${p.theme}`}
          safeArea={false}
          showTimeline={false}
        />
      </section>

      <aside className="ce-props" aria-label={t("ed.selection")}>
        {scene ? (
          <>
            <div className="ce-props-head">
              <h2>{t("ed.scene").replace("{n}", String(idx + 1))}</h2>
              <span className="muted small">{timeOf.get(scene.id) ? `${timeOf.get(scene.id)!.start.toFixed(1)}–${timeOf.get(scene.id)!.end.toFixed(1)} s` : ""}</span>
            </div>
            <p className="ce-quote bn">{sentence(scene.id)}</p>
            {p.options?.look === "reel" && <PictureTools pid={id} sid={scene.id} media={p.media ?? []} onChanged={() => r.reloadAll()} />}
            <h3>{t("ed.picture")}</h3>
            <div className="ce-layouts" role="group" aria-label={t("ed.picturelayout")}>
              {LAYOUTS.map((l) => (
                <button key={l.id} className={scene.layout === l.id ? "on" : ""} aria-pressed={scene.layout === l.id} title={t("ed.lay." + l.id + ".h")} onClick={() => r.patchScene(scene.id, { layout: l.id })}>{t("ed.lay." + l.id)}</button>
              ))}
            </div>
            <h3>{t("ed.comesin")}</h3>
            <select className="ce-select" value={scene.transition_in} aria-label={t("ed.transition")} onChange={(e) => r.patchScene(scene.id, { transition_in: e.target.value })}>
              {(cat?.transitions ?? [scene.transition_in]).map((x: string) => <option key={x} value={x}>{x.replace(/_/g, " ")}</option>)}
            </select>
            <div className="ce-props-actions">
              <Button onClick={() => scene && r.askClaude("scene", scene.id, "", 1).then(() => toast(t("ed.asked").replace("{n}", String(idx + 1)), "ok"))}><Sparkles size={14} /> {t("ed.redoai")}</Button>
              <Button disabled={idx >= scenes.length - 1} onClick={() => r.mergeNext(scene.id)}>{t("ed.join")}</Button>
              <Button variant="danger" disabled={scenes.length < 2} onClick={() => setConfirmDel(true)}><Trash2 size={14} /> {t("ed.delete")}</Button>
            </div>
            <Link className="ce-more" to={`/p/${id}/pro`}>{t("ed.moreoptions")}</Link>
          </>
        ) : (
          <p className="ce-help">{t("ed.selectscene")}</p>
        )}
      </aside>

      <section className="ce-timeline" aria-label={t("ed.timeline")}>
        <SimpleTimeline r={r} duration={dur} selected={selected} onSelect={setSelected} seek={seek} onSplit={split} onDelete={() => scenes.length > 1 && setConfirmDel(true)} canDelete={scenes.length > 1 && !!scene} />
      </section>

      {bin && <MediaBin id={id} onClose={() => setBin(false)} onChange={() => r.reloadAll()} onAddToTimeline={() => setBin(false)} />}
      {redoOpen && <RedoModal id={id} title={p.title} open={redoOpen} onClose={() => setRedoOpen(false)} />}
      {planOpen && <PlanSheet pid={id} onClose={() => setPlanOpen(false)} onStarted={() => { setPlanOpen(false); nav(`/p/${id}/progress`); }} />}
      {options && (
        <Sheet title={t("ed.videooptions.t")} onClose={() => setOptions(false)}>
          <VideoInspector r={r} p={p} useCases={useCases ?? []} onRedirect={() => nav(`/p/${id}/progress`)} onRepace={(pace, from) => post(`/api/projects/${id}/run`, { from_stage: from }).then(() => nav(`/p/${id}/progress`))} />
        </Sheet>
      )}
      {confirmDel && scene && (
        <Modal title={t("ed.delscene")} onClose={() => setConfirmDel(false)} footer={<><button className="btn" onClick={() => setConfirmDel(false)}>{t("ed.cancel")}</button><button className="btn danger" onClick={remove}>{t("ed.delete")}</button></>}>
          <p style={{ margin: 0 }}>{t("ed.delscene.b")}</p>
        </Modal>
      )}
    </div>
  );
}
