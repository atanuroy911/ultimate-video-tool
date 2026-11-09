import { ChevronLeft, Folder, FolderPlus, HardDrive } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post } from "../api";
import { Spinner } from "../ui";

/* A folder box with Browse. The folders listed are on the computer that makes the videos (GET /api/setup/folders), which may not be the one
   showing this window, so a native dialog would show the wrong disk. Only folder names are listed, never files. */
interface Listing { path: string; parent: string; folders: { name: string; path: string }[]; roots: { path: string; name: string; free_gb: number }[]; free_gb: number; writable: boolean }

export default function FolderPicker({ value, placeholder, onChange, label, where }: { value: string; placeholder: string; onChange: (v: string) => void; label: string; where: string }) {
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState<Listing | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState<string | null>(null);
  const [free, setFree] = useState<number | null>(null);

  const go = async (path: string) => {
    setBusy(true); setError("");
    try { setAt(await get<Listing>(`/api/setup/folders?path=${encodeURIComponent(path)}`)); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => {                                                        // the free space under the folder shown in the box, as it is typed or chosen
    const p = value || placeholder;
    const timer = setTimeout(() => get<Listing>(`/api/setup/folders?path=${encodeURIComponent(p)}`).then((l) => setFree(l.free_gb)).catch(() => setFree(null)), 300);
    return () => clearTimeout(timer);
  }, [value, placeholder]);
  const make = async () => {
    if (!at || !newName?.trim()) return;
    try { setAt(await post<Listing>("/api/setup/folders", { parent: at.path, name: newName })); setNewName(null); }
    catch (e: any) { setError(e.errors?.[0] || e.message); }
  };

  return (
    <div className="folder-pick">
      <div className="folder-pick-box">
        <input type="text" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} aria-label={label} spellCheck={false} />
        <button type="button" className="btn sm" onClick={() => { const o = !open; setOpen(o); if (o) go(value || placeholder); }} aria-expanded={open}>{open ? "Close" : "Browse…"}</button>
      </div>
      {free !== null && free > 0 && <span className="small muted">{free.toFixed(0)} GB free on that drive.</span>}
      {open && (
        <div className="folder-pick-panel" role="group" aria-label={`Folders on ${where}`}>
          {at && (
            <div className="folder-pick-drives">
              {at.roots.map((r) => (
                <button key={r.path} type="button" className={`chip ${at.path.toLowerCase().startsWith(r.path.toLowerCase()) ? "on" : ""}`} onClick={() => go(r.path)} title={`${r.free_gb.toFixed(0)} GB free`}>
                  <HardDrive size={13} /> {r.name} <span className="muted">· {r.free_gb.toFixed(0)} GB free</span>
                </button>
              ))}
            </div>
          )}
          {at?.path && (
            <div className="folder-pick-here">
              <button type="button" className="btn sm ghost" disabled={!at.parent || busy} onClick={() => go(at.parent)} aria-label="Up one folder"><ChevronLeft size={15} /></button>
              <span className="folder-pick-path" title={at.path}>{at.path}</span>
              {busy && <Spinner size={14} />}
            </div>
          )}
          {error && <p className="small" role="alert" style={{ color: "var(--err)", margin: 0 }}>{error}</p>}
          {at?.path && (
            <ul className="folder-pick-list">
              {at.folders.length === 0 && <li className="small muted">No folders in here.</li>}
              {at.folders.map((f) => (
                <li key={f.path}><button type="button" onClick={() => go(f.path)}><Folder size={15} /> {f.name}</button></li>
              ))}
            </ul>
          )}
          {at?.path && (
            <div className="folder-pick-actions">
              {newName === null
                ? <button type="button" className="btn sm ghost" onClick={() => setNewName("Video Tool")} disabled={!at.writable}><FolderPlus size={14} /> New folder</button>
                : <span className="row" style={{ gap: 6 }}><input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && make()} aria-label="New folder name" autoFocus style={{ width: 160 }} /><button type="button" className="btn sm" onClick={make}>Make</button><button type="button" className="btn sm ghost" onClick={() => setNewName(null)}>Cancel</button></span>}
              <span className="grow" />
              {!at.writable && <span className="small" style={{ color: "var(--warn)" }}>Video Tool can't save here.</span>}
              <button type="button" className="btn sm primary" disabled={!at.writable} onClick={() => { onChange(at.path); setOpen(false); }}>Use this folder</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
