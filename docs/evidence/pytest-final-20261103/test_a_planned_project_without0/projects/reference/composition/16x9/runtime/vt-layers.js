/* Layers: text, pictures and video clips the owner put on extra tracks (layers.json). Drawn above the scenes, below the captions.
   Each clip shows for its own time range with optional fades; video clips follow the timeline like backdrop videos do. */
(function () {
  "use strict";
  const X = window.VTX;
  if (!X) return;

  X.layers = (root, tl, D, W, H) => {
    const layer = document.createElement("div");
    layer.className = "layers-layer";
    root.appendChild(layer);
    (D.layers || []).forEach((c) => {
      const box = document.createElement("div");
      box.className = "lyr lyr-" + c.type;
      box.setAttribute("data-layer", c.id);
      let w = c.w * W, hgt = c.h != null ? c.h * H : null;
      let inner = null;
      if (c.type === "text") {
        inner = document.createElement("span");
        inner.className = "lyr-text" + (c.style.bg ? " plate" : "");
        inner.textContent = c.text;
        inner.style.fontSize = Math.round(c.style.size * W) + "px";
        inner.style.color = c.style.color;
        inner.style.fontWeight = String(c.style.weight);
        inner.style.textAlign = c.style.align;
        if (c.style.bg) inner.style.background = c.style.bg;
        box.style.display = "flex";                                  // the text (and its plate) sits where its alignment says, inside the box
        box.style.alignItems = "center";
        box.style.justifyContent = c.style.align === "left" ? "flex-start" : c.style.align === "right" ? "flex-end" : "center";
      } else if (X.mediaNode) {
        const mn = X.mediaNode(D, c.media, "lyr-media");
        if (mn) {
          inner = mn.node;
          inner.style.objectFit = c.fit;
          if (hgt == null) hgt = w / ((mn.m.w && mn.m.h) ? mn.m.w / mn.m.h : 1);        // keep the picture's own shape unless a height was set
          if (mn.m.kind === "video") {
            inner.setAttribute("data-start", String(c.start));
            inner.setAttribute("data-duration", String(c.dur));
            inner.setAttribute("data-media-start", String(c.in || 0));
            X.registerVideo(inner, c.start, c.end, c.in || 0, false);
          }
        }
      }
      if (!inner) return;
      box.appendChild(inner);
      box.style.left = c.x * W + "px";
      box.style.top = c.y * H + "px";
      box.style.width = w + "px";
      if (hgt != null) box.style.height = hgt + "px";
      layer.appendChild(box);
      const fi = Math.min(c.fade_in || 0, c.dur / 2), fo = Math.min(c.fade_out || 0, c.dur / 2);
      tl.set(box, { opacity: 0 }, 0);
      if (fi > 0.01) tl.fromTo(box, { opacity: 0 }, { opacity: c.opacity, duration: fi, ease: "none" }, c.start);
      else tl.set(box, { opacity: c.opacity }, c.start);
      if (fo > 0.01) tl.to(box, { opacity: 0, duration: fo, ease: "none" }, c.end - fo);
      tl.set(box, { opacity: 0 }, c.end);
      // a motion over the clip's whole time (a start and an end value, so it is a pair of keyframes)
      const span = Math.max(0.1, c.end - c.start), dx = 0.12 * W, dy = 0.12 * H;
      const A = { zoom_in: [{ scale: 1 }, { scale: 1.18 }], zoom_out: [{ scale: 1.18 }, { scale: 1 }], slide_left: [{ x: dx }, { x: 0 }], slide_right: [{ x: -dx }, { x: 0 }],
        slide_up: [{ y: dy }, { y: 0 }], slide_down: [{ y: -dy }, { y: 0 }] }[c.anim];
      if (A) tl.fromTo(inner, A[0], Object.assign({ duration: span, ease: "none" }, A[1]), c.start);
      else if (c.anim === "pulse") tl.fromTo(inner, { scale: 1 }, { scale: 1.08, duration: Math.min(0.6, span / 2), yoyo: true, repeat: Math.max(1, Math.floor(span / 1.2)) * 2 - 1, ease: "sine.inOut" }, c.start);
    });
  };
})();
