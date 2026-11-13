// Video Tool: stand-in for OpenChatCut src/agent/agent-session.ts (not taken; see src/occ/NOTICE.md). The ported chat components show
// messages; in Video Tool they come from our director (src/occ/bridge/DirectorChat.tsx), not from OpenChatCut's agent runtime. Only the
// types the components name are here, with the same shapes.
import type { SelectionReference } from './selection-refs';

export interface AgentRetryOptions {
  readonly askOnly?: boolean;
  readonly references?: SelectionReference[];
}

export interface AgentRetry extends AgentRetryOptions {
  readonly text: string;
}

export interface DisplayMessage {
  /** `note`: a muted system line; never sent to the model. */
  role: 'user' | 'assistant' | 'tool' | 'error' | 'continue' | 'note';
  text: string;
  thinking?: string;
  retry?: AgentRetry;
  tool?: { name: string; args: unknown; result: unknown };
}

export interface LiveTool {
  name: string;
  partial: string;
}
