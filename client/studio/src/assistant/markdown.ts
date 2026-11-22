// The small part of Markdown an agent's reply uses (W10.2): paragraphs, "-"/"*"/"1." lists, **bold**, `code`. Parsed into plain data, never
// into HTML, so nothing in a reply can inject markup; links are left to links.ts (vt:// becomes a button, anything else stays text).
export type Inline = { kind: "text" | "bold" | "code"; text: string };
export type Block = { kind: "p"; lines: Inline[][] } | { kind: "ul" | "ol"; items: Inline[][] };

export function inline(text: string): Inline[] {
  const out: Inline[] = [];
  const re = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/g;
  let at = 0;
  for (const m of text.matchAll(re)) {
    if (m.index! > at) out.push({ kind: "text", text: text.slice(at, m.index) });
    const t = m[0];
    out.push(t.startsWith("**") ? { kind: "bold", text: t.slice(2, -2) } : { kind: "code", text: t.slice(1, -1) });
    at = m.index! + t.length;
  }
  if (at < text.length) out.push({ kind: "text", text: text.slice(at) });
  return out;
}

export function blocks(text: string): Block[] {
  const out: Block[] = [];
  for (const chunk of text.replace(/\r\n/g, "\n").split(/\n{2,}/)) {
    const lines = chunk.split("\n").filter((l) => l.trim() !== "");
    if (!lines.length) continue;
    const bullet = lines.every((l) => /^\s*[-*]\s+/.test(l)), number = lines.every((l) => /^\s*\d+[.)]\s+/.test(l));
    if (bullet || number) out.push({ kind: bullet ? "ul" : "ol", items: lines.map((l) => inline(l.replace(/^\s*([-*]|\d+[.)])\s+/, ""))) });
    else out.push({ kind: "p", lines: lines.map(inline) });
  }
  return out;
}
