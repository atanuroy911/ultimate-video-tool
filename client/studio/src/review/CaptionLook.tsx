import { CAPTION_LABELS } from "../pages/NewOptions";
import type { Review } from "./useReview";

/** The caption look of the whole video, changeable after it is made (PATCH /api/projects/{id} options.caption_style). The same choices and
    names as the New page's Captions tile; "Match the theme" is what older videos have when nothing was chosen. */
export default function CaptionLook({ r }: { r: Review }) {
  const current = (r.project.data as any)?.options?.caption_style ?? "theme";
  return (
    <div className="caption-look col" style={{ gap: 6, padding: "12px 16px 4px" }}>
      <strong className="small">Caption look</strong>
      <div className="row wrap" style={{ gap: 6 }} role="group" aria-label="Caption look" data-testid="caption-looks">
        {Object.entries(CAPTION_LABELS).map(([id, label]) => (
          <button key={id} type="button" className={`btn sm ${current === id ? "primary" : ""}`} aria-pressed={current === id}
            onClick={() => current !== id && r.patchProject({ options: { caption_style: id } })}>{label}</button>
        ))}
      </div>
    </div>
  );
}
