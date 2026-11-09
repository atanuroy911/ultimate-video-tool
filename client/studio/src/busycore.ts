/* The list of things the person is waiting for. No framework and no imports from the rest of the app, so the API client can use it (the layer that draws it is in busy.tsx).
   Every POST/PUT/DELETE/upload is tracked here: one that is still running after a moment makes the full-screen layer appear; when the answer is a background job (an object with
   id, kind and status) the layer keeps following that job with its own words and progress until it ends. */

export interface BusyOp {
  id: number;
  title: string;
  step: string;
  frac: number | null;
  start: number;
  jobId?: string;
  cancellable: boolean;
  hidden: boolean;             // "keep working in the background": the job goes on, the layer goes away
  error?: string;
  done?: boolean;
}

let ops: BusyOp[] = [];
const subs = new Set<() => void>();
let seq = 0;
const emit = () => subs.forEach((f) => f());

export const getOps = () => ops;
export const subscribeOps = (f: () => void) => {
  subs.add(f);
  return () => subs.delete(f);
};

export const begin = (title: string, patch: Partial<BusyOp> = {}): BusyOp => {
  const op: BusyOp = { id: ++seq, title, step: "", frac: null, start: Date.now(), cancellable: false, hidden: false, ...patch };
  ops = [...ops, op];
  emit();
  return op;
};
export const update = (op: BusyOp, patch: Partial<BusyOp>) => {
  Object.assign(op, patch);
  ops = [...ops];
  emit();
};
export const end = (op: BusyOp) => {
  ops = ops.filter((o) => o !== op);
  emit();
};
export const hide = (op: BusyOp) => update(op, { hidden: true });

/** What the person is told while a request waits (before a job gives its own label). null = not worth a layer. */
const TITLES: [RegExp, string][] = [
  [/\/from-link/, "Downloading the video"],
  [/\/from-script/, "Making the voice"],
  [/\/export/, "Making your video file"],
  [/\/publish/, "Publishing"],
  [/\/voice\/overdub/, "Speaking in your voice"],
  [/\/sound-events/, "Listening for sounds"],
  [/\/cutout/, "Cutting out the picture"],
  [/\/media\/describe/, "Looking at your pictures"],
  [/\/context/, "Reading what the video is about"],
  [/\/transcript/, "Updating the words"],
  [/\/script\/(paste|generate)/, "Planning the scenes"],
  [/\/(replan|polish|plan)/, "Planning the scenes"],
  [/\/autofix/, "Auto-fixing suggestions"],
  [/\/qa/, "Checking the video"],
  [/\/aroll/, "Preparing the speaker video"],
  [/\/reshow/, "Redrawing the scene"],
  [/\/(ai|llm)\/test/, "Testing the AI"],
  [/\/llm\/setup/, "Setting up the local AI"],
  [/\/design\/build/, "Designing the theme"],
  [/\/catalog\/.*\/(project|music|add)/, "Downloading"],
  [/\/stock\/add/, "Downloading the picture"],
  [/\/models/, "Downloading the model"],
  [/\/run$/, "Processing"],
  [/\/api\/projects$/, "Uploading your recording"],
];
// background work nobody is waiting for (the Studio asks for these by itself): never worth a full-screen layer
const QUIET = [/\/thumbnails/, /\/open-folder/, /\/catalog\/refresh/, /\/catalog\/[^/]+\/check/, /\/api\/jobs\//, /\/api\/settings/, /\/api\/health/, /\/words\//, /\/duplicate/, /\/layers/, /\/themes\//, /\/glossary/,
  /\/api\/setup\/try\//, /\/api\/setup\/plan/, /\/api\/setup\/folders/, /\/api\/discover\/prepare\?/];   // the setup screens show their own progress

export function titleFor(method: string, url: string): string | null {
  if (method === "GET" || method === "HEAD") return null;
  if (QUIET.some((r) => r.test(url))) return null;
  const hit = TITLES.find(([r]) => r.test(url));
  return hit ? hit[1] : "Working";
}

const looksLikeJob = (d: any) => d && typeof d === "object" && typeof d.id === "string" && typeof d.kind === "string" && typeof d.status === "string" && "frac" in d;

async function follow(op: BusyOp, first: any) {
  let j = first;
  const t0 = Date.now();
  for (let i = 0; i < 20000; i++) {
    const label = j.label && j.label !== j.kind ? j.label : op.title;
    const waiting = j.status === "queued";
    update(op, { title: label, step: waiting ? "Waiting for the other job to finish" : j.msg || "", frac: waiting ? null : typeof j.frac === "number" && j.frac > 0 ? Math.min(1, j.frac) : null, jobId: j.id, cancellable: true });
    if (j.status === "done") {
      dispatchEvent(new CustomEvent("vt-job-done", { detail: { title: label, hidden: op.hidden, job: j } }));
      return end(op);
    }
    if (j.status === "cancelled") {
      dispatchEvent(new CustomEvent("vt-job-cancelled", { detail: { title: label } }));
      return end(op);
    }
    if (j.status === "error") {
      if (op.hidden) {
        dispatchEvent(new CustomEvent("vt-job-failed", { detail: { title: label, error: j.error || "It failed." } }));
        return end(op);
      }
      return update(op, { error: j.error || "It failed.", cancellable: false, hidden: false });        // the layer stays, with the reason and a Close button
    }
    await new Promise((r) => setTimeout(r, Date.now() - t0 < 4000 ? 450 : 900));
    try {
      const res = await fetch(`/api/jobs/${j.id}`);
      if (res.ok) j = await res.json();
      else if (res.status === 404) return end(op);
    } catch { /* the server is busy: ask again */ }
  }
  end(op);
}

/** Run a request and track it. The caller gets the answer exactly as before; a job answer is followed in the background of the call. */
export async function trackRequest<T>(method: string, url: string, run: (op: BusyOp | null) => Promise<T>): Promise<T> {
  const title = titleFor(method, url);
  if (!title) return run(null);
  const op = begin(title);
  let out: T;
  try {
    out = await run(op);
  } catch (e) {
    end(op);
    throw e;
  }
  if (looksLikeJob(out) && ["queued", "running"].includes((out as any).status)) {
    follow(op, out);
    return out;
  }
  end(op);
  return out;
}

export async function cancelOp(op: BusyOp) {
  if (!op.jobId) return;
  try { await fetch(`/api/jobs/${op.jobId}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); } catch { /* the poll will tell */ }
  update(op, { step: "Cancelling...", cancellable: false });
}
