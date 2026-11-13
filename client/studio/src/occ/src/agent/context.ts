// Video Tool: stand-in for OpenChatCut src/agent/context.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
// The ported transcript search only names this type; Video Tool's director passes its own context.
import type { TimelineState } from '../editor/types';
import type { ProjectDoc } from '../editor/projectTypes';
export interface AgentContext { getState: () => TimelineState; getDoc: () => ProjectDoc; [key: string]: unknown }
