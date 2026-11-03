import { useState } from "react";
import { useFetch } from "../hooks";
import type { StickCast } from "../types";
import { Seg } from "../ui";

/* The character editor: who plays each role (a stick figure, a cartoon character or an animal) and how they look.
   A change applies to the character in every scene, and the preview redraws. */
interface CastOptions {
  heads: string[];
  accessories: string[];
  heights: string[];
  hairs: string[];
  roles: string[];
  toons: { id: string; about: string }[];
  animals: { code: string; name: string }[];
}
type PlayedBy = "person" | "toon" | "emoji";

const emojiFromCode = (code?: string | null) => {
  try {
    return code ? String.fromCodePoint(...code.split("-").map((part) => parseInt(part, 16))) : "🐾";
  } catch {
    return "🐾";
  }
};
const DEFAULT_INK = "#1f2937";

function ColourField(props: { label: string; ariaLabel?: string; value?: string | null; fallback: string; onChange: (colour: string) => void }) {
  return (
    <label className="cast-colour">
      <input type="color" value={props.value || props.fallback} onChange={(e) => props.onChange(e.target.value)} aria-label={props.ariaLabel ?? props.label} />
      <span className="small">{props.label}</span>
    </label>
  );
}

function CharacterCard(props: { character: StickCast; options: CastOptions; onChange: (patch: Record<string, any>) => void }) {
  const { character, options, onChange } = props;
  const playedBy: PlayedBy = (character.kind as PlayedBy) || "person";
  const style = character.style ?? {};
  const changeStyle = (key: string, value: string) => onChange({ style: { [key]: value } });
  const [open, setOpen] = useState(false);
  const face = playedBy === "emoji" ? emojiFromCode(character.emoji) : playedBy === "toon" ? null : "🧍";

  return (
    <div className="el-card cast-card">
      <button type="button" className="cast-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {playedBy === "toon" && character.art ? <img src={`/bundled/cartoon/characters/${character.art}.svg`} alt="" className="cast-face" /> : <span className="cast-face" style={{ color: style.color || DEFAULT_INK }}>{face}</span>}
        <span className="col grow" style={{ gap: 0, textAlign: "left" }}>
          <strong className="bn">{character.name || character.id}</strong>
          <span className="small muted">{playedBy === "person" ? `Stick figure · ${style.height ?? "adult"}` : playedBy === "toon" ? `Cartoon · ${character.art ?? "choose"}` : `Animal · ${options.animals.find((a) => a.code === character.emoji)?.name ?? "choose"}`}</span>
        </span>
        <span className="small muted">{open ? "Done" : "Edit"}</span>
      </button>
      {open && (
        <div className="el-body col" style={{ gap: 12 }}>
          <input type="text" className="bn" aria-label={`Name of ${character.id}`} defaultValue={character.name ?? ""} placeholder="Name" maxLength={14}
            onBlur={(e) => e.target.value !== (character.name ?? "") && onChange({ name: e.target.value })} />
          <Seg<PlayedBy> value={playedBy} label="Played by" onChange={(kind) => onChange(kind === "toon" ? { kind, art: character.art ?? options.toons[0]?.id } : kind === "emoji" ? { kind, emoji: character.emoji ?? options.animals[0]?.code } : { kind })}
            options={[{ value: "person", label: "Stick figure" }, { value: "toon", label: "Cartoon" }, { value: "emoji", label: "Animal" }]} />

          {playedBy === "person" && (
            <>
              <Seg value={style.height ?? "adult"} label="Age" onChange={(v) => changeStyle("height", v)} options={options.heights.map((h) => ({ value: h, label: h === "child" ? "Child" : h === "elder" ? "Elder" : "Adult" }))} />
              <div className="row wrap" style={{ gap: 12 }}>
                <ColourField label="Lines" ariaLabel={`Colour of ${character.name || character.id}`} value={style.color} fallback={DEFAULT_INK} onChange={(c) => changeStyle("color", c)} />
                <ColourField label="Clothes" value={style.shirt} fallback="#3b82f6" onChange={(c) => changeStyle("shirt", c)} />
                <ColourField label="Skin" value={style.skin} fallback="#f2c9a0" onChange={(c) => changeStyle("skin", c)} />
              </div>
              <div className="cast-grid">
                <label className="field"><span>Head</span>
                  <select aria-label={`Head of ${character.id}`} value={style.head ?? "round"} onChange={(e) => changeStyle("head", e.target.value)}>{options.heads.map((h) => <option key={h} value={h}>{h}</option>)}</select>
                </label>
                <label className="field"><span>Hair</span>
                  <select aria-label={`Hair of ${character.id}`} value={style.hair ?? "none"} onChange={(e) => changeStyle("hair", e.target.value)}>{options.hairs.map((h) => <option key={h} value={h}>{h}</option>)}</select>
                </label>
                <label className="field"><span>Wears</span>
                  <select aria-label={`Accessory of ${character.id}`} value={style.accessory ?? "none"} onChange={(e) => changeStyle("accessory", e.target.value)}>{options.accessories.map((a) => <option key={a} value={a}>{a}</option>)}</select>
                </label>
              </div>
            </>
          )}

          {playedBy === "toon" && (
            <div className="cast-pick" role="radiogroup" aria-label="Cartoon character">
              {options.toons.map((toon) => (
                <button key={toon.id} type="button" role="radio" aria-checked={character.art === toon.id} className={character.art === toon.id ? "sel" : ""} onClick={() => onChange({ art: toon.id })} title={toon.about}>
                  <img src={`/bundled/cartoon/characters/${toon.id}.svg`} alt="" loading="lazy" />
                  <span className="small">{toon.id}</span>
                </button>
              ))}
            </div>
          )}

          {playedBy === "emoji" && (
            <div className="cast-pick animals" role="radiogroup" aria-label="Animal">
              {options.animals.map((animal) => (
                <button key={animal.code} type="button" role="radio" aria-checked={character.emoji === animal.code} className={character.emoji === animal.code ? "sel" : ""} onClick={() => onChange({ emoji: animal.code })} title={animal.name}>
                  <span className="cast-emoji">{emojiFromCode(animal.code)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CastEditor(props: { cast: StickCast[]; onChange: (characterId: string, patch: Record<string, any>) => void }) {
  const { data: options } = useFetch<CastOptions>("/api/cast-options");
  if (!options || !props.cast.length) return null;
  return (
    <div className="col" style={{ gap: 8 }} aria-label="Characters">
      {props.cast.map((character) => <CharacterCard key={character.id} character={character} options={options} onChange={(patch) => props.onChange(character.id, patch)} />)}
    </div>
  );
}
