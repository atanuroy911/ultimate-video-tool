// How the spoken words read on the timeline at any zoom (owner, 2026-11-23: "the words section is too much overlapping").
// Zoomed out, caption lines that would be too narrow to read are drawn as one block (their text joined, a tick where each word starts), so nothing
// overlaps. Zoomed in, once every word of a block has room, each word is drawn on its own at its time. Pure functions: tested in tests/caption-lod.test.mjs.

export interface LodWord { text: string; start: number; end: number; id?: string }
export interface LodPage { words: LodWord[]; start: number; end: number }

export const MIN_BLOCK_PX = 84;        // narrower than this, a caption line joins its neighbour
export const MAX_JOIN_GAP_MS = 700;    // a longer pause keeps lines apart (a new thought)
export const MIN_WORD_PX = 22;         // every word needs this much to be drawn on its own (a short word fits in 22 px at 11 px type)

/** Join neighbouring caption lines that would be too narrow to read at this zoom (pxPerMs: timeline pixels per millisecond). */
export function mergeNarrow<P extends LodPage>(pages: readonly P[], pxPerMs: number, minPx = MIN_BLOCK_PX, maxGapMs = MAX_JOIN_GAP_MS): LodPage[] {
  const out: LodPage[] = [];
  for (const p of pages) {
    const last = out[out.length - 1];
    const lastNarrow = last && (last.end - last.start) * pxPerMs < minPx;          // a block grows only until it can be read
    if (last && lastNarrow && p.start - last.end <= maxGapMs) {
      last.words = [...last.words, ...p.words];
      last.end = Math.max(last.end, p.end);
    } else {
      out.push({ words: [...p.words], start: p.start, end: p.end });
    }
  }
  return out;
}

/** Where each word sits inside its block (pixels from the block's left), or null when the words do not all have room yet. */
export function wordSpots(page: LodPage, pxPerMs: number, minWordPx = MIN_WORD_PX): Array<{ text: string; left: number; width: number; id?: string }> | null {
  if (page.words.length < 2) return null;
  const spots = page.words.map((w, i) => {
    const next = page.words[i + 1];
    const end = next ? Math.max(w.end, next.start) : Math.max(w.end, page.end);     // a word owns the pause after it
    return { text: w.text, id: w.id, left: (w.start - page.start) * pxPerMs, width: (end - w.start) * pxPerMs };
  });
  return spots.every((s) => s.width >= minWordPx) ? spots : null;
}

/** Ticks where the words after the first begin (pixels from the block's left), for a block too narrow to show its words. */
export function wordTicks(page: LodPage, pxPerMs: number): number[] {
  return page.words.slice(1).map((w) => Math.round((w.start - page.start) * pxPerMs)).filter((x) => x > 2);
}
