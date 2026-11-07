/* Cartoon engine (phase 2): characters, sets and speaker avatars drawn as SVG by rules, animated on the paused timeline.
   No external art: every shape is generated from the cast description, so characters stay consistent and recolour with the theme.
   Mouths follow the real loudness of the voice (D.envelope), so lip movement is in sync with the audio. */
(function () {
  "use strict";
  const X = window.VTX;
  if (!X) return;
  const { C, h, rt, fit, idle } = X;
  const NS = "http://www.w3.org/2000/svg";
  const sv = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };

  /* ---------- palettes (deterministic from who + name) ---------- */
  const SKIN = ["#f2c9a0", "#e0a878", "#c68a5c", "#9a6540", "#7a4a2e", "#f6d6b8"];
  const HAIR = ["#2b1d14", "#4a3020", "#1d1d1d", "#7a4a1e", "#b5651d", "#c9c9c9"];
  const SHIRT = ["var(--accent)", "var(--accent2)", "#3b82f6", "#10b981", "#8b5cf6", "#ef4444", "#f59e0b"];
  const hash = (str) => {
    let a = 2166136261;
    for (let i = 0; i < str.length; i++) a = Math.imul(a ^ str.charCodeAt(i), 16777619);
    return (a >>> 0);
  };
  const pick = (arr, seed) => arr[seed % arr.length];

  const BASE = {
    man: { skin: 0, hair: "short", shirt: 2, pants: "#334155", scale: 1 },
    woman: { skin: 1, hair: "long", shirt: 5, pants: "#475569", scale: 0.97 },
    boy: { skin: 0, hair: "short", shirt: 1, pants: "#1e3a8a", scale: 0.78, big: 1 },
    girl: { skin: 1, hair: "pony", shirt: 4, pants: "#7c3aed", scale: 0.78, big: 1 },
    elder: { skin: 5, hair: "bald", shirt: 0, pants: "#475569", scale: 0.94, glasses: 1, white: 1 },
    old_woman: { skin: 5, hair: "bun", shirt: 4, pants: "#475569", scale: 0.94, glasses: 1, white: 1, skirt: 1 },
    worker: { skin: 2, hair: "helmet", shirt: 6, pants: "#1f2937", scale: 1 },
    teacher: { skin: 1, hair: "bun", shirt: 3, pants: "#1f2937", scale: 0.98, glasses: 1 },
    doctor: { skin: 0, hair: "short", shirt: -1, pants: "#334155", scale: 1, coat: 1 },
    robot: { skin: -1, hair: "antenna", shirt: -2, pants: "#64748b", scale: 1 },
  };

  /* ---------- the character ---------- */
  function character(m, idx) {
    const base = BASE[m.who] || BASE.man;
    const seed = hash((m.name || "") + m.who);
    const skin = base.skin >= 0 ? SKIN[(base.skin + (m.name ? seed % 3 : 0)) % SKIN.length] : "#cbd5e1";
    const hair = m.hair || HAIR[(base.white ? 5 : seed % 5)];
    const shirt = m.clothes || (base.shirt === -1 ? "#ffffff" : base.shirt === -2 ? "#94a3b8" : SHIRT[(base.shirt + (m.name ? seed % 3 : 0)) % SHIRT.length]);
    const g = sv("g", { class: "ch", "data-who": m.who, "data-name": m.name || "", "data-skin": skin, "data-hair": hair, "data-clothes": shirt });
    // A bicycle is part of the riding rig, rather than an unrelated sticker. It stays still while the rider pedals.
    const bike = sv("g", { class: "ch-bike", opacity: 0 }, g);
    const wheels = [65, 255].map(cx => {
      const wheel = sv("g", { class: "ch-wheel" }, bike);
      sv("circle", { cx, cy: 451, r: 62, fill: "#f8fafc", stroke: "#334155", "stroke-width": 10 }, wheel);
      for (let i = 0; i < 8; i++) {
        const a = i * Math.PI / 4;
        sv("line", { x1: cx, y1: 451, x2: cx + Math.cos(a) * 57, y2: 451 + Math.sin(a) * 57, stroke: "#94a3b8", "stroke-width": 3 }, wheel);
      }
      return wheel;
    });
    sv("path", { d: "M65 451 L124 365 L169 451 Z M124 365 L226 365 L169 451 M226 365 L255 451 M226 365 L215 330 L242 330", fill: "none", stroke: "#0f766e", "stroke-width": 12, "stroke-linecap": "round", "stroke-linejoin": "round" }, bike);
    sv("path", { d: "M124 365 L116 345 M94 345 H139 M173 330 H245", fill: "none", stroke: "#334155", "stroke-width": 10, "stroke-linecap": "round" }, bike);
    const crank = sv("g", { class: "ch-crank" }, bike);
    sv("circle", { cx: 169, cy: 451, r: 13, fill: "#334155" }, crank);
    sv("path", { d: "M149 470 L188 433 M139 470 H159 M178 433 H198", fill: "none", stroke: "#334155", "stroke-width": 7, "stroke-linecap": "round" }, crank);
    const body = sv("g", { class: "ch-body" }, g);
    // legs
    const legL = sv("g", { class: "ch-legL" }, body);
    const legR = sv("g", { class: "ch-legR" }, body);
    const shins = [legL, legR].map((l, i) => {
      sv("rect", { x: i ? 152 : 98, y: 330, width: 50, height: 88, rx: 22, fill: base.pants }, l);
      const shin = sv("g", { class: "ch-shin" }, l);
      sv("rect", { x: i ? 152 : 98, y: 395, width: 50, height: 85, rx: 22, fill: base.pants }, shin);
      sv("ellipse", { cx: i ? 183 : 123, cy: 484, rx: 40, ry: 17, fill: "#1f2937" }, shin);
      return shin;
    });
    // arms behind torso: left
    const armL = sv("g", { class: "ch-armL" }, body);
    sv("rect", { x: 40, y: 200, width: 46, height: 92, rx: 22, fill: shirt }, armL);
    const foreL = sv("g", { class: "ch-forearm" }, armL);
    sv("rect", { x: 40, y: 270, width: 46, height: 80, rx: 22, fill: shirt }, foreL);
    sv("circle", { cx: 63, cy: 358, r: 25, fill: skin }, foreL);
    // torso
    sv("rect", { x: 70, y: 190, width: 160, height: 190, rx: 44, fill: shirt }, body);
    if (base.skirt) sv("path", { d: "M85 320 H215 L235 437 Q150 455 65 437 Z", fill: shirt, class: "ch-skirt" }, body);
    if (base.coat) {
      sv("path", { d: "M150 192 L120 380 M150 192 L180 380", stroke: "#cbd5e1", "stroke-width": 5, fill: "none" }, body);
      sv("circle", { cx: 150, cy: 300, r: 10, fill: "#38bdf8" }, body);
    }
    if (m.who === "teacher") sv("path", { d: "M150 200 L136 250 L150 290 L164 250 Z", fill: "#ef4444" }, body);
    if (m.who === "worker") sv("rect", { x: 70, y: 250, width: 160, height: 22, fill: "#fde047", opacity: 0.9 }, body);
    if (base.skin === 5 && m.who === "elder") sv("path", { d: "M95 215 q55 40 110 0", stroke: "rgba(0,0,0,.15)", "stroke-width": 6, fill: "none" }, body);
    // arm right (front)
    const armR = sv("g", { class: "ch-armR" }, body);
    sv("rect", { x: 214, y: 200, width: 46, height: 92, rx: 22, fill: shirt }, armR);
    const foreR = sv("g", { class: "ch-forearm" }, armR);
    sv("rect", { x: 214, y: 270, width: 46, height: 80, rx: 22, fill: shirt }, foreR);
    const handR = sv("g", { class: "ch-hand" }, foreR);
    sv("circle", { cx: 237, cy: 358, r: 25, fill: skin }, handR);
    const fingers = ["M222 350 V310", "M236 350 V303", "M250 350 V313", "M263 354 V326", "M220 361 L205 339"].map(d => sv("path", { d, stroke: skin, "stroke-width": 11, "stroke-linecap": "round", opacity: 0, class: "ch-count-finger" }, handR));
    // neck + head
    sv("rect", { x: 130, y: 168, width: 40, height: 40, rx: 14, fill: skin }, body);
    const head = sv("g", { class: "ch-head" }, body);
    const hr = base.big ? 92 : 78;
    if (m.who === "robot") {
      sv("rect", { x: 150 - hr, y: 170 - hr * 1.5, width: hr * 2, height: hr * 1.6, rx: 26, fill: "#cbd5e1", stroke: "#64748b", "stroke-width": 6 }, head);
      sv("line", { x1: 150, y1: 170 - hr * 1.5, x2: 150, y2: 170 - hr * 1.5 - 36, stroke: "#64748b", "stroke-width": 8 }, head);
      sv("circle", { cx: 150, cy: 170 - hr * 1.5 - 42, r: 14, fill: "var(--accent)" }, head);
    } else {
      // hair behind
      if (base.hair === "long") {          // long hair falls behind the shoulders on both sides of the face, never below the chin
        sv("rect", { x: 58, y: 70, width: 60, height: 190, rx: 30, fill: hair }, head);
        sv("rect", { x: 182, y: 70, width: 60, height: 190, rx: 30, fill: hair }, head);
      }
      if (base.hair === "pony") sv("path", { d: "M215 80 q60 10 36 110 q-28 -36 -56 -62 Z", fill: hair }, head);
      sv("circle", { cx: 150, cy: 120, r: hr, fill: skin }, head);
      if (base.hair === "short") sv("path", { d: "M" + (150 - hr) + " 112 q10 -80 " + hr + " -78 q" + (hr - 4) + " 0 " + hr + " 78 q-30 -32 -" + hr + " -34 q-" + (hr - 12) + " 2 -" + hr + " 34 Z", fill: hair }, head);
      if (base.hair === "long" || base.hair === "pony" || base.hair === "bun") sv("path", { d: "M" + (150 - hr) + " 118 q" + 12 + " -88 " + hr + " -84 q" + (hr - 6) + " 0 " + hr + " 84 q-20 -40 -" + hr + " -42 q-" + (hr - 10) + " 2 -" + hr + " 42 Z", fill: hair }, head);
      if (base.hair === "bun") sv("circle", { cx: 150, cy: 30, r: 30, fill: hair }, head);
      if (base.hair === "helmet") {
        sv("path", { d: "M70 112 q0 -82 80 -82 q80 0 80 82 Z", fill: "#fde047" }, head);
        sv("rect", { x: 62, y: 106, width: 176, height: 16, rx: 8, fill: "#facc15" }, head);
      }
      if (base.hair === "bald") sv("path", { d: "M72 120 q-6 -30 14 -40 M228 120 q6 -30 -14 -40", stroke: "#cfcfcf", "stroke-width": 14, fill: "none", "stroke-linecap": "round" }, head);
    }
    // face
    const face = sv("g", { class: "ch-face" }, head);
    const ey = base.big ? 118 : 116;
    const eyeL = sv("g", { class: "ch-eye" }, face), eyeR = sv("g", { class: "ch-eye" }, face);
    [[eyeL, 118], [eyeR, 182]].forEach(([g2, cx]) => {
      sv("ellipse", { cx, cy: ey, rx: 15, ry: 18, fill: "#fff" }, g2);
      sv("circle", { cx, cy: ey + 2, r: 9, fill: "#1f2937", class: "ch-pupil" }, g2);
      sv("rect", { x: cx - 17, y: ey - 20, width: 34, height: 0, fill: skin, class: "ch-lid" }, g2);
    });
    if (base.glasses) {
      sv("circle", { cx: 118, cy: ey, r: 24, fill: "none", stroke: "#334155", "stroke-width": 5 }, face);
      sv("circle", { cx: 182, cy: ey, r: 24, fill: "none", stroke: "#334155", "stroke-width": 5 }, face);
      sv("line", { x1: 142, y1: ey, x2: 158, y2: ey, stroke: "#334155", "stroke-width": 5 }, face);
    }
    if (base.white) sv("path", { d: `M89 ${ey + 14} l-8 6 M211 ${ey + 14} l8 6 M124 186 q26 10 52 0`, stroke: "#9a6540", "stroke-width": 3, fill: "none", "stroke-linecap": "round" }, face);
    if (base.skirt) [77, 223].forEach(cx => sv("circle", { cx, cy: 148, r: 7, fill: "#f0c75e" }, face));
    const laughEyes = sv("g", { opacity: 0, class: "ch-laugh-eyes" }, face);
    [118, 182].forEach(cx => sv("path", { d: `M${cx - 14} ${ey + 4} q14 -17 28 0`, fill: "none", stroke: "#334155", "stroke-width": 7, "stroke-linecap": "round" }, laughEyes));
    const browL = sv("line", { x1: 100, y1: ey - 30, x2: 136, y2: ey - 30, stroke: hair, "stroke-width": 8, "stroke-linecap": "round", class: "ch-brow" }, face);
    const browR = sv("line", { x1: 164, y1: ey - 30, x2: 200, y2: ey - 30, stroke: hair, "stroke-width": 8, "stroke-linecap": "round", class: "ch-brow" }, face);
    sv("circle", { cx: 150, cy: ey + 20, r: 6, fill: "rgba(0,0,0,.12)" }, face);
    // mouth shapes
    const my = ey + 50;
    const mouths = {
      neutral: sv("path", { d: "M128 " + my + " q22 6 44 0", stroke: "#7c2d12", "stroke-width": 7, fill: "none", "stroke-linecap": "round" }, face),
      happy: sv("path", { d: "M122 " + (my - 4) + " q28 34 56 0 Z", fill: "#7c2d12", stroke: "#7c2d12", "stroke-width": 5, "stroke-linejoin": "round" }, face),
      sad: sv("path", { d: "M128 " + (my + 8) + " q22 -22 44 0", stroke: "#7c2d12", "stroke-width": 7, fill: "none", "stroke-linecap": "round" }, face),
      surprised: sv("ellipse", { cx: 150, cy: my + 6, rx: 15, ry: 20, fill: "#7c2d12" }, face),
      angry: sv("path", { d: "M128 " + (my + 6) + " q22 -14 44 0", stroke: "#7c2d12", "stroke-width": 7, fill: "none", "stroke-linecap": "round" }, face),
      thinking: sv("path", { d: "M132 " + (my + 2) + " q18 -8 38 6", stroke: "#7c2d12", "stroke-width": 7, fill: "none", "stroke-linecap": "round" }, face),
      laugh: sv("path", { d: `M119 ${my - 7} Q150 ${my + 57} 181 ${my - 7} Q150 ${my + 2} 119 ${my - 7} Z`, fill: "#7c2d12", stroke: "#7c2d12", "stroke-width": 4 }, face),
      confused: sv("path", { d: `M125 ${my + 5} q12 -10 25 0 t25 0`, stroke: "#7c2d12", "stroke-width": 7, fill: "none", "stroke-linecap": "round" }, face),
    };
    const question = sv("text", { x: 258, y: 47, fill: "#475569", "font-size": 56, "font-family": "sans-serif", "font-weight": 800, opacity: 0, class: "ch-question" }, g);
    question.textContent = "?";
    const talk = sv("g", { class: "ch-talk", opacity: 0 }, face);
    sv("ellipse", { cx: 150, cy: my + 6, rx: 22, ry: 22, fill: "#7c2d12" }, talk);
    sv("ellipse", { cx: 150, cy: my + 16, rx: 12, ry: 8, fill: "#ef7d7d" }, talk);
    Object.values(mouths).forEach((e) => e.setAttribute("opacity", 0));
    return { g, body, legL, legR, shins, armL, armR, foreL, foreR, handR, fingers, head, face, eyes: [eyeL, eyeR], laughEyes, question, bike, wheels, crank, browL, browR, mouths, talk, scale: base.scale, mouthY: my };
  }

  const POSE = {
    stand: { l: 5, r: -5, hop: 0 },
    point: { l: 4, r: -85, hop: 0 },
    think: { l: 4, r: -150, hop: 0 },
    wave: { l: 4, r: -150, wave: 1 },
    celebrate: { l: 160, r: -160, hop: 1 },
    sad: { l: 3, r: -3, tilt: 7, drop: 8 },
    shrug: { l: -38, r: 38, up: 8 },
    walk: { l: 0, r: 0, walk: 1 },
    sit: { l: 10, r: -10, sit: 1 },
    idle: { l: 8, r: -8, idle: 1 },
    run: { l: 65, r: -65, run: 1 },
    laugh: { l: -25, r: 25, laugh: 1 },
    count: { l: 5, r: -145, count: 1 },
    confused: { l: -35, r: -145, tilt: -10, confused: 1 },
    ride: { l: -38, r: 0, ride: 1 },
  };
  const BROW = { neutral: [0, 0, 0], happy: [-6, 6, -6], sad: [-14, 14, 6], surprised: [0, 0, -14], angry: [14, -14, 4], thinking: [-4, 0, 0], laugh: [-9, 9, -7], confused: [-19, -3, -5] };

  /* mouth open amount from the voice, quantised so it reads as animation rather than jitter */
  function envelopeAt(env, t) {
    if (!env || !env.v || !env.v.length) return 0;
    const i = Math.max(0, Math.min(env.v.length - 1, Math.round(t / env.dt)));
    return env.v[i];
  }
  function lipSync(tl, talkEl, env, t0, t1, step) {
    if (!env) return;
    step = step || 0.09;
    let last = -1;
    for (let t = t0; t < t1; t += step) {
      const v = envelopeAt(env, t);
      const q = v < 0.12 ? 0 : v < 0.3 ? 0.35 : v < 0.55 ? 0.65 : 1;
      if (q !== last) {
        tl.set(talkEl, q === 0 ? { opacity: 0 } : { opacity: 1, scaleY: q, svgOrigin: "150 140" }, t);
        last = q;
      }
    }
    tl.set(talkEl, { opacity: 0 }, t1);
  }

  /* animate one character inside the scene time range [t, end] */
  function animateCharacter(tl, ch, m, t, end, env, speaking, M) {
    const P = POSE[m.pose] || POSE.stand;
    const o = { ease: "power2.out", duration: 0.5 };
    const expression = m.expression && m.expression !== "neutral" ? m.expression : P.laugh ? "laugh" : P.confused ? "confused" : "neutral";
    // face
    Object.values(ch.mouths).forEach((e) => tl.set(e, {opacity:0}, t));
    tl.set(ch.mouths[expression] || ch.mouths.neutral, {opacity:1}, t);
    tl.set(ch.eyes, {opacity: expression === "laugh" ? 0 : 1}, t);
    tl.set(ch.laughEyes, {opacity: expression === "laugh" ? 1 : 0}, t);
    tl.set(ch.question, {opacity: expression === "confused" || P.confused ? 1 : 0}, t);
    const b = BROW[expression] || BROW.neutral;
    tl.set(ch.browL, { rotation: b[0], svgOrigin: "118 86", y: b[2] }, t);
    tl.set(ch.browR, { rotation: b[1], svgOrigin: "182 86", y: b[2] }, t);
    tl.set(ch.head, {rotation:0,y:0}, t);
    tl.set([ch.legL,ch.legR], {rotation:0,y:0}, t);
    tl.set(ch.g, {y:0}, t);
    tl.set(ch.body, {rotation:0,y:0,svgOrigin:"150 330"}, t);
    tl.set(ch.shins[0], {rotation:0,svgOrigin:"123 405"}, t);
    tl.set(ch.shins[1], {rotation:0,svgOrigin:"177 405"}, t);
    tl.set(ch.foreL, {rotation:0,svgOrigin:"63 280"}, t);
    tl.set(ch.foreR, {rotation:0,svgOrigin:"237 280"}, t);
    tl.set(ch.handR, {rotation:0,svgOrigin:"237 358"}, t);
    tl.set(ch.fingers, {opacity:0}, t);
    tl.set(ch.bike, {opacity:P.ride ? 1 : 0}, t);
    // pose
    tl.set(ch.armL, { rotation: P.l, y:0, svgOrigin: "63 215" }, t);
    tl.set(ch.armR, { rotation: P.r, y:0, svgOrigin: "237 215" }, t);
    if (P.tilt) tl.set(ch.head, { rotation: P.tilt, svgOrigin: "150 200" }, t);
    if (P.drop) tl.set(ch.head, { y: P.drop }, t);
    if (P.sit) tl.set([ch.legL, ch.legR], { y: -60, rotation: 0 }, t);
    if (m.pose === "think") tl.set(ch.head, { rotation: -5, svgOrigin: "150 200" }, t);
    // blink every ~3 s
    const lids = ch.eyes.map((e) => e.querySelector(".ch-lid"));
    for (let bt = t + 1.2; bt < end - 0.2; bt += 3.1 + (hash(m.who + m.x) % 7) / 10) {
      tl.to(lids, { attr: { height: 40 }, duration: 0.07, ease: "none" }, bt);
      tl.to(lids, { attr: { height: 0 }, duration: 0.09, ease: "none" }, bt + 0.08);
    }
    const span = Math.max(0.01, end - t);
    // breathing
    const nb = Math.max(1, Math.floor(span / .8));
    tl.to(ch.body, { y: -6, duration: Math.min(.8,span), yoyo: true, repeat: nb - 1, ease: "sine.inOut" }, t);
    if (P.wave) {
      const n = Math.max(1, Math.floor(span / .25));
      tl.to(ch.armR, { rotation: -120, svgOrigin: "237 215", duration: Math.min(.25,span), yoyo: true, repeat: n - 1, ease: "sine.inOut" }, t);
    }
    if (P.hop) {
      const n = Math.max(1, Math.floor(span / .3));
      tl.to(ch.g, { y: -28, duration: Math.min(.3,span), yoyo: true, repeat: n - 1, ease: "power1.out" }, t);
    }
    if (P.walk) {
      const n = Math.max(1, Math.floor(span / .45));
      tl.fromTo(ch.legL, { rotation: -22, svgOrigin: "123 330" }, { rotation: 22, svgOrigin: "123 330", duration: Math.min(.45,span), yoyo: true, repeat: n - 1, ease: "sine.inOut" }, t);
      tl.fromTo(ch.legR, { rotation: 22, svgOrigin: "177 330" }, { rotation: -22, svgOrigin: "177 330", duration: Math.min(.45,span), yoyo: true, repeat: n - 1, ease: "sine.inOut" }, t);
      tl.fromTo(ch.armL, { rotation: 24, svgOrigin: "63 215" }, { rotation: -24, svgOrigin: "63 215", duration: Math.min(.45,span), yoyo: true, repeat: n - 1, ease: "sine.inOut" }, t);
      tl.fromTo(ch.armR, { rotation: -24, svgOrigin: "237 215" }, { rotation: 24, svgOrigin: "237 215", duration: Math.min(.45,span), yoyo: true, repeat: n - 1, ease: "sine.inOut" }, t);
    }
    const swing = (target, from, to, seconds, extra = {}) => {
      const duration = Math.min(seconds, span);
      tl.fromTo(target, from, {...to, ...extra, duration, yoyo:true, repeat:Math.max(0,Math.floor(span / duration)-1), ease:"sine.inOut", immediateRender:false}, t);
    };
    if (P.idle) {
      swing(ch.body, {rotation:-1.8}, {rotation:1.8}, 1.1);
      swing(ch.head, {rotation:2}, {rotation:-2}, 1.5, {svgOrigin:"150 170"});
    }
    if (P.run) {
      tl.set(ch.body, {rotation:-9,y:-8,svgOrigin:"150 330"}, t);
      tl.set(ch.foreL, {rotation:-65}, t);
      tl.set(ch.foreR, {rotation:65}, t);
      swing(ch.legL, {rotation:-40}, {rotation:40}, .21, {svgOrigin:"123 330"});
      swing(ch.legR, {rotation:40}, {rotation:-40}, .21, {svgOrigin:"177 330"});
      swing(ch.shins[0], {rotation:30}, {rotation:95}, .21);
      swing(ch.shins[1], {rotation:95}, {rotation:30}, .21);
      swing(ch.armL, {rotation:60}, {rotation:-60}, .21);
      swing(ch.armR, {rotation:-60}, {rotation:60}, .21);
      swing(ch.g, {y:0}, {y:-16}, .105);
    }
    if (P.laugh) {
      tl.set(ch.foreL, {rotation:-55}, t);
      tl.set(ch.foreR, {rotation:55}, t);
      swing(ch.body, {y:0}, {y:-9}, .13);
      swing(ch.head, {rotation:-5}, {rotation:5}, .26, {svgOrigin:"150 170"});
    }
    if (P.count) {
      tl.set(ch.handR, {rotation:145,svgOrigin:"237 358"}, t);
      const count = Math.max(1,Math.min(5,m.count || 3));
      ch.fingers.slice(0,count).forEach((finger, i) => tl.set(finger, {opacity:1}, t + span * i / count));
    }
    if (P.confused) {
      tl.set(ch.armR, {rotation:-170}, t);
      tl.set(ch.foreR, {rotation:-35}, t);
      tl.set(ch.foreL, {rotation:65}, t);
      swing(ch.head, {rotation:-10}, {rotation:-5}, .7, {svgOrigin:"150 170"});
    }
    if (P.ride) {
      tl.set(ch.foreL, {rotation:-15}, t);
      tl.set(ch.armR, {y:-25}, t);
      swing(ch.legL, {rotation:-40}, {rotation:-60}, .35, {svgOrigin:"123 330"});
      swing(ch.legR, {rotation:10}, {rotation:35}, .35, {svgOrigin:"177 330"});
      swing(ch.shins[0], {rotation:70}, {rotation:85}, .35);
      swing(ch.shins[1], {rotation:-45}, {rotation:-70}, .35);
      [65,255].forEach((cx,i) => tl.fromTo(ch.wheels[i], {rotation:0}, {rotation:span*180,svgOrigin:`${cx} 451`,duration:span,ease:"none",immediateRender:false}, t));
      tl.fromTo(ch.crank, {rotation:0}, {rotation:span*360,svgOrigin:"169 451",duration:span,ease:"none",immediateRender:false}, t);
    }
    if (P.up) tl.set(ch.body, { y: -P.up }, t);
    if (speaking) lipSync(tl, ch.talk, env, t + 0.2, end - 0.1);
  }

  /* ---------- sets ---------- */
  const F = (v) => "fill:" + v;
  const sky = "color-mix(in srgb, var(--accent2) 26%, var(--bg))";
  const SETS = {
    plain: (g) => {
      sv("rect", { x: -100, y: 0, width: 1200, height: 700, style: F("color-mix(in srgb, var(--accent) 10%, var(--bg))") }, g.far);
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("color-mix(in srgb, var(--ink) 10%, var(--bg))") }, g.near);
    },
    village: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F(sky) }, g.far);
      sv("circle", { cx: 830, cy: 130, r: 64, style: F("var(--accent2)") }, g.far);
      sv("path", { d: "M-20 470 Q200 330 420 440 T820 410 T1040 450 V700 H-20 Z", style: F("color-mix(in srgb, #10b981 55%, var(--bg))") }, g.far);
      [[180, 420], [560, 400], [820, 430]].forEach(([x, y]) => {
        sv("rect", { x, y: y - 60, width: 130, height: 90, style: F("#d6a96b") }, g.mid);
        sv("path", { d: "M" + (x - 14) + " " + (y - 58) + " L" + (x + 65) + " " + (y - 130) + " L" + (x + 144) + " " + (y - 58) + " Z", style: F("#b45309") }, g.mid);
        sv("rect", { x: x + 50, y: y - 20, width: 30, height: 50, style: F("#7c4a1e") }, g.mid);
      });
      [[90, 470], [420, 480], [940, 480]].forEach(([x, y]) => {
        sv("rect", { x: x - 10, y: y - 40, width: 20, height: 80, style: F("#7c4a1e") }, g.mid);
        sv("circle", { cx: x, cy: y - 70, r: 55, style: F("#22a06b") }, g.mid);
      });
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("color-mix(in srgb, #22a06b 60%, #7c4a1e)") }, g.near);
    },
    market: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F(sky) }, g.far);
      [[60, 0], [360, 1], [660, 2]].forEach(([x, i]) => {
        sv("rect", { x, y: 360, width: 260, height: 200, style: F("#e9c991") }, g.mid);
        for (let k = 0; k < 6; k++) sv("rect", { x: x + k * 44 - 4, y: 300, width: 44, height: 70, style: F(k % 2 ? "var(--accent)" : "#ffffff") }, g.mid);
        const fruit = ["#ef4444", "#f59e0b", "#84cc16"][i];
        for (let k = 0; k < 5; k++) sv("circle", { cx: x + 40 + k * 44, cy: 500, r: 20, style: F(fruit) }, g.mid);
      });
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("#c9b08a") }, g.near);
    },
    home: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F("color-mix(in srgb, var(--accent2) 22%, #fff7ed)") }, g.far);
      sv("rect", { x: 620, y: 130, width: 250, height: 220, rx: 14, style: F("#bfe3ff") }, g.mid);
      sv("path", { d: "M745 130 V350 M620 240 H870", stroke: "#fff", "stroke-width": 10 }, g.mid);
      sv("rect", { x: 70, y: 380, width: 340, height: 160, rx: 40, style: F("var(--accent)") }, g.mid);
      sv("rect", { x: 70, y: 330, width: 340, height: 90, rx: 40, style: F("color-mix(in srgb, var(--accent) 80%, #000)") }, g.mid);
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("#b08968") }, g.near);
    },
    office: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F("color-mix(in srgb, var(--ink) 6%, var(--bg))") }, g.far);
      sv("rect", { x: 80, y: 120, width: 300, height: 220, rx: 10, style: F("#bfe3ff") }, g.far);
      sv("rect", { x: 560, y: 400, width: 360, height: 28, style: F("#8b6b4a") }, g.mid);
      sv("rect", { x: 580, y: 428, width: 20, height: 140, style: F("#8b6b4a") }, g.mid);
      sv("rect", { x: 880, y: 428, width: 20, height: 140, style: F("#8b6b4a") }, g.mid);
      sv("rect", { x: 650, y: 300, width: 170, height: 100, rx: 8, style: F("#1f2937") }, g.mid);
      sv("rect", { x: 660, y: 310, width: 150, height: 78, style: F("color-mix(in srgb, var(--accent) 70%, #fff)") }, g.mid);
      sv("circle", { cx: 150, cy: 470, r: 50, style: F("#22a06b") }, g.mid);
      sv("rect", { x: 122, y: 500, width: 56, height: 60, style: F("#b45309") }, g.mid);
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("color-mix(in srgb, var(--ink) 14%, var(--bg))") }, g.near);
    },
    classroom: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F("color-mix(in srgb, var(--accent2) 18%, #fffbeb)") }, g.far);
      sv("rect", { x: 200, y: 110, width: 600, height: 280, rx: 12, style: F("#245c4a") }, g.mid);
      sv("rect", { x: 200, y: 110, width: 600, height: 280, rx: 12, fill: "none", stroke: "#b08968", "stroke-width": 14 }, g.mid);
      sv("path", { d: "M260 190 q60 -30 120 0 t120 0", stroke: "#fff", "stroke-width": 6, fill: "none", opacity: 0.8 }, g.mid);
      [[90, 470], [770, 470]].forEach(([x, y]) => {
        sv("rect", { x, y, width: 150, height: 20, style: F("#b08968") }, g.mid);
        sv("rect", { x: x + 12, y: y + 20, width: 14, height: 90, style: F("#8b6b4a") }, g.mid);
        sv("rect", { x: x + 124, y: y + 20, width: 14, height: 90, style: F("#8b6b4a") }, g.mid);
      });
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("#c9b08a") }, g.near);
    },
    street: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F(sky) }, g.far);
      [[0, 300, 200], [190, 240, 170], [380, 330, 220], [600, 260, 180], [790, 320, 210]].forEach(([x, y, w], i) => {
        sv("rect", { x, y, width: w, height: 330, style: F(["#94a3b8", "#cbd5e1", "#a8b5c9", "#b8c4d6", "#9aa7bb"][i]) }, g.mid);
        for (let r = 0; r < 4; r++) for (let c = 0; c < Math.floor(w / 56); c++) sv("rect", { x: x + 16 + c * 56, y: y + 24 + r * 70, width: 30, height: 40, style: F("#fde68a") }, g.mid);
      });
      sv("rect", { x: 880, y: 330, width: 10, height: 240, style: F("#475569") }, g.mid);
      sv("circle", { cx: 885, cy: 325, r: 20, style: F("#fde047") }, g.mid);
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("#64748b") }, g.near);
      sv("path", { d: "M0 640 H1000", stroke: "#fff", "stroke-width": 6, "stroke-dasharray": "50 40" }, g.near);
    },
    nature: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F(sky) }, g.far);
      sv("circle", { cx: 150, cy: 120, r: 58, style: F("var(--accent2)") }, g.far);
      sv("path", { d: "M-20 480 L180 260 L330 400 L520 220 L730 420 L880 300 L1040 470 V700 H-20 Z", style: F("color-mix(in srgb, #64748b 55%, var(--bg))") }, g.far);
      sv("path", { d: "M-20 520 Q250 430 500 500 T1040 480 V700 H-20 Z", style: F("#22a06b") }, g.mid);
      [[130, 520], [830, 500], [900, 540]].forEach(([x, y]) => {
        sv("rect", { x: x - 10, y: y - 30, width: 20, height: 70, style: F("#7c4a1e") }, g.mid);
        sv("path", { d: "M" + (x - 60) + " " + (y - 20) + " L" + x + " " + (y - 150) + " L" + (x + 60) + " " + (y - 20) + " Z", style: F("#15803d") }, g.mid);
      });
      sv("rect", { x: -100, y: 570, width: 1200, height: 400, style: F("#4d9f55") }, g.near);
    },
    studio: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F("color-mix(in srgb, var(--ink) 80%, var(--accent))") }, g.far);
      sv("path", { d: "M300 0 L180 600 H820 L700 0 Z", fill: "rgba(255,255,255,.10)" }, g.far);
      sv("rect", { x: 80, y: 80, width: 140, height: 300, style: F("var(--accent)") }, g.mid);
      sv("rect", { x: 780, y: 80, width: 140, height: 300, style: F("var(--accent)") }, g.mid);
      sv("rect", { x: 480, y: 430, width: 10, height: 130, style: F("#94a3b8") }, g.mid);
      sv("ellipse", { cx: 485, cy: 420, rx: 24, ry: 34, style: F("#334155") }, g.mid);
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("color-mix(in srgb, var(--ink) 55%, #000)") }, g.near);
    },
    shop: (g) => {
      sv("rect", { x: -100, width: 1200, height: 700, style: F("color-mix(in srgb, var(--accent2) 16%, #fff)") }, g.far);
      for (let r = 0; r < 3; r++) {
        sv("rect", { x: 60, y: 140 + r * 120, width: 380, height: 14, style: F("#8b6b4a") }, g.mid);
        for (let k = 0; k < 7; k++) sv("rect", { x: 74 + k * 52, y: 92 + r * 120, width: 38, height: 48, rx: 6, style: F(["var(--accent)", "var(--accent2)", "#3b82f6", "#10b981"][(k + r) % 4]) }, g.mid);
      }
      sv("rect", { x: 560, y: 410, width: 360, height: 150, style: F("#8b6b4a") }, g.mid);
      sv("rect", { x: 580, y: 360, width: 110, height: 60, rx: 6, style: F("#1f2937") }, g.mid);
      sv("rect", { x: -100, y: 560, width: 1200, height: 400, style: F("#c9b08a") }, g.near);
    },
  };

  function buildSet(name) {
    const svg = sv("svg", { viewBox: "0 0 1000 700", class: "cn-svg", preserveAspectRatio: "xMidYMid slice" });
    const far = sv("g", { class: "cn-far" }, svg), mid = sv("g", { class: "cn-mid" }, svg), near = sv("g", { class: "cn-near" }, svg);
    (SETS[name] || SETS.plain)({ far, mid, near });
    return { svg, far, mid, near };
  }

  /* ---------- the cartoon element ---------- */
  C.cartoon = (d, ctx) => {
    const wrap = h("div", "cn cn-style-" + (d.character_style || "classic") + " cn-light-" + (d.lighting || "day"));
    const fullScene = d.framing === "scene";
    if(fullScene) {
      wrap.classList.add("cn-scene");
      wrap.style.width=ctx.D.format.width+"px";
      wrap.style.height=ctx.D.format.height+"px";
      wrap.style.setProperty("--scene-height",ctx.D.format.height+"px");
    }
    const stageEl = h("div", "cn-stage" + ((d.labels||[]).length ? " cn-has-labels" : ""));
    wrap.appendChild(stageEl);
    const set = buildSet(d.set || "plain");
    if (fullScene && ctx.D.format.height > ctx.D.format.width * 1.2) set.svg.setAttribute("viewBox", "0 105 1000 700");   // tall frame: the floor rises to meet the feet, above the captions
    const world=d.world==='3d'&&X.storyWorld?X.storyWorld(d,ctx.D.format):null;
    stageEl.appendChild(world?world.canvas:set.svg);
    const addArtifact = (a) => {
      const m = ctx.D.media && ctx.D.media[a.media];
      if (!m || m.kind === "video") return;
      const img = h("img", "cn-artifact");
      img.src = m.src; img.alt = "";
      Object.assign(img.style, {left:a.x*100+"%",top:a.y*100+"%",width:a.width*100+"%",height:a.height*100+"%",transform:`translate(-50%,-50%) rotate(${a.rotation||0}deg)`});
      stageEl.appendChild(img);
    };
    (d.artifacts || []).filter(a=>a.depth==="behind").forEach(addArtifact);
    (d.labels || []).forEach(a=>{
      const label = h("div", "cn-environment-text cn-text-"+a.treatment, a.text);
      Object.assign(label.style,{left:a.x*100+"%",top:a.y*100+"%",width:a.width*100+"%",transform:`translate(-50%,-50%) rotate(${a.rotation||0}deg)`});
      stageEl.appendChild(label);
    });
    const actors = d.cast.map((m, i) => {
      const box = h("div", "cn-actor");
      box.setAttribute("data-name", m.name || m.who || "");
      const svg = sv("svg", { viewBox: "0 0 300 520", class: "cn-char" });
      const ch = character(m, i);
      svg.appendChild(ch.g);
      box.appendChild(svg);
      const sc = ch.scale;
      box.style.left = (m.x * 100) + "%";
      if (m.y != null) box.style.bottom = ((1 - m.y) * 100) + "%";
      box.style.setProperty("--k", sc);
      if (m.flip) svg.style.transform = "scaleX(-1)";
      stageEl.appendChild(box);
      if (m.name && !fullScene) box.appendChild(h("div", "cn-name", m.name));
      return { box, ch, m };
    });
    (d.artifacts || []).filter(a=>a.depth!=="behind").forEach(addArtifact);
    const props = (d.props || []).map((k, i) => {
      const p = h("div", "cn-prop");
      p.innerHTML = (ctx.D.stickers && ctx.D.stickers[k]) || "";
      p.style.left = (i % 2 ? 84 - i * 4 : 10 + i * 5) + "%";
      stageEl.appendChild(p);
      return p;
    });
    let bubble = null;
    if (d.bubble) {
      bubble = h("div", "cn-bubble");
      bubble.appendChild(rt("span", "cn-btext", d.bubble));
      bubble.appendChild(h("i", "cn-tail"));
      const sp = d.cast[Math.min(d.speaker || 0, d.cast.length - 1)];
      bubble.style.left = Math.min(66, Math.max(4, sp.x * 100 - 22)) + "%";
      stageEl.appendChild(bubble);
    }
    return {
      el: wrap,
      backdrop: fullScene,
      enter(tl, t, M, c, sc) {
        const end = sc ? sc.end : t + 4;
        if(world) world.animate(tl,t,end);
        const env = ctx.D.envelope;
        tl.fromTo(wrap, { opacity: fullScene ? 1 : 0, scale: fullScene ? 1 : .92, y: fullScene ? 0 : 30 }, { opacity: 1, scale: 1, y: 0, duration: M.dur + 0.15, ease: M.ease }, t);
        // camera: a slow push-in with parallax between the layers
        const span = Math.max(1, end - t);
        const camera = d.camera || "push";
        if (camera !== "still") {
          const from = camera === "pull" ? 1.09 : camera === "pan" ? 1.08 : 1;
          const to = camera === "pull" ? 1 : camera === "pan" ? 1.08 : 1.09;
          tl.fromTo(stageEl, {scale:from,xPercent:camera==="pan"?-2:0}, {scale:to,xPercent:camera==="pan"?2:0,duration:span,ease:"none",transformOrigin:"50% 60%"},t);
          tl.fromTo(set.far, { x: -8 }, { x: 8, duration: span, ease: "none" }, t);
          tl.fromTo(set.mid, { x: -18 }, { x: 18, duration: span, ease: "none" }, t);
        }
        actors.forEach((a, i) => {
          const chosen = a.m.arrive != null;                   // the director may say when each character arrives; 0 is already there
          const at = t + (chosen ? a.m.arrive : 0.15 + i * 0.22);
          const walking = a.m.pose === "walk" || a.m.pose === "run" || a.m.pose === "ride";
          const dir = a.m.flip ? -1 : 1;
          if (chosen && a.m.arrive === 0) gsap.set(a.box, { xPercent: -50 });
          else tl.fromTo(a.box, { opacity: 0, y: 40, xPercent: -50 + (walking ? -dir * 14 : 0) }, { opacity: 1, y: 0, xPercent: -50, duration: M.dur + 0.2, ease: "back.out(1.6)", data: chosen ? "chosen" : undefined }, at);
          if (walking) tl.to(a.box, { xPercent: -50 + dir * 22, duration: Math.max(1, end - at - 0.3), ease: "none" }, at + 0.3);
          const speaking = i === Math.min(d.speaker || 0, actors.length - 1) && !!d.bubble;
          const cues = (d.cues||[]).filter(c=>c.actor===i&&c.end>at&&c.start<end).sort((a,b)=>a.start-b.start);
          if (!cues.length) animateCharacter(tl,a.ch,a.m,at,end,env,speaking,M);
          else {
            let cursor=at;
            cues.forEach(cue=>{
              const start=Math.max(cursor,at,cue.start), stop=Math.min(end,cue.end);
              if(start>cursor) animateCharacter(tl,a.ch,a.m,cursor,start,env,speaking,M);
              if(stop>start) animateCharacter(tl,a.ch,{...a.m,pose:cue.pose,expression:cue.expression,count:cue.count??a.m.count},start,stop,env,speaking,M);
              cursor=Math.max(cursor,stop);
            });
            if(cursor<end) animateCharacter(tl,a.ch,a.m,cursor,end,env,speaking,M);
          }
        });
        props.forEach((p, i) => {
          tl.fromTo(p, { opacity: 0, scale: 0.2, y: 20 }, { opacity: 1, scale: 1, y: 0, duration: M.dur + 0.2, ease: "back.out(2.4)" }, t + 0.5 + i * 0.2);
          idle(tl, p, t + 1.2 + i * 0.2, end, 10, 1.1);
        });
        if (bubble) tl.fromTo(bubble, { opacity: 0, scale: 0.6, transformOrigin: "20% 100%" }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(2)" }, t + 0.6);
      },
    };
  };

  /* ---------- speaker card (discussion) ---------- */
  const AV = ["#ff7a59", "#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444"];
  C.speaker_card = (d, ctx) => {
    const wrap = h("div", "spk spk-" + (d.side || "left"));
    const av = h("div", "spk-av");
    const svg = sv("svg", { viewBox: "0 0 200 200", class: "spk-svg" });
    sv("circle", { cx: 100, cy: 100, r: 100, fill: AV[d.color % 6] }, svg);
    const ch = character({ who: hash(d.name) % 2 ? "woman" : "man", name: d.name, pose: "stand", expression: "neutral" }, 0);
    const inner = sv("g", { transform: "translate(-35 -6) scale(0.9)" }, svg);
    inner.appendChild(ch.g);
    // only the head and shoulders show: clip to the avatar circle
    const clip = sv("clipPath", { id: "av" + hash(d.name + d.text) }, svg);
    sv("circle", { cx: 100, cy: 100, r: 100 }, clip);
    inner.setAttribute("clip-path", "url(#av" + hash(d.name + d.text) + ")");
    av.appendChild(svg);
    const body = h("div", "spk-body");
    const nm = rt("div", "spk-name", d.name);
    const bars = h("div", "spk-bars");
    const bs = [0, 1, 2, 3, 4].map(() => { const b = h("i", "spk-bar"); bars.appendChild(b); return b; });
    const head = h("div", "spk-head");
    head.appendChild(nm);
    head.appendChild(bars);
    body.appendChild(head);
    let txt = null;
    if (d.text) {
      txt = rt("div", "spk-text", d.text);
      body.appendChild(txt);
    }
    wrap.appendChild(av);
    wrap.appendChild(body);
    return {
      el: wrap,
      enter(tl, t, M, c, sc) {
        const end = sc ? sc.end : t + 4;
        const env = ctx.D.envelope;
        tl.fromTo(av, { opacity: 0, scale: 0.4, x: d.side === "right" ? 60 : -60 }, { opacity: 1, scale: 1, x: 0, duration: M.dur + 0.2, ease: "back.out(2)" }, t);
        tl.fromTo(body, { opacity: 0, x: d.side === "right" ? 50 : -50 }, { opacity: 1, x: 0, duration: M.dur + 0.1, ease: M.ease }, t + 0.15);
        ch.mouths.neutral.setAttribute("opacity", 1);
        lipSync(tl, ch.talk, env, t + 0.3, end - 0.1);
        // equaliser bars follow the loudness
        for (let tt = t + 0.3; tt < end - 0.1; tt += 0.12) {
          bs.forEach((b, i) => {
            const v = envelopeAt(env, tt + i * 0.03);
            tl.set(b, { scaleY: 0.2 + 0.8 * Math.min(1, v * (0.7 + (i % 3) * 0.25)) }, tt);
          });
        }
      },
    };
  };

  window.VTX.lipSync = lipSync;
  window.VTX.envelopeAt = envelopeAt;
})();
