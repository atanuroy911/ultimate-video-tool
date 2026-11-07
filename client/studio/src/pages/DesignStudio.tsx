import { Dices, RotateCcw, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post } from "../api";
import { toast } from "../store";
import type { Theme } from "../types";
import { Field, Seg } from "../ui";

interface Catalogue {
  styles: { key: string; label: string; about: string; background: string; animated: boolean; motion: string }[];
  palettes: { key: string; label: string; dark: boolean; colors: string[] }[];
  backgrounds: string[];
}

/** Pick a look (style) and colours (palette) and every combination is a complete, readable theme. Applies to the open draft live. */
export default function DesignStudio({ draft, onApply, onPatch }: { draft: Theme; onApply: (t: Theme) => void; onPatch: (path: string[], v: any) => void }) {
  const [cat, setCat] = useState<Catalogue | null>(null);
  const [mode, setMode] = useState<"all" | "light" | "dark">("all");
  const [previous, setPrevious] = useState<Theme | null>(null);
  const style = (draft as any).style as string | undefined;
  const palette = (draft as any).palette as string | undefined;

  useEffect(() => {
    get<Catalogue>("/api/design").then(setCat).catch((e) => toast(e.message, "err"));
  }, []);

  const keepIdentity = (t: Theme): Theme => ({ ...t, name: draft.name, label: draft.label, currency: draft.currency, caption: { ...t.caption, words_per_line: draft.caption.words_per_line } });

  const build = async (s: string, p: string) => {
    try {
      const t = await post<Theme>("/api/design/build", { style: s, palette: p });
      setPrevious(draft);
      onApply(keepIdentity(t));
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const surprise = async () => {
    try {
      const t = await get<Theme>(`/api/design/surprise?seed=${Math.floor(Math.random() * 1e6)}${mode === "all" ? "" : `&dark=${mode === "dark"}`}`);
      setPrevious(draft);
      onApply(keepIdentity(t));
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  if (!cat) return null;
  const palettes = cat.palettes.filter((p) => mode === "all" || (mode === "dark") === p.dark);
  return (
    <div className="group design-studio" aria-label="Look">
      <div className="row wrap">
        <h3 className="grow"><Wand2 size={16} style={{ verticalAlign: -2 }} /> Look</h3>
        <Seg value={mode} onChange={setMode} label="Palette brightness" options={[{ value: "all", label: "All" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
        <button className="btn" onClick={surprise}><Dices size={14} /> Surprise me</button>
        <button className="btn" disabled={!previous} onClick={() => { if (previous) { onApply(previous); setPrevious(null); } }}><RotateCcw size={14} /> Undo</button>
      </div>

      <span className="small muted" style={{ fontWeight: 600 }}>Look</span>
      <div className="ds-styles" role="listbox" aria-label="Styles">
        {cat.styles.map((s) => (
          <button key={s.key} type="button" role="option" aria-selected={style === s.key} className={`ds-style ${style === s.key ? "on" : ""}`} onClick={() => build(s.key, palette || (draft.color.bg < "#888888" ? "neon" : "marigold"))}>
            <strong>{s.label}</strong>
            <span className="small muted">{s.about}</span>
            <span className="row" style={{ gap: 6 }}>
              <span className="chip">{s.background}</span>
              {s.animated && <span className="chip accent">moving</span>}
            </span>
          </button>
        ))}
      </div>

      <span className="small muted" style={{ fontWeight: 600 }}>Colours</span>
      <div className="ds-palettes" role="listbox" aria-label="Palettes">
        {palettes.map((p) => (
          <button key={p.key} type="button" role="option" aria-selected={palette === p.key} className={`ds-palette ${palette === p.key ? "on" : ""}`} onClick={() => build(style || "brutalist", p.key)} title={p.label}>
            <span className="swatches">{p.colors.map((c, i) => <i key={i} style={{ background: c }} />)}</span>
            <span className="small">{p.label}</span>
          </button>
        ))}
      </div>

      <div className="row wrap" style={{ gap: 16 }}>
        <Field label="Background pattern">
          <select value={draft.background.kind} onChange={(e) => onPatch(["background", "kind"], e.target.value)}>{cat.backgrounds.map((k) => <option key={k}>{k}</option>)}</select>
        </Field>
        <label className="check" style={{ alignSelf: "end" }}>
          <input type="checkbox" checked={!!(draft.background as any).animated} onChange={(e) => onPatch(["background", "animated"], e.target.checked)} /> Moving background
        </label>
        <label className="field grow" style={{ minWidth: 160 }}>
          <span className="row"><span className="grow">Pattern strength</span><span>{Math.round(((draft.background as any).pattern ?? 0.5) * 100)}%</span></span>
          <input type="range" min={0} max={1} step={0.05} value={(draft.background as any).pattern ?? 0.5} onChange={(e) => onPatch(["background", "pattern"], +e.target.value)} />
        </label>
      </div>
      <span className="small muted">Pick a look, then a palette: every pair keeps text readable. Fine-tune anything below, then <strong>Save as new…</strong>.</span>
    </div>
  );
}
