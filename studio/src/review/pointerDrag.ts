/** One pointer gesture. Release always applies the final position before saving. */
export function pointerDrag(
  e: { clientX: number; clientY: number; pointerId: number; target: EventTarget | null },
  move: (ev: PointerEvent) => void,
  up: (ev: PointerEvent, moved: boolean) => void,
  cancel?: () => void,
): () => void {
  const sx = e.clientX, sy = e.clientY;
  let moved = false, finished = false, frame = 0, last: PointerEvent | null = null;
  try { (e.target as Element)?.setPointerCapture?.(e.pointerId); } catch { /* detached target */ }
  document.body.classList.add("tl-scrubbing");
  const cleanup = () => {
    finished = true;
    cancelAnimationFrame(frame);
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    window.removeEventListener("pointercancel", onCancel);
    window.removeEventListener("keydown", onKey, true);
    document.body.classList.remove("tl-scrubbing");
  };
  const onMove = (ev: PointerEvent) => {
    if (ev.pointerId !== e.pointerId) return;
    if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) < 3) return;
    moved = true; last = ev;
    if (!frame) frame = requestAnimationFrame(() => { frame = 0; if (last && !finished) move(last); });
  };
  const onUp = (ev: PointerEvent) => {
    if (ev.pointerId !== e.pointerId) return;
    moved ||= Math.hypot(ev.clientX - sx, ev.clientY - sy) >= 3;
    if (moved) move(ev);
    cleanup(); up(ev, moved);
  };
  const onCancel = (ev?: PointerEvent) => { if (ev && ev.pointerId !== e.pointerId) return; if (!finished) { cleanup(); cancel?.(); } };
  const onKey = (ev: KeyboardEvent) => { if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); onCancel(); } };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);
  window.addEventListener("pointercancel", onCancel);
  window.addEventListener("keydown", onKey, true);
  return onCancel;
}
