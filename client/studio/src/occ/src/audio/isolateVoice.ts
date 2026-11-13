// Video Tool: stand-in for OpenChatCut src/audio/isolateVoice.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
// Voice cleaning in Video Tool is its own (server preprocess); the timeline's "isolate voice" action is not offered.
export function strengthFromAudioFxId(id: string): number {
  const m = /(\d+)$/.exec(id);
  return m ? Math.max(0, Math.min(100, Number(m[1]))) : 70;
}
export function isIsolateAudioFxId(id: string): boolean {
  return id.startsWith('library:audio-fx:isolate-voice') || id === 'isolate-voice';
}
export interface IsolateVoiceResult { path: string; bytes?: number; engine?: string; sourceRevision: string; strength: number }
export async function isolateVoiceOnSrc(_src: string, _strength = 70, _opts?: { force?: boolean; sourceRevision?: string }): Promise<IsolateVoiceResult> {
  throw new Error('Voice cleaning runs when the video is made. It cannot be applied from the timeline yet.');
}
