// The keys that show and hide the editor's panes, the ones people know from VS Code (docs/plans/PLAN-WORKBENCH.MD, D14). Pure, so it is tested without a browser.
//   Ctrl+Shift+B library    Ctrl+Alt+B assistant    Ctrl+J timeline    Ctrl+Alt+I inspector    Ctrl+L the assistant's message box    Ctrl+Shift+P the command palette
// (Cmd for Ctrl on a Mac). Ctrl+B alone stays "split the selected clip" in the timeline, which is used far more than hiding the library. While a field has the keyboard only Ctrl+L and Ctrl+Shift+P work, so typing is never interrupted.
export type PaneAction = "library" | "assistant" | "timeline" | "inspector" | "focus-assistant" | "palette";

export interface KeyLike { key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean; shiftKey: boolean }

export function paneAction(e: KeyLike, typing: boolean): PaneAction | null {
  if (!(e.ctrlKey || e.metaKey)) return null;
  const k = e.key.toLowerCase();
  if (k === "l" && !e.altKey && !e.shiftKey) return "focus-assistant";
  if (k === "p" && e.shiftKey && !e.altKey) return "palette";
  if (typing) return null;
  if (k === "b" && e.shiftKey && !e.altKey) return "library";
  if (e.shiftKey) return null;
  if (k === "b" && e.altKey) return "assistant";
  if (k === "j" && !e.altKey) return "timeline";
  if (k === "i" && e.altKey) return "inspector";
  return null;
}
