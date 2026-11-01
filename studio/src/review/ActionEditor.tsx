import { useState } from "react";
import { ChevronDown, ChevronRight, MessageSquare, Play, Plus, Smile, Sparkles, Trash2, User, Wand2 } from "lucide-react";
import type { StickAction, StickCast } from "../types";
import type { Review } from "./useReview";
import { Seg } from "../ui";

export interface VerbCategory {
  name: string;
  verbs: { id: string; label: string; desc: string; icon?: string }[];
}

export const VERB_CATEGORIES: VerbCategory[] = [
  {
    name: "Gestures",
    verbs: [
      { id: "explain", label: "Explain", desc: "Open palms, talking with hands" },
      { id: "point", label: "Point", desc: "Points toward target, prop or viewer" },
      { id: "wave", label: "Wave", desc: "Waves hand hello/goodbye" },
      { id: "wave_both", label: "Wave both", desc: "Waves both arms: look here!" },
      { id: "think", label: "Think", desc: "Hand on chin, thought mark" },
      { id: "nod", label: "Nod", desc: "Nods head yes" },
      { id: "shake_head", label: "Shake head", desc: "Shakes head no" },
      { id: "shrug", label: "Shrug", desc: "Open palms: unsure / whatever" },
      { id: "facepalm", label: "Facepalm", desc: "Hand on forehead: oops" },
      { id: "count", label: "Count", desc: "Counts on fingers (1 to 5)" },
      { id: "bow", label: "Bow", desc: "Bows politely" },
      { id: "clap", label: "Clap", desc: "Claps hands excitedly" },
    ],
  },
  {
    name: "Expressions",
    verbs: [
      { id: "say", label: "Say (Speech)", desc: "Speech bubble with mouth moving" },
      { id: "react", label: "Emotion react", desc: "Shows feeling with face and body" },
      { id: "celebrate", label: "Celebrate", desc: "Cheering with both arms up" },
      { id: "laugh", label: "Laugh", desc: "Laughs out loud, shaking shoulders" },
      { id: "cry", label: "Cry", desc: "Hands to face, crying" },
      { id: "argue", label: "Argue", desc: "Shakes fist and shouts" },
      { id: "dance", label: "Dance", desc: "Dances with knees swinging" },
      { id: "yawn", label: "Yawn", desc: "Yawns and stretches" },
      { id: "mark", label: "Emote mark", desc: "Pops icon above head (!, ?, 💡, ❤️, 💢)" },
    ],
  },
  {
    name: "Movement",
    verbs: [
      { id: "walk_in", label: "Walk in", desc: "Enters from side into scene" },
      { id: "walk_to", label: "Walk to", desc: "Walks to horizontal position" },
      { id: "walk_out", label: "Walk out", desc: "Exits off screen to a side" },
      { id: "run", label: "Run", desc: "Runs faster, leaning forward" },
      { id: "chase", label: "Chase", desc: "Runs after someone/something" },
      { id: "sneak", label: "Sneak", desc: "Tiptoes low and quietly" },
      { id: "jump", label: "Jump", desc: "Jumps up in the air" },
      { id: "fall", label: "Trip & Fall", desc: "Trips and falls on floor" },
      { id: "sit", label: "Sit down", desc: "Sits down on prop or floor" },
      { id: "stand", label: "Stand up", desc: "Stands back up" },
      { id: "turn", label: "Turn", desc: "Turns left or right" },
      { id: "idle", label: "Idle / Stand", desc: "Stands naturally and breathes" },
    ],
  },
  {
    name: "Props & Signs",
    verbs: [
      { id: "hold_sign", label: "Hold sign", desc: "Holds up sign with text or number" },
      { id: "write_board", label: "Write on board", desc: "Writes text onto board/chart" },
      { id: "phone", label: "Phone", desc: "Holds phone to ear" },
      { id: "type", label: "Type", desc: "Types on laptop or keyboard" },
      { id: "eat", label: "Eat / Drink", desc: "Brings hand/mug to mouth" },
      { id: "carry", label: "Carry prop", desc: "Picks up and carries prop" },
      { id: "drop", label: "Put down", desc: "Puts carried prop down" },
      { id: "lift", label: "Lift heavy", desc: "Strains to lift something heavy" },
      { id: "give", label: "Give prop", desc: "Hands prop to another character" },
      { id: "throw", label: "Throw prop", desc: "Throws prop toward a spot" },
    ],
  },
  {
    name: "Interaction",
    verbs: [
      { id: "look_at", label: "Look at", desc: "Turns head toward target" },
      { id: "high_five", label: "High five", desc: "High-fives another character" },
      { id: "handshake", label: "Handshake", desc: "Shakes hands with another" },
      { id: "hug", label: "Hug", desc: "Hugs another character" },
      { id: "push", label: "Push", desc: "Pushes character or prop" },
      { id: "pull", label: "Pull", desc: "Pulls character or prop" },
      { id: "hide", label: "Hide", desc: "Ducks behind a prop" },
      { id: "peek", label: "Peek", desc: "Leans out to look" },
      { id: "bounce", label: "Bounce", desc: "Bounces up and down" },
      { id: "spin", label: "Spin", desc: "Spins around" },
    ],
  },
];

const ALL_VERBS = VERB_CATEGORIES.flatMap((c) => c.verbs);
const VERB_MAP = new Map(ALL_VERBS.map((v) => [v.id, v]));

const EMOTIONS = [
  { value: "neutral", label: "Neutral" },
  { value: "happy", label: "Happy" },
  { value: "sad", label: "Sad" },
  { value: "thinking", label: "Thinking" },
  { value: "angry", label: "Angry" },
  { value: "surprised", label: "Surprised" },
];

const MARKS = [
  { value: "exclamation", label: "❗ Exclamation" },
  { value: "question", label: "❓ Question" },
  { value: "bulb", label: "💡 Lightbulb" },
  { value: "heart", label: "❤️ Heart" },
  { value: "anger", label: "💢 Anger" },
  { value: "sweat", label: "💧 Sweat" },
  { value: "zzz", label: "💤 Zzz" },
];

export default function ActionEditor(props: {
  sceneId: string;
  cast: StickCast[];
  actions: StickAction[];
  words: { id: string; text: string; start: number }[];
  playheadWord?: string | null;
  r: Review;
}) {
  const { sceneId, cast, actions, words, playheadWord, r } = props;
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);

  // Form state for new action
  const [newWho, setNewWho] = useState(cast[0]?.id || "maya");
  const [newDo, setNewDo] = useState("explain");
  const [newWord, setNewWord] = useState(playheadWord && words.some((w) => w.id === playheadWord) ? playheadWord : words[0]?.id || "");
  const [newBubble, setNewBubble] = useState("");
  const [newEmotion, setNewEmotion] = useState("happy");
  const [newCategory, setNewCategory] = useState("Gestures");

  const wordMap = new Map(words.map((w) => [w.id, w.text]));

  const handleAdd = () => {
    if (!newWord) return;
    const actionPayload: Record<string, any> = {
      who: newWho,
      do: newDo,
      at_word: newWord,
    };
    if (newDo === "say" || newDo === "hold_sign" || newDo === "write_board") {
      actionPayload.bubble = newBubble.trim() || wordMap.get(newWord) || "Hello!";
    }
    if (newDo === "react") {
      actionPayload.emotion = newEmotion;
    }
    if (newDo === "walk_in") {
      actionPayload.from = "left";
      actionPayload.to = 0.45;
    }

    r.addAction(sceneId, actionPayload);
    setAdding(false);
    setNewBubble("");
  };

  const verbNeedsBubble = (verb: string) => verb === "say" || verb === "hold_sign" || verb === "write_board";
  const verbNeedsEmotion = (verb: string) => verb === "react";
  const verbNeedsTarget = (verb: string) =>
    verb === "point" || verb === "look_at" || verb === "high_five" || verb === "handshake" || verb === "hug" || verb === "push" || verb === "pull" || verb === "give" || verb === "throw";

  return (
    <div className="col action-editor" style={{ gap: 10 }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h3>Stick Actions & Poses ({actions.length})</h3>
        <button
          type="button"
          className="btn sm primary"
          onClick={() => {
            if (playheadWord && words.some((w) => w.id === playheadWord)) {
              setNewWord(playheadWord);
            }
            setAdding((v) => !v);
          }}
        >
          <Plus size={14} /> Add Action
        </button>
      </div>

      {adding && (
        <div className="card card-pad col" style={{ gap: 10, border: "1.5px solid var(--accent)", background: "var(--accent-soft)" }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <strong>New Animation Action</strong>
            <button type="button" className="btn ghost sm" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>

          <div className="row wrap" style={{ gap: 8 }}>
            <label className="field grow">
              <span>Who</span>
              <select value={newWho} onChange={(e) => setNewWho(e.target.value)}>
                {cast.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name || c.id}
                  </option>
                ))}
              </select>
            </label>

            <label className="field grow">
              <span>At word</span>
              <select value={newWord} onChange={(e) => setNewWord(e.target.value)}>
                {words.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.text} ({w.start.toFixed(1)}s)
                  </option>
                ))}
              </select>
            </label>

            {playheadWord && words.some((w) => w.id === playheadWord) && (
              <button
                type="button"
                className="btn sm"
                style={{ alignSelf: "flex-end" }}
                onClick={() => setNewWord(playheadWord)}
                title="Anchor at word currently under playhead"
              >
                At Playhead
              </button>
            )}
          </div>

          <div className="col" style={{ gap: 4 }}>
            <span className="small muted">Pose / Verb Category</span>
            <div className="row wrap" style={{ gap: 4 }}>
              {VERB_CATEGORIES.map((cat) => (
                <button
                  key={cat.name}
                  type="button"
                  className={`chip ${newCategory === cat.name ? "accent" : ""}`}
                  onClick={() => {
                    setNewCategory(cat.name);
                    const first = cat.verbs[0];
                    if (first) setNewDo(first.id);
                  }}
                >
                  {cat.name}
                </button>
              ))}
            </div>
          </div>

          <label className="field">
            <span>Action Pose</span>
            <select value={newDo} onChange={(e) => setNewDo(e.target.value)}>
              {(VERB_CATEGORIES.find((c) => c.name === newCategory)?.verbs || ALL_VERBS).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label} — {v.desc}
                </option>
              ))}
            </select>
          </label>

          {verbNeedsBubble(newDo) && (
            <label className="field">
              <span>{newDo === "hold_sign" ? "Sign Text" : newDo === "write_board" ? "Board Text" : "Speech Bubble Text"}</span>
              <input
                type="text"
                value={newBubble}
                onChange={(e) => setNewBubble(e.target.value)}
                placeholder={wordMap.get(newWord) || "What they say or show…"}
                maxLength={70}
              />
            </label>
          )}

          {verbNeedsEmotion(newDo) && (
            <label className="field">
              <span>Emotion</span>
              <select value={newEmotion} onChange={(e) => setNewEmotion(e.target.value)}>
                {EMOTIONS.map((em) => (
                  <option key={em.value} value={em.value}>
                    {em.label}
                  </option>
                ))}
              </select>
            </label>
          )}

          <button type="button" className="btn primary" onClick={handleAdd}>
            <Wand2 size={14} /> Add Stickman Animation
          </button>
        </div>
      )}

      {actions.length === 0 && !adding && (
        <div className="small muted" style={{ padding: "8px 0" }}>
          No stick animations defined for this scene. Click &ldquo;Add Action&rdquo; to make characters walk, talk, point, or react!
        </div>
      )}

      {actions.map((act, idx) => {
        const isOpen = openIndex === idx;
        const verbInfo = VERB_MAP.get(act.do);
        const anchorText = wordMap.get(act.at_word) || act.at_word;

        return (
          <div key={idx} className={`el-card ${isOpen ? "picked" : ""}`} style={{ padding: "8px 12px" }}>
            <div
              className="row"
              style={{ alignItems: "center", gap: 8, cursor: "pointer" }}
              onClick={() => setOpenIndex(isOpen ? null : idx)}
            >
              {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <span className="chip" style={{ fontWeight: 600 }}>
                {act.who}
              </span>
              <strong style={{ fontSize: 13 }}>{verbInfo?.label || act.do.replace("_", " ")}</strong>
              <span className="muted small bn grow" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                at &ldquo;{anchorText}&rdquo;{act.bubble ? ` · “${act.bubble}”` : act.target ? ` → ${act.target}` : ""}
              </span>
              <button
                type="button"
                className="btn ghost icon sm"
                aria-label={`Delete action ${act.do}`}
                onClick={(e) => {
                  e.stopPropagation();
                  r.patchAction(sceneId, idx, { delete: true });
                }}
              >
                <Trash2 size={13} />
              </button>
            </div>

            {isOpen && (
              <div className="col" style={{ gap: 8, marginTop: 10, paddingTop: 8, borderTop: "1px solid var(--border)" }}>
                <div className="row wrap" style={{ gap: 8 }}>
                  <label className="field grow">
                    <span>Character</span>
                    <select
                      value={act.who}
                      onChange={(e) => r.patchAction(sceneId, idx, { patch: { who: e.target.value } })}
                    >
                      {cast.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name || c.id}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="field grow">
                    <span>Anchor Word</span>
                    <select
                      value={act.at_word}
                      onChange={(e) => r.patchAction(sceneId, idx, { patch: { at_word: e.target.value } })}
                    >
                      {words.map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.text} ({w.start.toFixed(1)}s)
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <label className="field">
                  <span>Pose / Action (Verb)</span>
                  <select
                    value={act.do}
                    onChange={(e) => r.patchAction(sceneId, idx, { patch: { do: e.target.value } })}
                  >
                    {VERB_CATEGORIES.map((cat) => (
                      <optgroup key={cat.name} label={cat.name}>
                        {cat.verbs.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.label} — {v.desc}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </label>

                {verbNeedsBubble(act.do) && (
                  <label className="field">
                    <span>Bubble / Sign Text</span>
                    <input
                      type="text"
                      defaultValue={act.bubble || ""}
                      placeholder="What should be written in the bubble?"
                      maxLength={70}
                      onBlur={(e) => r.patchAction(sceneId, idx, { patch: { bubble: e.target.value } })}
                    />
                  </label>
                )}

                {verbNeedsEmotion(act.do) && (
                  <label className="field">
                    <span>Emotion</span>
                    <select
                      value={act.emotion || "happy"}
                      onChange={(e) => r.patchAction(sceneId, idx, { patch: { emotion: e.target.value } })}
                    >
                      {EMOTIONS.map((em) => (
                        <option key={em.value} value={em.value}>
                          {em.label}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {verbNeedsTarget(act.do) && (
                  <label className="field">
                    <span>Target (Character or Prop)</span>
                    <input
                      type="text"
                      defaultValue={act.target || ""}
                      placeholder="e.g. hero, maya, board, desk..."
                      maxLength={24}
                      onBlur={(e) => r.patchAction(sceneId, idx, { patch: { target: e.target.value } })}
                    />
                  </label>
                )}

                {act.do === "mark" && (
                  <label className="field">
                    <span>Mark</span>
                    <select
                      value={act.mark || "exclamation"}
                      onChange={(e) => r.patchAction(sceneId, idx, { patch: { mark: e.target.value } })}
                    >
                      {MARKS.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {act.do === "walk_in" && (
                  <div className="row" style={{ gap: 8 }}>
                    <label className="field grow">
                      <span>From side</span>
                      <select
                        value={act.from || "left"}
                        onChange={(e) => r.patchAction(sceneId, idx, { patch: { from: e.target.value } })}
                      >
                        <option value="left">Left</option>
                        <option value="right">Right</option>
                      </select>
                    </label>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      <span className="small muted">
        💡 Tip: You can also drag any action chip horizontally on the Timeline to re-time it to another spoken word.
      </span>
    </div>
  );
}
