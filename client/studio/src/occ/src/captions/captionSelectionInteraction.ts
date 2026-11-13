// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/captions/captionSelectionInteraction.ts @ 9242a95. See src/occ/NOTICE.md.
import { captionSelectionKey, type CaptionSelectionRef } from './captionSelection';

export const CAPTION_SELECTION_TIMELINE_CLIP_SELECTOR = '[data-timeline-clip]';
export const CAPTION_SELECTION_TIMELINE_REGION_SELECTOR = '[data-caption-selection-region="timeline"]';
export const CAPTION_SELECTION_TIMELINE_HEAD_SELECTOR = '.cc-timeline-ruler, .cc-track-head';
export const CAPTION_SELECTION_OWNER_SELECTOR = '[data-caption-selection-owner]';

export function shouldClearCaptionSelectionFromPointer(context: {
  insideTimelineClip: boolean;
  insideTimelineBlank: boolean;
  insideTimelineHead: boolean;
  additive: boolean;
}): boolean {
  return context.insideTimelineBlank && !context.insideTimelineHead && !context.additive;
}

export function updateCaptionSelections(
  current: CaptionSelectionRef[],
  selection: CaptionSelectionRef,
  mode: 'add' | 'toggle',
): CaptionSelectionRef[] {
  const key = captionSelectionKey(selection);
  const exists = current.some((item) => captionSelectionKey(item) === key);
  if (mode === 'toggle' && exists) {
    return current.filter((item) => captionSelectionKey(item) !== key);
  }
  return exists ? current : [...current, selection];
}

/** macOS converts Ctrl+click into a contextmenu event after pointerdown. */
export function captionContextMenuIntent(ctrlKey: boolean): 'ignore-after-toggle' | 'open-menu' {
  return ctrlKey ? 'ignore-after-toggle' : 'open-menu';
}
