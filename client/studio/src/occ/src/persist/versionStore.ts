// Video Tool: stand-in for OpenChatCut src/persist/versionStore.ts (not taken; see src/occ/NOTICE.md). Video Tool keeps a video's history on
// its server (snapshots); the "save a version" shortcut keeps one in this browser session until phase 2 sends it there.
import type { ProjectDoc } from '../editor/projectTypes';

export interface ProjectVersion {
  id: string;
  name: string;
  createdAt: number;
  automatic?: boolean;
  doc: ProjectDoc;
}

const kept: ProjectVersion[] = [];

export function saveVersion(_projectId: string, name: string, doc: ProjectDoc): Promise<ProjectVersion> {
  const v: ProjectVersion = { id: `v${Date.now()}`, name, createdAt: Date.now(), doc };
  kept.push(v);
  return Promise.resolve(v);
}
