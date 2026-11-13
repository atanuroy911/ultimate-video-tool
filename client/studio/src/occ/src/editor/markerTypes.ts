// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/editor/markerTypes.ts @ 9242a95. See src/occ/NOTICE.md.
/** marker palette (8 named colors → tailwind-500 hex) */
export type MarkerColor = 'blue' | 'cyan' | 'fuchsia' | 'green' | 'pink' | 'purple' | 'red' | 'yellow';
export const MARKER_HEX: Record<MarkerColor, string> = {
  blue: '#3b82f6', cyan: '#06b6d4', fuchsia: '#d946ef', green: '#10b981',
  pink: '#ec4899', purple: '#8b5cf6', red: '#ef4444', yellow: '#f59e0b',
};

/** a timeline annotation (manage_markers): point (durationFrames 0) or
 * range (>0), anchored to the ruler (scope 'project') or a clip (scope 'item'). */
export interface Marker {
  id: string;
  scope: 'project' | 'item';
  itemId?: string; // scope 'item' only
  fromFrame: number;
  durationFrames: number;
  note: string;
  color: MarkerColor;
}
