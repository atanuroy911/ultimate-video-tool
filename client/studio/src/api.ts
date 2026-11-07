import { trackRequest, update, type BusyOp } from "./busycore";

export class ApiError extends Error {
  status: number;
  errors: string[];
  constructor(status: number, message: string, errors: string[] = []) {
    super(message);
    this.status = status;
    this.errors = errors.length ? errors : [message];
  }
}

async function parse(res: Response) {
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event("vt-server-refused"));     // the server does not accept this computer (Reach.tsx)
    const d = data && data.detail;
    if (d && typeof d === "object" && Array.isArray(d.errors)) throw new ApiError(res.status, d.errors[0], d.errors);
    if (Array.isArray(d)) throw new ApiError(res.status, d.map((x: any) => x.msg).join("; "));
    if (res.status === 405) throw new ApiError(405, "The Studio server does not support this action. It is probably older than this page: close the Studio and start it again (vt studio).");
    const plain = typeof d === "string" && !/^(Internal Server Error|Bad Gateway|Service Unavailable|Gateway Timeout)$/i.test(d.trim()) ? d : "";
    throw new ApiError(res.status, plain || (res.status >= 500 ? `The server hit a problem (error ${res.status}). Try again; if it keeps happening, look at Details.` : `Request failed (${res.status})`));
  }
  return data;
}

export async function api<T = any>(method: string, url: string, body?: unknown): Promise<T> {
  return trackRequest(method, url, async () => {                       // anything slow shows the full-screen loading layer (busycore.ts / busy.tsx)
    let res: Response;
    try {
      res = await fetch(url, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      if (e instanceof TypeError) throw new ApiError(0, "The server did not answer. Check that it is running and that this computer can reach it.");     // the browser's own words ("Failed to fetch") mean nothing to a person
      throw e;
    }
    return parse(res);
  });
}

export const get = <T = any>(u: string) => api<T>("GET", u);
export const post = <T = any>(u: string, b?: unknown) => api<T>("POST", u, b ?? {});
export const put = <T = any>(u: string, b?: unknown) => api<T>("PUT", u, b ?? {});
export const patch = <T = any>(u: string, b?: unknown) => api<T>("PATCH", u, b ?? {});
export const del = <T = any>(u: string) => api<T>("DELETE", u);

/* Big files go up in chunks that survive a dropped connection (vt/server/uploads.py): the request then names the finished upload
 * (`audio_upload`, `file_upload`) instead of carrying the file. A file sent once (looked at, then made into a project) is not sent again. */
const CHUNKED_FROM = 8 * 1024 * 1024;
const CHUNK = 8 * 1024 * 1024;
const CHUNKED_FIELDS = ["audio", "file"];
const sentFiles = new WeakMap<Blob, string>();
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function sendInChunks(blob: Blob, name: string, onFrac: (f: number) => void): Promise<string> {
  const key = blob instanceof File ? `vt-upload:${name}:${blob.size}:${blob.lastModified}` : "";
  let id = sentFiles.get(blob) || (key ? (() => { try { return localStorage.getItem(key) || ""; } catch { return ""; } })() : "");
  let offset = 0;
  if (id) {
    const r = await fetch(`/api/uploads/${id}`);
    if (r.ok) offset = (await r.json()).offset;
    else id = "";
  }
  if (!id) {
    const made = await parse(await fetch("/api/uploads", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, size: blob.size }) }));
    id = made.id;
    try { if (key) localStorage.setItem(key, id); } catch { /* private window: resuming after a reload just starts over */ }
  }
  let failures = 0;
  while (offset < blob.size) {
    onFrac(offset / blob.size);
    try {
      const res = await fetch(`/api/uploads/${id}?offset=${offset}`, { method: "PUT", body: blob.slice(offset, offset + CHUNK) });
      if (res.ok || res.status === 409) {
        const d = await res.json();
        offset = res.ok ? d.offset : d.detail.offset;               // 409: an earlier try did arrive; carry on from where the server is
        failures = 0;
        continue;
      }
      if (res.status < 500) return parse(res);                       // a real refusal: show it
    } catch { /* the connection dropped: wait and ask the server where it got to */ }
    if (++failures > 40) throw new ApiError(0, "The upload keeps failing. Check the connection to the server; it will carry on where it stopped when you try again.");
    await pause(Math.min(15000, 500 * 2 ** Math.min(failures, 5)));
    try {
      const r = await fetch(`/api/uploads/${id}`);
      if (r.ok) offset = (await r.json()).offset;
    } catch { /* still offline */ }
  }
  onFrac(1);
  sentFiles.set(blob, id);
  try { if (key) localStorage.removeItem(key); } catch { /* ignore */ }
  return id;
}

export function upload<T = any>(url: string, form: FormData, onProgress?: (f: number) => void): Promise<T> {
  return trackRequest("POST", url, async (op) => {
    const big = CHUNKED_FIELDS.map((k) => [k, form.get(k)] as const).find(([, v]) => v instanceof Blob && v.size >= CHUNKED_FROM);
    if (big) {
      const [field, blob] = big as [string, File];
      const id = await sendInChunks(blob, blob.name || "recording.webm", (f) => {
        onProgress?.(f);
        if (op) update(op, { step: `Uploading ${Math.round(100 * f)}%`, frac: f });
      });
      const small = new FormData();
      form.forEach((v, k) => { if (k !== field) small.append(k, v); });
      small.append(`${field}_upload`, id);
      if (op) update(op, { step: "Preparing the audio", frac: null });
      form = small;
    }
    return sendForm<T>(url, form, big ? undefined : onProgress, op);
  });
}

function sendForm<T>(url: string, form: FormData, onProgress: ((f: number) => void) | undefined, op: BusyOp | null): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      onProgress?.(e.loaded / e.total);
      if (op) update(op, e.loaded >= e.total ? { step: "Preparing the audio", frac: null } : { step: `Uploading ${Math.round((100 * e.loaded) / e.total)}%`, frac: e.loaded / e.total });
    };
    xhr.onload = () => {
      let data: any = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else {
        const d = data?.detail;
        reject(new ApiError(xhr.status, typeof d === "string" ? d : d?.errors?.[0] ?? `Upload failed (${xhr.status})`, d?.errors ?? []));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Could not reach the Video Tool server. Check that it is running and that this device is on its network."));
    xhr.send(form);
  });
}

export const EXPECTED_API = 8;          // keep in step with API_VERSION in vt/server/app.py

export const fmtTime = (s: number) => {
  if (!isFinite(s)) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
};
export const fmtSize = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);
