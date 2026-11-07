import { CheckSquare, Film, MoreHorizontal, Plus, Search, Square, Trash2, UserSquare, Mic, Type, Download, Filter } from "lucide-react";
import { openFolder } from "../openFolder";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { del, fmtTime, patch, post } from "../api";
import { MenuItem, MenuSep, Popover } from "../ds";
import { useFetch } from "../hooks";
import { useT } from "../i18n";
import { jobsStore, onChanged, toast, useStore } from "../store";
import type { ProjectSummary } from "../types";
import { Modal, ProgressBar, Spinner } from "../ui";
import RedoModal from "../components/RedoModal";

/* The dashboard: always-visible search + filter + batch-select bar, then every video as a cover. */
const LAST_OPENED = "vt-last-project";

const timeAgo = (iso?: string | null) => {
  if (!iso) return "";
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  if (seconds < 86400 * 7) return `${Math.floor(seconds / 86400)} d ago`;
  return iso.slice(0, 10);
};
const isBusy = (project: ProjectSummary) => project.status === "processing" || !!project.active_job;
/** The video is still being made (not just a download being rendered): only then does opening it show progress. A finished video that is exporting opens in the editor. */
export const isBeingMade = (project: ProjectSummary) => ["processing", "interrupted", "cancelled"].includes(project.status) || (!!project.active_job && project.active_job.kind !== "export");
const MODE_ICON: Record<string, React.ReactNode> = { talking_head: <UserSquare size={12} />, audio: <Mic size={12} />, script: <Type size={12} /> };

function statusLine(project: ProjectSummary, jobFraction: number | null, t: (key: string) => string): { text: string; tone: "" | "ok" | "warn" | "err" } {
  if (isBusy(project)) return { text: jobFraction != null ? `${t("dash.making")} ${Math.round(jobFraction * 100)}%` : t("dash.making"), tone: "" };
  if (project.status === "interrupted") return { text: "Interrupted · open to continue", tone: "warn" };
  if (project.status === "cancelled") return { text: "Stopped · open to continue", tone: "warn" };
  if (project.status === "error") return { text: t("dash.error"), tone: "err" };
  if (project.pending_requests > 0) return { text: "Waiting for Claude", tone: "warn" };
  if (project.export_count > 0) return { text: `${t("dash.ready")} · ${t("dash.edited")} ${timeAgo(project.updated_at || project.created_at)}`, tone: "ok" };
  if (project.scene_count > 0) return { text: `${t("dash.not_exported")} · ${t("dash.edited")} ${timeAgo(project.updated_at || project.created_at)}`, tone: "" };
  return { text: `Added ${timeAgo(project.created_at)}`, tone: "" };
}

type StatusFilter = "all" | "ready" | "processing" | "error" | "draft";
type AspectFilter = "all" | "9:16" | "16:9" | "1:1";

export default function ProjectsPage() {
  const t = useT();
  const nav = useNavigate();
  const { data, loading, error, refetch } = useFetch<ProjectSummary[]>("/api/projects");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [aspectFilter, setAspectFilter] = useState<AspectFilter>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selecting, setSelecting] = useState(false);
  const [filtersOpen,setFiltersOpen]=useState(false);
  const [toDelete, setToDelete] = useState<ProjectSummary | null>(null);
  const [toBatchDelete, setToBatchDelete] = useState(false);
  const [toRename, setToRename] = useState<ProjectSummary | null>(null);
  const [newName, setNewName] = useState("");
  const [redoProject, setRedoProject] = useState<ProjectSummary | null>(null);
  const jobs = useStore(jobsStore);
  useEffect(() => onChanged(() => refetch()), [refetch]);

  // "n" starts a new video
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if ((target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key.toLowerCase() === "n") nav("/new");
      if (e.key === "Escape") { setSelecting(false); setSelected(new Set()); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nav]);

  const allProjects = data ?? [];

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: allProjects.length, ready: 0, processing: 0, error: 0, draft: 0 };
    for (const p of allProjects) {
      if (isBusy(p)) counts.processing++;
      else if (["error", "interrupted"].includes(p.status)) counts.error++;
      else if (p.export_count > 0) counts.ready++;
      else counts.draft++;
    }
    return counts;
  }, [allProjects]);

  const shownProjects = useMemo(() => {
    const words = query.toLowerCase().trim();
    return allProjects
      .filter((p) => !words || p.title.toLowerCase().includes(words))
      .filter((p) => {
        if (aspectFilter !== "all" && p.aspect !== aspectFilter) return false;
        if (statusFilter === "ready") return p.export_count > 0 && !isBusy(p) && !["error", "interrupted"].includes(p.status);
        if (statusFilter === "processing") return isBusy(p);
        if (statusFilter === "error") return ["error", "interrupted"].includes(p.status);
        if (statusFilter === "draft") return p.export_count === 0 && !isBusy(p) && !["error", "interrupted"].includes(p.status);
        return true;
      })
      .sort((a, b) => (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at));
  }, [allProjects, query, statusFilter, aspectFilter]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };
  const selectAll = () => setSelected(new Set(shownProjects.map((p) => p.id)));
  const clearSelection = () => { setSelected(new Set()); setSelecting(false); };

  const open = (project: ProjectSummary) => {
    if (selecting) { toggleSelect(project.id); return; }
    localStorage.setItem(LAST_OPENED, project.id);
    nav(isBeingMade(project) ? `/p/${project.id}/progress` : `/p/${project.id}`);
  };
  const duplicate = async (project: ProjectSummary) => {
    try {
      const copy = await post<ProjectSummary>(`/api/projects/${project.id}/duplicate`);
      toast(`Copied as "${copy.title}"`, "ok");
      refetch();
    } catch (e: any) {
      toast(e.message, "err");
    }
  };
  const saveRename = async () => {
    if (!toRename || !newName.trim()) return;
    try {
      await patch(`/api/projects/${toRename.id}`, { title: newName.trim() });
      refetch();
    } catch (e: any) {
      toast(e.message, "err");
    }
    setToRename(null);
  };
  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await del(`/api/projects/${toDelete.id}`);
      toast("Deleted", "ok");
    } catch (e: any) {
      toast(e.message, "err");
    }
    setToDelete(null);
    refetch();
  };
  const confirmBatchDelete = async () => {
    setToBatchDelete(false);
    let ok = 0, fail = 0;
    for (const id of selected) {
      try { await del(`/api/projects/${id}`); ok++; } catch { fail++; }
    }
    toast(fail ? `Deleted ${ok}, failed ${fail}` : `Deleted ${ok} video${ok !== 1 ? "s" : ""}`, fail ? "err" : "ok");
    setSelected(new Set());
    setSelecting(false);
    refetch();
  };

  const card = (project: ProjectSummary) => {
    const job = Object.values(jobs).find((j) => j.project === project.id && (j.status === "running" || j.status === "queued"));
    const status = statusLine(project, job ? job.frac : null, t);
    const cover = project.cover_url || project.thumb;
    const mode = project.source_mode === "talking_head" ? "talking_head" : project.source === "script" ? "script" : "audio";
    const isSelected = selected.has(project.id);
    return (
      <article key={project.id} className={`dash2-card ${isSelected ? "dash2-selected" : ""}`} aria-label={project.title}>
        <button className="dash2-cover" onClick={() => open(project)} aria-label={`Open ${project.title}`} data-shape={project.aspect}>
          {cover ? <img src={cover} alt="" loading="lazy" decoding="async" />
            : project.last_export_url ? <video src={`${project.last_export_url}#t=1`} preload="metadata" muted playsInline aria-hidden />
            : <Film size={28} />}
          {project.duration ? <span className="dash2-length">{fmtTime(project.duration)}</span> : null}
          {job && <span className="dash2-progress"><ProgressBar frac={job.frac} /></span>}
          {/* Select checkbox overlay */}
          {(selecting || isSelected) && (
            <button
              className={`dash2-check-btn ${isSelected ? "checked" : ""}`}
              onClick={(e) => { e.stopPropagation(); toggleSelect(project.id); }}
              aria-label={isSelected ? "Deselect" : "Select"}
            >
              {isSelected ? <CheckSquare size={18} /> : <Square size={18} />}
            </button>
          )}
        </button>
        <div className="dash2-info">
          <div className="col grow" style={{ gap: 2, minWidth: 0 }}>
            <strong className="bn dash2-title" title={project.title}>{project.title}</strong>
            <span className={`small dash2-status ${status.tone}`}>{MODE_ICON[mode]} {status.text}</span>
          </div>
          <Popover label={`Actions for ${project.title}`} align="right" trigger={<MoreHorizontal size={16} aria-label={`Actions for ${project.title}`} />}>
            <MenuItem onClick={() => open(project)}>Open</MenuItem>
            <MenuItem onClick={() => nav(`/p/${project.id}/export`)} disabled={isBusy(project) || !project.scene_count}>Download…</MenuItem>
            <MenuItem onClick={() => setRedoProject(project)} disabled={isBusy(project)}>Direct again…</MenuItem>
            <MenuSep />
            <MenuItem onClick={() => { setToRename(project); setNewName(project.title); }}>Rename…</MenuItem>
            <MenuItem onClick={() => duplicate(project)} disabled={isBusy(project)}>Duplicate</MenuItem>
            <MenuItem onClick={() => openFolder(project.id)}>Show in folder</MenuItem>
            <MenuSep />
            <MenuItem onClick={() => { toggleSelect(project.id); setSelecting(true); }}>Select</MenuItem>
            <MenuSep />
            <MenuItem onClick={() => setToDelete(project)}>Delete…</MenuItem>
          </Popover>
        </div>
      </article>
    );
  };

  const filterBtns: { key: StatusFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "ready", label: "Ready" },
    { key: "processing", label: "Processing" },
    { key: "draft", label: "Draft" },
    { key: "error", label: "Error" },
  ];
  const aspectBtns: { key: AspectFilter; label: string }[] = [
    { key: "all", label: "Any shape" },
    { key: "9:16", label: "9:16" },
    { key: "16:9", label: "16:9" },
    { key: "1:1", label: "1:1" },
  ];

  return (
    <div className="page-inner dash2">
      {/* ── Top bar: title + search ── */}
      <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
        <h1 className="grow" style={{ margin: 0 }}>{t("projects.title")}</h1>
        {allProjects.length >= 1 && (
        <div className="dash2-search">
          <Search size={15} />
          <input type="search" placeholder={t("projects.search")} value={query} onChange={(e) => setQuery(e.target.value)} aria-label={t("projects.search")} />
        </div>
        )}
        {allProjects.length >= 1 && <button
          className={`btn sm ${selecting ? "primary" : ""}`}
          onClick={() => { if (selecting) clearSelection(); else setSelecting(true); }}
          aria-pressed={selecting}
          title="Select multiple videos for batch operations"
        >
          <CheckSquare size={14} /> {selecting ? `${selected.size} selected` : "Select"}
        </button>}
      </div>

      {/* ── Filter bar ── */}
      {allProjects.length >= 2 && <div className={`dash2-filter-wrap ${filtersOpen?"expanded":"collapsed"}`}>
        <button className="btn ghost dash2-filter-toggle" aria-expanded={filtersOpen} aria-controls="video-filters" onClick={()=>setFiltersOpen(v=>!v)}><Filter size={14}/>Filters</button>
        <div className="dash2-filters-bar" id="video-filters">
        <Filter size={13} style={{ color: "var(--muted)", flexShrink: 0 }} />
        <div className="dash-filters" role="group" aria-label="Filter by status">
          {filterBtns.map((f) => (
            <button key={f.key} className={statusFilter === f.key ? "on" : ""} onClick={() => setStatusFilter(f.key)} disabled={statusCounts[f.key] === 0 && f.key !== "all"}>
              {f.label}
              <span className="ds-badge">{statusCounts[f.key] ?? 0}</span>
            </button>
          ))}
        </div>
        <div className="dash2-filter-sep" />
        <div className="dash-filters" role="group" aria-label="Filter by aspect">
          {aspectBtns.map((f) => (
            <button key={f.key} className={aspectFilter === f.key ? "on" : ""} onClick={() => setAspectFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>
      </div></div>}

      {/* ── Batch actions bar (when selecting) ── */}
      {selecting && selected.size > 0 && (
        <div className="dash2-batch-bar">
          <span className="small" style={{ fontWeight: 600 }}>{selected.size} video{selected.size !== 1 ? "s" : ""} selected</span>
          <button className="btn sm" onClick={selectAll}><CheckSquare size={13} /> Select all ({shownProjects.length})</button>
          <div className="spacer" />
          <button className="btn sm" onClick={clearSelection}>Cancel</button>
          <button
            className="btn sm danger"
            onClick={() => setToBatchDelete(true)}
            disabled={selected.size === 0}
          >
            <Trash2 size={13} /> Delete {selected.size}
          </button>
          <button
            className="btn sm primary"
            onClick={() => {
              const ids = [...selected];
              const first = allProjects.find((p) => p.id === ids[0]);
              if (first) nav(`/p/${first.id}/export`);
            }}
            disabled={selected.size !== 1}
            title={selected.size !== 1 ? "Select exactly one video to export" : "Export selected"}
          >
            <Download size={13} /> Export
          </button>
        </div>
      )}

      {error && <div className="banner err">Could not load your videos. {error}</div>}
      {loading && !data && <div className="row muted"><Spinner /> Loading…</div>}

      <div className="dash2-grid">
        {!query && statusFilter === "all" && aspectFilter === "all" && (
          <button className="dash2-new" onClick={() => nav("/new")} aria-label={t("projects.new")}>
            <span className="dash2-plus"><Plus size={30} /></span>
            <strong>{t("projects.new")}</strong>
            <span className="small muted">{t("dash.new.about")}</span>
          </button>
        )}
        {shownProjects.map(card)}
      </div>
      {data && shownProjects.length === 0 && (
        <div className="empty">
          {query ? `No videos match "${query}".` : statusFilter !== "all" || aspectFilter !== "all" ? "No videos match the current filters." : "No videos yet."}
        </div>
      )}

      {toDelete && (
        <Modal title="Delete this video?" onClose={() => setToDelete(null)}
          footer={<><button className="btn" onClick={() => setToDelete(null)}>{t("common.cancel")}</button><button className="btn danger" onClick={confirmDelete}>{t("common.delete")}</button></>}>
          <p style={{ margin: 0 }}>"{toDelete.title}" and its recording, transcript and exports will be removed from this computer. This cannot be undone.</p>
        </Modal>
      )}
      {toBatchDelete && (
        <Modal title={`Delete ${selected.size} video${selected.size !== 1 ? "s" : ""}?`} onClose={() => setToBatchDelete(false)}
          footer={<><button className="btn" onClick={() => setToBatchDelete(false)}>{t("common.cancel")}</button><button className="btn danger" onClick={confirmBatchDelete}><Trash2 size={14} /> Delete {selected.size}</button></>}>
          <p style={{ margin: 0 }}>All recordings, transcripts and exports for these {selected.size} video{selected.size !== 1 ? "s" : ""} will be removed from this computer. This cannot be undone.</p>
        </Modal>
      )}
      {toRename && (
        <Modal title="Rename" onClose={() => setToRename(null)}
          footer={<><button className="btn" onClick={() => setToRename(null)}>{t("common.cancel")}</button><button className="btn primary" onClick={saveRename} disabled={!newName.trim()}>Save</button></>}>
          <input type="text" className="bn" autoFocus value={newName} aria-label="New name" onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && saveRename()} style={{ width: "100%" }} />
        </Modal>
      )}
      {redoProject && (
        <RedoModal
          id={redoProject.id}
          title={redoProject.title}
          open={!!redoProject}
          onClose={() => setRedoProject(null)}
        />
      )}
    </div>
  );
}
