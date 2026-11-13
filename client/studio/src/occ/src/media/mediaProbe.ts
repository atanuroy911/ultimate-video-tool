// Video Tool: stand-in for OpenChatCut src/media/mediaProbe.ts (not taken; see src/occ/NOTICE.md). Same exports the ported timeline uses.
export type MediaKind = 'video' | 'image' | 'audio' | 'gif' | 'svg';
export function kindOf(file: File): MediaKind | null {
  const type = file.type.toLowerCase();
  if (type === 'image/gif') return 'gif';
  if (type === 'image/svg+xml') return 'svg';
  if (type.startsWith('image/')) return 'image';
  if (type.startsWith('video/')) return 'video';
  if (type.startsWith('audio/')) return 'audio';
  return null;
}
const VIDEO_EXTENSIONS = ['.mp4', '.m4v', '.mov', '.webm'];
const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.avif', '.heic', '.heif'];
const AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.opus', '.flac'];
export function kindOfDescriptor(rawName: string, rawType = ''): MediaKind | null {
  const name = rawName.toLowerCase(), type = rawType.toLowerCase();
  const dot = name.lastIndexOf('.');
  if (type === 'image/gif' || name.endsWith('.gif')) return 'gif';
  if (type === 'image/svg+xml' || name.endsWith('.svg')) return 'svg';
  if (VIDEO_EXTENSIONS.some((e) => name.endsWith(e))) return 'video';
  if (IMAGE_EXTENSIONS.some((e) => name.endsWith(e))) return 'image';
  if (AUDIO_EXTENSIONS.some((e) => name.endsWith(e))) return 'audio';
  if (dot >= 0 && dot < name.length - 1) return null;
  if (type.startsWith('video/')) return 'video';
  if (type.startsWith('image/')) return 'image';
  if (type.startsWith('audio/')) return 'audio';
  return null;
}
