// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/components/chat/ChatRunStatus.ts @ 9242a95. See src/occ/NOTICE.md.
/** Elapsed run seconds for the chat status timer; kept outside the component
 *  module so Fast Refresh stays clean (component files export components). */
export function elapsedRunSeconds(startedAt: number, now = Date.now()): number {
  return Math.max(0, (now - startedAt) / 1000);
}
