import "../new-options.css";
import { MessageSquareText, AudioLines, Bot, Check, ChevronRight, Cpu, Eraser, Film, Gauge, Images, Languages, Laptop, MonitorPlay, Music, Palette, Play, Repeat, Server, Sparkles, Square, Subtitles, Terminal, Timer, Upload, Volume2, VolumeX, Wand2, X } from "lucide-react";
import { useEffect, useMemo, useRef, type ReactNode } from "react";

/* Every choice the New-video flow offers beyond the basics, as a tile on one overview and as its own page of big visual cards.
   Nothing here is a drop-down: a person picks by looking. "Automatic" is always the first card and says what it will do. */
export type OptionId = "language" | "style" | "edit" | "director" | "look" | "music" | "captions" | "voice" | "pace" | "cleanup" | "length" | "sfx" | "words" | "pictures" | "script";

export interface OptionsCtx {
  source: string | null;
  hasPicture: boolean;
  language: string; setLanguage: (v: any) => void; languageGuess: string;
  style: string; setStyle: (v: any) => void; styleTitle: string;
  recordingEdit: string; setRecordingEdit: (v: any) => void;
  director: string; setDirector: (v: string) => void; directors: { id: string; label: string; available: boolean; note: string }[];
  theme: string; setTheme: (v: string) => void; themes: { name: string; label?: string; color: { bg: string; accent: string; accent2: string; ink: string } }[];
  musicTrack: string; setMusicTrack: (v: string) => void; music: { id: string; title: string; mood: string; url: string }[]; previewingTrack: string | null; toggleTrackPreview: (t: { id: string; url: string }) => void;
  captions: string; setCaptions: (v: string) => void;
  pace: string; setPace: (v: any) => void;
  removeFillers: boolean; setRemoveFillers: (v: boolean) => void; removeRetakes: boolean; setRemoveRetakes: (v: boolean) => void;
  targetLength: string; setTargetLength: (v: any) => void;
  soundEffects: string; setSoundEffects: (v: any) => void;
  glossary: string; setGlossary: (v: string) => void;
  pictures: File[]; addPictures: () => void; removePicture: (i: number) => void;
  endCard: string; setEndCard: (v: string) => void;
  reviewScript: boolean; setReviewScript: (v: boolean) => void;
  voiceSummary: string;
  legacy: (id: "style" | "voice") => ReactNode;       // the style cards and the voice settings already exist as full pages
}

const CAPTION_LABELS: Record<string, string> = { auto: "Automatic", pop: "Bold short lines", theme: "Match the theme", word: "One word at a time", keyword: "Emphasize key words", box: "Boxed", pill: "Rounded background", underline: "Underline" };
const LANGUAGE_NAMES: Record<string, string> = { auto: "Automatic", bn: "বাংলা", en: "English" };
const EDIT_NAMES: Record<string, string> = { auto: "Automatic edit", subtitles: "Keep my video, add subtitles", screen: "Screen recording with graphics" };
const LENGTH_NAMES: Record<string, string> = { auto: "Automatic", keep: "Keep it all", "60": "About 60 seconds", "90": "About 90 seconds" };
const SFX_NAMES: Record<string, string> = { off: "None", subtle: "A little", normal: "Normal", rich: "Lots" };
const PACE_NAMES: Record<string, string> = { calm: "Calm", normal: "Normal", fast: "Fast" };

interface Def { id: OptionId; title: string; question: string; hint: string; icon: ReactNode; hue: number; show?: (c: OptionsCtx) => boolean; value: (c: OptionsCtx) => string; auto: (c: OptionsCtx) => boolean }

const DEFS: Def[] = [
  { id: "language", title: "Language", question: "What language is spoken?", hint: "Automatic listens to the first seconds and decides.", icon: <Languages size={20} />, hue: 205, value: (c) => LANGUAGE_NAMES[c.language] ?? c.language, auto: (c) => c.language === "auto" },
  { id: "style", title: "Style", question: "What should it look like?", hint: "The style decides what appears on screen while you speak.", icon: <Film size={20} />, hue: 275, value: (c) => c.styleTitle, auto: (c) => c.style === "auto" },
  { id: "edit", title: "Edit this recording", question: "How much should we change your recording?", hint: "Your picture and pauses can stay exactly as they are.", icon: <MonitorPlay size={20} />, hue: 190, show: (c) => c.hasPicture, value: (c) => EDIT_NAMES[c.recordingEdit] ?? c.recordingEdit, auto: (c) => c.recordingEdit === "auto" },
  { id: "director", title: "Director", question: "Who directs this video?", hint: "The director reads the whole script and decides what every moment shows.", icon: <Bot size={20} />, hue: 255, value: (c) => c.directors.find((d) => d.id === c.director)?.label ?? "Best available", auto: (c) => c.director === "best" },
  { id: "look", title: "Look", question: "Pick the colours and type.", hint: "Colours, fonts and the feel of titles.", icon: <Palette size={20} />, hue: 330, value: (c) => (c.theme === "auto" ? "Automatic" : c.themes.find((t) => t.name === c.theme)?.label ?? c.theme), auto: (c) => c.theme === "auto" },
  { id: "music", title: "Music", question: "Which music sits under your voice?", hint: "It lowers by itself while someone speaks. You can fine-tune the level later in the editor.", icon: <Music size={20} />, hue: 20, value: (c) => (c.musicTrack === "auto" ? "Automatic" : c.musicTrack === "" ? "No music" : c.music.find((m) => m.id === c.musicTrack)?.title ?? c.musicTrack), auto: (c) => c.musicTrack === "auto" },
  { id: "captions", title: "Captions", question: "How should the words appear?", hint: "Each card shows the real look.", icon: <Subtitles size={20} />, hue: 45, value: (c) => CAPTION_LABELS[c.captions] ?? c.captions, auto: (c) => c.captions === "auto" },
  { id: "voice", title: "AI voice", question: "Who reads your script?", hint: "", icon: <Volume2 size={20} />, hue: 160, show: (c) => c.source === "script", value: (c) => c.voiceSummary, auto: (c) => /^(Best|Automatic)/.test(c.voiceSummary) },
  { id: "pace", title: "Pace", question: "How quickly should it move?", hint: "How fast scenes change and how tightly pauses are trimmed.", icon: <Gauge size={20} />, hue: 120, value: (c) => PACE_NAMES[c.pace] ?? c.pace, auto: (c) => c.pace === "normal" },
  { id: "cleanup", title: "Clean up speech", question: "What should we cut from the talk?", hint: "Everything cut can be put back in the editor.", icon: <Eraser size={20} />, hue: 0, value: (c) => (c.removeFillers && c.removeRetakes ? "Fillers and retakes" : c.removeFillers ? "Fillers only" : c.removeRetakes ? "Retakes only" : "Nothing"), auto: (c) => c.removeFillers && c.removeRetakes },
  { id: "length", title: "Length", question: "How long should the video be?", hint: "Automatic shortens a long vertical video to about a minute.", icon: <Timer size={20} />, hue: 230, value: (c) => LENGTH_NAMES[c.targetLength] ?? c.targetLength, auto: (c) => c.targetLength === "auto" },
  { id: "sfx", title: "Sound effects", question: "How many sound effects?", hint: "Whooshes for moving pictures, ticks for lists, hits for big moments.", icon: <AudioLines size={20} />, hue: 300, value: (c) => SFX_NAMES[c.soundEffects] ?? c.soundEffects, auto: (c) => c.soundEffects === "normal" },
  { id: "words", title: "Words to get right", question: "Names and unusual words", hint: "Speech recognition can mishear them. List them and they are spelled your way.", icon: <Wand2 size={20} />, hue: 90, value: (c) => (c.glossary.trim() ? `${c.glossary.split(/[,\n]/).filter((s) => s.trim()).length} word(s)` : "None"), auto: (c) => !c.glossary.trim() },
  { id: "script", title: "Director’s script", question: "Review what the director planned?", hint: "The director plans every scene first. You can read it, change options and send feedback before anything is polished.", icon: <MessageSquareText size={20} />, hue: 250, value: (c) => (c.reviewScript ? "Review it first" : "Straight to the editor"), auto: (c) => !c.reviewScript },
  { id: "pictures", title: "Your own pictures", question: "Add pictures of your own", hint: "Name a file after a word you say and it appears when that word is spoken.", icon: <Images size={20} />, hue: 175, value: (c) => (c.pictures.length ? `${c.pictures.length} added` : "None"), auto: (c) => !c.pictures.length },
];

export const optionDef = (id: OptionId) => DEFS.find((d) => d.id === id)!;
const tint = (hue: number) => ({ "--h": hue } as React.CSSProperties);

/* ------------------------------------------------------------------ overview: one tile per choice */
/** Plain sentences about what will really happen with the choices made so far, so nothing is a surprise after Create. */
function plan(c: OptionsCtx): string[] {
  const who = c.directors.find((d) => d.id === c.director)?.label ?? "The best available director";
  const lines: string[] = [];
  if (c.hasPicture && c.recordingEdit === "subtitles") lines.push("Your picture and pauses stay exactly as recorded. No director plans scenes; captions are added.");
  else if (c.hasPicture && c.recordingEdit === "screen") lines.push(`Your picture stays whole. ${who} adds titles and callouts on top.`);
  else if (c.hasPicture && c.recordingEdit === "auto") lines.push(`A screen recording is kept as recorded (no director). A person talking to the camera is edited normally by ${who}.`);
  else lines.push(`${who} plans every scene. If it is unavailable the next one in your fallback order is used, and the video says which one did.`);
  lines.push(c.reviewScript ? "You review the director’s script before anything is made." : "The video is made straight away; the script can still be reviewed later.");
  lines.push(`Music: ${c.musicTrack === "" ? "none" : c.musicTrack === "auto" ? "picked to fit the words" : c.music.find((m) => m.id === c.musicTrack)?.title ?? c.musicTrack}. Sound effects: ${(SFX_NAMES[c.soundEffects] ?? c.soundEffects).toLowerCase()}. Captions: ${(CAPTION_LABELS[c.captions] ?? c.captions).toLowerCase()}.`);
  return lines;
}

export function OptionsHub({ c, onOpen }: { c: OptionsCtx; onOpen: (id: OptionId) => void }) {
  const defs = DEFS.filter((d) => !d.show || d.show(c));
  return (
    <section className="opt-hub" aria-label="Choices for this video">
      <div className="opt-hub-head"><strong>Make it yours</strong><span>Tap any tile to see your options. Anything on Automatic is chosen for you.</span></div>
      <ul className="opt-plan" aria-label="What will happen"><li className="opt-plan-h">What will happen</li>{plan(c).map((l) => <li key={l}>{l}</li>)}</ul>
      <div className="opt-tiles">
        {defs.map((d) => (
          <button key={d.id} type="button" className="opt-tile" style={tint(d.hue)} onClick={() => onOpen(d.id)}>
            <span className="opt-tile-icon" aria-hidden>{d.icon}</span>
            <span className="opt-tile-text">
              <span className="opt-tile-title">{d.title}</span>
              <span className="opt-tile-value">{d.value(c)}</span>
            </span>
            {d.auto(c) ? <span className="opt-auto"><Sparkles size={11} aria-hidden /> Auto</span> : <span className="opt-yours">Yours</span>}
            <ChevronRight size={16} className="opt-chev" aria-hidden />
          </button>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ building blocks */
function Card({ selected, onPick, title, about, visual, disabled, tag }: { selected: boolean; onPick: () => void; title: string; about?: string; visual: ReactNode; disabled?: boolean; tag?: string }) {
  return (
    <button type="button" role="radio" aria-checked={selected} disabled={disabled} className={`vcard${selected ? " sel" : ""}`} onClick={onPick}>
      <span className="vcard-visual" aria-hidden>{visual}</span>
      <span className="vcard-title">{title}{tag && <em>{tag}</em>}</span>
      {about && <span className="vcard-about">{about}</span>}
      {selected && <span className="vcard-check" aria-hidden><Check size={14} /></span>}
    </button>
  );
}
const Grid = ({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) => <div className={`vgrid${wide ? " wide" : ""}`} role="radiogroup" aria-label={label}>{children}</div>;
const Glyph = ({ children, hue }: { children: ReactNode; hue: number }) => <span className="vglyph" style={tint(hue)}>{children}</span>;

/* a small frame showing the real caption look */
function CaptionFrame({ kind }: { kind: string }) {
  if (kind === "auto") return <span className="cap-frame"><Sparkles size={26} /><small>The best look for this video</small></span>;
  return (
    <span className={`cap-frame cap-${kind}`}>
      <span className="cap-scene" />
      {kind === "word" ? <b className="cap-text">COUNT</b> : <span className="cap-text">Make every <b>word</b> count</span>}
    </span>
  );
}

function Bars({ n }: { n: number }) {
  return <span className="sfx-bars">{Array.from({ length: 6 }, (_, i) => <i key={i} className={i < n ? "on" : ""} style={{ height: `${30 + ((i * 37) % 60)}%` }} />)}</span>;
}

function directorVisual(id: string): { icon: ReactNode; where: string } {
  if (id === "best") return { icon: <Sparkles size={26} />, where: "Recommended" };
  if (id === "local") return { icon: <Cpu size={26} />, where: "Runs on the server" };
  if (id === "claude-server") return { icon: <Server size={26} />, where: "Claude on the server" };
  if (id.startsWith("claude@") || id === "claude-client") return { icon: <Laptop size={26} />, where: "Claude on this computer" };
  if (id.startsWith("codex")) return { icon: <Terminal size={26} />, where: "Codex" };
  return { icon: <Bot size={26} />, where: "" };
}

/** The same director choice on New and Direct again. */
export function DirectorChoices({value,onChange,directors,onShortcut}:{value:string;onChange:(id:string)=>void;directors:OptionsCtx["directors"];onShortcut?:(pick:()=>void)=>void}) {
 return <Grid label="Director" wide>{directors.map(d=>{
   const v=directorVisual(d.id);
   if(d.available) onShortcut?.(()=>onChange(d.id));
   return <Card key={d.id} selected={value===d.id} disabled={!d.available} onPick={()=>onChange(d.id)} title={d.id==="best"?"Best available":d.label} tag={v.where||undefined} about={d.available?d.note:`Not available: ${d.note}`} visual={<Glyph hue={255}>{v.icon}</Glyph>}/>;
 })}</Grid>;
}

/* ------------------------------------------------------------------ one page per choice */
export function OptionPage({ id, c }: { id: OptionId; c: OptionsCtx }) {
  const filesFor = useMemo(() => c.pictures.map((f) => URL.createObjectURL(f)), [c.pictures]);
  useEffect(() => () => filesFor.forEach(URL.revokeObjectURL), [filesFor]);
  const trackBox = useRef<HTMLDivElement>(null);

  switch (id) {
    case "language":
      return (
        <>
          {c.languageGuess && <p className="vnote">{c.languageGuess}</p>}
          <Grid label="Language">
            <Card selected={c.language === "auto"} onPick={() => c.setLanguage("auto")} title="Automatic" about="Listens to the first seconds and decides." visual={<Glyph hue={205}><Sparkles size={28} /></Glyph>} />
            <Card selected={c.language === "en"} onPick={() => c.setLanguage("en")} title="English" visual={<Glyph hue={205}><b className="vbig">Aa</b></Glyph>} />
            <Card selected={c.language === "bn"} onPick={() => c.setLanguage("bn")} title="বাংলা" about="Bangla, including English words mixed in." visual={<Glyph hue={205}><b className="vbig">অ</b></Glyph>} />
          </Grid>
        </>
      );
    case "style":
      return <>{c.legacy("style")}{c.style === "reel" && <label className="field" style={{ marginTop: 18 }}>Closing line (optional)<input value={c.endCard} maxLength={40} onChange={(e) => c.setEndCard(e.target.value)} placeholder="e.g. Save this for later" /><span className="small muted">Shown over the last picture. Leave blank to keep only your script.</span></label>}</>;
    case "edit":
      return (
        <Grid label="Edit this recording" wide>
          <Card selected={c.recordingEdit === "auto"} onPick={() => c.setRecordingEdit("auto")} title="Automatic edit" about="The app decides: tidy a talking person, or protect a screen recording." visual={<Glyph hue={190}><Wand2 size={28} /></Glyph>} />
          <Card selected={c.recordingEdit === "subtitles"} onPick={() => c.setRecordingEdit("subtitles")} title="Keep my video" tag="Safest" about="Your picture and pauses stay exactly as recorded. Subtitles are added." visual={<Glyph hue={190}><Subtitles size={28} /></Glyph>} />
          <Card selected={c.recordingEdit === "screen"} onPick={() => c.setRecordingEdit("screen")} title="Screen recording + graphics" about="Your picture stays whole. Titles and callouts appear on top where they help." visual={<Glyph hue={190}><MonitorPlay size={28} /></Glyph>} />
        </Grid>
      );
    case "director":
      return <DirectorChoices value={c.director} onChange={c.setDirector} directors={c.directors}/>;
    case "look":
      return (
        <Grid label="Look">
          <Card selected={c.theme === "auto"} onPick={() => c.setTheme("auto")} title="Automatic" about="Picked to suit the words." visual={<span className="swatch-strip">{["#f26a1f", "#35e0ff", "#12a36b", "#7c4dff"].map((x) => <i key={x} style={{ background: x }} />)}</span>} />
          {c.themes.filter((t) => !t.name.startsWith("auto-")).map((t) => (
            <Card key={t.name} selected={c.theme === t.name} onPick={() => c.setTheme(t.name)} title={t.label || t.name} visual={
              <span className="look-frame" style={{ background: t.color.bg, color: t.color.ink }}><b style={{ color: t.color.accent }}>Title</b><i style={{ background: t.color.accent2 }} /><small>Subtitle line</small></span>} />
          ))}
        </Grid>
      );
    case "music":
      return (
        <>
          <Grid label="Music">
            <Card selected={c.musicTrack === "auto"} onPick={() => c.setMusicTrack("auto")} title="Automatic" about="A track that fits the mood of the words." visual={<Glyph hue={20}><Sparkles size={28} /></Glyph>} />
            <Card selected={c.musicTrack === ""} onPick={() => c.setMusicTrack("")} title="No music" about="Voice and sound effects only." visual={<Glyph hue={20}><VolumeX size={28} /></Glyph>} />
          </Grid>
          {c.music.length > 0 && <h3 className="vsub">Or choose a track</h3>}
          <div className="tracklist" ref={trackBox} role="radiogroup" aria-label="Tracks">
            {c.music.map((m) => (
              <div key={m.id} className={`track${c.musicTrack === m.id ? " sel" : ""}`}>
                <button type="button" className="track-play" aria-label={c.previewingTrack === m.id ? `Stop ${m.title}` : `Listen to ${m.title}`} onClick={() => c.toggleTrackPreview({ id: m.id, url: m.url })}>{c.previewingTrack === m.id ? <Square size={14} /> : <Play size={14} />}</button>
                <button type="button" role="radio" aria-checked={c.musicTrack === m.id} className="track-pick" onClick={() => c.setMusicTrack(m.id)}>
                  <span className="track-title">{m.title}</span><span className="track-mood">{m.mood}</span>
                  {c.musicTrack === m.id && <Check size={16} />}
                </button>
              </div>
            ))}
          </div>
        </>
      );
    case "captions":
      return (
        <Grid label="Captions" wide>
          {Object.entries(CAPTION_LABELS).map(([v, label]) => (
            <Card key={v} selected={c.captions === v} onPick={() => c.setCaptions(v)} title={label} visual={<CaptionFrame kind={v} />} />
          ))}
        </Grid>
      );
    case "voice":
      return <>{c.legacy("voice")}</>;
    case "pace":
      return (
        <Grid label="Pace">
          <Card selected={c.pace === "calm"} onPick={() => c.setPace("calm")} title="Calm" about="Longer scenes, room to breathe." visual={<Glyph hue={120}><span className="pace pace-1"><i /><i /><i /></span></Glyph>} />
          <Card selected={c.pace === "normal"} onPick={() => c.setPace("normal")} title="Normal" tag="Default" about="A natural rhythm." visual={<Glyph hue={120}><span className="pace pace-2"><i /><i /><i /><i /></span></Glyph>} />
          <Card selected={c.pace === "fast"} onPick={() => c.setPace("fast")} title="Fast" about="Quick cuts, tight pauses." visual={<Glyph hue={120}><span className="pace pace-3"><i /><i /><i /><i /><i /><i /></span></Glyph>} />
        </Grid>
      );
    case "cleanup":
      return (
        <div className="vgrid wide">
          <ToggleCard on={c.removeFillers} set={c.setRemoveFillers} icon={<Eraser size={26} />} title="Remove “um”, “uh” and long pauses" about="Tightens the talk without changing what you said." />
          <ToggleCard on={c.removeRetakes} set={c.setRemoveRetakes} icon={<Repeat size={26} />} title="Keep the best take" about="When you repeat a line, only the last take stays." />
        </div>
      );
    case "length":
      return (
        <Grid label="Length">
          <Card selected={c.targetLength === "auto"} onPick={() => c.setTargetLength("auto")} title="Automatic" about="Shortens a long vertical video to about a minute." visual={<Glyph hue={230}><Sparkles size={28} /></Glyph>} />
          <Card selected={c.targetLength === "keep"} onPick={() => c.setTargetLength("keep")} title="Keep it all" about="Nothing is shortened." visual={<Glyph hue={230}><b className="vbig">All</b></Glyph>} />
          <Card selected={c.targetLength === "60"} onPick={() => c.setTargetLength("60")} title="About 60 seconds" about="The best parts, tightened." visual={<Glyph hue={230}><b className="vbig">60s</b></Glyph>} />
          <Card selected={c.targetLength === "90"} onPick={() => c.setTargetLength("90")} title="About 90 seconds" about="A little more room." visual={<Glyph hue={230}><b className="vbig">90s</b></Glyph>} />
        </Grid>
      );
    case "sfx":
      return (
        <Grid label="Sound effects">
          <Card selected={c.soundEffects === "off"} onPick={() => c.setSoundEffects("off")} title="None" about="Voice and music only." visual={<Glyph hue={300}><Bars n={0} /></Glyph>} />
          <Card selected={c.soundEffects === "subtle"} onPick={() => c.setSoundEffects("subtle")} title="A little" about="Only big moments and transitions." visual={<Glyph hue={300}><Bars n={2} /></Glyph>} />
          <Card selected={c.soundEffects === "normal"} onPick={() => c.setSoundEffects("normal")} title="Normal" tag="Default" about="A sound for each thing that appears." visual={<Glyph hue={300}><Bars n={4} /></Glyph>} />
          <Card selected={c.soundEffects === "rich"} onPick={() => c.setSoundEffects("rich")} title="Lots" about="Also ticks for every list item and risers." visual={<Glyph hue={300}><Bars n={6} /></Glyph>} />
        </Grid>
      );
    case "script":
      return (
        <Grid label="Director's script" wide>
          <Card selected={!c.reviewScript} onPick={() => c.setReviewScript(false)} title="Straight to the editor" tag="Default" about="Make the video, then open the editor. You can still ask for changes there." visual={<Glyph hue={250}><Sparkles size={28} /></Glyph>} />
          <Card selected={c.reviewScript} onPick={() => c.setReviewScript(true)} title="Let me review the script first" about="After the director plans, read it scene by scene, change options and send feedback in rounds until you approve." visual={<Glyph hue={250}><MessageSquareText size={28} /></Glyph>} />
        </Grid>
      );
    case "words":
      return (
        <div className="vpanel">
          <label className="field">Words separated by commas
            <textarea rows={4} value={c.glossary} onChange={(e) => c.setGlossary(e.target.value)} placeholder="Atanu, RARL, Kubernetes, Ollama" />
          </label>
          <p className="small muted">Write a name the way it should be spelled. To fix a specific mishearing, write <code>heard=right</code>, for example <code>yield=ইয়েল্ড</code>.</p>
        </div>
      );
    case "pictures":
      return (
        <div className="vpanel">
          <button type="button" className="dropzone" onClick={c.addPictures}><Upload size={26} /><strong>{c.pictures.length ? "Add more pictures" : "Choose pictures"}</strong><span className="small muted">Photos, screenshots or logos from your computer</span></button>
          {c.pictures.length > 0 && (
            <div className="thumbs">
              {c.pictures.map((f, i) => (
                <figure key={i} className="thumb">
                  {/\.(mp4|mov|webm|mkv)$/i.test(f.name) ? <span className="thumb-video"><Film size={22} /></span> : <img src={filesFor[i]} alt="" />}
                  <figcaption title={f.name}>{f.name}</figcaption>
                  <button type="button" className="thumb-x" aria-label={`Remove ${f.name}`} onClick={() => c.removePicture(i)}><X size={13} /></button>
                </figure>
              ))}
            </div>
          )}
        </div>
      );
  }
}

function ToggleCard({ on, set, icon, title, about }: { on: boolean; set: (v: boolean) => void; icon: ReactNode; title: string; about: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} className={`vcard toggle${on ? " sel" : ""}`} onClick={() => set(!on)}>
      <span className="vcard-visual" aria-hidden><Glyph hue={on ? 150 : 0}>{icon}</Glyph></span>
      <span className="vcard-title">{title}<em>{on ? "On" : "Off"}</em></span>
      <span className="vcard-about">{about}</span>
      <span className="vswitch" aria-hidden><i /></span>
    </button>
  );
}

