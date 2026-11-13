// Video Tool: stand-in for OpenChatCut src/captions/translate.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
export async function translateLines(_lines: string[], _lang: string): Promise<string[]> {
  throw new Error('Caption translation is not available in Video Tool yet.');
}
