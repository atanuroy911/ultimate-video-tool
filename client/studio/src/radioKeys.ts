/** The arrow keys in every radio group (`role="radiogroup"` with `role="radio"` buttons): they move to the next choice and pick it, wrapping at the ends,
 *  as people expect from a radio group. A control that handles the keys itself (it calls preventDefault) is left alone. */
export function installRadioKeys(): () => void {
  const onKey = (e: KeyboardEvent) => {
    if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    const now = e.target instanceof HTMLElement && e.target.getAttribute("role") === "radio" ? e.target : null;
    const group = now?.closest('[role="radiogroup"]');
    if (!step || !now || !group) return;
    const all = Array.from(group.querySelectorAll<HTMLElement>('[role="radio"]')).filter((r) => !(r as HTMLButtonElement).disabled && r.closest('[role="radiogroup"]') === group);
    const at = all.indexOf(now);
    if (at < 0 || all.length < 2) return;
    e.preventDefault();
    const next = all[(at + step + all.length) % all.length];
    next.focus();
    next.click();
  };
  document.addEventListener("keydown", onKey);
  return () => document.removeEventListener("keydown", onKey);
}
