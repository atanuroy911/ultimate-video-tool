// The code of a code-native shot, beside its preview (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C4). CodeMirror 6, bundled (nothing from the network).
// Saving sends the code to the server, which checks it has a timed root before it replaces the old one; the visual edits are kept apart and stay.
import { html as htmlLang } from "@codemirror/lang-html";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { basicSetup } from "codemirror";
import { useEffect, useRef, useState } from "react";

export default function ShotCode({ code, onSave, dark }: { code: string; onSave: (code: string) => Promise<boolean>; dark: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const saveRef = useRef(onSave);
  saveRef.current = onSave;
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const savedText = useRef(code);

  const save = async () => {
    const v = view.current;
    if (!v || busy) return true;
    const text = v.state.doc.toString();
    if (text === savedText.current) return true;
    setBusy(true);
    const ok = await saveRef.current(text);
    setBusy(false);
    if (ok) { savedText.current = text; setDirty(false); }
    return true;
  };
  const saveCmd = useRef(save);
  saveCmd.current = save;

  useEffect(() => {
    if (!host.current) return;
    const v = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: code,
        extensions: [
          basicSetup,
          htmlLang(),
          keymap.of([{ key: "Mod-s", preventDefault: true, run: () => { saveCmd.current(); return true; } }]),
          EditorView.updateListener.of((u) => { if (u.docChanged) setDirty(u.state.doc.toString() !== savedText.current); }),
          EditorView.theme({ "&": { height: "100%", fontSize: "13px" }, ".cm-scroller": { fontFamily: "var(--font-mono)" } }, { dark }),
        ],
      }),
    });
    view.current = v;
    return () => { v.destroy(); view.current = null; };
    // The editor is made once per shot; a new shot gets a new component (key).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="shot-code">
      <div className="shot-code-bar">
        <span className="small muted">{busy ? "Checking and saving…" : dirty ? "Not saved: Ctrl+S saves" : "Saved"}</span>
        <button className="btn sm" disabled={!dirty || busy} onClick={save}>Save code</button>
      </div>
      <div className="shot-code-editor" ref={host} aria-label="The shot's code" />
    </div>
  );
}
