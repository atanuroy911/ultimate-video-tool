import { useEffect, useMemo, useRef, useState } from "react";

export interface Command {
  id: string;
  title: string;
  group: string;
  keys?: string;
  run: () => void;
  enabled?: boolean;
}

/** Ctrl/Cmd+K: every action in the editor, searchable. */
export default function CommandPalette({ commands, onClose }: { commands: Command[]; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => input.current?.focus(), []);
  const list = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return commands.filter((c) => c.enabled !== false && words.every((w) => (c.title + " " + c.group).toLowerCase().includes(w)));
  }, [q, commands]);
  useEffect(() => setI(0), [q]);
  const go = (c?: Command) => {
    if (!c) return;
    onClose();
    setTimeout(c.run, 0);
  };
  let lastGroup = "";
  return (
    <div className="cmdk-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="cmdk" role="dialog" aria-modal="true" aria-label="Command palette">
        <input
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Type a command…"
          aria-label="Search commands"
          role="combobox"
          aria-expanded
          aria-controls="cmdk-list"
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(list.length - 1, x + 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(0, x - 1)); }
            else if (e.key === "Enter") go(list[i]);
          }}
        />
        <ul id="cmdk-list" role="listbox">
          {list.length === 0 && <li className="grp">No matching command</li>}
          {list.map((c, k) => {
            const head = c.group !== lastGroup ? c.group : "";
            lastGroup = c.group;
            return (
              <li key={c.id} role="presentation">
                {head && <div className="grp">{head}</div>}
                <button role="option" aria-selected={k === i} onMouseEnter={() => setI(k)} onClick={() => go(c)}>
                  {c.title}
                  {c.keys && <small>{c.keys}</small>}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

export const SHORTCUTS: [string, string][] = [
  ["Space", "Play / pause"], ["← →", "Previous / next word"], ["J  K", "Previous / next scene"], ["E", "Edit the word at the playhead"], ["H", "Highlight the word"],
  ["R", "Ask the AI to redo this scene"], ["Ctrl+K", "Command palette"], ["Ctrl+Z / Ctrl+Shift+Z", "Undo / redo"], ["Ctrl+Enter", "Export"],
  ["Ctrl+wheel (timeline)", "Zoom around the pointer (pinch works too)"], ["V  B  N", "Timeline: select tool, blade tool, snapping"], ["Ctrl+B", "Split the voice at the playhead"],
  ["Delete", "Cut out the selected voice range (the gap closes)"], ["M", "Mute / unmute the selected voice range"], ["\\", "Fit the whole video in the timeline"], ["Drag on the voice", "Select a range"], ["Drag a clip edge", "Trim (inward cuts, outward brings a cut back)"], ["Alt while dragging", "Ignore snapping"], ["Drag a scene edge", "Move where a scene ends (snaps to sentences)"], ["Click the canvas", "Select the element under the pointer"], ["Esc", "Clear the selection"],
];
