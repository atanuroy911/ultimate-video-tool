import { useEffect, useState } from "react";

/** Is the server answering? Asked every few seconds while the page is open. Two failed answers in a row (not a refusal: that is its own screen) mean the connection is lost;
 *  the first good answer after that says it is back, and every view that had failed to load asks again. */
export const BACK_EVENT = "vt-server-back";
export type Link = "ok" | "lost" | "back";

let state: Link = "ok";
let misses = 0;
let timer: number | undefined;
let backTimer: number | undefined;
const listeners = new Set<(s: Link) => void>();
const set = (s: Link) => { if (s !== state) { state = s; listeners.forEach((l) => l(s)); } };

async function ask() {
  if (document.hidden) return;
  try {
    const r = await fetch("/api/health", { cache: "no-store" });
    if (r.status === 401) return;                                   // the server answered and refused this computer: Reach.tsx shows that
    misses = 0;
    if (state === "lost") {
      set("back");
      window.dispatchEvent(new Event(BACK_EVENT));
      window.clearTimeout(backTimer);
      backTimer = window.setTimeout(() => set("ok"), 4000);
    }
  } catch {
    misses += 1;
    if (misses >= 2) { window.clearTimeout(backTimer); set("lost"); }
  }
}

/** The state of the connection, for the banner. Starts the asking with the first user and stops with the last. */
export function useLink(every = 3000): Link {
  const [s, setS] = useState<Link>(state);
  useEffect(() => {
    listeners.add(setS);
    if (timer === undefined) { void ask(); timer = window.setInterval(ask, every); }
    return () => { listeners.delete(setS); if (!listeners.size && timer !== undefined) { window.clearInterval(timer); timer = undefined; } };
  }, [every]);
  return s;
}
