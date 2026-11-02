import { Minus, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { ComponentSpec, El, MediaItem } from "../types";
import { PackIcon } from "../ui";
import VisualPicker from "./VisualPicker";

export interface WordLite {
  id: string;
  text: string;
  start: number;
}

type Schema = Record<string, any>;

/** Resolve $ref / anyOf (Optional) to the concrete schema. */
function resolve(s: Schema, defs: Schema): Schema {
  if (!s) return {};
  if (s.$ref) return resolve(defs[s.$ref.split("/").pop() as string] || {}, defs);
  if (s.allOf?.length === 1) return resolve(s.allOf[0], defs);
  if (s.anyOf) {
    const nn = s.anyOf.find((x: Schema) => x.type !== "null");
    return { ...resolve(nn, defs), title: s.title, description: s.description, default: s.default };
  }
  return s;
}

/** A valid starting value for a schema (used for "add item"). */
export function blank(s0: Schema, defs: Schema): any {
  const s = resolve(s0, defs);
  if (s.default !== undefined && s.default !== null) return JSON.parse(JSON.stringify(s.default));
  if (s.enum) return s.enum[0];
  switch (s.type) {
    case "string":
      return "";
    case "integer":
    case "number":
      return s.minimum ?? 0;
    case "array":
      return Array.from({ length: s.minItems ?? 0 }, () => blank(s.items, defs));
    case "object": {
      const o: Record<string, any> = {};
      for (const k of s.required || []) o[k] = blank(s.properties?.[k], defs);
      return o;
    }
  }
  return null;
}

const label = (k: string) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

interface Ctx {
  media?:MediaItem[];
  defs: Schema;
  words: WordLite[];
  icons: Record<string, string>;
  playheadWord: string | null;
  componentType: string;
  startsAt?: number;
}

function IconPicker({ value, onChange, icons, allowCoin }: { value: string; onChange: (v: string) => void; icons: Record<string, string>; allowCoin: boolean }) {
  const [q, setQ] = useState("");
  const names = useMemo(() => Object.keys(icons).filter((n) => n.includes(q.toLowerCase())), [icons, q]);
  return (
    <div className="col" style={{ gap: 6 }}>
      <div style={{ position: "relative" }}>
        <Search size={14} style={{ position: "absolute", left: 9, top: 11, color: "var(--muted)" }} />
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search icons (selected: ${value})`} style={{ paddingLeft: 30 }} aria-label="Search icons" />
      </div>
      <div className="icon-grid" role="listbox" aria-label="Icons">
        {allowCoin && (
          <button type="button" className={value === "coin" ? "on" : ""} onClick={() => onChange("coin")} title="coin" aria-label="coin" style={{ fontWeight: 800 }}>
            ৳
          </button>
        )}
        {names.map((n) => (
          <button key={n} type="button" className={value === n ? "on" : ""} onClick={() => onChange(n)} title={n} aria-label={n} aria-selected={value === n}>
            <PackIcon inner={icons[n]} />
          </button>
        ))}
      </div>
    </div>
  );
}

function Counter({ value, max }: { value: string; max?: number }) {
  if (!max) return null;
  const n = [...value].length;
  return <span className="small" style={{ color: n > max ? "var(--err)" : n > max * 0.8 ? "var(--warn)" : "var(--muted)", fontWeight: 400 }}>{n}/{max}</span>;
}

function Node({ k, schema, value, onChange, ctx }: { k: string; schema: Schema; value: any; onChange: (v: any) => void; ctx: Ctx }) {
  const s = resolve(schema, ctx.defs);

  if (k === "at_word" || k === "until_word") {
    const ending = k === "until_word";
    const choices = ending ? ctx.words.filter(w => w.start >= (ctx.startsAt ?? 0)) : ctx.words;
    return (
      <label className="field">
        <span>{ending ? "Disappear after" : "Appear at"}</span>
        <div className="row">
          <select aria-label={ending ? "Disappear after word" : "Appear at word"} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} className="bn">
            {ending && <option value="">Automatically — when this sentence finishes</option>}
            {value && !ctx.words.some((w) => w.id === value) && <option value={value}>Word outside this scene</option>}
            {choices.map((w) => (
              <option key={w.id} value={w.id}>
                {w.text} · {w.start.toFixed(1)}s
              </option>
            ))}
          </select>
          <button type="button" className="btn sm" disabled={!choices.some(w => w.id === ctx.playheadWord)} onClick={() => ctx.playheadWord && onChange(ctx.playheadWord)} title="Use the word at the current video position">
            Use current word
          </button>
        </div>
      </label>
    );
  }

  if ((k === "emoji" && (ctx.componentType === "sticker" || ctx.componentType === "keyword")) || (k === "icon" && ctx.componentType === "keyword")
      || (k === "name" && ctx.componentType === "icon")) {
    return <VisualPicker value={value ?? ""} onChange={(v) => onChange(v || undefined)} kind={k === "emoji" ? "sticker" : "icon"} label={k === "emoji" ? "Sticker" : "Line icon"} />;
  }

  if ((k === "name" && ctx.componentType === "icon") || (k === "icon" && ctx.componentType === "icon_row")) {
    return (
      <div className="field">
        <span>Icon</span>
        <IconPicker value={value} onChange={onChange} icons={ctx.icons} allowCoin={ctx.componentType === "icon_row"} />
      </div>
    );
  }

  if(k === "media") return <label className="field"><span>Picture or video</span><select value={value??""} onChange={e=>onChange(e.target.value||null)}><option value="">Choose a file…</option>{(ctx.media??[]).map(m=><option key={m.id} value={m.id}>{m.caption||m.file} ({m.kind})</option>)}</select></label>;
  if (s.enum) {
    return (
      <label className="field">
        <span>{label(k)}</span>
        <select value={value ?? s.enum[0]} onChange={(e) => onChange(e.target.value)}>
          {s.enum.map((o: string) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (k === "color" && s.pattern?.includes("0-9a-fA-F")) {
    return <label className="field"><span>Color</span><input type="color" value={/^#[0-9a-f]{6}$/i.test(value) ? value : "#6366f1"} onChange={e => onChange(e.target.value)}/></label>;
  }
  if (k === "width" && ctx.componentType === "shape") {
    return <label className="field"><span>Size · {Math.round((value ?? .65)*100)}%</span><input type="range" min={10} max={100} step={1} value={Math.round((value ?? .65)*100)} onChange={e => onChange(Number(e.target.value)/100)}/></label>;
  }
  if (s.type === "string") {
    const v = value ?? "";
    const long = (s.maxLength ?? 0) > 50;
    return (
      <label className="field">
        <span className="row">
          <span className="grow">{label(k)}</span>
          <Counter value={v} max={s.maxLength} />
        </span>
        {long ? (
          <textarea rows={2} value={v} onChange={(e) => onChange(e.target.value)} className="bn" />
        ) : (
          <input type="text" value={v} onChange={(e) => onChange(e.target.value)} className="bn" />
        )}
        {s.description && <span className="small muted" style={{ fontWeight: 400 }}>{s.description}</span>}
      </label>
    );
  }

  if (s.type === "integer" || s.type === "number") {
    return (
      <label className="field">
        <span>{label(k)}</span>
        <div className="row">
          {s.type === "integer" && s.minimum != null && s.maximum != null && s.maximum - s.minimum <= 12 && (
            <>
              <button type="button" className="btn sm icon" aria-label="Decrease" onClick={() => onChange(Math.max(s.minimum, (value ?? 0) - 1))}>
                <Minus size={14} />
              </button>
              <strong style={{ minWidth: 24, textAlign: "center" }}>{value}</strong>
              <button type="button" className="btn sm icon" aria-label="Increase" onClick={() => onChange(Math.min(s.maximum, (value ?? 0) + 1))}>
                <Plus size={14} />
              </button>
            </>
          )}
          {!(s.type === "integer" && s.minimum != null && s.maximum != null && s.maximum - s.minimum <= 12) && (
            <input type="number" value={value ?? 0} min={s.minimum} max={s.maximum} step={s.type === "integer" ? 1 : "any"} onChange={(e) => onChange(e.target.value === "" ? 0 : +e.target.value)} />
          )}
        </div>
      </label>
    );
  }

  if (s.type === "array") {
    const items: any[] = value ?? [];
    const item = resolve(s.items, ctx.defs);
    const min = s.minItems ?? 0;
    const max = s.maxItems ?? 12;
    return (
      <div className="field">
        <span className="row">
          <span className="grow">{label(k)}</span>
          <span className="small muted" style={{ fontWeight: 400 }}>{items.length}/{max}</span>
        </span>
        <div className="col" style={{ gap: 8 }}>
          {items.map((it, i) => (
            <div key={i} className="row" style={{ alignItems: "flex-start" }}>
              <div className="grow">
                {item.type === "object" ? (
                  <div className="sub">
                    <ObjectFields schema={item} value={it} onChange={(v) => onChange(items.map((x, j) => (j === i ? v : x)))} ctx={ctx} />
                  </div>
                ) : (
                  <input type="text" className="bn" value={it} maxLength={item.maxLength} onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))} aria-label={`${label(k)} ${i + 1}`} />
                )}
              </div>
              <button type="button" className="btn sm icon ghost" disabled={items.length <= min} aria-label={`Remove item ${i + 1}`} onClick={() => onChange(items.filter((_, j) => j !== i))}>
                <Minus size={14} />
              </button>
            </div>
          ))}
          <button type="button" className="btn sm" disabled={items.length >= max} onClick={() => onChange([...items, blank(s.items, ctx.defs)])}>
            <Plus size={14} /> Add
          </button>
        </div>
      </div>
    );
  }

  if (s.type === "object") {
    return (
      <div className="field">
        <span>{label(k)}</span>
        <div className="sub">
          <ObjectFields schema={s} value={value ?? {}} onChange={onChange} ctx={ctx} />
        </div>
      </div>
    );
  }
  return null;
}

function ObjectFields({ schema, value, onChange, ctx }: { schema: Schema; value: Record<string, any>; onChange: (v: any) => void; ctx: Ctx }) {
  const props = schema.properties || {};
  return (
    <>
      {Object.keys(props)
        .filter((k) => k !== "type" && k !== "id")
        .map((k) => (
          <Node key={k} k={k} schema={props[k]} value={value[k]} onChange={(v) => onChange({ ...value, [k]: v })} ctx={ctx} />
        ))}
    </>
  );
}

export default function SchemaForm(props: {
  media?:MediaItem[];
  spec: ComponentSpec;
  value: El;
  words: WordLite[];
  icons: Record<string, string>;
  playheadWord: string | null;
  onChange: (v: El) => void;
}) {
  const ctx: Ctx = { media:props.media, defs: props.spec.defs, words: props.words, icons: props.icons, playheadWord: props.playheadWord, componentType: props.spec.type, startsAt: props.words.find(w => w.id === props.value.at_word)?.start };
  const fields = props.spec.fields;
  // Content first; timing follows it, expressed in words and seconds rather than internal IDs.
  const keys = [...Object.keys(fields).filter(k => !["edited","at_word","until_word","start","end","x","y","scale","rotation","opacity"].includes(k)), "at_word", ...(fields.until_word ? ["until_word"] : [])];
  return (
    <div className="col" style={{ gap: 12 }}>
      {keys.map((k) => (
        <Node key={k} k={k} schema={fields[k] || { type: "string" }} value={(props.value as any)[k]} onChange={(v) => {
          const next = { ...props.value, [k]: v };
          if (k === "at_word") next.start = null;
          if (k === "until_word") next.end = null;
          if (k === "at_word" && next.until_word) {
            const start = props.words.find(w => w.id === v)?.start ?? 0;
            const end = props.words.find(w => w.id === next.until_word)?.start ?? Infinity;
            if (end < start) next.until_word = null;
          }
          props.onChange(next);
        }} ctx={ctx} />
      ))}
    </div>
  );
}
