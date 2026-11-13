// Video Tool: stand-in for OpenChatCut src/fonts/googleFontCatalog.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
export function fontFamilyCss(family: string, fallback: string): string {
  return `"${family.replace(/"/g, '')}", ${fallback}`;
}
