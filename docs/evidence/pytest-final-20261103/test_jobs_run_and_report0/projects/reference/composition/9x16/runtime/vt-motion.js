/* Motion library: the shot recipes of video-shotcraft (third_party/video-shotcraft, 124 cards), re-made for this renderer (GSAP on a
   paused timeline, frame-exact, deterministic). Four registries, chosen per element / scene by the composer (vt/compose/motion.py):
     X.motion.text[name](tl, w, at, ctx)      an element's entrance (titles, keywords, tags, quotes, stickers...)
     X.motion.trans[name](tl, el, prev, t, W, H) -> duration   a scene's transition in
     X.motion.scene[name](tl, el, sc, W, H)    a whole-scene move: openings, outros, camera moves, rhythm hits
   Every recipe ends in the element's normal resting state (no transform, full opacity), so a still frame after the move is the
   same as without it. Text is split into grapheme clusters (Intl.Segmenter), so Bangla conjuncts never break apart. */
(function () {
  "use strict";
  const X = window.VTX;
  if (!X) return;
  const hash = (s) => { let a = 2166136261; for (let i = 0; i < s.length; i++) a = Math.imul(a ^ s.charCodeAt(i), 16777619); return (a >>> 0) / 4294967295; };
  const rnd = (seed, i) => hash(seed + ":" + i);

  /* ---------- text splitting ---------- */
  const seg = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: "grapheme" }) : null;
  const graphemes = (s) => (seg ? Array.from(seg.segment(s), (x) => x.segment) : Array.from(s));
  function textNodes(root) {
    const out = [];
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: (n) => (n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT) });
    while (walk.nextNode()) out.push(walk.currentNode);
    return out.filter((n) => !n.parentElement.closest("svg"));
  }
  function split(root, unit) {               // wrap words (or graphemes) in inline-block spans; returns them in reading order
    if (root._split && root._split[unit]) return root._split[unit];
    const spans = [];
    textNodes(root).forEach((n) => {
      const frag = document.createDocumentFragment();
      n.nodeValue.split(/(\s+)/).forEach((part) => {
        if (!part) return;
        if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
        const word = document.createElement("span");
        word.className = "mw";
        if (unit === "char") graphemes(part).forEach((g) => { const c = document.createElement("span"); c.className = "mc"; c.textContent = g; word.appendChild(c); spans.push(c); });
        else { word.textContent = part; spans.push(word); }
        frag.appendChild(word);
      });
      n.parentNode.replaceChild(frag, n);
    });
    root._split = Object.assign(root._split || {}, { [unit]: spans });
    return spans;
  }
  const words = (w) => split(w, "word");
  const chars = (w) => split(w, "char");
  const svgsIn = (w) => Array.from(w.querySelectorAll("svg"));
  const settle = { x: 0, y: 0, xPercent: 0, yPercent: 0, rotation: 0, rotationX: 0, rotationY: 0, scale: 1, skewX: 0, opacity: 1, filter: "none", clearProps: "transform,filter,clipPath,textShadow,letterSpacing" };
  const overlay = (parent, css) => { const d = document.createElement("div"); Object.assign(d.style, { position: "absolute", pointerEvents: "none" }, css); parent.appendChild(d); return d; };

  /* ---------- element entrances ---------- */
  const T = {};
  // typography
  T["blur-slide"] = (tl, w, at) => tl.fromTo(words(w), { x: -60, opacity: 0, filter: "blur(14px)" }, Object.assign({}, settle, { duration: 0.5, ease: "power3.out", stagger: 0.06 }), at);
  T["flying-words"] = (tl, w, at, c) => words(w).forEach((s, i) => { const a = rnd(c.seed, i) * Math.PI * 2; tl.fromTo(s, { x: Math.cos(a) * 520, y: Math.sin(a) * 420, rotation: (rnd(c.seed, i + 9) - 0.5) * 90, opacity: 0 }, Object.assign({}, settle, { duration: 0.55, ease: "back.out(1.4)" }), at + i * 0.07); });
  T["glitch-cycle"] = (tl, w, at) => { tl.set(w, { opacity: 0 }, at - 0.001); for (let i = 0; i < 6; i++) tl.set(w, { opacity: i % 2 ? 0.4 : 1, x: [14, -18, 10, -6, 4, 0][i], skewX: [12, -10, 6, -4, 2, 0][i], textShadow: i < 5 ? "4px 0 #ff2a6d, -4px 0 #05d9e8" : "none" }, at + i * 0.04); tl.set(w, settle, at + 0.26); };
  T["gradient-word-sweep"] = (tl, w, at) => { const ws = words(w); tl.fromTo(ws, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.3, stagger: 0.05, ease: "power2.out" }, at); ws.forEach((s, i) => tl.fromTo(s, { color: "var(--accent2)" }, { color: "", duration: 0.5, clearProps: "color" }, at + 0.2 + i * 0.05)); };
  T["lead-word-zoom-assemble"] = (tl, w, at) => { const ws = words(w); if (!ws.length) return; tl.fromTo(ws[0], { scale: 3.2, opacity: 0 }, Object.assign({}, settle, { duration: 0.45, ease: "power4.out" }), at); if (ws.length > 1) tl.fromTo(ws.slice(1), { y: 60, opacity: 0 }, Object.assign({}, settle, { duration: 0.35, ease: "power3.out", stagger: 0.05 }), at + 0.3); };
  T["marker-underline-title"] = (tl, w, at) => { w.style.position = w.style.position || "relative"; const bar = overlay(w, { left: "4%", right: "4%", bottom: "6%", height: "18%", background: "var(--accent)", opacity: "0.35", borderRadius: "6px", transformOrigin: "left center", zIndex: "-1" }); tl.fromTo(w, { opacity: 0, y: 20 }, Object.assign({}, settle, { duration: 0.3 }), at); tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.45, ease: "power2.inOut" }, at + 0.25); };
  T["outline-word-fill"] = (tl, w, at) => { const ws = words(w); tl.fromTo(ws, { opacity: 0, scale: 0.9, color: "transparent", webkitTextStroke: "2px var(--ink)" }, { opacity: 1, scale: 1, duration: 0.3, stagger: 0.05 }, at); tl.to(ws, { color: "", webkitTextStroke: "0px transparent", duration: 0.35, stagger: 0.05, clearProps: "color,webkitTextStroke,transform" }, at + 0.35); };
  T["typewriter-moves"] = (tl, w, at) => { const cs = chars(w); const step = Math.min(0.045, 0.9 / Math.max(1, cs.length)); cs.forEach((c, i) => tl.fromTo(c, { opacity: 0 }, { opacity: 1, duration: 0.01 }, at + i * step)); };
  T["vertical-word-roll-blur-cycle"] = (tl, w, at) => tl.fromTo(words(w), { yPercent: 110, opacity: 0, filter: "blur(8px)" }, Object.assign({}, settle, { duration: 0.45, ease: "expo.out", stagger: 0.08 }), at);
  T["letterspace-materialize"] = (tl, w, at) => tl.fromTo(w, { letterSpacing: "0.5em", opacity: 0, filter: "blur(10px)" }, Object.assign({}, settle, { duration: 0.8, ease: "power3.out" }), at);
  T["type-assembly-moves"] = (tl, w, at, c) => chars(w).forEach((s, i) => tl.fromTo(s, { x: (rnd(c.seed, i) - 0.5) * 600, y: (rnd(c.seed, i + 77) - 0.5) * 500, rotation: (rnd(c.seed, i + 5) - 0.5) * 180, opacity: 0 }, Object.assign({}, settle, { duration: 0.6, ease: "power3.out" }), at + rnd(c.seed, i + 3) * 0.25));
  T["brace-expand"] = (tl, w, at) => tl.fromTo(w, { clipPath: "inset(0 50% 0 50%)", opacity: 0.2 }, Object.assign({}, settle, { clipPath: "inset(0 0% 0 0%)", duration: 0.5, ease: "power2.out" }), at);
  T["slam-entrance-moves"] = (tl, w, at) => { tl.fromTo(w, { scale: 2.8, opacity: 0, filter: "blur(6px)" }, { scale: 1, opacity: 1, filter: "blur(0px)", duration: 0.22, ease: "power4.in" }, at); tl.fromTo(w, { x: -12 }, { x: 0, duration: 0.3, ease: "elastic.out(1, 0.3)", clearProps: "transform,filter" }, at + 0.22); };
  T["paper-title-card"] = (tl, w, at) => tl.fromTo(w, { y: -260, rotation: -9, opacity: 0 }, Object.assign({}, settle, { duration: 0.6, ease: "bounce.out" }), at);
  T["text-as-mask"] = (tl, w, at) => tl.fromTo(w, { clipPath: "circle(0% at 50% 50%)" }, Object.assign({}, settle, { clipPath: "circle(75% at 50% 50%)", duration: 0.6, ease: "power2.inOut" }), at);
  T["countdown-arc-scatter"] = (tl, w, at) => { textNodes(w).forEach((n) => { const m = /\d[\d,]*/.exec(n.nodeValue); if (!m) return; const target = +m[0].replace(/,/g, ""); const o = { v: 0 }; const pre = n.nodeValue.slice(0, m.index), post = n.nodeValue.slice(m.index + m[0].length); tl.fromTo(o, { v: target * 0.6 }, { v: target, duration: 0.45, ease: "power3.out", onUpdate: () => { n.nodeValue = pre + Math.round(o.v).toLocaleString("en-US") + post; } }, at); }); tl.fromTo(w, { scale: 0.7, opacity: 0 }, Object.assign({}, settle, { duration: 0.3 }), at); };
  T["pill-slot-cycle"] = (tl, w, at) => { tl.fromTo(w, { yPercent: -300, filter: "blur(10px)", opacity: 1 }, { yPercent: 0, filter: "blur(0px)", duration: 0.5, ease: "back.out(1.6)", clearProps: "transform,filter" }, at); };
  T["word-relay-geometry"] = (tl, w, at) => { const ws = words(w); ws.forEach((s, i) => tl.fromTo(s, { opacity: 0, rotationX: -90, transformOrigin: "50% 100%" }, Object.assign({}, settle, { duration: 0.35, ease: "back.out(2)" }), at + i * 0.1)); };
  T["type-rhythm-sync"] = (tl, w, at) => tl.fromTo(words(w), { scale: 0, opacity: 0 }, Object.assign({}, settle, { duration: 0.3, ease: "back.out(3)", stagger: 0.12 }), at);
  // element bodies (cards, stickers, icons)
  T["deck-deal-flyin"] = (tl, w, at) => tl.fromTo(w, { x: 420, y: 360, rotation: 28, opacity: 0 }, Object.assign({}, settle, { duration: 0.5, ease: "power3.out" }), at);
  T["card-flip-reveal"] = (tl, w, at) => tl.fromTo(w, { rotationY: 92, opacity: 0, transformPerspective: 1200 }, Object.assign({}, settle, { duration: 0.55, ease: "back.out(1.4)" }), at);
  T["element-body-moves"] = (tl, w, at) => tl.fromTo(w, { scale: 0.2, rotation: -14, opacity: 0 }, Object.assign({}, settle, { duration: 0.6, ease: "elastic.out(1, 0.45)" }), at);
  T["cloner-depth-echo"] = (tl, w, at) => { tl.fromTo(w, { scale: 0.55, opacity: 0, filter: "drop-shadow(0 0 0 rgba(0,0,0,0))" }, { scale: 1, opacity: 1, filter: "drop-shadow(26px 26px 0 rgba(0,0,0,.18)) drop-shadow(52px 52px 0 rgba(0,0,0,.09))", duration: 0.4, ease: "power3.out" }, at); tl.to(w, Object.assign({}, settle, { duration: 0.35 }), at + 0.4); };
  T["draw-svg-trace"] = (tl, w, at) => { const ps = svgsIn(w).flatMap((s) => Array.from(s.querySelectorAll("path,circle,ellipse,rect,polygon"))).slice(0, 80); tl.fromTo(w, { opacity: 0 }, { opacity: 1, duration: 0.05 }, at); ps.forEach((p) => { let L = 600; try { L = p.getTotalLength ? p.getTotalLength() : 600; } catch (e) {} tl.fromTo(p, { strokeDasharray: L, strokeDashoffset: L, fillOpacity: 0, stroke: "var(--ink)", strokeWidth: 3 }, { strokeDashoffset: 0, duration: 0.6, ease: "power1.inOut" }, at); tl.to(p, { fillOpacity: 1, duration: 0.3, clearProps: "strokeDasharray,strokeDashoffset,fillOpacity,stroke,strokeWidth" }, at + 0.55); }); };
  T["radial-wave"] = (tl, w, at) => { w.style.position = w.style.position || "relative"; const ring = overlay(w, { left: "50%", top: "50%", width: "120px", height: "120px", marginLeft: "-60px", marginTop: "-60px", borderRadius: "50%", border: "8px solid var(--accent)", zIndex: "-1" }); tl.fromTo(ring, { scale: 0.2, opacity: 0.9 }, { scale: 6, opacity: 0, duration: 0.9, ease: "power2.out" }, at); tl.fromTo(w, { scale: 0.4, opacity: 0 }, Object.assign({}, settle, { duration: 0.45, ease: "back.out(2.2)" }), at + 0.05); };
  T["neon-frame-orbit-drop"] = (tl, w, at) => { tl.fromTo(w, { y: -200, opacity: 0, filter: "drop-shadow(0 0 0 var(--accent))" }, { y: 0, opacity: 1, filter: "drop-shadow(0 0 28px var(--accent))", duration: 0.45, ease: "power3.out" }, at); tl.to(w, Object.assign({}, settle, { duration: 0.5 }), at + 0.5); };
  T["scan-bracket-sweep"] = (tl, w, at) => { w.style.position = w.style.position || "relative"; const mk = (css) => overlay(w, Object.assign({ width: "36px", height: "36px", borderColor: "var(--accent)", borderStyle: "solid", borderWidth: "0" }, css)); const cs = [mk({ left: "-18px", top: "-18px", borderLeftWidth: "7px", borderTopWidth: "7px" }), mk({ right: "-18px", top: "-18px", borderRightWidth: "7px", borderTopWidth: "7px" }), mk({ left: "-18px", bottom: "-18px", borderLeftWidth: "7px", borderBottomWidth: "7px" }), mk({ right: "-18px", bottom: "-18px", borderRightWidth: "7px", borderBottomWidth: "7px" })]; tl.fromTo(cs, { scale: 3, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.3, stagger: 0.04 }, at); tl.fromTo(w, { opacity: 0 }, { opacity: 1, duration: 0.25 }, at + 0.2); tl.to(cs, { opacity: 0, duration: 0.3 }, at + 1.1); };
  T["spotlight-sweep-moves"] = (tl, w, at) => { w.style.position = w.style.position || "relative"; w.style.overflow = "hidden"; const g = overlay(w, { top: "-20%", bottom: "-20%", width: "40%", left: "-50%", background: "linear-gradient(100deg, transparent, rgba(255,255,255,.75), transparent)", mixBlendMode: "overlay" }); tl.fromTo(w, { opacity: 0, scale: 0.94 }, Object.assign({}, settle, { duration: 0.35 }), at); tl.fromTo(g, { left: "-50%" }, { left: "120%", duration: 0.7, ease: "power2.inOut" }, at + 0.25); };
  T["impact-feedback"] = (tl, w, at) => { tl.fromTo(w, { scale: 1.6, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.16, ease: "power4.in" }, at); [10, -8, 6, -3, 0].forEach((x, i) => tl.set(w, { x }, at + 0.16 + i * 0.035)); tl.set(w, settle, at + 0.36); };
  T["riso-print-hits"] = (tl, w, at) => { tl.fromTo(w, { opacity: 0, textShadow: "10px 6px 0 var(--accent2), -8px -4px 0 var(--accent)" }, { opacity: 1, textShadow: "0px 0px 0 transparent", duration: 0.45, ease: "steps(5)", clearProps: "textShadow" }, at); };
  T["glow-flyline-moves"] = (tl, w, at) => { w.style.position = w.style.position || "relative"; const line = overlay(w, { left: "-120%", top: "50%", height: "6px", width: "100%", background: "linear-gradient(90deg, transparent, var(--accent))", boxShadow: "0 0 18px var(--accent)", borderRadius: "3px" }); tl.fromTo(line, { left: "-120%", opacity: 1 }, { left: "110%", duration: 0.45, ease: "power2.in" }, at); tl.set(line, { opacity: 0 }, at + 0.46); tl.fromTo(w, { opacity: 0 }, { opacity: 1, duration: 0.2 }, at + 0.35); };
  X.motion = { text: T };

  /* ---------- scene transitions ---------- */
  const R = {};
  const base = (tl, el, t) => tl.set(el, { opacity: 1 }, t);
  R["circle-match-iris"] = (tl, el, prev, t) => { base(tl, el, t); tl.fromTo(el, { clipPath: "circle(0% at 50% 45%)" }, { clipPath: "circle(150% at 50% 45%)", duration: 0.55, ease: "power2.inOut", clearProps: "clipPath" }, t); return 0.55; };
  R["wipe-transitions"] = (tl, el, prev, t, W, H, k) => { base(tl, el, t); const dirs = ["inset(0 100% 0 0)", "inset(0 0 0 100%)", "inset(100% 0 0 0)", "inset(0 0 100% 0)"]; tl.fromTo(el, { clipPath: dirs[k % 4] }, { clipPath: "inset(0 0% 0 0)", duration: 0.45, ease: "power3.inOut", clearProps: "clipPath" }, t); return 0.45; };
  R["white-flash-logo-simplify-cut"] = (tl, el, prev, t) => { base(tl, el, t); const f = overlay(el, { inset: "0", background: "#fff", zIndex: "50" }); tl.fromTo(f, { opacity: 1 }, { opacity: 0, duration: 0.35, ease: "power2.out" }, t); return 0.05; };
  R["card-flip-reveal"] = (tl, el, prev, t) => { base(tl, el, t); tl.fromTo(el, { rotationY: -90, transformPerspective: 1600 }, { rotationY: 0, duration: 0.6, ease: "power3.out", clearProps: "transform" }, t); if (prev) tl.to(prev, { rotationY: 90, transformPerspective: 1600, duration: 0.3, ease: "power2.in" }, t); return 0.6; };
  R["page-turn-transitions"] = (tl, el, prev, t) => { base(tl, el, t); tl.fromTo(el, { xPercent: 100, skewY: -6, transformOrigin: "100% 50%", boxShadow: "-40px 0 60px rgba(0,0,0,.35)" }, { xPercent: 0, skewY: 0, boxShadow: "0 0 0 rgba(0,0,0,0)", duration: 0.6, ease: "power2.out", clearProps: "transform,boxShadow" }, t); return 0.6; };
  R["mosaic-reframe"] = (tl, el, prev, t, W, H, k, seed) => { base(tl, el, t); const n = 6, m = 10, cells = []; for (let r = 0; r < m; r++) for (let c = 0; c < n; c++) cells.push(overlay(el, { left: (c * W) / n + "px", top: (r * H) / m + "px", width: W / n + 1 + "px", height: H / m + 1 + "px", background: "var(--bg)", zIndex: "40" })); cells.forEach((d, i) => tl.to(d, { opacity: 0, scale: 0.4, duration: 0.25 }, t + rnd(seed, i) * 0.4)); return 0.6; };
  R["gradient-transition"] = (tl, el, prev, t, W) => { base(tl, el, t); const g = overlay(el, { top: "0", bottom: "0", width: W * 1.6 + "px", left: "0", background: "linear-gradient(90deg, transparent 0%, var(--accent) 30%, var(--accent2) 70%, transparent 100%)", zIndex: "40" }); tl.fromTo(g, { x: -W * 1.6 }, { x: W, duration: 0.7, ease: "power2.inOut" }, t - 0.2); tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.01 }, t + 0.1); return 0.5; };
  R["bottom-push-stack-wipe"] = (tl, el, prev, t) => { base(tl, el, t); tl.fromTo(el, { yPercent: 100 }, { yPercent: 0, duration: 0.5, ease: "power3.out", clearProps: "transform" }, t); if (prev) tl.to(prev, { scale: 0.88, opacity: 0.4, duration: 0.5, ease: "power2.out" }, t); return 0.5; };
  R["tear-streak-transitions"] = (tl, el, prev, t, W, H, k, seed) => { base(tl, el, t); for (let i = 0; i < 7; i++) { const s = overlay(el, { left: "-30%", top: (i * H) / 7 + "px", height: H / 7 + 2 + "px", width: "160%", background: i % 2 ? "var(--accent)" : "var(--ink)", transform: "skewX(-20deg)", zIndex: "40" }); tl.fromTo(s, { xPercent: -110 }, { xPercent: 110, duration: 0.5, ease: "power2.inOut" }, t - 0.25 + rnd(seed, i) * 0.12); } tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.01 }, t); return 0.4; };
  R["line-carry-transition"] = (tl, el, prev, t) => { base(tl, el, t); const l = overlay(el, { left: "0", right: "0", top: "50%", height: "8px", background: "var(--accent)", transformOrigin: "left", zIndex: "40" }); tl.fromTo(l, { scaleX: 0 }, { scaleX: 1, duration: 0.25, ease: "power2.in" }, t); tl.fromTo(el, { clipPath: "inset(50% 0 50% 0)" }, { clipPath: "inset(0% 0 0% 0)", duration: 0.4, ease: "power3.out", clearProps: "clipPath" }, t + 0.22); tl.to(l, { opacity: 0, duration: 0.2 }, t + 0.5); return 0.62; };
  R["shot-transitions"] = (tl, el, prev, t) => { base(tl, el, t); if (prev) tl.to(prev, { scale: 1.5, filter: "blur(12px)", opacity: 0, duration: 0.35, ease: "power2.in" }, t); tl.fromTo(el, { scale: 0.7, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.45, ease: "power3.out", clearProps: "transform" }, t + 0.1); return 0.55; };
  R["transition-travel"] = (tl, el, prev, t, W) => { base(tl, el, t); tl.fromTo(el, { x: W, filter: "blur(16px)" }, { x: 0, filter: "blur(0px)", duration: 0.35, ease: "expo.out", clearProps: "transform,filter" }, t); if (prev) tl.to(prev, { x: -W, filter: "blur(16px)", duration: 0.35, ease: "expo.out" }, t); return 0.35; };
  R["transition-hidden-cut"] = (tl, el, prev, t) => { base(tl, el, t); if (prev) tl.to(prev, { scale: 3, duration: 0.25, ease: "power3.in" }, t - 0.2); tl.fromTo(el, { scale: 0.4 }, { scale: 1, duration: 0.35, ease: "power3.out", clearProps: "transform" }, t); return 0.35; };
  R["print-texture-transitions"] = (tl, el, prev, t) => { base(tl, el, t); const d = overlay(el, { inset: "0", backgroundImage: "radial-gradient(var(--ink) 22%, transparent 23%)", backgroundSize: "26px 26px", zIndex: "40" }); tl.fromTo(d, { opacity: 0.9 }, { opacity: 0, duration: 0.45, ease: "steps(6)" }, t); return 0.3; };
  R["card-flock-tumble"] = (tl, el, prev, t, W, H, k, seed) => { base(tl, el, t); for (let i = 0; i < 9; i++) { const c = overlay(el, { left: (i % 3) * W / 3 + "px", top: Math.floor(i / 3) * H / 3 + "px", width: W / 3 + 2 + "px", height: H / 3 + 2 + "px", background: i % 2 ? "var(--accent)" : "var(--accent2)", zIndex: "40" }); tl.to(c, { y: H, rotation: (rnd(seed, i) - 0.5) * 90, opacity: 0, duration: 0.5, ease: "power2.in" }, t + i * 0.03); } return 0.5; };
  R["beat-cut-moves"] = (tl, el, prev, t) => { base(tl, el, t); tl.fromTo(el, { scale: 1.08 }, { scale: 1, duration: 0.25, ease: "power3.out", clearProps: "transform" }, t); return 0; };
  X.motion.trans = R;

  /* ---------- whole-scene moves: openings, outros, camera, rhythm ---------- */
  const S = {};
  const sceneEls = (el) => Array.from(el.querySelectorAll(".el"));
  S["orbit-ring-title-open"] = (tl, el, sc, W, H) => { for (let i = 0; i < 3; i++) { const r = overlay(el, { left: W / 2 - 200 - i * 90 + "px", top: H * 0.33 - 200 - i * 90 + "px", width: 400 + i * 180 + "px", height: 400 + i * 180 + "px", borderRadius: "50%", border: "5px solid var(--accent)", borderTopColor: "transparent", zIndex: "0" }); tl.fromTo(r, { rotation: -120 * (i + 1), scale: 0.3, opacity: 0 }, { rotation: 0, scale: 1, opacity: 0.6 - i * 0.15, duration: 1.1, ease: "power3.out" }, sc.start); tl.to(r, { opacity: 0, duration: 0.5 }, sc.start + 1.6); } };
  S["spotlight-hero-card"] = (tl, el, sc) => { const m = overlay(el, { inset: "0", background: "radial-gradient(circle at 50% 38%, transparent 0%, rgba(0,0,0,.85) 38%)", zIndex: "30" }); tl.fromTo(m, { opacity: 1, scale: 0.6 }, { opacity: 0, scale: 2.5, duration: 1.0, ease: "power2.inOut" }, sc.start + 0.1); };
  S["brand-ink-open"] = (tl, el, sc) => { tl.fromTo(el, { clipPath: "circle(4% at 50% 40%)" }, { clipPath: "circle(140% at 50% 40%)", duration: 0.9, ease: "power3.inOut", clearProps: "clipPath" }, sc.start); };
  S["crane-rise-reveal"] = (tl, el, sc) => { tl.fromTo(el, { y: 240, scale: 1.12 }, { y: 0, scale: 1, duration: 1.1, ease: "power2.out", clearProps: "transform" }, sc.start); };
  S["fracture"] = (tl, el, sc, W, H) => { for (let i = 0; i < 5; i++) { const s = overlay(el, { left: "0", width: W + "px", top: (i * H) / 5 + "px", height: H / 5 + 1 + "px", background: "var(--ink)", zIndex: "30" }); tl.to(s, { xPercent: i % 2 ? 105 : -105, duration: 0.55, ease: "power3.inOut" }, sc.start + 0.05 + i * 0.05); } };
  S["grain-dissolve"] = (tl, el, sc) => { const g = overlay(el, { inset: "0", backgroundImage: "radial-gradient(var(--bg) 30%, transparent 31%)", backgroundSize: "6px 6px", zIndex: "40" }); tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: 0.8, ease: "steps(8)" }, Math.max(sc.start, sc.end - 0.8)); };
  S["ui-strip-away-outro"] = (tl, el, sc) => { const es = sceneEls(el); es.forEach((e, i) => tl.to(e, { y: -900, rotation: (i % 2 ? 1 : -1) * 12, opacity: 0, duration: 0.45, ease: "power3.in" }, Math.max(sc.start, sc.end - 0.6) + i * 0.05)); };
  S["logo-shrink-wordmark-lockup"] = (tl, el, sc) => { const st = el.querySelector(".stage"); if (st) tl.to(st, { scale: 0.6, y: -120, duration: 0.6, ease: "power3.inOut" }, Math.max(sc.start, sc.end - 0.7)); };
  S["neon-triple-marquee"] = (tl, el, sc, W, H) => { const txt = (el.querySelector(".el") || {}).textContent || ""; if (!txt.trim()) return; for (let i = 0; i < 3; i++) { const b = overlay(el, { left: "0", top: H * (0.12 + i * 0.08) + "px", whiteSpace: "nowrap", font: "800 64px var(--font-head)", color: "transparent", webkitTextStroke: "2px var(--accent)", opacity: "0.35", zIndex: "0" }); b.textContent = (txt.trim() + "  ·  ").repeat(6); tl.fromTo(b, { x: i % 2 ? -W : 0 }, { x: i % 2 ? 0 : -W, duration: Math.max(1, sc.end - sc.start), ease: "none" }, sc.start); } };
  S["crash-zoom-punch"] = (tl, el, sc) => { const st = el.querySelector(".stage") || el; tl.fromTo(st, { scale: 1 }, { scale: 1.22, duration: 0.12, ease: "power4.out" }, sc.start + 0.25); tl.to(st, { scale: 1, duration: 0.6, ease: "power2.out", clearProps: "transform" }, sc.start + 0.6); };
  S["depth-layer-moves"] = (tl, el, sc) => { sceneEls(el).forEach((e, i) => tl.fromTo(e, { y: 30 + i * 25 }, { y: 0, duration: Math.max(0.6, sc.end - sc.start), ease: "none", clearProps: "transform" }, sc.start)); };
  S["tension-camera-moves"] = (tl, el, sc) => { const st = el.querySelector(".stage") || el; const d = Math.max(0.6, sc.end - sc.start); tl.fromTo(st, { scale: 1 }, { scale: 1.07, duration: d, ease: "none" }, sc.start); for (let i = 0; i < 8; i++) tl.set(st, { x: ((i * 37) % 9) - 4, y: ((i * 53) % 7) - 3 }, sc.start + (d * i) / 8); tl.set(st, { clearProps: "transform" }, sc.start + d); };
  S["steep-tilt-glide"] = (tl, el, sc) => { const st = el.querySelector(".stage") || el; tl.fromTo(st, { rotationX: 28, transformPerspective: 1400, y: 120 }, { rotationX: 0, y: 0, duration: 0.9, ease: "power3.out", clearProps: "transform" }, sc.start); };
  S["speed-ramp-freeze"] = (tl, el, sc) => { const f = overlay(el, { inset: "0", background: "#fff", mixBlendMode: "overlay", zIndex: "45" }); tl.fromTo(f, { opacity: 0.8 }, { opacity: 0, duration: 0.5 }, sc.start + Math.min(1.2, (sc.end - sc.start) / 2)); };
  S["rhythm-interrupt-moves"] = (tl, el, sc) => { const f = overlay(el, { inset: "0", background: "var(--ink)", zIndex: "45" }); tl.fromTo(f, { opacity: 1 }, { opacity: 0, duration: 0.08 }, sc.start); };
  X.motion.scene = S;

  /* one entry point for vt.js */
  X.motionEnter = (name, tl, w, at, seed) => { const f = T[name]; if (!f) return false; f(tl, w, at, { seed: seed || "vt" }); return true; };
  X.motionTrans = (name, tl, el, prev, t, W, H, k, seed) => { const f = R[name]; return f ? f(tl, el, prev, t, W, H, k || 0, seed || "vt") : null; };
  X.motionScene = (names, tl, el, sc, W, H) => (names || []).forEach((n) => S[n] && S[n](tl, el, sc, W, H));
})();
