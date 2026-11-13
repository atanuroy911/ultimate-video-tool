// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/editor/initial.ts @ 9242a95. See src/occ/NOTICE.md.
import type { Tpl } from '../types';
import type { TimelineState } from './types';

// Video Tool: OpenChatCut's 211 built-in motion-graphic templates (1.9 MB of JSON) are not bundled with the timeline; Video Tool's own
// elements become templates in phase 3 of docs/plans/PLAN-OPENCHATCUT.MD and load on demand. The first-run seed is an empty timeline.
export const TEMPLATES: Tpl[] = [];

export const INITIAL: TimelineState = {
  fps: 30,
  width: 1920,
  height: 1080,
  items: [],
  selectedId: null,
};
