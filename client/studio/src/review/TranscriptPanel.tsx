import { AlertTriangle, ArrowDownToLine, ArrowUpToLine, Scissors, SplitSquareVertical, Highlighter, Pencil, RotateCcw, BookPlus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { fmtTime } from "../api";
import { Menu, Modal } from "../ui";
import type { Word } from "../types";
import type { Review } from "./useReview";
import { clearPreview, previewWord } from "./previewEdits";

export default function TranscriptPanel(props: {
  r: Review;
  time: number;
  playing: boolean;
  seek: (t: number) => void;
  selected: string | null;
  onSelectScene: (id: string) => void;
  editingId: string | null;
  setEditingId: (id: string | null) => void;
}) {
  const { r, time, seek, editingId, setEditingId } = props;
  const [menu, setMenu] = useState<{ x: number; y: number; w: Word } | null>(null);
  const [gloss, setGloss] = useState<Word | null>(null);
  const [glossVal, setGlossVal] = useState("");
  const [reviewIdx, setReviewIdx] = useState(0);
  const beatRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const wrap = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);

  /** Scroll only inside the transcript (scrollIntoView would also scroll the preview column it sits in). */
  const scrollWithin = (el: HTMLElement | null | undefined, ratio = 0.3) => {
    const c = wrap.current;
    if (!c || !el) return;
    c.scrollTo({ top: Math.max(0, el.offsetTop - c.clientHeight * ratio), behavior: "smooth" });
  };

  const scenes = r.plan?.scenes ?? [];
  const sceneOfBeat = useMemo(() => {
    const m = new Map<string, { id: string; index: number; first: boolean; count: number }>();
    scenes.forEach((s, i) => s.beats.forEach((b, k) => m.set(b, { id: s.id, index: i, first: k === 0, count: s.beats.length })));
    return m;
  }, [scenes]);
  const hl = useMemo(() => new Set(scenes.flatMap((s) => s.caption.highlight_words)), [scenes]);
  const anchors = useMemo(() => new Set(scenes.flatMap((s) => s.elements.map((e) => e.at_word))), [scenes]);

  // words per beat, including cut words that sit between beats (so they can be restored)
  const words = r.words;
  const idx = useMemo(() => new Map(words.map((w, i) => [w.id, i])), [words]);
  const groups = useMemo(() => {
    return r.beats.map((b, i) => {
      const from = i === 0 ? 0 : idx.get(b.word_ids[0]) ?? 0;
      const nxt = r.beats[i + 1];
      const to = nxt ? (idx.get(nxt.word_ids[0]) ?? words.length) : words.length;
      return { beat: b, words: words.slice(from, to) };
    });
  }, [r.beats, words, idx]);

  const cur = words.find((w) => !w.cut && time >= w.start && time < w.end + 0.05);
  const curBeat = r.beats.find((b) => time >= b.start - 0.02 && time <= b.end + 0.3)?.id;
  useEffect(() => {
    if (props.playing) setFollow(true);
  }, [props.playing]);
  // keep the current sentence in a comfortable band; do nothing while it is already well placed or the user is reading elsewhere
  useEffect(() => {
    const c = wrap.current;
    const el = curBeat ? beatRefs.current[curBeat] : null;
    if (!follow || !c || !el) return;
    const top = el.offsetTop - c.scrollTop;
    if (top < c.clientHeight * 0.08 || top > c.clientHeight * 0.62) scrollWithin(el);
  }, [curBeat, follow]); // eslint-disable-line react-hooks/exhaustive-deps

  const review = words.filter((w) => w.flag === "review" && !w.cut);
  const nextReview = () => {
    if (!review.length) return;
    const w = review[reviewIdx % review.length];
    setReviewIdx((i) => i + 1);
    seek(w.start);
    scrollWithin(document.getElementById(`word-${w.id}`), 0.4);
  };

  const toggleHighlight = (w: Word) => {
    const s = scenes.find((sc) => sc.beats.some((b) => r.beats.find((x) => x.id === b)?.word_ids.includes(w.id)));
    if (!s) return;
    const list = s.caption.highlight_words;
    const next = list.includes(w.id) ? list.filter((x) => x !== w.id) : [...list, w.id].slice(-3);
    r.patchScene(s.id, { caption: { highlight_words: next } });
  };

  return (
    <div className="transcript-wrap" ref={wrap} onWheel={() => setFollow(false)} onTouchMove={() => setFollow(false)} onPointerDown={(e) => e.target === e.currentTarget && setFollow(false)}>
    <div className="transcript">
      <div className="row" style={{ margin: "8px 0 2px" }}>
        <h3 className="grow">Transcript</h3>
        <button className="btn sm" onClick={nextReview} disabled={!review.length} title="Jump to words the recognizer was unsure about">
          <AlertTriangle size={13} color="var(--warn)" /> {review.length ? `Next to check (${review.length})` : "Nothing to check"}
        </button>
      </div>
      <span className="small muted" style={{ marginBottom: 6 }}>
        Click a word to jump there · double-click to fix the spelling · right-click for more. Underlined words are ones the recognizer was unsure about.
      </span>

      {groups.map(({ beat, words: ws }) => {
        const info = sceneOfBeat.get(beat.id);
        const prevScene = info && info.first && info.index > 0 ? scenes[info.index - 1] : null;
        return (
          <div key={beat.id} ref={(el) => { beatRefs.current[beat.id] = el; }} className={`beat ${info?.first ? "sceneStart" : ""} ${curBeat === beat.id ? "cur" : ""}`}>
            <div className="gutter">
              {info?.first && <strong style={{ color: "var(--accent)" }}>Scene {info.index + 1}</strong>}
              <span>{fmtTime(beat.start)}</span>
              {info && !info.first && (
                <button className="btn ghost sm" style={{ padding: "0 6px", height: 24 }} onClick={() => r.splitScene(info.id, beat.id)} title="Start a new scene at this sentence">
                  <SplitSquareVertical size={12} /> Split
                </button>
              )}
              {prevScene && (
                <div className="row" style={{ gap: 2 }}>
                  <button
                    className="btn ghost icon sm"
                    style={{ width: 24, height: 24 }}
                    disabled={prevScene.beats.length < 2}
                    onClick={() => r.moveBoundary(prevScene.id, prevScene.beats[prevScene.beats.length - 1])}
                    title="Start this scene one sentence earlier"
                    aria-label="Move scene start earlier"
                  >
                    <ArrowUpToLine size={12} />
                  </button>
                  <button
                    className="btn ghost icon sm"
                    style={{ width: 24, height: 24 }}
                    disabled={(info?.count ?? 0) < 2}
                    onClick={() => r.moveBoundary(prevScene.id, scenes[info!.index].beats[1])}
                    title="Start this scene one sentence later"
                    aria-label="Move scene start later"
                  >
                    <ArrowDownToLine size={12} />
                  </button>
                </div>
              )}
            </div>
            <div className="words" lang="en">
              {ws.map((w) =>
                editingId === w.id ? (
                  <input
                    key={w.id}
                    className="w-input bn"
                    autoFocus
                    defaultValue={w.text}
                    onFocus={(e) => e.currentTarget.select()}
                    onChange={(e) => previewWord(w.id, w.caption_start ?? w.start, w.caption_end ?? w.end, e.currentTarget.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        e.currentTarget.blur();
                      } else if (e.key === "Escape") {
                        e.currentTarget.value = w.text;
                        clearPreview();
                        e.currentTarget.blur();
                      }
                      e.stopPropagation();
                    }}
                    onBlur={(e) => {
                      const v = e.currentTarget.value.trim();
                      setEditingId(null);
                      if (v && v !== w.text) r.editWord(w.id, { text: v });
                      else clearPreview();
                    }}
                    aria-label="Edit word"
                  />
                ) : (
                  <span
                    key={w.id}
                    id={`word-${w.id}`}
                    className={`w ${cur?.id === w.id ? "cur" : ""} ${w.flag === "review" && !w.cut ? "review" : ""} ${w.cut ? "cut" : ""} ${hl.has(w.id) ? "hl" : ""} ${anchors.has(w.id) ? "anchor" : ""}`}
                    onClick={() => seek(w.start)}
                    onDoubleClick={() => setEditingId(w.id)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setMenu({ x: e.clientX, y: e.clientY, w });
                    }}
                    title={`${w.start.toFixed(2)}s · confidence ${(w.conf * 100).toFixed(0)}%${anchors.has(w.id) ? " · an element appears here" : ""}`}
                  >
                    {w.text}
                  </span>
                )
              )}
            </div>
          </div>
        );
      })}

      {menu && (
        <Menu x={menu.x} y={menu.y} onClose={() => setMenu(null)}>
          <button onClick={() => { setEditingId(menu.w.id); setMenu(null); }}><Pencil size={14} /> Edit text</button>
          <button onClick={() => { toggleHighlight(menu.w); setMenu(null); }}><Highlighter size={14} /> {hl.has(menu.w.id) ? "Remove caption highlight" : "Highlight in caption"}</button>
          <button onClick={() => { r.editWord(menu.w.id, { cut: !menu.w.cut }); setMenu(null); }}><Scissors size={14} /> {menu.w.cut ? "Restore word" : "Remove word from captions"}</button>
          <button onClick={() => { setGloss(menu.w); setGlossVal(menu.w.text.replace(/[.,;:!?।]+$/, "")); setMenu(null); }}><BookPlus size={14} /> Always spell it like this…</button>
          <hr />
          <button onClick={() => { r.editWord(menu.w.id, { restore: true }); setMenu(null); }}><RotateCcw size={14} /> Reset my edits to this word</button>
        </Menu>
      )}

      {gloss && (
        <Modal
          title="Add to glossary"
          onClose={() => setGloss(null)}
          footer={
            <>
              <button className="btn" onClick={() => setGloss(null)}>Cancel</button>
              <button
                className="btn primary"
                disabled={!glossVal.trim()}
                onClick={async () => {
                  await r.addGlossary(gloss.text.replace(/[.,;:!?।]+$/, ""), glossVal.trim());
                  setGloss(null);
                }}
              >
                Save
              </button>
            </>
          }
        >
          <p style={{ margin: 0 }} className="muted">Every time the recognizer hears “{gloss.text}” in this video, write it as:</p>
          <input type="text" className="bn" value={glossVal} onChange={(e) => setGlossVal(e.target.value)} autoFocus aria-label="Replacement" />
        </Modal>
      )}
    </div>
    {!follow && (
      <button className="btn sm primary follow-pill" onClick={() => { setFollow(true); scrollWithin(curBeat ? beatRefs.current[curBeat] : null); }}>
        Follow playback
      </button>
    )}
    </div>
  );
}
