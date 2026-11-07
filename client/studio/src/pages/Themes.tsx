import { Copy, Download, Pause, Play, Save, Star, Trash2, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { del, fmtTime, get, post, put } from "../api";
import { useFetch, useThemes } from "../hooks";
import { settingsStore, toast, useStore } from "../store";
import type { Aspect, Theme } from "../types";
import { Field, Modal, Seg, contrastRatio } from "../ui";
import DesignStudio from "./DesignStudio";

const BUILTIN = new Set(["paper", "dark-neon", "minimal"]);
const BN_FONTS = ["Hind Siliguri", "Baloo Da 2", "Noto Sans Bengali", "Anek Bangla"];
const COLOR_LABELS: [string, string][] = [
  ["bg", "Background"], ["bg2", "Background 2 (gradient end)"], ["ink", "Text"], ["muted", "Secondary text"], ["accent", "Accent"], ["accent2", "Second accent (coins, tags)"],
  ["card", "Card fill"], ["card_border", "Card border"], ["caption_bg", "Caption box"], ["caption_ink", "Caption text"],
  ["highlight_bg", "Highlight pill"], ["highlight_ink", "Highlight text"], ["tag_bg", "Tag fill"], ["tag_ink", "Tag text"], ["arc", "Decorative lines"],
];
const PAIRS: [string, string, string][] = [["ink", "bg", "Text on background"], ["caption_ink", "caption_bg", "Caption"], ["highlight_ink", "highlight_bg", "Highlight"], ["tag_ink", "tag_bg", "Tag"]];
const ROLES: ["headline" | "body" | "numeral" | "caption", string][] = [["headline", "Headlines"], ["body", "Body text"], ["numeral", "Numbers"], ["caption", "Captions"]];

function setIn<T>(obj: T, path: string[], value: any): T {
  const clone: any = Array.isArray(obj) ? [...(obj as any)] : { ...(obj as any) };
  let cur = clone;
  for (let i = 0; i < path.length - 1; i++) {
    cur[path[i]] = Array.isArray(cur[path[i]]) ? [...cur[path[i]]] : { ...(cur[path[i]] || {}) };
    cur = cur[path[i]];
  }
  cur[path[path.length - 1]] = value;
  return clone;
}

function ColorRow({ label, value, onChange }: { label: string; value: string | undefined; onChange: (v: string) => void }) {
  const v = value ?? "";
  const hex = /^#[0-9a-f]{6}$/i.test(v);
  return (
    <div className="col" style={{ gap: 4 }}>
      <span className="small muted" style={{ fontWeight: 600 }}>{label}</span>
      <div className="color-row">
        <input type="color" value={hex ? v : "#888888"} onChange={(e) => onChange(e.target.value)} aria-label={`${label} colour`} disabled={!hex && v !== ""} />
        <input type="text" value={v} onChange={(e) => onChange(e.target.value)} spellCheck={false} aria-label={`${label} value`} />
      </div>
    </div>
  );
}

function Range({ label, value, min, max, step = 1, onChange, unit = "" }: { label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void; unit?: string }) {
  return (
    <label className="field">
      <span className="row"><span className="grow">{label}</span><span>{value}{unit}</span></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} />
    </label>
  );
}

export default function ThemesPage() {
  const { name: routeName } = useParams();
  const nav = useNavigate();
  const settings = useStore(settingsStore);
  const { data: list, refetch } = useThemes();
  const { data: allFonts } = useFetch<string[]>("/api/themes/fonts");
  const wanted = routeName || settings.default_theme || "paper";
  // "auto" (the default for new videos) is not a theme file: open the first real one instead of an error
  const name = !routeName && list && !list.some((t) => t.name === wanted) ? (list.find((t) => t.name === "paper") ?? list[0])?.name ?? wanted : wanted;
  const saved = list?.find((t) => t.name === name) ?? null;
  const [draft, setDraft] = useState<Theme | null>(null);
  const [aspect, setAspect] = useState<Aspect>("9:16");
  const [saveAs, setSaveAs] = useState(false);
  const [newName, setNewName] = useState("");
  const [spec, setSpec] = useState<{ url: string; data: any } | null>(null);
  const [ready, setReady] = useState(false);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const frame = useRef<HTMLIFrameElement>(null);
  const t0 = useRef(0);
  const fileIn = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (saved) setDraft(JSON.parse(JSON.stringify(saved)));
  }, [saved?.name, list]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(() => !!draft && !!saved && JSON.stringify(draft) !== JSON.stringify(saved), [draft, saved]);

  // load the specimen composition (all fonts included) for the chosen theme + shape
  useEffect(() => {
    if (!name || !list?.some((t) => t.name === name)) return;
    setReady(false);
    get(`/api/specimen?theme=${encodeURIComponent(name)}&aspect=${encodeURIComponent(aspect)}`).then(setSpec).catch((e) => toast(e.message, "err"));
  }, [name, aspect, !!list]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const on = (e: MessageEvent) => {
      if (e.source !== frame.current?.contentWindow) return;
      if (e.data?.vt === "ready") {
        setReady(true);
        t0.current = 6.4; // a moment where the card, arrow and coins are all on screen
        setTime(6.4);
      }
      if (e.data?.vt === "time") setTime(e.data.t);
      if (e.data?.vt === "ended") setPlaying(false);
    };
    window.addEventListener("message", on);
    return () => window.removeEventListener("message", on);
  }, []);

  // push the draft theme into the live preview (no reload)
  useEffect(() => {
    if (!ready || !spec || !draft) return;
    const tm = setTimeout(() => {
      frame.current?.contentWindow?.postMessage({ vt: "data", data: { ...spec.data, theme: draft } }, "*");
      frame.current?.contentWindow?.postMessage({ vt: "seek", t: t0.current }, "*");
    }, 60);
    return () => clearTimeout(tm);
  }, [draft, ready, spec]);

  const set = (path: string[], v: any) => setDraft((d) => (d ? setIn(d, path, v) : d));
  const dur: number = spec?.data?.duration ?? 24;
  const box = aspect === "9:16" ? 300 : aspect === "1:1" ? 340 : 400;
  const sz = aspect === "9:16" ? { w: 1080, h: 1920 } : aspect === "1:1" ? { w: 1080, h: 1080 } : { w: 1920, h: 1080 };
  const scale = box / sz.w;

  const post2 = (m: any) => frame.current?.contentWindow?.postMessage(m, "*");
  const toggle = () => {
    if (playing) {
      post2({ vt: "pause" });
      setPlaying(false);
    } else {
      post2({ vt: "play", t: time >= dur - 0.1 ? 0 : time });
      setPlaying(true);
    }
  };

  const save = async () => {
    if (!draft) return;
    try {
      await put(`/api/themes/${name}`, draft);
      toast("Theme saved. Videos using it were updated.", "ok");
      refetch();
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };
  const create = async () => {
    if (!draft || !/^[a-z0-9][a-z0-9-]{0,40}$/.test(newName)) {
      toast("Use lowercase letters, digits and dashes for the name.", "err");
      return;
    }
    try {
      await post(`/api/themes/${name}/duplicate`, { new_name: newName, label: newName });
      await put(`/api/themes/${newName}`, { ...draft, label: newName });
      setSaveAs(false);
      await refetch();
      nav(`/themes/${newName}`);
      toast(`Saved as “${newName}”`, "ok");
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };
  const remove = async () => {
    try {
      await del(`/api/themes/${name}`);
      await refetch();
      nav("/themes/paper");
    } catch (e: any) {
      toast(e.message, "err", 7000);
    }
  };
  const importFile = async (f: File) => {
    const fd = new FormData();
    fd.append("file", f);
    const res = await fetch("/api/themes/import", { method: "POST", body: fd });
    const j = await res.json();
    if (!res.ok) return toast(typeof j.detail === "string" ? j.detail : "Not a valid theme file", "err", 7000);
    await refetch();
    nav(`/themes/${j.name}`);
    toast(`Imported “${j.name}”`, "ok");
  };

  const fontRow = (role: "headline" | "body" | "numeral" | "caption", label: string) => {
    if (!draft) return null;
    const stack = (draft.font as any)[role] ?? draft.font.headline;
    const latin = stack[0], bn = stack[1] ?? "Hind Siliguri";
    return (
      <div key={role} className="row wrap" style={{ gap: 10 }}>
        <span style={{ width: 90, fontWeight: 600 }}>{label}</span>
        <label className="field grow"><span>English / numerals</span>
          <select value={latin} onChange={(e) => set(["font", role], [e.target.value, bn])}>{(allFonts || [latin]).map((f) => <option key={f}>{f}</option>)}</select>
        </label>
        <label className="field grow"><span>Bangla</span>
          <select value={bn} onChange={(e) => set(["font", role], [latin, e.target.value])}>{BN_FONTS.map((f) => <option key={f}>{f}</option>)}</select>
        </label>
      </div>
    );
  };

  const isDefault = settings.default_theme === name;
  return (
    <div className="themes" style={{ height: "100%" }}>
      <section aria-label="Theme list">
        <div className="panel-head"><h3 className="grow">Looks</h3></div>
        {(list || []).map((t) => (
          <div key={t.name} className={`theme-item ${t.name === name ? "sel" : ""}`} onClick={() => nav(`/themes/${t.name}`)} tabIndex={0} role="button" onKeyDown={(e) => e.key === "Enter" && nav(`/themes/${t.name}`)}>
            <span className="swatches">{[t.color.bg, t.color.accent, t.color.accent2, t.color.ink].map((c, i) => <i key={i} style={{ background: c }} />)}</span>
            <span className="grow"><strong>{t.label || t.name}</strong>{BUILTIN.has(t.name) && <div className="small muted">built in</div>}</span>
            {settings.default_theme === t.name && <Star size={14} color="var(--accent)" fill="var(--accent)" aria-label="Default" />}
          </div>
        ))}
        <div className="col" style={{ padding: 12, gap: 8 }}>
          <button className="btn" onClick={() => fileIn.current?.click()}><Upload size={14} /> Import theme…</button>
          <input ref={fileIn} type="file" accept=".vttheme,.json,application/zip,application/json" hidden onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])} />
        </div>
      </section>

      <section className="ed" aria-label="Theme editor">
        {!draft ? <div className="muted">Loading…</div> : (
          <>
            <div className="row wrap">
              <h1 className="grow">{draft.label || draft.name}{dirty && <span className="chip warn" style={{ marginLeft: 10 }}>unsaved changes</span>}</h1>
              <button className="btn primary" disabled={!dirty || BUILTIN.has(name)} onClick={save} title={BUILTIN.has(name) ? "Built-in themes are read-only. Use Save as new." : ""}><Save size={14} /> Save</button>
              <button className="btn" onClick={() => { setNewName(BUILTIN.has(name) ? "" : name + "-2"); setSaveAs(true); }}><Copy size={14} /> Save as new…</button>
              <button className="btn" onClick={() => { settingsStore.set((s) => ({ ...s, default_theme: name })); put("/api/settings", { default_theme: name }).then(() => toast("Default theme set", "ok")); }} disabled={isDefault}><Star size={14} /> {isDefault ? "Default" : "Set as default"}</button>
              <a className="btn" href={`/api/themes/${name}/export`}><Download size={14} /> Export</a>
              {!BUILTIN.has(name) && <button className="btn danger" onClick={remove}><Trash2 size={14} /> Delete</button>}
            </div>
            {BUILTIN.has(name) && <div className="banner small"><span>This is a built-in theme. Change anything to try it out, then choose <strong>Save as new…</strong> to keep your version.</span></div>}

            <DesignStudio draft={draft} onApply={setDraft} onPatch={set} />

            <div className="group">
              <h3>Colours</h3>
              <div className="colors">
                {COLOR_LABELS.filter(([k]) => k !== "bg2" || ["gradient", "mesh", "aurora"].includes(draft.background.kind)).map(([k, l]) => (
                  <ColorRow key={k} label={l} value={(draft.color as any)[k]} onChange={(v) => set(["color", k], v)} />
                ))}
              </div>
              <div className="row wrap">
                {PAIRS.map(([a, b, l]) => {
                  const cr = contrastRatio((draft.color as any)[a] ?? "", (draft.color as any)[b] ?? draft.color.bg);
                  return cr ? <span key={l} className={`chip ${cr >= 4.5 ? "ok" : cr >= 3 ? "warn" : "err"}`} title="Contrast ratio. 4.5 or more is easy to read.">{l}: {cr.toFixed(1)}:1 {cr >= 4.5 ? "✓" : "low"}</span> : null;
                })}
              </div>
            </div>

            <div className="group">
              <h3>Fonts</h3>
              {ROLES.map(([k, l]) => fontRow(k, l))}
              <Field label="Headline weight">
                <select value={draft.font.headline_weight} onChange={(e) => set(["font", "headline_weight"], +e.target.value)}>
                  {[600, 700, 800].map((w) => <option key={w} value={w}>{w}</option>)}
                </select>
              </Field>
              <span className="small muted">Each text role uses an English font first and falls back to the Bangla font for Bangla letters, so mixed lines look consistent.</span>
            </div>

            <div className="group">
              <h3>Shape</h3>
              <div className="colors">
                <Range label="Corner radius" value={draft.shape.radius} min={0} max={48} onChange={(v) => set(["shape", "radius"], v)} unit="px" />
                <Range label="Border thickness" value={draft.shape.stroke} min={0} max={10} onChange={(v) => set(["shape", "stroke"], v)} unit="px" />
                <Range label="Shadow across" value={draft.shape.shadow.x} min={0} max={20} onChange={(v) => set(["shape", "shadow", "x"], v)} unit="px" />
                <Range label="Shadow down" value={draft.shape.shadow.y} min={0} max={20} onChange={(v) => set(["shape", "shadow", "y"], v)} unit="px" />
                <Range label="Shadow softness" value={draft.shape.shadow.blur ?? 0} min={0} max={60} onChange={(v) => set(["shape", "shadow", "blur"], v)} unit="px" />
                <Range label="Card tilt" value={draft.shape.card_tilt} min={-8} max={8} step={0.5} onChange={(v) => set(["shape", "card_tilt"], v)} unit="°" />
                <ColorRow label="Shadow colour" value={draft.shape.shadow.color} onChange={(v) => set(["shape", "shadow", "color"], v)} />
              </div>
            </div>

            <div className="group">
              <h3>Background &amp; motion</h3>
              <div className="row wrap" style={{ gap: 16 }}>
                <Field label="Background"><select value={draft.background.kind} onChange={(e) => set(["background", "kind"], e.target.value)}>{["paper", "flat", "gradient", "grid", "dots", "stripes", "checks", "waves", "rings", "mesh", "aurora"].map((k) => <option key={k}>{k}</option>)}</select></Field>
                <Field label="Motion"><select value={draft.motion.preset} onChange={(e) => set(["motion", "preset"], e.target.value)}><option value="snappy">Snappy</option><option value="smooth">Smooth</option><option value="bouncy">Bouncy</option></select></Field>
              </div>
              <div className="colors">
                <Range label="Paper grain" value={draft.background.grain} min={0} max={1} step={0.05} onChange={(v) => set(["background", "grain"], v)} />
                <label className="check" style={{ alignSelf: "end" }}><input type="checkbox" checked={draft.background.arcs} onChange={(e) => set(["background", "arcs"], e.target.checked)} /> Decorative arcs</label>
              </div>
            </div>

            <div className="group">
              <h3>Captions</h3>
              <div className="row wrap" style={{ gap: 16 }}>
                <Field label="Style"><select value={draft.caption.style} onChange={(e) => set(["caption", "style"], e.target.value)}><option value="box">Box</option><option value="pill">Pill</option><option value="underline">Plain + underline highlight</option><option value="none">No background</option></select></Field>
                <Field label="Reveal"><select value={draft.caption.reveal} onChange={(e) => set(["caption", "reveal"], e.target.value)}><option value="line">Whole line at once</option><option value="words">Word by word</option></select></Field>
              </div>
              <div className="colors">
                <Range label="Text size" value={draft.caption.size} min={36} max={84} onChange={(v) => set(["caption", "size"], v)} unit="px" />
                <Range label="Words per line (applies after saving)" value={draft.caption.words_per_line} min={3} max={9} onChange={(v) => set(["caption", "words_per_line"], v)} />
                <Range label="Distance from bottom, vertical" value={draft.caption.safe_bottom.portrait} min={60} max={520} onChange={(v) => set(["caption", "safe_bottom", "portrait"], v)} unit="px" />
                <Range label="Distance from bottom, wide" value={draft.caption.safe_bottom.landscape} min={20} max={240} onChange={(v) => set(["caption", "safe_bottom", "landscape"], v)} unit="px" />
              </div>
              <Field label="Currency symbol for coins"><input type="text" value={draft.currency} maxLength={3} onChange={(e) => set(["currency"], e.target.value)} style={{ width: 80 }} /></Field>
            </div>
          </>
        )}
      </section>

      <section className="pv" aria-label="Live specimen">
        <Seg value={aspect} onChange={setAspect} options={[{ value: "9:16", label: "9:16" }, { value: "1:1", label: "1:1" }, { value: "16:9", label: "16:9" }]} label="Preview shape" />
        <div className="phone" style={{ width: box, height: sz.h * scale }}>
          {spec && <iframe ref={frame} title="Theme specimen" src={spec.url + "?v=" + name} style={{ width: sz.w, height: sz.h, transform: `scale(${scale})` }} sandbox="allow-scripts allow-same-origin" />}
        </div>
        <div className="scrub" style={{ maxWidth: box }}>
          <button className="btn icon" onClick={toggle} aria-label={playing ? "Pause" : "Play"}>{playing ? <Pause size={16} /> : <Play size={16} />}</button>
          <input type="range" min={0} max={dur} step={0.05} value={time} onChange={(e) => { const t = +e.target.value; t0.current = t; setTime(t); setPlaying(false); post2({ vt: "seek", t }); }} aria-label="Seek" />
          <span className="small muted">{fmtTime(time)}</span>
        </div>
        <span className="small muted center" style={{ maxWidth: box }}>A sample video using every element. Changes show here instantly; Save keeps them.</span>
      </section>

      {saveAs && (
        <Modal title="Save as new theme" onClose={() => setSaveAs(false)} footer={<><button className="btn" onClick={() => setSaveAs(false)}>Cancel</button><button className="btn primary" onClick={create} disabled={!newName}>Save</button></>}>
          <Field label="Name" hint="Lowercase letters, digits and dashes, e.g. my-brand"><input type="text" value={newName} onChange={(e) => setNewName(e.target.value.toLowerCase())} autoFocus /></Field>
        </Modal>
      )}
    </div>
  );
}
