/* Media (phase 2): scene backdrops, framed media, device mockups. Images, GIFs (pre-converted to video) and video clips.
   Text over media stays readable because the contrast engine (vt/director/contrast.py) already chose ink colour and scrim
   for every scene; this file only draws what it decided. */
(function () {
  "use strict";
  const X = window.VTX;
  if (!X) return;
  const { C, h, rt, svgIcon } = X;
  X.videos = [];

  function mediaNode(D, id, cls) {
    const m = (D.media && D.media[id]) || null;
    if (!m) return null;
    let node;
    if (m.kind === "video") {
      node = document.createElement("video");
      // HyperFrames extracts/injects frames by DOM id; anonymous videos are skipped.
      node.id = 'vt-video-' + (X.nextVideoId = (X.nextVideoId || 0) + 1);
      node.muted = true;
      node.setAttribute("muted", "");
      node.playsInline = true;
      node.preload = "auto";
      node.src = m.src;
    } else {
      node = document.createElement("img");
      node.src = m.src;
      node.alt = "";
    }
    node.className = cls || "";
    if (m.faces?.length) {
      node.dataset.faces = JSON.stringify(m.faces);
      node.dataset.personName = m.caption || id;
      node.dataset.sourceWidth = m.w || 0;
      node.dataset.sourceHeight = m.h || 0;
    }
    node.style.objectPosition = Math.round((m.fx != null ? m.fx : 0.5) * 100) + "% " + Math.round((m.fy != null ? m.fy : 0.5) * 100) + "%";
    return { node, m };
  }

  X.mediaNode = mediaNode;

  /* keep video clips on the timeline when previewing in the Studio (the renderer drives video frames itself) */
  X.registerVideo = (node, start, end, trim, loop) => X.videos.push({ node, start, end, trim: trim || 0, loop: !!loop, dur: 0 });
  X.syncVideos = (t) => {
    if (window.parent === window) return;
    for (const v of X.videos) {
      if (!v.node.isConnected) continue;
      const local = Math.max(0, Math.min(t, v.end) - v.start) + v.trim;
      const d = v.node.duration;
      const at = v.loop && isFinite(d) && d > 0 ? local % d : local;
      if (Math.abs(v.node.currentTime - at) > 0.05) {
        try { v.node.currentTime = at; } catch (e) { /* not ready yet */ }
      }
    }
  };

  /* slow camera move: zoom towards the subject, kept inside the frame by the zoom amount */
  function cameraMove(tl, el, t0, t1, motion, fx, fy) {
    if (motion === "none") return;
    const span = Math.max(0.5, t1 - t0);
    const dx = (0.5 - fx) * 6, dy = (0.5 - fy) * 6;
    if (motion === "drift-in" || motion === "drift-out") {          // calm looks (watercolour, ink): a slow eased drift, alternating in and out, never a fast zoom that shimmers on a painting
      const a = motion === "drift-in" ? 1.0 : 1.06, b = motion === "drift-in" ? 1.06 : 1.0;
      tl.fromTo(el, { scale: a, xPercent: 0, yPercent: 0 }, { scale: b, xPercent: dx / 3, yPercent: dy / 3, duration: span, ease: "sine.inOut" }, t0);
      return;
    }
    if (motion === "pan") tl.fromTo(el, { scale: 1.16, xPercent: -4, yPercent: dy / 2 }, { scale: 1.16, xPercent: 4, yPercent: dy / 2, duration: span, ease: "none" }, t0);
    else tl.fromTo(el, { scale: 1.02, xPercent: 0, yPercent: 0 }, { scale: 1.14, xPercent: dx, yPercent: dy, duration: span, ease: "none" }, t0);
  }

  /* ---------- scene backdrop ---------- */
  X.backdrop = (sceneEl, sc, tl, D) => {
    const b = sc.backdrop;
    const mn = mediaNode(D, b.media, "bd-media");
    if (!mn) return;
    const fx = b.fx != null ? b.fx : mn.m.fx != null ? mn.m.fx : 0.5, fy = b.fy != null ? b.fy : mn.m.fy != null ? mn.m.fy : 0.5;
    mn.node.style.objectPosition = Math.round(fx * 100) + "% " + Math.round(fy * 100) + "%";      // this scene's own framing (the head of the person in it)
    const bd = h("div", "bd");
    const protectedSource=!!D.screen_recording && mn.m.role==='a_roll';
    if(protectedSource){mn.node.style.objectFit='contain';}
    if (D.theme && D.theme.caption && D.theme.caption.style === "paper" && mn.m.kind !== "video")
      bd.classList.add("bd-paperfit");                   // a painting sits on the sheet: it fades into the paper below, where the caption lives (never over the subject)
    bd.appendChild(mn.node);
    if (mn.m.textBand && !protectedSource) {     // tutorials must retain even text near an edge
      bd.style.transformOrigin = "50% 0%";        // the crop already centres the head: zoom about the middle, from the top
      bd.style.transform = "scale(" + Math.min(1.4, 1 / Math.max(0.5, mn.m.textBand)).toFixed(3) + ")";
    }
    const s = b.scrim || {};
    const scrim = h("div", "bd-scrim bd-" + (s.kind || "none") + " bd-edge-" + (s.edge || "bottom"));
    scrim.style.setProperty("--a", String(s.strength || 0));
    scrim.style.setProperty("--sc", s.ink === "dark" ? "255,255,255" : "0,0,0");   // a dark scrim sits under light text and vice versa
    bd.appendChild(scrim);
    sceneEl.insertBefore(bd, sceneEl.firstChild);
    const later = typeof b.from === "number" && b.from > sc.start;
    sceneEl.classList.add("has-backdrop");
    if (!later) sceneEl.classList.add("ink-" + (s.ink || "light"));   // a card that leaves before its picture arrives keeps its own ink (white on paper is unreadable)
    if (later) {                                                    // a card said its line: the picture comes back under it (composer _hand_cards_back)
      tl.set(bd, { opacity: 0 }, sc.start);
      tl.to(bd, { opacity: 1, duration: 0.45, ease: "power1.out" }, b.from);
    }
    if (mn.m.kind === "video") {
      mn.node.setAttribute("data-start", String(sc.start));
      mn.node.setAttribute("data-duration", String(Math.max(0.1, sc.end - sc.start)));
      const t0 = b.offset != null ? b.offset : mn.m.trim || 0;                  // the A-roll is already cut to the edited voice: scene time is media time
      mn.node.setAttribute("data-media-start", String(t0));
      X.registerVideo(mn.node, sc.start, sc.end, t0, mn.m.loop);
    }
    let move = protectedSource || mn.m.kind === "video" && b.motion === "kenburns" ? "none" : b.motion;
    if (move === "kenburns" && D.theme && D.theme.motion && D.theme.motion.preset === "smooth")
      move = (D.scenes || []).indexOf(sc) % 2 ? "drift-out" : "drift-in";
    cameraMove(tl, mn.node, sc.start, sc.end, move, fx, fy);
    if (!protectedSource && mn.m.kind === "video" && mn.m.shots && mn.m.shots.length && b.offset != null) {
      const fw = D.format.width, fh = D.format.height, vw = Math.min(1, (fw / fh) / ((mn.m.w || 16) / (mn.m.h || 9)));
      const aim = (hx) => (vw >= 0.999 ? 0.5 : Math.min(1, Math.max(0, (hx - vw / 2) / (1 - vw))));
      const dur = sc.end - sc.start;
      mn.m.shots.forEach((s) => {
        if (s[2] < 0 || s[1] <= b.offset || s[0] >= b.offset + dur) return;
        const at = sc.start + Math.max(0, s[0] - b.offset);
        const pos = (hx) => Math.round(aim(hx) * 100) + "% " + Math.round(fy * 100) + "%";
        tl.set(mn.node, { objectPosition: pos(s[2]) }, at);
        const hxEnd = s.length > 4 && s[4] >= 0 ? s[4] : s[2];
        if (Math.abs(hxEnd - s[2]) > 0.005) {                                           // a steady pan inside the shot (L1-optimal path, vt/camerapath.py)
          const until = sc.start + Math.min(dur, s[1] - b.offset);
          if (until - at > 0.2) tl.to(mn.node, { objectPosition: pos(hxEnd), duration: until - at, ease: "none" }, at);
        }
      });
    }
    tl.fromTo(scrim, { opacity: 0 }, { opacity: 1, duration: 0.5 }, sc.start);
    if (s.ink) (X.inkRanges = X.inkRanges || []).push({ t0: sc.start, t1: sc.end, ink: s.ink });
  };

  /* ---------- framed media ---------- */
  C.media_frame = (d, ctx) => {
    const wrap = h("div", "mf mf-" + d.frame);
    const inner = h("div", "mf-inner");
    const mn = mediaNode(ctx.D, d.media, "mf-media");
    if (mn) inner.appendChild(mn.node);
    else inner.classList.add("mf-missing");
    wrap.appendChild(inner);
    let cap = null;
    if (d.caption) {
      cap = rt("div", "mf-cap", d.caption);
      wrap.appendChild(cap);
    }
    return {
      el: wrap,
      enter(tl, t, M, c, sc) {
        const end = d.until ?? (sc ? sc.end : t + 4);
        tl.fromTo(wrap, { opacity: 0, scale: 0.85, rotation: d.frame === "polaroid" ? -6 : 0, y: 40 }, { opacity: 1, scale: 1, rotation: d.frame === "polaroid" ? -2.5 : 0, y: 0, duration: M.dur + 0.2, ease: "back.out(1.5)" }, t);
        if (mn) {
          if (mn.m.kind === "video") {
            mn.node.setAttribute("data-start", String(t));
            mn.node.setAttribute("data-duration", String(Math.max(0.1, end - t)));
            mn.node.setAttribute("data-media-start", String((mn.m.trim || 0) + (d.offset || 0)));
            X.registerVideo(mn.node, t, end, (mn.m.trim || 0) + (d.offset || 0), mn.m.loop);
          } else cameraMove(tl, mn.node, t, end, d.motion === "none" ? "none" : "kenburns", mn.m.fx != null ? mn.m.fx : 0.5, mn.m.fy != null ? mn.m.fy : 0.5);
        }
        if (cap) tl.fromTo(cap, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: M.dur }, t + 0.4);
      },
    };
  };

  /* ---------- device mockups ---------- */
  C.device = (d, ctx) => {
    const wrap = h("div", "dv dv-" + d.kind);
    const frame = h("div", "dv-frame");
    if (d.kind === "browser") {
      const bar = h("div", "dv-bar");
      for (let i = 0; i < 3; i++) bar.appendChild(h("i", "dv-dot"));
      bar.appendChild(h("span", "dv-url"));
      frame.appendChild(bar);
    }
    if (d.kind === "phone") frame.appendChild(h("i", "dv-notch"));
    const screen = h("div", "dv-screen");
    const mn = d.media ? mediaNode(ctx.D, d.media, "dv-media") : null;
    if (mn) screen.appendChild(mn.node);
    else screen.appendChild(h("div", "dv-ph"));
    frame.appendChild(screen);
    wrap.appendChild(frame);
    if (d.kind === "laptop") wrap.appendChild(h("div", "dv-base"));
    const calls = (d.callouts || []).map((c, i) => {
      const e = h("div", "dv-call");
      e.style.left = c.x * 100 + "%";
      e.style.top = c.y * 100 + "%";
      e.appendChild(h("i", "dv-pin"));
      const lab = rt("span", "dv-calltext", c.text);
      e.appendChild(lab);
      screen.appendChild(e);
      return e;
    });
    let cap = null;
    if (d.caption) {
      cap = rt("div", "dv-cap", d.caption);
      wrap.appendChild(cap);
    }
    return {
      el: wrap,
      enter(tl, t, M, c, sc) {
        const end = d.until ?? (sc ? sc.end : t + 4);
        tl.fromTo(frame, { opacity: 0, y: 90, scale: 0.9, rotation: d.kind === "phone" ? 4 : 0 }, { opacity: 1, y: 0, scale: 1, rotation: 0, duration: M.dur + 0.25, ease: "back.out(1.4)" }, t);
        if (mn) {
          if (mn.m.kind === "video") {
            mn.node.setAttribute("data-start", String(t));
            mn.node.setAttribute("data-duration", String(Math.max(0.1, end - t)));
            X.registerVideo(mn.node, t, end, (mn.m.trim || 0) + (d.offset || 0), mn.m.loop);
          } else cameraMove(tl, mn.node, t + 0.3, end, "kenburns", mn.m.fx != null ? mn.m.fx : 0.5, mn.m.fy != null ? mn.m.fy : 0.5);
        }
        calls.forEach((e, i) => tl.fromTo(e, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2.4)" }, t + 0.7 + i * 0.5));
        if (cap) tl.fromTo(cap, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: M.dur }, t + 0.5);
      },
    };
  };
})();
