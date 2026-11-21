// Links in an agent's reply that point back into the video (docs/plans/PLAN-WORKBENCH.MD W13.4):
//   [scene 3](vt://scene/s3)   [0:12.5](vt://t/12.5)   [the title](vt://element/s3/2)   [the hook](vt://range/0/3.1)
// Nothing else is ever a link: an address that is not one of these, or has an odd value, is shown as its plain text, and the window never navigates.

export type VtLink =
  | { kind: "scene"; scene: string }
  | { kind: "time"; t: number }
  | { kind: "element"; scene: string; index: number }
  | { kind: "range"; from: number; to: number };

const ID = /^[A-Za-z0-9_-]{1,64}$/;
const SECONDS = /^\d{1,6}(\.\d{1,3})?$/;

export function parseVtLink(href: string): VtLink | null {
  const m = /^vt:\/\/([a-z]+)((?:\/[^/\s]*){1,3})$/.exec(String(href).trim());
  if (!m) return null;
  const parts = m[2].slice(1).split("/");
  if (m[1] === "scene" && parts.length === 1 && ID.test(parts[0])) return { kind: "scene", scene: parts[0] };
  if (m[1] === "t" && parts.length === 1 && SECONDS.test(parts[0])) return { kind: "time", t: Number(parts[0]) };
  if (m[1] === "element" && parts.length === 2 && ID.test(parts[0]) && /^\d{1,3}$/.test(parts[1])) return { kind: "element", scene: parts[0], index: Number(parts[1]) };
  if (m[1] === "range" && parts.length === 2 && SECONDS.test(parts[0]) && SECONDS.test(parts[1]) && Number(parts[0]) <= Number(parts[1])) return { kind: "range", from: Number(parts[0]), to: Number(parts[1]) };
  return null;
}

export type Piece = { text: string } | { label: string; link: VtLink };

/** The reply cut into plain text and links. A Markdown link whose address is not a valid vt:// link keeps only its label. */
export function pieces(text: string): Piece[] {
  const out: Piece[] = [];
  const re = /\[([^\]\n]{1,120})\]\(([^)\s]{1,200})\)/g;
  let last = 0;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) });
    const link = parseVtLink(m[2]);
    out.push(link ? { label: m[1], link } : { text: m[1] });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}
