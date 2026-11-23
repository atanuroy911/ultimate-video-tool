import { ArrowDown, Copy, GitMerge, MessageSquare, Clapperboard, ImagePlus, MoreHorizontal, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { fmtTime } from "../api";
import { Menu, Modal } from "../ui";
import type { Review } from "./useReview";
import SceneThumbnail from "./SceneThumbnail";

const TYPE_LABEL: Record<string, string> = {
  title: "title", value_card: "card", big_number: "number", arrow: "arrow", icon_row: "icons", tag: "tag", compare: "compare",
  list: "list", equation: "equation", quote: "quote", bar_chart: "bars", icon: "icon",
};

export default function ScenesPanel({ r, selected, onSelect, seek }: { r: Review; selected: string | null; onSelect: (id: string) => void; seek: (t: number) => void }) {
  const [menu, setMenu] = useState<{ x: number; y: number; sid: string } | null>(null);
  const [splitFor, setSplitFor] = useState<string | null>(null);
  const [confirmDel, setConfirmDel] = useState<string | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const c = panel.current?.parentElement;
    const el = selected ? (panel.current?.querySelector(`[data-scene="${selected}"]`) as HTMLElement | null) : null;
    if (!c || !el) return;
    const top = el.getBoundingClientRect().top - c.getBoundingClientRect().top, bottom = top + el.offsetHeight;   // on screen, in the list: offsetTop counts from another parent
    if (top < 64 || bottom > c.clientHeight) c.scrollTo({ top: Math.max(0, c.scrollTop + top - Math.max(64, c.clientHeight * 0.25)), behavior: "smooth" });   // clear of the sticky SCENES header
  }, [selected]);
  const timing = new Map(r.timing.scenes.map((s) => [s.id, s]));
  const thumbs = r.th.data?.scenes ?? {};
  const wide = r.aspect === "16:9";
  const scenes = r.plan?.scenes ?? [];
  const beatById = new Map(r.beats.map((b) => [b.id, b]));

  return (
    <div ref={panel}>
      <div className="panel-head">
        <h3 className="grow">Scenes</h3>
        <span className="small muted">{scenes.length}</span>
      </div>
      {scenes.map((s, i) => {
        const t = timing.get(s.id);
        return (
          <div
            key={s.id}
            data-scene={s.id}
            className={`scene-card ${selected === s.id ? "sel" : ""}`}
            onClick={() => {
              onSelect(s.id);
              if (t) seek(t.start);
            }}
            onContextMenu={(e) => {
              e.preventDefault();
              setMenu({ x: e.clientX, y: e.clientY, sid: s.id });
            }}
            tabIndex={0}
            role="group"
            aria-label={`Scene ${i + 1}`}
            aria-current={selected === s.id}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                onSelect(s.id);
                if (t) seek(t.start);
              }
            }}
          >
            <SceneThumbnail src={thumbs[s.id]} className={`scene-thumb ${wide ? "wide" : r.aspect === "1:1" ? "square" : ""}`} label={`Scene ${i + 1} preview`} lazy />
            <div className="scene-meta">
              <div className="row">
                <strong>{i + 1}</strong>
                <span className="small muted grow">{t ? `${fmtTime(t.start)}–${fmtTime(t.end)}` : ""}</span>
                <button
                  className="btn ghost icon sm"
                  aria-label={`Scene ${i + 1} actions`}
                  onClick={(e) => {
                    e.stopPropagation();
                    const b = (e.currentTarget as HTMLElement).getBoundingClientRect();
                    setMenu({ x: b.left, y: b.bottom + 4, sid: s.id });
                  }}
                >
                  <MoreHorizontal size={15} />
                </button>
              </div>
              <div className="scene-types">
                {s.elements.length === 0 && <span className="chip">talking</span>}
                {s.elements.map((e, k) => (
                  <span key={k} className="chip accent">{TYPE_LABEL[e.type] || e.type}</span>
                ))}
              </div>
              <span className="small muted bn" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {s.beats.map((b) => beatById.get(b)?.text).filter(Boolean).join(" ")}
              </span>
            </div>
          </div>
        );
      })}

      {menu && (
        <Menu x={menu.x} y={menu.y} onClose={() => setMenu(null)}>
          <button
            disabled={(scenes.find((s) => s.id === menu.sid)?.beats.length ?? 0) < 2}
            onClick={() => {
              setSplitFor(menu.sid);
              setMenu(null);
            }}
          >
            <ArrowDown size={14} /> Split this scene…
          </button>
          <button
            disabled={scenes.findIndex((s) => s.id === menu.sid) === scenes.length - 1}
            onClick={() => {
              r.mergeNext(menu.sid);
              setMenu(null);
            }}
          >
            <GitMerge size={14} /> Merge with next
          </button>
          <button
            onClick={() => {
              window.dispatchEvent(new CustomEvent("vt-ask-scene", { detail: menu.sid }));          // W13.3: point the assistant at this scene
              setMenu(null);
            }}
          >
            <MessageSquare size={14} /> Ask the assistant about this
          </button>
          {scenes.find((x) => x.id === menu.sid)?.shot && (                 // only a scene made of HTML (a code-native shot) opens in HyperFrames
            <button onClick={() => { window.dispatchEvent(new CustomEvent("vt-scene-hyperframes", { detail: menu.sid })); setMenu(null); }}>
              <Clapperboard size={14} /> Edit this scene in HyperFrames
            </button>
          )}
          <button onClick={() => { window.dispatchEvent(new CustomEvent("vt-scene-pictures", { detail: menu.sid })); setMenu(null); }}>
            <ImagePlus size={14} /> Pictures for this scene
          </button>
          <button
            onClick={() => {
              navigator.clipboard?.writeText(menu.sid);
              setMenu(null);
            }}
          >
            <Copy size={14} /> Copy scene id
          </button>
          <hr />
          <button
            disabled={scenes.length < 2}
            onClick={() => {
              setConfirmDel(menu.sid);
              setMenu(null);
            }}
            style={{ color: "var(--err)" }}
          >
            <Trash2 size={14} /> Delete scene
          </button>
        </Menu>
      )}

      {splitFor && (
        <Modal title="Split scene" onClose={() => setSplitFor(null)}>
          <p style={{ margin: 0 }} className="muted">Choose the sentence where the new scene should start.</p>
          <div className="col">
            {(scenes.find((s) => s.id === splitFor)?.beats ?? []).slice(1).map((bid) => (
              <button
                key={bid}
                className="btn bn"
                style={{ justifyContent: "flex-start", height: "auto", padding: "8px 12px", whiteSpace: "normal", textAlign: "left" }}
                onClick={async () => {
                  await r.splitScene(splitFor, bid);
                  setSplitFor(null);
                }}
              >
                {beatById.get(bid)?.text}
              </button>
            ))}
          </div>
        </Modal>
      )}
      {confirmDel && (
        <Modal
          title="Delete this scene?"
          onClose={() => setConfirmDel(null)}
          footer={
            <>
              <button className="btn" onClick={() => setConfirmDel(null)}>Cancel</button>
              <button
                className="btn danger"
                onClick={async () => {
                  await r.removeScene(confirmDel);
                  setConfirmDel(null);
                }}
              >
                Delete
              </button>
            </>
          }
        >
          <p style={{ margin: 0 }}>Its visuals are removed. The spoken part stays and joins the neighbouring scene, so no audio is lost. You can undo this.</p>
        </Modal>
      )}
    </div>
  );
}
