import type { ComponentSpec, El, MediaItem } from "../types";

/** Prepare the same validated component used by directors, preview and export. */
export function newSceneElement(spec: ComponentSpec, atWord: string, media: Pick<MediaItem, "id" | "kind">[]): El {
  if (!atWord) throw new Error("Choose a scene with narration before adding a visual.");
  const el = structuredClone(spec.starter ?? spec.example) as El;
  el.at_word = atWord;
  el.edited = true;
  if (el.type === "media_frame" || el.type === "device") {
    const picture = media.find(m => m.kind !== "audio");
    if (!picture && el.type === "media_frame") throw new Error("Add a picture in the Pictures tab first, then choose Framed picture.");
    el.media = picture?.id ?? null;
  }
  return el;
}
