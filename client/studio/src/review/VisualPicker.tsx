import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { get } from "../api";
import { PackIcon } from "../ui";

interface Visual {
  id: string;
  kind: "icon" | "sticker";
  label: string;
  label_bn?: string;
  emoji?: string;
  svg?: string;
  inner?: string;
}

function Glyph({ v, size = 26 }: { v: Visual; size?: number }) {
  if (v.svg) return <span style={{ width: size, height: size, display: "inline-grid" }} dangerouslySetInnerHTML={{ __html: v.svg.replace("<svg", `<svg width="${size}" height="${size}"`) }} />;
  return <PackIcon inner={v.inner} size={size} />;
}

/** Search the whole visual library by meaning (English, Bangla, ...). kind decides what the value is: a sticker's hex key or a line-icon id. */
export default function VisualPicker({ value, onChange, kind, label }: { value: string; onChange: (v: string) => void; kind: "icon" | "sticker"; label: string }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Visual[]>([]);
  const [current, setCurrent] = useState<Visual | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    if (!value) {
      setCurrent(null);
      return;
    }
    get(`/api/visuals/get?ids=${encodeURIComponent(value)}`)
      .then((r) => live && setCurrent(r[value] ?? null))
      .catch(() => live && setCurrent(null));
    return () => {
      live = false;
    };
  }, [value]);

  useEffect(() => {
    if (!q.trim()) {
      setHits([]);
      return;
    }
    let live = true;
    setBusy(true);
    const t = setTimeout(() => {
      get(`/api/visuals/search?q=${encodeURIComponent(q)}&kind=${kind}&limit=18`)
        .then((r) => live && setHits(r))
        .catch(() => live && setHits([]))
        .finally(() => live && setBusy(false));
    }, 300);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q, kind]);

  const pick = (v: Visual) => onChange(kind === "sticker" ? v.id.replace("emoji:", "") : v.id);

  return (
    <div className="field">
      <span className="row">
        <span className="grow">{label}</span>
        {value && (
          <button type="button" className="btn sm ghost" onClick={() => onChange("")} aria-label={`Remove ${label}`}>
            <X size={13} /> None
          </button>
        )}
      </span>
      {current && (
        <div className="row" style={{ gap: 10 }}>
          <Glyph v={current} size={34} />
          <span className="small muted" style={{ fontWeight: 400 }}>{current.label}{current.label_bn ? ` · ${current.label_bn}` : ""}</span>
        </div>
      )}
      <div style={{ position: "relative" }}>
        <Search size={14} style={{ position: "absolute", left: 9, top: 11, color: "var(--muted)" }} />
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by meaning, e.g. stone, পাথর, savings" style={{ paddingLeft: 30 }} aria-label={`Search ${label}`} />
      </div>
      {q.trim() && (
        <div className="icon-grid" role="listbox" aria-label={`${label} results`} aria-busy={busy}>
          {hits.map((h) => (
            <button key={h.id} type="button" className={current?.id === h.id ? "on" : ""} title={h.label} aria-label={h.label} onClick={() => pick(h)}>
              <Glyph v={h} />
            </button>
          ))}
          {!busy && hits.length === 0 && <span className="small muted" style={{ gridColumn: "1 / -1", padding: 8 }}>Nothing found</span>}
        </div>
      )}
    </div>
  );
}
