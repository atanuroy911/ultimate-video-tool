// Video Tool: stand-in for OpenChatCut src/media/upload.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
import type { MediaAsset } from '../editor/mediaTypes';
// Video Tool adds media through its own media bin (POST /api/projects/{id}/media); a drop on the timeline goes there instead.
export async function importMedia(_file: File, _fps: number, _hooks?: unknown): Promise<MediaAsset> {
  throw new Error('Add pictures and clips from the media bin.');
}
