// Video Tool: stand-in for OpenChatCut src/gl/fx/uniforms.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
// Only the types the timeline names; Video Tool draws no GL effects on the timeline.
export interface FxProperty { name: string; type: string; default?: unknown; min?: number; max?: number; step?: number; label?: string }
export interface FxDef { id: string; name: string; desc: string; frag: string; props: FxProperty[]; passes?: string[]; cube?: string }
export interface SerializableFxDef { id: string; name: string; desc: string; frag: string; props: FxProperty[]; passes?: string[]; cube?: string }
