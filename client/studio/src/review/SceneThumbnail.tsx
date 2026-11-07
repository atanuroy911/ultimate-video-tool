import { Image as ImageIcon } from "lucide-react";
import { useState } from "react";
import "./editor-cleanup.css";

/** A pending or failed thumbnail always has a visible state, including while its image is decoding. */
export default function SceneThumbnail({ src, className = "", label = "Scene preview", lazy = false }: { src?: string; className?: string; label?: string; lazy?: boolean }) {
  // Keying the inner image by its URL resets loading state when a fresh preview arrives.
  return <ThumbnailImage key={src ?? "pending"} src={src} className={className} label={label} lazy={lazy} />;
}

function ThumbnailImage({ src, className, label, lazy }: { src?: string; className: string; label: string; lazy: boolean }) {
  const [state, setState] = useState<"loading" | "loaded" | "failed">("loading");
  return <span className={`scene-thumbnail ${className} ${state}`} aria-busy={state === "loading"}>
    {state !== "loaded" && <span className="scene-thumbnail-skeleton" role="img" aria-label={state === "failed" ? `${label} unavailable` : `Loading ${label.toLowerCase()}`}><ImageIcon size={16} aria-hidden="true" /></span>}
    {src && <img className={state === "loaded" ? "" : "pending"} src={src} alt="" loading={lazy ? "lazy" : "eager"} draggable={false} onLoad={() => setState("loaded")} onError={() => setState("failed")} />}
  </span>;
}
