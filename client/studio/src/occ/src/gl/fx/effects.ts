// Video Tool: stand-in for OpenChatCut src/gl/fx/effects.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
import type { FxDef, SerializableFxDef } from './uniforms';
export type { FxDef, FxProperty } from './uniforms';
export const FX_EFFECTS: Record<string, FxDef> = {};
export const LUT_EFFECTS: Record<string, FxDef> = {};
export const ALL_FX: Record<string, FxDef> = {};
export function serializableDefsFor(_effects: Array<{ assetId: string }>): SerializableFxDef[] { return []; }
