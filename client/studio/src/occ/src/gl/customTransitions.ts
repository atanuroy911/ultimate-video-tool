// Video Tool: stand-in for OpenChatCut src/gl/customTransitions.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
export interface CustomTransitionDef { id: string; label: string; frag: string; props: unknown[] }
export function getCustomTransition(_id: string): CustomTransitionDef | undefined { return undefined; }
export function customTransitionUniforms(_def: CustomTransitionDef): Record<string, number> { return {}; }
