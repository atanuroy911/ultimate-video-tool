/* Stick-figure engine: a 15-joint rig with fixed bone lengths, two-bone IK for hands, feet that stay on the floor, a verb library, sets and props,
   speech bubbles, a camera. Everything is a pure function of time (poses are computed from the action list), so seeking is frame-exact:
   one tween per scene calls draw(t) and draw(t) rebuilds the whole picture. No external art.
   Input: scene.stick = { set:{kind,props}, camera:{shot,move}, cast:[{id,role,name,style}], actions:[{who,do,start,end,from,to,...}] }. */
(function () {
  "use strict";
  const X = window.VTX;
  if (!X) return;
  const NS = "http://www.w3.org/2000/svg";
  const sv = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a || 1), 0, 1); return t * t * (3 - 2 * t); };
  const RAD = Math.PI / 180;
  const FLOOR = 520, TH = 60, SH = 60, TORSO = 100, NECK = 12, HR = 32, UA = 55, FA = 52;
  const R = Math.round;
  const K = 1.3;                              // drawn size of a figure relative to the rig's units

  /* ---------- props and sets ---------- */
  const SPOT = { board: [760, 270], sign: [780, 300], desk: [250, 470], door: [110, 380], window: [440, 95], book: [270, 440], laptop: [240, 430], chart: [760, 270],
    plant: [900, 450], lamp: [140, 350], bench: [330, 490], car: [780, 460], shop: [600, 370], tree: [880, 350], rock: [330, 495], river: [560, 508], sun: [880, 110],
    flower: [190, 495], table: [260, 480], flask: [260, 430], microscope: [330, 440], planet: [780, 170], rocket: [180, 300], star: [480, 90], moon: [900, 130],
    sofa: [260, 470], tv: [760, 370], podium: [790, 460], screen: [660, 280], curtain: [110, 290], stall: [760, 410], basket: [260, 490], scale: [500, 490],
    stove: [250, 480], fridge: [140, 440], plate: [260, 452], swing: [820, 420], fence: [600, 480], safe: [840, 470], bed: [300, 500], shelf: [140, 455], counter: [700, 480],
    machine: [800, 480], pipe: [480, 480], crate: [620, 486], gauge: [900, 350], barn: [820, 460], haystack: [620, 480], plane: [780, 330], suitcase: [330, 496], tower: [850, 370],
    peak: [650, 460], flag: [880, 460], palm: [880, 360], boat: [640, 500] };
  const P = (g, tag, a) => sv(tag, Object.assign({ fill: "none", stroke: "var(--ink)", "stroke-width": 5, "stroke-linecap": "round", "stroke-linejoin": "round" }, a), g);
  const CARD = "var(--card)";
  const DRAW = {
    board: (g) => { P(g, "rect", { x: -150, y: -95, width: 300, height: 190, rx: 8, fill: CARD }); P(g, "path", { d: "M-150 95 h300 M-100 95 v20 M100 95 v20" }); },
    sign: (g) => { P(g, "rect", { x: -90, y: -60, width: 180, height: 90, rx: 8, fill: CARD }); P(g, "path", { d: "M0 30 v70" }); },
    chart: (g) => { P(g, "rect", { x: -130, y: -90, width: 260, height: 180, rx: 8, fill: CARD }); P(g, "path", { d: "M-100 60 L-50 10 L0 35 L60 -40 L100 -20" }); },
    screen: (g) => { P(g, "rect", { x: -150, y: -90, width: 300, height: 170, rx: 8, fill: CARD }); P(g, "path", { d: "M0 80 v30 M-50 110 h100" }); },
    desk: (g) => { P(g, "path", { d: "M-100 -20 h200 M-85 -20 v95 M85 -20 v95" }); },
    table: (g) => { P(g, "path", { d: "M-100 -20 h200 M-85 -20 v90 M85 -20 v90" }); },
    door: (g) => { P(g, "rect", { x: -50, y: -140, width: 100, height: 270, rx: 6, fill: CARD }); P(g, "circle", { cx: 28, cy: 0, r: 5 }); },
    window: (g) => { P(g, "rect", { x: -70, y: -60, width: 140, height: 120, rx: 6, fill: CARD }); P(g, "path", { d: "M0 -60 v120 M-70 0 h140" }); },
    book: (g) => { P(g, "rect", { x: -22, y: -16, width: 44, height: 32, rx: 4, fill: CARD }); P(g, "path", { d: "M0 -16 v32" }); },
    laptop: (g) => { P(g, "rect", { x: -34, y: -40, width: 68, height: 44, rx: 4, fill: CARD }); P(g, "path", { d: "M-48 12 h96" }); },
    plant: (g) => { P(g, "path", { d: "M-24 70 l6 -40 h36 l6 40 z" }); P(g, "path", { d: "M0 30 q-30 -40 -40 -70 M0 30 q4 -60 0 -90 M0 30 q30 -40 40 -70" }); },
    lamp: (g) => { P(g, "path", { d: "M0 160 V-60 M-30 -60 h60 l-12 -34 h-36 z" }); },
    bench: (g) => { P(g, "path", { d: "M-80 -10 h160 M-70 -10 v40 M70 -10 v40" }); },
    car: (g) => { P(g, "path", { d: "M-110 10 h220 v-40 l-40 -10 l-30 -36 h-70 l-30 36 l-50 10 z" }); P(g, "circle", { cx: -60, cy: 14, r: 22, fill: CARD }); P(g, "circle", { cx: 60, cy: 14, r: 22, fill: CARD }); },
    shop: (g) => { P(g, "rect", { x: -110, y: -60, width: 220, height: 170, fill: CARD }); P(g, "path", { d: "M-120 -60 h240 l-14 -36 h-212 z" }); },
    tree: (g) => { P(g, "path", { d: "M0 160 V20" }); P(g, "circle", { cx: 0, cy: -30, r: 70, fill: CARD }); },
    rock: (g) => { P(g, "path", { d: "M-50 20 l12 -34 l40 -14 l40 20 l8 28 z", fill: CARD }); },
    river: (g) => { P(g, "path", { d: "M-300 0 q40 -14 80 0 t80 0 t80 0 t80 0 t80 0 t80 0" }); },
    sun: (g) => { P(g, "circle", { r: 34 }); P(g, "path", { d: "M0 -50 v-18 M0 50 v18 M-50 0 h-18 M50 0 h18 M36 -36 l12 -12 M-36 36 l-12 12 M36 36 l12 12 M-36 -36 l-12 -12" }); },
    flower: (g) => { P(g, "path", { d: "M0 30 v-50" }); P(g, "circle", { cy: -30, r: 12, fill: "var(--accent2)" }); },
    flask: (g) => { P(g, "path", { d: "M-10 -34 h20 v26 l22 40 q4 14 -10 14 h-44 q-14 0 -10 -14 l22 -40 z", fill: CARD }); },
    microscope: (g) => { P(g, "path", { d: "M-20 40 h60 M0 40 v-30 M-10 -50 l30 40 M-14 -56 l14 -16 l14 16" }); },
    planet: (g) => { P(g, "circle", { r: 44, fill: CARD }); P(g, "path", { d: "M-70 14 q70 -36 140 -14" }); },
    rocket: (g) => { P(g, "path", { d: "M0 -80 q30 40 24 100 h-48 q-6 -60 24 -100 z M-24 20 l-22 30 l22 -8 M24 20 l22 30 l-22 -8", fill: CARD }); },
    star: (g) => { P(g, "path", { d: "M0 -26 l8 18 l20 2 l-15 13 l5 20 l-18 -11 l-18 11 l5 -20 l-15 -13 l20 -2 z" }); },
    moon: (g) => { P(g, "path", { d: "M10 -40 a40 40 0 1 0 20 70 a32 32 0 0 1 -20 -70 z" }); },
    sofa: (g) => { P(g, "path", { d: "M-100 20 v-50 q0 -20 20 -20 h160 q20 0 20 20 v50 z M-100 20 v30 M100 20 v30" }); },
    tv: (g) => { P(g, "rect", { x: -80, y: -50, width: 160, height: 100, rx: 8, fill: CARD }); P(g, "path", { d: "M-30 50 l-10 20 h80 l-10 -20" }); },
    podium: (g) => { P(g, "path", { d: "M-50 -30 h100 l-12 100 h-76 z", fill: CARD }); },
    curtain: (g) => { P(g, "path", { d: "M-40 -150 q30 140 0 290 M40 -150 q-30 140 0 290" }); },
    stall: (g) => { P(g, "path", { d: "M-110 -40 h220 l-16 -40 h-188 z M-100 -40 v100 M100 -40 v100 M-100 20 h200" }); },
    basket: (g) => { P(g, "path", { d: "M-40 -10 h80 l-10 44 h-60 z M-34 -10 q34 -50 68 0" }); },
    scale: (g) => { P(g, "path", { d: "M0 40 V-30 M-60 -30 h120 M-60 -30 l-20 36 h40 z M60 -30 l-20 36 h40 z" }); },
    ball: (g) => { P(g, "circle", { r: 16, fill: "var(--accent)" }); },
    wallet: (g) => { P(g, "rect", { x: -20, y: -13, width: 40, height: 26, rx: 5, fill: "var(--accent2)" }); P(g, "circle", { cx: 10, cy: 0, r: 3 }); },
    stove: (g) => { P(g, "rect", { x: -50, y: -30, width: 100, height: 70, rx: 6, fill: CARD }); P(g, "circle", { cx: -24, cy: -14, r: 11 }); P(g, "circle", { cx: 24, cy: -14, r: 11 }); P(g, "path", { d: "M-30 18 h8 M-4 18 h8 M22 18 h8" }); },
    fridge: (g) => { P(g, "rect", { x: -34, y: -100, width: 68, height: 180, rx: 8, fill: CARD }); P(g, "path", { d: "M-34 -30 h68 M20 -78 v-14 M20 -20 v26" }); },
    plate: (g) => { P(g, "ellipse", { rx: 28, ry: 8, fill: CARD }); P(g, "ellipse", { rx: 15, ry: 4 }); },
    swing: (g) => { P(g, "path", { d: "M-70 100 L-40 -100 L40 -100 L70 100 M-20 -100 v140 M20 -100 v140 M-28 40 h56" }); },
    fence: (g) => { P(g, "path", { d: "M-110 -20 h220 M-110 14 h220 M-100 -40 v80 M-60 -40 v80 M-20 -40 v80 M20 -40 v80 M60 -40 v80 M100 -40 v80" }); },
    safe: (g) => { P(g, "rect", { x: -50, y: -50, width: 100, height: 100, rx: 8, fill: CARD }); P(g, "circle", { cx: 6, cy: 0, r: 16 }); P(g, "path", { d: "M6 -10 v10 l7 5 M-40 50 v8 M40 50 v8" }); },
    bed: (g) => { P(g, "path", { d: "M-90 20 h180 M-90 20 v-64 M90 20 v-20 M-90 -6 h180" }); P(g, "rect", { x: -80, y: -26, width: 44, height: 20, rx: 8, fill: CARD }); },
    shelf: (g) => { P(g, "path", { d: "M-90 -60 h180 M-90 0 h180 M-90 60 h180 M-90 -60 v120 M90 -60 v120" }); P(g, "rect", { x: -70, y: -24, width: 26, height: 24, fill: CARD }); P(g, "rect", { x: 10, y: -34, width: 22, height: 34, fill: CARD }); P(g, "rect", { x: -50, y: 30, width: 34, height: 30, fill: CARD }); },
    counter: (g) => { P(g, "rect", { x: -100, y: -30, width: 200, height: 70, fill: CARD }); P(g, "path", { d: "M-108 -30 h216" }); },
    machine: (g) => { P(g, "rect", { x: -60, y: -60, width: 120, height: 100, rx: 8, fill: CARD }); P(g, "circle", { cx: -14, cy: -12, r: 22 }); P(g, "path", { d: "M-14 -34 v44 M-36 -12 h44 M30 -40 h16 M30 -20 h16" }); },
    pipe: (g) => { P(g, "path", { d: "M-120 -20 h200 q30 0 30 30 v60 M-60 -34 v28 M20 -34 v28" }); },
    crate: (g) => { P(g, "rect", { x: -34, y: -34, width: 68, height: 68, fill: CARD }); P(g, "path", { d: "M-34 -34 L34 34 M34 -34 L-34 34" }); },
    gauge: (g) => { P(g, "circle", { r: 40, fill: CARD }); P(g, "path", { d: "M0 0 L22 -22 M-30 20 a38 38 0 0 1 60 0" }); },
    barn: (g) => { P(g, "path", { d: "M-90 60 v-80 l90 -50 l90 50 v80 z", fill: CARD }); P(g, "rect", { x: -28, y: 0, width: 56, height: 60 }); P(g, "path", { d: "M-28 0 L28 60 M28 0 L-28 60" }); },
    haystack: (g) => { P(g, "path", { d: "M-60 40 q0 -70 60 -70 q60 0 60 70 z", fill: CARD }); P(g, "path", { d: "M-30 20 l16 -22 M0 24 l8 -30 M30 20 l-12 -24" }); },
    plane: (g) => { P(g, "path", { d: "M-100 0 q100 -40 200 0 q-20 20 -100 20 z", fill: CARD }); P(g, "path", { d: "M-10 0 l-40 -50 h20 l50 50 M-10 14 l-40 44 h20 l50 -44" }); },
    suitcase: (g) => { P(g, "rect", { x: -34, y: -24, width: 68, height: 48, rx: 6, fill: CARD }); P(g, "path", { d: "M-12 -24 v-10 h24 v10" }); },
    tower: (g) => { P(g, "rect", { x: -40, y: -150, width: 80, height: 300, fill: CARD }); P(g, "path", { d: "M-22 -120 h12 M10 -120 h12 M-22 -70 h12 M10 -70 h12 M-22 -20 h12 M10 -20 h12 M-22 30 h12 M10 30 h12 M-22 80 h12 M10 80 h12" }); },
    peak: (g) => { P(g, "path", { d: "M-120 60 l100 -150 l40 60 l30 -40 l110 130 z", fill: CARD }); P(g, "path", { d: "M-34 -64 l14 -26 l16 24" }); },
    flag: (g) => { P(g, "path", { d: "M0 60 V-100" }); P(g, "path", { d: "M0 -100 h50 l-10 20 l10 20 h-50", fill: "var(--accent)" }); },
    palm: (g) => { P(g, "path", { d: "M0 160 q-10 -80 8 -150" }); P(g, "path", { d: "M8 10 q-50 -30 -70 10 M8 10 q-20 -50 -60 -40 M8 10 q30 -50 70 -30 M8 10 q50 -10 60 30" }); },
    boat: (g) => { P(g, "path", { d: "M-80 0 h160 l-30 40 h-100 z", fill: CARD }); P(g, "path", { d: "M0 0 V-90" }); P(g, "path", { d: "M0 -90 l50 70 h-50", fill: "var(--accent2)" }); },
  };
  const ON_FLOOR = new Set(["desk", "table", "door", "plant", "lamp", "bench", "car", "shop", "tree", "rock", "river", "flower", "sofa", "podium", "stall", "basket", "scale", "microscope", "flask", "book", "laptop", "ball", "wallet", "stove", "fridge", "swing", "fence", "safe", "bed", "shelf", "counter", "machine", "crate", "barn", "haystack", "suitcase", "tower", "peak", "flag", "palm", "boat", "plate"]);
  const REST_Y = { ball: 504, wallet: 508, book: 504, rock: 495, flask: 500, suitcase: 496, crate: 486, plate: 508 };
  const HEIGHT = { child: 0.78, adult: 1, elder: 0.94 };

  function propSprite(name, art) {
    const g = sv("g", { class: "stk-prop" });
    if (DRAW[name]) DRAW[name](g);
    else if (art && art[name]) {
      try {
        const doc = new DOMParser().parseFromString(art[name], "image/svg+xml");
        const n = document.importNode(doc.documentElement, true);
        n.setAttribute("x", -34); n.setAttribute("y", -34); n.setAttribute("width", 68); n.setAttribute("height", 68);
        g.appendChild(n);
      } catch (e) { P(g, "circle", { r: 20, fill: CARD }); }
    } else {
      P(g, "circle", { r: 22, fill: CARD });
      const t = sv("text", { y: 9, "text-anchor": "middle", "font-size": 24, "font-weight": 800, fill: "var(--ink)", "font-family": "var(--font-body)" }, g);
      t.textContent = (name || "?").slice(0, 1).toUpperCase();
    }
    return g;
  }

  /* ---------- the rig ---------- */
  const fk = (deg, len) => [Math.sin(deg * RAD) * len, Math.cos(deg * RAD) * len];     // angle measured from straight down, positive = forward
  const FACE = {
    neutral: { m: "M-9 13 Q0 16 9 13", br: null },
    happy: { m: "M-11 9 Q0 25 11 9", br: null },
    sad: { m: "M-10 18 Q0 7 10 18", br: [-1, 1] },
    angry: { m: "M-9 16 L9 16", br: [2, -2] },
    surprised: { m: "M-5 12 Q0 22 5 12 Q0 6 -5 12", br: [-3, -3], big: 1 },
    confused: { m: "M-10 14 Q-4 8 0 14 T10 14", br: [-3, 1] },
    scared: { m: "M-9 17 Q-4 10 0 17 T9 17", br: [-2, -2], big: 1 },
  };

  function ik2(sx, sy, tx, ty) {         // two-bone IK in local coordinates; returns absolute upper-arm and forearm angles; clamps when out of reach
    let dx = tx - sx, dy = ty - sy, d = Math.hypot(dx, dy);
    const reach = UA + FA - 0.5, minr = Math.abs(UA - FA) + 1;
    const dd = clamp(d, minr, reach);
    const base = Math.atan2(dx, dy);
    const cosA = clamp((UA * UA + dd * dd - FA * FA) / (2 * UA * dd), -1, 1);
    const s = base - Math.acos(cosA);                                     // elbow bends down/back
    const ex = sx + Math.sin(s) * UA, ey = sy + Math.cos(s) * UA;
    const tx2 = sx + Math.sin(base) * dd, ty2 = sy + Math.cos(base) * dd;
    return [s / RAD, Math.atan2(tx2 - ex, ty2 - ey) / RAD];
  }

  /* a small sign that pops above a head or an actor: ! ? light bulb heart anger sweat zzz sparkle */
  function addMarks(o, root) {
    const g = sv("g", { opacity: 0 }, root);
    o.markG = g;
    o.marks = {};
    const mk = (name, fn) => { const m = sv("g", { opacity: 0 }, g); fn(m); o.marks[name] = m; };
    const T = (m, txt, size, fill) => { const t = sv("text", { "text-anchor": "middle", "font-size": size, "font-weight": 800, fill: fill || "var(--accent)", "font-family": "var(--font-head)", y: size * 0.35 }, m); t.textContent = txt; };
    mk("exclaim", (m) => T(m, "!", 70, "var(--accent)"));
    mk("question", (m) => T(m, "?", 70, "var(--accent2)"));
    mk("idea", (m) => { P(m, "path", { d: "M-14 8 q-18 -16 -10 -34 q10 -22 24 -22 q14 0 24 22 q8 18 -10 34 z", fill: "#fde047" }); P(m, "path", { d: "M-9 14 h18 M-7 22 h14" }); P(m, "path", { d: "M0 -62 v-12 M-34 -48 l-10 -8 M34 -48 l10 -8", "stroke-width": 4 }); });
    mk("heart", (m) => P(m, "path", { d: "M0 24 q-40 -26 -30 -50 q12 -22 30 -4 q18 -18 30 4 q10 24 -30 50 z", fill: "#fb7185", "stroke-width": 4 }));
    mk("anger", (m) => P(m, "path", { d: "M-24 -24 q10 8 4 20 M24 -24 q-10 8 -4 20 M-24 24 q10 -8 4 -20 M24 24 q-10 -8 -4 -20", stroke: "#ef4444", "stroke-width": 8 }));
    mk("sweat", (m) => P(m, "path", { d: "M0 -34 q-22 32 -12 46 q12 14 24 0 q10 -14 -12 -46 z", fill: "#7dd3fc", "stroke-width": 4 }));
    mk("zzz", (m) => { T(m, "Z", 46, "var(--accent2)"); const t = sv("text", { x: 28, y: -22, "text-anchor": "middle", "font-size": 32, "font-weight": 800, fill: "var(--accent2)", "font-family": "var(--font-head)" }, m); t.textContent = "z"; });
    mk("sparkle", (m) => { P(m, "path", { d: "M0 -34 l8 24 l24 8 l-24 8 l-8 24 l-8 -24 l-24 -8 l24 -8 z", fill: "#fde047", "stroke-width": 4 }); });
  }
  const MARK_RISE = 0.18;
  function showMark(o, t, x, y, sc, flip) {
    const m = (o.markList || []).find((e) => t >= e.t0 && t <= e.t1);
    if (!m) { o.markG.setAttribute("opacity", 0); return; }
    const u = clamp((t - m.t0) / MARK_RISE, 0, 1);
    const pop = u < 1 ? 1.25 * Math.sin(u * Math.PI * 0.5) : 1 + 0.08 * Math.sin((t - m.t0) * 9) * Math.max(0, 1 - (t - m.t0) / 1.2);
    for (const k in o.marks) o.marks[k].setAttribute("opacity", k === m.mark ? 1 : 0);
    o.markG.setAttribute("opacity", 1);
    o.markG.setAttribute("transform", `translate(${R(x)} ${R(y)}) scale(${(pop * sc * (flip || 1)).toFixed(3)} ${(pop * sc).toFixed(3)})`);
  }

  /* an actor drawn from a sticker (a fox, a coin, a wallet, a bulb): it walks, hops, spins, grows and talks by the same verbs */
  const ANIMAL_SIZE = { "1f418": 1.35, "1f981": 1.15, "1f405": 1.15, "1f43b": 1.2, "1f40e": 1.2, "1f42b": 1.2, "1f404": 1.15, "1f40a": 1.1,
    "1f42d": 0.5, "1f426": 0.55, "1f438": 0.5, "1f407": 0.6, "1f408": 0.65, "1f986": 0.6, "1f414": 0.6, "1f41c": 0.35, "1f41d": 0.4, "1f98b": 0.45, "1f40c": 0.4 };
  function buildActor(c, idx, root, o, propArt) {
    o.actor = true;
    // an illustrated character is a whole figure; an animal is drawn at character size when the story has no people (it IS the cast),
    // else sticker-sized beside them; a mouse stays smaller than a lion
    const life = ANIMAL_SIZE[(c.emoji || "").toLowerCase()] || 1;
    const size = (c.kind === "toon" ? 330 : (buildActor.noPeople ? 250 * life : 104 * Math.max(0.7, life))) * (HEIGHT[(c.style && c.style.height) || "adult"] || 1);
    o.size = size;
    o.k = K;
    const inner = sv("g", {}, root);
    o.inner = inner;
    const g = sv("g", {}, inner);
    o.sprite = g;
    const art = propArt && propArt["actor:" + c.id];
    if (art) {
      try {
        const doc = new DOMParser().parseFromString(art, "image/svg+xml");
        const n = document.importNode(doc.documentElement, true);
        n.setAttribute("x", -size / 2); n.setAttribute("y", -size); n.setAttribute("width", size); n.setAttribute("height", size);
        n.querySelectorAll("style").forEach((st) => st.remove());                  // a drawing's own CSS would also hide or show the other characters' mouths
        g.appendChild(n);
        const mouths = {};
        n.querySelectorAll(".mouth-group").forEach((m) => { const k = (/mouth-([A-HX])\b/.exec(m.getAttribute("class")) || [])[1]; if (k) mouths[k] = m; });
        if (mouths.X) o.mouths = mouths;                                           // a rigged cartoon character: it talks with the voice
      } catch (e) { P(g, "circle", { cy: -size / 2, r: size / 2.4, fill: CARD }); }
    } else {
      P(g, "circle", { cy: -size / 2, r: size / 2.4, fill: CARD });
      const t = sv("text", { y: -size / 2 + 10, "text-anchor": "middle", "font-size": 34, "font-weight": 800, fill: "var(--ink)", "font-family": "var(--font-body)" }, g);
      t.textContent = (c.name || c.id || "?").slice(0, 1).toUpperCase();
    }
    addMarks(o, root);
    return o;
  }

  /* WCAG relative luminance and contrast ratio, for "would this colour be seen on this background?" */
  const lum = (hex) => { const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim()); if (!m) return null; const v = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const contrast = (a, b) => { const la = lum(a), lb = lum(b); if (la == null || lb == null) return 21; return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05); };
  const BG = () => (getComputedStyle(document.documentElement).getPropertyValue("--bg") || "#ffffff").trim();

  function buildChar(c, idx, propArt) {
    const own = c.style && c.style.color && c.style.color !== "#1f2937" ? c.style.color : null;
    const col = own && contrast(own, BG()) >= 3 ? own : "var(--ink)";             // a figure that would disappear into the background (WCAG < 3:1) is drawn in the theme's ink
    const st = (o) => Object.assign({ fill: "none", stroke: col, "stroke-width": 9, "stroke-linecap": "round", "stroke-linejoin": "round" }, o || {});
    const root = sv("g", { class: "stk-ch" });
    const body = sv("g", {}, root);
    const o = { id: c.id, c, idx, root, body };
    if (c.kind === "emoji" || c.kind === "toon") return buildActor(c, idx, root, o, propArt);
    const acc = (c.style && c.style.accessory) || "none";
    const hfac = HEIGHT[(c.style && c.style.height) || "adult"] || 1;
    o.k = K * hfac;
    o.stoop = ((c.style && c.style.height) || "adult") === "elder" ? 7 : 0;
    const skin = (c.style && c.style.skin) || "var(--card)";
    const shirt = c.style && c.style.shirt;
    const hair = (c.style && c.style.hair) || "none";
    o.armB = sv("path", st({ opacity: 0.8 }), body);
    o.legB = sv("path", st({ opacity: 0.8 }), body);
    if (acc === "labcoat") o.coat = sv("path", { fill: "none", stroke: "#f8fafc", "stroke-width": 34, "stroke-linecap": "round", opacity: 0.95 }, body);
    if (shirt) o.shirt = sv("path", { fill: "none", stroke: shirt, "stroke-width": 30, "stroke-linecap": "round" }, body);
    if (acc === "apron") o.apron = sv("path", { fill: "none", stroke: "#f8fafc", "stroke-width": 22, "stroke-linecap": "round", opacity: 0.95 }, body);
    o.torso = sv("path", st({ "stroke-width": 10 }), body);
    o.legF = sv("path", st(), body);
    if (acc === "tie") o.tie = sv("path", { d: "M0 0 l-6 10 l6 26 l6 -26 z", fill: "var(--accent)", stroke: "none" }, body);
    if (acc === "scarf") o.scarf = sv("path", { d: "M-16 0 h32", stroke: "var(--accent)", "stroke-width": 12, "stroke-linecap": "round" }, body);
    o.head = sv("g", {}, body);
    const hshape = (c.style && c.style.head) || "round";
    if (hshape === "square") sv("rect", { x: -HR, y: -HR, width: HR * 2, height: HR * 2, rx: 10, fill: skin, stroke: col, "stroke-width": 8 }, o.head);
    else if (hshape === "oval") sv("ellipse", { rx: HR * 0.86, ry: HR * 1.08, fill: skin, stroke: col, "stroke-width": 8 }, o.head);
    else sv("circle", { r: HR, fill: skin, stroke: col, "stroke-width": 8 }, o.head);
    o.face = sv("g", {}, o.head);
    o.eyeL = sv("circle", { cx: -10, cy: -5, r: 3.4, fill: col }, o.face);
    o.eyeR = sv("circle", { cx: 10, cy: -5, r: 3.4, fill: col }, o.face);
    o.browL = sv("path", { d: "M-16 -13 L-4 -13", stroke: col, "stroke-width": 3.5, "stroke-linecap": "round", fill: "none" }, o.face);
    o.browR = sv("path", { d: "M4 -13 L16 -13", stroke: col, "stroke-width": 3.5, "stroke-linecap": "round", fill: "none" }, o.face);
    o.mouth = sv("path", { d: FACE.neutral.m, stroke: col, "stroke-width": 4, "stroke-linecap": "round", fill: "none" }, o.face);
    o.talk = sv("ellipse", { cx: 0, cy: 14, rx: 8, ry: 2, fill: col, opacity: 0 }, o.face);
    if (acc === "glasses") { P(o.face, "circle", { cx: -11, cy: -5, r: 10, stroke: col, "stroke-width": 3 }); P(o.face, "circle", { cx: 11, cy: -5, r: 10, stroke: col, "stroke-width": 3 }); P(o.face, "path", { d: "M-1 -5 h2", stroke: col, "stroke-width": 3 }); }
    if (acc === "hat") { P(o.head, "path", { d: "M-40 -26 h80", stroke: col, "stroke-width": 7 }); P(o.head, "rect", { x: -22, y: -64, width: 44, height: 38, fill: col, stroke: col }); }
    if (acc === "cap") { P(o.head, "path", { d: "M-32 -10 A32 32 0 0 1 32 -10 Z", fill: "var(--accent)", stroke: col, "stroke-width": 5 }); P(o.head, "path", { d: "M12 -12 L44 -6", stroke: col, "stroke-width": 6 }); }
    if (acc === "hair") P(o.head, "path", { d: "M-20 -29 l-6 -12 M-8 -33 l-3 -14 M6 -33 l3 -14 M20 -29 l6 -12", stroke: col, "stroke-width": 5 });
    if (hair === "short") P(o.head, "path", { d: "M-30 -8 Q-34 -40 0 -40 Q34 -40 30 -8 Q20 -26 0 -26 Q-20 -26 -30 -8 z", fill: col, stroke: col, "stroke-width": 4 });
    if (hair === "long") P(o.head, "path", { d: "M-32 -4 Q-38 -44 0 -42 Q38 -44 32 -4 L34 30 L24 30 L24 -18 Q0 -30 -24 -18 L-24 30 L-34 30 z", fill: col, stroke: col, "stroke-width": 4 });
    if (hair === "bun") { P(o.head, "path", { d: "M-30 -8 Q-34 -40 0 -40 Q34 -40 30 -8 Q20 -26 0 -26 Q-20 -26 -30 -8 z", fill: col, stroke: col, "stroke-width": 4 }); P(o.head, "circle", { cx: 0, cy: -46, r: 11, fill: col, stroke: col }); }
    if (hair === "curly") { for (let k = -2; k <= 2; k++) P(o.head, "circle", { cx: k * 13, cy: -32 + Math.abs(k) * 6, r: 11, fill: col, stroke: col, "stroke-width": 3 }); }
    if (acc === "beard") P(o.head, "path", { d: "M-24 8 Q0 50 24 8 Q12 22 0 22 Q-12 22 -24 8 z", fill: col, stroke: col, "stroke-width": 4 });
    if (acc === "bow") { P(o.head, "path", { d: "M14 -38 l16 -10 v20 z M14 -38 l-14 -10 v20 z", fill: "var(--accent)", stroke: col, "stroke-width": 3 }); }
    if (acc === "crown") P(o.head, "path", { d: "M-24 -36 l-4 -26 l16 12 l12 -20 l12 20 l16 -12 l-4 26 z", fill: "#fbbf24", stroke: col, "stroke-width": 5 });
    if (acc === "headband") P(o.head, "path", { d: "M-32 -16 Q0 -30 32 -16", stroke: "var(--accent)", "stroke-width": 9 });
    if (acc === "helmet") P(o.head, "path", { d: "M-36 -6 A36 36 0 0 1 36 -6 Z", fill: "#fbbf24", stroke: col, "stroke-width": 6 });
    if (acc === "mask") P(o.face, "path", { d: "M-24 2 h48 v14 q-24 12 -48 0 z", fill: "#e2e8f0", stroke: col, "stroke-width": 3 });
    if (acc === "backpack") o.pack = sv("rect", { x: -8, y: -4, width: 20, height: 46, rx: 8, fill: "var(--accent2)", stroke: col, "stroke-width": 5 }, body);
    o.think = sv("text", { "text-anchor": "middle", "font-size": 54, "font-weight": 800, fill: "var(--accent)", "font-family": "var(--font-head)", opacity: 0 }, root);
    o.think.textContent = "?";
    addMarks(o, root);
    o.fingers = sv("path", st({ "stroke-width": 4 }), body);
    o.armF = sv("path", st(), body);
    return o;
  }

  function idlePose(t, seed) {
    const b = Math.sin(t * 2.2 + seed);
    return { lean: 1.2 * b, tilt: 0, hdx: 0, hdy: 0, shr: 0, lift: 0, rot: 0, sit: 0,
      sA: [-8 + b, 7 - b], fA: [-2 + b, 16 - b], hA: [3, -3], kA: [4, 4], ik: [null, null], fingers: 0, emo: "neutral", open: 0, think: 0 };
  }
  const blend = (P0, k, v, w) => { P0[k] = lerp(P0[k], v, w); };
  const blendArm = (P0, i, s, f, w) => { P0.sA[i] = lerp(P0.sA[i], s, w); P0.fA[i] = lerp(P0.fA[i], f, w); };

  /* ---------- the scene ---------- */
  X.stickState = X.stickState || {};
  X.stick = function (sceneEl, sc, tl, D) {
    const S = sc.stick;
    const f = D.format, asp = f.aspect;
    const alone = !(sc.elements && sc.elements.length);                         // no overlay element shares the frame: the drawing may use all of it
    // vertical: a closer shot of the middle of the set (where people stand) so the figures are big on a phone; the floor ends above the caption box
    const vb = asp === "9:16" ? { x: 120, y: 30, w: 760, h: 570 } : { x: 0, y: 0, w: 1000, h: 600 };
    const rc = asp === "9:16" ? { l: 0, t: 600, w: 1080, h: 810 }
      : asp === "1:1" ? { l: 140, t: 520, w: 800, h: 480 }
      : alone ? { l: 160, t: 80, w: 1600, h: 770 } : { l: 40, t: 150, w: 1100, h: 660 };      // wide: the right panel belongs to the overlay elements when there are some
    const stage = document.createElement("div");
    stage.className = "stk-stage";
    Object.assign(stage.style, { left: rc.l + "px", top: rc.t + "px", width: rc.w + "px", height: rc.h + "px" });
    const sx = Math.min(rc.w / vb.w, rc.h / vb.h), ox = (rc.w - vb.w * sx) / 2 - vb.x * sx, oy = (rc.h - vb.h * sx) / 2 - vb.y * sx;
    const svg = sv("svg", { viewBox: `${vb.x} ${vb.y} ${vb.w} ${vb.h}`, width: rc.w, height: rc.h, class: "stk-svg" });
    stage.appendChild(svg);
    const ov = document.createElement("div");
    ov.className = "stk-ov";
    stage.appendChild(ov);
    sceneEl.insertBefore(stage, sceneEl.firstChild);
    const world = sv("g", {}, svg);
    const setC = S.set || {};
    const tod = setC.time || "day", wea = setC.weather || "none";
    if (tod !== "day") {                                                         // evening, dawn and night recolour the whole scene (a night scene turns the ink light)
      const pal = { dawn: "#fde6c9", evening: "#fcd9b0", night: "#101a33" }[tod];
      sceneEl.style.background = pal;
      if (tod === "night") { sceneEl.style.setProperty("--ink", "#f1f5f9"); sceneEl.style.setProperty("--card", "#26344d"); }
    }
    const paint = setC.art && S.propArt && S.propArt["scene:" + setC.art];
    if (paint) {                                                                // a painted place (cartoon style): full-bleed behind the whole frame, its ground low like the floor
      sceneEl.style.backgroundImage = "url(\"data:image/svg+xml;charset=utf-8," + encodeURIComponent(paint) + "\")";
      sceneEl.style.backgroundSize = "cover";
      sceneEl.style.backgroundPosition = "center 70%";
    } else sv("path", { d: "M-200 " + FLOOR + " H1200", stroke: "var(--ink)", "stroke-width": 5, "stroke-linecap": "round", opacity: 0.55, fill: "none" }, world);

    /* weather: drawn on top of the world, a pure function of time */
    const fxg = sv("g", {}, svg);
    const fxEls = [];
    if (wea === "rain" || wea === "snow") {
      for (let i = 0; i < (wea === "rain" ? 60 : 44); i++) fxEls.push(wea === "rain" ? sv("line", { stroke: "#7dd3fc", "stroke-width": 3, opacity: 0.75, "stroke-linecap": "round" }, fxg) : sv("circle", { r: 3 + (i % 3), fill: "#e2e8f0", opacity: 0.92 }, fxg));
    }
    if (tod === "night") for (let i = 0; i < 26; i++) fxEls.push(sv("circle", { cx: (i * 137) % 1000, cy: 20 + ((i * 71) % 260), r: 2.2, fill: "#f8fafc", opacity: 0.8 }, fxg));
    const drawFx = (t) => {
      let k = 0;
      if (wea === "rain") for (let i = 0; i < 60; i++, k++) { const x = ((i * 83.7) % 1100) - 40, y = ((i * 57 + t * 620 * (0.7 + (i % 5) * 0.1)) % 700) - 60; const e = fxEls[k]; e.setAttribute("x1", R(x)); e.setAttribute("y1", R(y)); e.setAttribute("x2", R(x - 12)); e.setAttribute("y2", R(y + 34)); }
      else if (wea === "snow") for (let i = 0; i < 44; i++, k++) { const x = ((i * 97) % 1000) + 18 * Math.sin(t * 1.3 + i), y = ((i * 41 + t * 70 * (0.6 + (i % 4) * 0.2)) % 640) - 20; const e = fxEls[k]; e.setAttribute("cx", R(x)); e.setAttribute("cy", R(y)); }
      if (tod === "night") for (let i = 0; i < 26; i++, k++) fxEls[k].setAttribute("opacity", (0.45 + 0.4 * Math.sin(t * 2 + i * 1.7)).toFixed(2));
    };

    /* props */
    const names = [];
    const setProps = (S.set && S.set.props) || [];
    const add = (n) => { if (n && !names.includes(n) && !["viewer", "camera"].includes(n) && !S.cast.some((c) => c.id === n)) names.push(n); };
    setProps.forEach(add);
    S.actions.forEach((a) => { add(a.target); add(a.prop); });
    if (S.camera && S.camera.focus) add(S.camera.focus);
    const spots = {};
    let free = 0;
    names.forEach((n) => {
      if (SPOT[n]) spots[n] = SPOT[n].slice();
      else { spots[n] = [160 + (free++ % 6) * 130, 496]; }
    });
    const persist = X.stickState;
    persist.props = persist.props || {};
    const spriteOf = {};
    names.forEach((n) => {
      const g = propSprite(n, S.propArt);
      world.appendChild(g);
      spriteOf[n] = g;
      if (persist.props[n]) spots[n] = persist.props[n].slice();
    });
    const board = names.includes("board") || names.includes("sign") ? (names.includes("board") ? "board" : "sign") : null;
    const boardText = board ? sv("text", { "text-anchor": "middle", "font-size": 30, "font-weight": 700, fill: "var(--ink)", "font-family": "var(--font-body)" }, world) : null;

    /* characters */
    const cast = S.cast || [];
    const appears = new Set(S.actions.map((a) => a.who));
    if (cast.length) appears.add(cast[0].id);
    const chars = [];
    cast.forEach((c, i) => {
      if (!appears.has(c.id) && !(persist[c.id])) return;
      buildActor.noPeople = !S.cast.some((x) => !x.kind || x.kind === "person" || x.kind === "toon");
    chars.push(buildChar(c, i, S.propArt));
    });
    chars.forEach((ch) => world.appendChild(ch.root));
    const slots = chars.length === 1 ? [500] : chars.length === 2 ? [330, 670] : chars.length === 3 ? [230, 500, 770] : chars.map((_, k) => 110 + (780 * k) / (chars.length - 1));
    /* the plan of each character: moves, facings, sits, carries, emotions */
    chars.forEach((ch) => { ch.xfer = []; ch.markList = []; });
    chars.forEach((ch, ci) => {                                     // starting positions first (characters refer to each other)
      const prev = persist[ch.id];
      const first = S.actions.filter((a) => a.who === ch.id).sort((a, b) => a.start - b.start)[0];
      ch.x0 = prev ? prev.x : slots[ci];
      if (first && first.do === "walk_in") {
        const dest = first.to != null ? first.to * 1000 : slots[ci];
        // the video's very first frame already shows the figure (thumbnails, first impression): it only walks the last bit
        ch.x0 = S.t0 < 0.05 && first.start < 0.8 ? clamp(dest + (first.from === "right" ? 170 : -170), 40, 960) : (first.from === "right" ? 1130 : -130);
      }
    });
    const ctxs = {};
    chars.forEach((ch, ci) => {
      const prev = persist[ch.id];
      const acts = S.actions.filter((a) => a.who === ch.id).sort((a, b) => a.start - b.start);
      let x = ch.x0;
      let face = prev ? prev.face : (slots[ci] > 500 ? -1 : 1);
      ch.moves = []; ch.faces = [{ t: -1, dir: face, prev: face }]; ch.sits = []; ch.emos = []; ch.carry = []; ch.acts = acts; ch.markList = ch.markList || []; ch.xfer = ch.xfer || [];
      let sit = prev ? prev.sit : 0;
      ch.sit0 = sit;
      let carrying = prev ? prev.carrying : null;
      ch.carrying0 = carrying;
      if (carrying) ch.carry.push({ t: -9, prop: carrying, hold: true });
      const step = (a) => {
        const dur = Math.max(0.2, a.end - a.start);
        const faceTo = (tx) => { const d = tx >= x ? 1 : -1; if (d !== face) { ch.faces.push({ t: a.start, dir: d, prev: face }); face = d; } };
        const move = (x1, t0, t1) => { ch.moves.push({ t0, t1, x0: x, x1 }); x = x1; };
        switch (a.do) {
          case "walk_in": { const x1 = a.to != null ? a.to * 1000 : slots[ci]; faceTo(x1); move(x1, a.start, a.end); break; }
          case "walk_out": { const x1 = a.to_side === "left" ? -140 : 1140; faceTo(x1); move(x1, a.start, a.end); break; }
          case "run": case "walk_to": case "chase": case "follow": case "sneak": case "fly": { const x1 = a.to != null ? a.to * 1000 : x + (face > 0 ? 160 : -160); faceTo(x1); move(clamp(x1, 40, 960), a.start, a.end); break; }
          case "turn": { const d = a.side === "left" ? -1 : 1; if (d !== face) { ch.faces.push({ t: a.start, dir: d, prev: face }); face = d; } break; }
          case "point": case "look_at": case "push": case "pull": { const tx = a.target === "viewer" || a.target === "camera" ? x + 100 * face : (spots[a.target] ? spots[a.target][0] : (chars.find((c) => c.id === a.target) ? 0 : x + 100 * face)); if (a.target !== "viewer" && a.target !== "camera") faceTo(chars.find((c) => c.id === a.target) ? chars.find((c) => c.id === a.target).x0 : tx); break; }
          case "high_five": case "handshake": { const o = chars.find((c) => c.id === a.target); const tx = o ? ctxs[o.id].x : x + 200; faceTo(tx); const fc = face; if (Math.abs(tx - x) > 150) move(clamp(tx - fc * 140, 40, 960), a.start, a.start + dur * 0.45); break; }
          case "sit": ch.sits.push({ t0: a.start, t1: a.end, v0: sit, v1: 1 }); sit = 1; break;
          case "stand": ch.sits.push({ t0: a.start, t1: a.end, v0: sit, v1: 0 }); sit = 0; break;
          case "carry": ch.carry.push({ t: a.start + dur * 0.5, prop: a.prop, hold: true }); carrying = a.prop; break;
          case "drop": if (carrying) { ch.carry.push({ t: a.start + dur * 0.45, prop: carrying, hold: false, x: x + face * 50 }); persist.props[carrying] = [x + face * 50, REST_Y[carrying] || 500]; carrying = null; } break;
          case "react": ch.emos.push({ t0: a.start, t1: a.end + 0.9, e: a.emotion || "happy" }); break;
          case "hug": { const o = chars.find((c) => c.id === a.target); const tx = o ? ctxs[o.id].x : x + 200; faceTo(tx); const fc = face; if (Math.abs(tx - x) > 90) move(clamp(tx - fc * 78, 40, 960), a.start, a.start + dur * 0.4); break; }
          case "lift": { if (carrying !== a.prop) { ch.carry.push({ t: a.start + dur * 0.5, prop: a.prop, hold: true }); carrying = a.prop; } break; }
          case "give": {
            const o = chars.find((c) => c.id === a.target); const tx = o ? ctxs[o.id].x : x + 200; faceTo(tx); const fc = face; if (Math.abs(tx - x) > 150) move(clamp(tx - fc * 140, 40, 960), a.start, a.start + dur * 0.45);
            const tm = a.start + dur * 0.55;
            if (carrying !== a.prop) ch.carry.push({ t: a.start + dur * 0.1, prop: a.prop, hold: true });
            ch.carry.push({ t: tm, prop: a.prop, hold: false, give: a.target });
            if (o) o.xfer.push({ t: tm + 0.001, prop: a.prop, hold: true });
            carrying = null; break;
          }
          case "throw": {
            const o = chars.find((c) => c.id === a.target); const tx = o ? ctxs[o.id].x : (spots[a.target] ? spots[a.target][0] : x + face * 260); faceTo(tx);
            const tm = a.start + dur * 0.55;
            if (carrying !== a.prop) ch.carry.push({ t: a.start + dur * 0.1, prop: a.prop, hold: true });
            ch.carry.push({ t: tm, prop: a.prop, hold: false, fly: { x: tx, t0: tm, t1: tm + 0.6 } });
            persist.props[a.prop] = [tx, REST_Y[a.prop] || 500]; carrying = null; break;
          }
          case "hide": { const g = spots[a.target]; if (g) { const hx = g[0] - face * 60; faceTo(g[0]); move(hx, a.start, a.start + dur * 0.5); } break; }
          case "appear": if (ch.appearT === undefined) ch.appearT = a.start; break;
          case "mark": ch.markList.push({ t0: a.start, t1: a.end + 0.3, mark: a.mark || "exclaim" }); break;
        }
      };
      ctxs[ch.id] = { acts, step, get x() { return x; }, get face() { return face; }, get sit() { return sit; }, get carrying() { return carrying; } };
    });
    const queue = [];
    chars.forEach((ch) => ctxs[ch.id].acts.forEach((a) => queue.push({ id: ch.id, a })));
    queue.sort((p, q) => p.a.start - q.a.start);                    // the stable sort keeps one character's own order for equal times
    queue.forEach(({ id, a }) => ctxs[id].step(a));
    chars.forEach((ch) => { const c = ctxs[ch.id]; persist[ch.id] = { x: c.x, face: c.face, sit: c.sit, carrying: c.carrying }; });
    const sgn = (v) => (v >= 0 ? 1 : -1);
    chars.forEach((ch) => {
      ch.xAt = (t) => {
        let x = ch.x0;
        for (const m of ch.moves) {
          if (t < m.t0) break;
          if (t >= m.t1) { x = m.x1; continue; }
          const u = (t - m.t0) / (m.t1 - m.t0);
          return lerp(m.x0, m.x1, 0.25 * sstep(0, 1, u) + 0.75 * u);
        }
        return x;
      };
      ch.faceAt = (t) => {
        let cur = ch.faces[0].dir;
        for (const e of ch.faces) {
          if (e.t > t) break;
          cur = e.t < 0 ? e.dir : lerp(e.prev, e.dir, sstep(0, 0.28, t - e.t));
        }
        return cur;
      };
      ch.sitAt = (t) => { let v = ch.sit0; for (const s of ch.sits) { if (t < s.t0) break; v = t >= s.t1 ? s.v1 : lerp(s.v0, s.v1, sstep(s.t0, s.t1, t)); } return v; };
      ch.emoAt = (t) => { let e = "neutral"; for (const m of ch.emos) if (t >= m.t0 && t <= m.t1) e = m.e; return e; };
      ch.carryAll = [...ch.carry, ...(ch.xfer || [])].sort((a, b) => a.t - b.t);
      ch.carryAt = (t) => { let c = ch.carrying0 ? { prop: ch.carrying0, t: -9, hold: true } : null; for (const e of ch.carryAll) { if (t < e.t) break; c = e.hold ? e : null; } return c; };
    });

    /* speech bubbles / signs (HTML, so every script wraps and sizes itself) */
    const bubbles = [];
    S.actions.forEach((a) => {
      if (a.do !== "say" && a.do !== "hold_sign") return;
      const d = document.createElement("div");
      d.className = "stk-bub " + (a.do === "hold_sign" ? "sign" : "say");
      d.textContent = a.bubble || "";
      d.style.opacity = 0;
      d.style.fontSize = Math.round(40 * sx) + "px";
      ov.appendChild(d);
      bubbles.push({ a, d, ch: chars.find((c) => c.id === a.who), shown: 0 });
    });

    /* camera */
    const shotZ = { wide: 1.0, medium: 1.12, close: 1.4 }[(S.camera && S.camera.shot) || "medium"] || 1.1;
    const move = (S.camera && S.camera.move) || "none";
    const t0 = S.t0 != null ? S.t0 : sc.start, t1 = S.t1 != null ? S.t1 : sc.end, span = Math.max(0.1, t1 - t0);   // the whole scene's span: its pages film the same shot
    const focusAt = (t) => {
      const a = S.actions.find((q) => q.start <= t && t <= q.end && (q.do === "say" || q.do === "explain" || q.do === "point")) || null;
      const ch = (a && chars.find((c) => c.id === a.who)) || chars[0];
      return ch ? ch.xAt(t) : 500;
    };
    const focusPt = (t) => { const f = S.camera && S.camera.focus; if (!f) return null; if (spots[f]) return spots[f].slice(); const c = chars.find((q) => q.id === f); return c ? [c.xAt(t), 330] : null; };
    const camAt = (t) => {
      const u = clamp((t - t0) / span, 0, 1);
      let z = shotZ, cx = 500;
      if (move === "push_in") z *= 1 + 0.16 * u;
      else if (move === "pull_out") z *= 1.16 - 0.16 * u;
      else if (move === "zoom_to") z *= 1 + 0.55 * sstep(0, 0.85, u);
      else if (move === "pan_left") cx = 500 + 70 * (1 - 2 * u);
      else if (move === "pan_right") cx = 500 - 70 * (1 - 2 * u);
      if (z > 1.02 && (move === "follow" || shotZ > 1.3 || chars.length === 1)) cx = lerp(cx, focusAt(t), move === "follow" ? 1 : 0.55);
      if (move === "follow" && z < 1.1) z = 1.15;
      let fcy = null;
      if (move === "zoom_to") { const fp = focusPt(t); if (fp) { const k = sstep(0, 0.85, u); cx = lerp(cx, fp[0], k); fcy = lerp(300, fp[1], k); } }
      cx = clamp(cx, 500 / z, 1000 - 500 / z);
      const cy = fcy !== null ? clamp(fcy, 300 / z, 600 - 300 / z) : (z > 1.02 ? clamp(FLOOR - 200, 300 / z, 600 - 300 / z) : 300);
      const shake = move === "shake" ? 5 * Math.sin(t * 61) * (1 - u) : 0;
      return { z, cx: cx + shake, cy: cy + (move === "shake" ? 4 * Math.sin(t * 47) * (1 - u) : 0) };
    };
    const toPx = (cam, wx, wy) => [ox + ((wx - cam.cx) * cam.z + 500) * sx, oy + ((wy - cam.cy) * cam.z + 300) * sx];

    /* drawing one frame */
    function poseOf(ch, t) {
      const K = ch.k || 1.3;
      const seed = ch.idx * 1.7;
      const p = idlePose(t, seed);
      p.lean += ch.stoop || 0;
      const x = ch.xAt(t);
      const v = (ch.xAt(t + 0.06) - ch.xAt(t - 0.06)) / 0.12;
      const ww = clamp(Math.abs(v) / 45, 0, 1);
      if (ww > 0.02) {
        const amp = 1 + clamp((Math.abs(v) - 130) / 220, 0, 1) * 0.9;            // a run: wider strides, higher knees, leaning into it
        const ph = (2 * Math.PI * x) / (120 * (1 + (amp - 1) * 0.5));
        const sA = Math.sin(ph), cA = Math.sin(ph + Math.PI);
        p.hA = [lerp(p.hA[0], 30 * amp * cA, ww), lerp(p.hA[1], 30 * amp * sA, ww)];
        p.kA = [lerp(p.kA[0], 6 + 36 * amp * Math.max(0, Math.cos(ph + Math.PI)), ww), lerp(p.kA[1], 6 + 36 * amp * Math.max(0, Math.cos(ph)), ww)];
        blendArm(p, 0, 26 * amp * sA - 4, 26 * amp * sA + 14 + 30 * (amp - 1), ww);
        blendArm(p, 1, -26 * amp * sA + 6, -26 * amp * sA + 28 + 30 * (amp - 1), ww);
        p.lean += (3 + 9 * (amp - 1)) * ww;
      }
      const sit = ch.sitAt(t);
      if (sit > 0.01) { p.hA = [lerp(p.hA[0], 88, sit), lerp(p.hA[1], 88, sit)]; p.kA = [lerp(p.kA[0], 88, sit), lerp(p.kA[1], 88, sit)]; blendArm(p, 1, 28, 70, sit * 0.7); blendArm(p, 0, 22, 65, sit * 0.7); }
      p.sit = sit;
      const car = ch.carryAt(t);
      if (car) { const w = sstep(car.t - 0.1, car.t + 0.25, t); blendArm(p, 0, 52, 96, w); blendArm(p, 1, 56, 100, w); }
      const e0 = ch.emoAt(t);
      p.emo = e0;
      const a = ch.acts.find((q) => t >= q.start && t <= q.end);
      const dirNow = sgn(ch.faceAt(t));
      let sp = p.sit;
      if (a) {
        const dur = Math.max(0.2, a.end - a.start), u = (t - a.start) / dur, e = Math.min(0.3, dur * 0.35);
        const w = sstep(0, e, t - a.start) * sstep(0, e, a.end - t);
        const T = t - a.start;
        const tgt = (nm) => {
          if (nm === "viewer" || nm === "camera") return [x + dirNow * 320, 230];
          if (spots[nm]) return [spots[nm][0], spots[nm][1]];
          const o = chars.find((c) => c.id === nm);
          if (o) return [o.xAt(t), 330];
          return [x + dirNow * 200, 300];
        };
        const loc = (wx, wy) => [((wx - x) * dirNow) / K, FLOOR + (wy - FLOOR) / K];
        const hipY = () => { const ft = (i) => TH * Math.cos(p.hA[i] * RAD) + SH * Math.cos((p.hA[i] - p.kA[i]) * RAD); return FLOOR - Math.max(ft(0), ft(1)) - p.lift; };
        const shoulder = () => [Math.sin(p.lean * RAD) * TORSO * 0.92, hipY() - Math.cos(p.lean * RAD) * TORSO * 0.92];
        const setIK = (arm, wx, wy, ww2) => { const sh = shoulder(); const l = loc(wx, wy); const r = ik2(sh[0], sh[1], l[0], l[1]); p.ik[arm] = { s: r[0], f: r[1], w: ww2 }; };
        switch (a.do) {
          case "wave": blendArm(p, 1, 150, 160 + 28 * Math.sin(T * 11), w); p.tilt = 6 * w; break;
          case "nod": p.hdy += w * Math.sin(u * Math.PI * 4) * 7; break;
          case "shake_head": p.hdx += w * Math.sin(u * Math.PI * 6) * 7; break;
          case "shrug": blendArm(p, 0, -52, 30, w); blendArm(p, 1, 52, 120, w); p.shr = 9 * w; p.tilt = 8 * w; break;
          case "think": { const tp = [x + dirNow * 8, hipY() - TORSO - NECK + 2]; setIK(1, tp[0] + dirNow * 6, tp[1], w); p.tilt = 9 * w; p.think = w; break; }
          case "explain": blendArm(p, 1, 58 + 26 * Math.sin(T * 3.2), 118 + 20 * Math.sin(T * 3.2), w); blendArm(p, 0, -30 + 20 * Math.sin(T * 3.2 + 1.3), 40 + 14 * Math.sin(T * 3.2 + 1.3), w); break;
          case "count": blendArm(p, 1, 105, 168, w); p.fingers = (a.count || 1) * (w > 0.5 ? 1 : 0); break;
          case "point": { const g = tgt(a.target); setIK(1, g[0], g[1], w); blendArm(p, 0, -10, 6, w); p.lean += 4 * w; break; }
          case "look_at": { const g = tgt(a.target); p.tilt = clamp((g[1] - 250) / 20, -10, 10) * -w; p.hdx += w * 4; break; }
          case "push": blendArm(p, 0, 84, 90, w); blendArm(p, 1, 84, 90, w); p.lean += 12 * w; break;
          case "pull": blendArm(p, 0, 70, 90, w); blendArm(p, 1, 70, 90, w); p.lean -= 10 * w; break;
          case "carry": { const g = tgt(a.prop); const k = 1 - sstep(0.15, 0.55, u); setIK(1, g[0], g[1] - 6, w * k); setIK(0, g[0], g[1] - 6, w * k); p.lean += 6 * w * k; break; }
          case "drop": p.kA = [p.kA[0] + 30 * w * Math.sin(u * Math.PI), p.kA[1] + 30 * w * Math.sin(u * Math.PI)]; p.hA = [p.hA[0] + 15 * w, p.hA[1] + 15 * w]; p.lean += 14 * w; break;
          case "jump": { const j = Math.sin(clamp(u, 0, 1) * Math.PI); p.lift = 80 * j; blendArm(p, 0, 140 * j, 150 * j, 1); blendArm(p, 1, 140 * j, 150 * j, 1); p.hA = [40 * j, 40 * j]; p.kA = [70 * j + 4, 70 * j + 4]; break; }
          case "fall": { const r = u < 0.35 ? sstep(0, 0.35, u) : 1 - sstep(0.7, 1, u); p.rot = 86 * r; blendArm(p, 0, 120 * r, 140 * r, 1); blendArm(p, 1, 130 * r, 150 * r, 1); break; }
          case "celebrate": blendArm(p, 0, 158 + 8 * Math.sin(T * 9), 170, w); blendArm(p, 1, 158 - 8 * Math.sin(T * 9), 170, w); p.lift = 16 * Math.abs(Math.sin(T * 7)) * w; p.emo = "happy"; break;
          case "facepalm": { setIK(1, x + dirNow * 4, hipY() - TORSO - NECK - HR - 2, w); p.lean += 9 * w; p.tilt = 10 * w; p.emo = "sad"; break; }
          case "write_board": { const g = tgt(a.target || board || "board"); setIK(1, g[0] - 60 + 120 * ((Math.sin(T * 3) + 1) / 2), g[1] - 30 + 18 * Math.sin(T * 8), w); break; }
          case "hold_sign": { const hx = x; setIK(1, hx + dirNow * 26, hipY() - TORSO - NECK - 2 * HR - 30, w); setIK(0, hx - dirNow * 26, hipY() - TORSO - NECK - 2 * HR - 30, w); break; }
          case "say": blendArm(p, 1, 40 + 22 * Math.sin(T * 4), 85 + 16 * Math.sin(T * 4), w * 0.8); break;
          case "high_five": case "handshake": { const oc = chars.find((c) => c.id === a.target); const ox2 = oc ? oc.xAt(t) : x + dirNow * 120; const mid = (x + ox2) / 2; const k = sstep(0.4, 0.65, u) * (1 - sstep(0.85, 1, u)); setIK(1, a.do === "high_five" ? mid : mid, a.do === "high_five" ? 250 : 350, k); break; }
          case "clap": blendArm(p, 1, 62 + 16 * Math.sin(T * 17), 98, w); blendArm(p, 0, 62 - 16 * Math.sin(T * 17), 98, w); p.emo = "happy"; p.lift = 5 * Math.abs(Math.sin(T * 8.5)) * w; break;
          case "bow": { const bk = Math.sin(clamp(u, 0, 1) * Math.PI); p.lean += 52 * bk; p.hdy += 6 * bk; blendArm(p, 0, 14, 24, bk); blendArm(p, 1, 18, 30, bk); break; }
          case "laugh": p.emo = "happy"; p.lean -= 9 * w; p.hdy += 3 * Math.sin(T * 26) * w; p.shr = 4 * Math.abs(Math.sin(T * 13)) * w; blendArm(p, 1, 38, 112, w * 0.65); blendArm(p, 0, 30, 100, w * 0.4); break;
          case "cry": { p.emo = "sad"; const hy = hipY() - TORSO - NECK - HR; setIK(1, x + dirNow * 8, hy, w); setIK(0, x - dirNow * 6, hy + 6, w); p.lean += 12 * w; p.hdy += 2 * Math.sin(T * 20) * w; p.shr = 3 * Math.abs(Math.sin(T * 10)) * w; break; }
          case "yawn": p.emo = "surprised"; p.lean -= 9 * w; blendArm(p, 0, 150, 172, w); blendArm(p, 1, 146, 170, w); break;
          case "dance": { const b = Math.sin(T * 7); p.lift = 15 * Math.abs(b) * w; p.tilt = 9 * b * w; p.emo = "happy"; blendArm(p, 0, 132 + 32 * b, 160, w); blendArm(p, 1, 132 - 32 * b, 160, w); p.kA = [p.kA[0] + 22 * Math.abs(b) * w, p.kA[1] + 22 * (1 - Math.abs(b)) * w]; break; }
          case "phone": { const hy = hipY() - TORSO - NECK - HR + 4; setIK(1, x + dirNow * 14, hy, w); p.tilt = 8 * w; blendArm(p, 0, 8, 20, w * 0.5); break; }
          case "type": blendArm(p, 0, 48, 72 + 8 * Math.sin(T * 18), w); blendArm(p, 1, 50, 74 - 8 * Math.sin(T * 18), w); p.lean += 8 * w; break;
          case "eat": { const hy = hipY() - TORSO - NECK - HR + 12; setIK(1, x + dirNow * 20, hy, w * (0.45 + 0.55 * Math.sin(T * 6) ** 2)); p.hdy += 2 * Math.sin(T * 12) * w; break; }
          case "lift": { p.lean += 22 * w; blendArm(p, 0, 36, 58, w); blendArm(p, 1, 40, 62, w); p.kA = [p.kA[0] + 24 * w, p.kA[1] + 24 * w]; p.hA = [p.hA[0] + 12 * w, p.hA[1] + 12 * w]; p.emo = "angry"; p.hdx += 1.6 * Math.sin(T * 30) * w; break; }
          case "throw": { const sw = sstep(0.35, 0.58, u); blendArm(p, 1, lerp(-70, 150, sw), lerp(-50, 160, sw), w); blendArm(p, 0, 20, 80, w * 0.5); p.lean += (sw < 1 ? -10 + 24 * sw : 6) * w; break; }
          case "give": { const k = sstep(0.3, 0.55, u) * (1 - sstep(0.8, 1, u)); blendArm(p, 1, 74, 70, k); blendArm(p, 0, 70, 66, k); break; }
          case "chase": p.lean += 7 * w; p.emo = "angry"; break;
          case "sneak": p.kA = [p.kA[0] + 42 * w, p.kA[1] + 42 * w]; p.hA = [p.hA[0] + 22 * w, p.hA[1] + 22 * w]; p.lean += 18 * w; p.hdy += 4 * w; blendArm(p, 0, -12, 20, w * 0.7); break;
          case "hide": p.kA = [p.kA[0] + 62 * w, p.kA[1] + 62 * w]; p.hA = [p.hA[0] + 36 * w, p.hA[1] + 36 * w]; p.lean += 20 * w; p.emo = "scared"; blendArm(p, 1, 80, 150, w); break;
          case "peek": { const hy = hipY() - TORSO - NECK - HR; p.lean += 16 * w; p.tilt = 10 * w; setIK(1, x + dirNow * 22, hy - 4, w); break; }
          case "hug": { const k = sstep(0.3, 0.55, u) * (1 - sstep(0.85, 1, u)); blendArm(p, 0, 76, 26, k); blendArm(p, 1, 82, 30, k); p.lean += 10 * k; p.emo = "happy"; break; }
          case "argue": p.emo = "angry"; p.lean += 6 * w; blendArm(p, 1, 150 + 6 * Math.sin(T * 22), 164, w); p.hdx += w * Math.sin(T * 24) * 2.2; blendArm(p, 0, 24, 100, w * 0.6); break;
          case "wave_both": blendArm(p, 0, 150 + 24 * Math.sin(T * 10), 172, w); blendArm(p, 1, 150 - 24 * Math.sin(T * 10), 172, w); p.emo = "happy"; break;
          case "react": {
            const em = a.emotion || "happy";
            p.emo = em;
            if (em === "surprised") { p.lean -= 10 * w; blendArm(p, 0, 62, 100, w); blendArm(p, 1, 70, 110, w); p.lift = 10 * Math.sin(Math.min(1, u * 3) * Math.PI); }
            else if (em === "happy") { p.lift = 12 * Math.abs(Math.sin(T * 8)) * w; blendArm(p, 1, 110, 150, w * 0.6); }
            else if (em === "sad") { p.lean += 16 * w; p.hdy += 7 * w; p.tilt = 12 * w; }
            else if (em === "angry") { blendArm(p, 0, 30, 150, w); blendArm(p, 1, 30, 150, w); p.hdx += w * Math.sin(T * 28) * 2.5; }
            else if (em === "confused") { p.tilt = 14 * w; blendArm(p, 1, 40, 130, w); }
            else if (em === "scared") { p.kA = [p.kA[0] + 28 * w, p.kA[1] + 28 * w]; p.hA = [p.hA[0] + 16 * w, p.hA[1] + 16 * w]; p.lean -= 10 * w; blendArm(p, 0, 90, 150, w); blendArm(p, 1, 96, 150, w); }
            break;
          }
        }
        ch.ba = a; ch.bw = w;
      } else { ch.ba = null; ch.bw = 0; }
      return p;
    }

    function drawActor(ch, t, speakerId, env) {
      if (ch.mouths) {                                                            // the nine mouth shapes, chosen by the loudness of the voice (any language)
        const e = ch.id === speakerId ? (env || 0) : 0;
        const k = e < 0.12 ? "X" : e < 0.28 ? "B" : e < 0.48 ? "C" : Math.floor(t * 9) % 2 ? "D" : "E";
        for (const m in ch.mouths) ch.mouths[m].style.opacity = m === k || (!ch.mouths[k] && m === "X") ? 1 : 0;
      }
      const x = ch.xAt(t);
      const f = ch.faceAt(t);
      const v = (ch.xAt(t + 0.06) - ch.xAt(t - 0.06)) / 0.12;
      const ww = clamp(Math.abs(v) / 45, 0, 1);
      let lift = ww * 12 * Math.abs(Math.sin((x / 26) * Math.PI)), rot = 0, sc = 1, op = 1;
      const a = ch.acts.find((q) => t >= q.start && t <= q.end);
      if (a) {
        const dur = Math.max(0.2, a.end - a.start), u = clamp((t - a.start) / dur, 0, 1), T = t - a.start;
        switch (a.do) {
          case "bounce": lift += 70 * Math.abs(Math.sin(u * Math.PI * 3)); break;
          case "jump": lift += 100 * Math.sin(u * Math.PI); break;
          case "spin": rot = 360 * sstep(0, 1, u); break;
          case "grow": sc = 1 + 0.7 * Math.sin(u * Math.PI * 0.9); break;
          case "shake_head": case "argue": rot = 10 * Math.sin(T * 30) * (1 - u * 0.3); break;
          case "fall": rot = 88 * sstep(0, 0.35, u); break;
          case "react": case "celebrate": case "laugh": case "dance": case "clap": lift += 36 * Math.abs(Math.sin(T * 8)); break;
          case "say": case "explain": lift += 8 * Math.abs(Math.sin(T * 6)); break;
          case "fly": lift += 120 * Math.sin(u * Math.PI); break;
          case "wave": case "wave_both": rot = 12 * Math.sin(T * 10); break;
          case "think": case "nod": case "bow": rot = 8 * Math.sin(T * 6); break;
        }
      }
      if (ch.appearT !== undefined) { const k = clamp((t - ch.appearT) / 0.45, 0, 1); op = t < ch.appearT ? 0 : 1; if (k < 1 && t >= ch.appearT) sc *= 1.15 * Math.sin(k * Math.PI * 0.5); }
      const idle = 1 + 0.02 * Math.sin(t * 3 + ch.idx);
      ch.root.setAttribute("transform", `translate(${R(x)} ${R(FLOOR - lift)})`);
      ch.inner.setAttribute("transform", `rotate(${rot.toFixed(1)} 0 ${(-ch.size / 2).toFixed(0)}) scale(${((f >= 0 ? 1 : -1) * sc * idle).toFixed(3)} ${(sc * idle).toFixed(3)})`);
      ch.root.setAttribute("opacity", op);
      ch.headW = [x, FLOOR - lift - ch.size * sc - 12];
      ch.hand = [x + 30 * (f >= 0 ? 1 : -1), FLOOR - lift - ch.size * 0.4];
      showMark(ch, t, 0, -ch.size * sc - 44, 1, 1);
    }

    function drawChar(ch, t, speakerId, env) {
      if (ch.actor) return drawActor(ch, t, speakerId, env);
      const K = ch.k || 1.3;
      const p = poseOf(ch, t);
      const x = ch.xAt(t);
      const f = ch.faceAt(t);
      // legs and hip height: the lower foot always touches the floor
      const foot = (i) => TH * Math.cos(p.hA[i] * RAD) + SH * Math.cos((p.hA[i] - p.kA[i]) * RAD);
      const hipY = FLOOR - Math.max(foot(0), foot(1)) - p.lift;
      const hip = [0, hipY];
      const lean = p.lean * RAD;
      const neck = [hip[0] + Math.sin(lean) * TORSO, hip[1] - Math.cos(lean) * TORSO];
      const sh = [hip[0] + Math.sin(lean) * TORSO * 0.92, hip[1] - Math.cos(lean) * TORSO * 0.92 - p.shr];
      const legPath = (i) => {
        const k = [hip[0] + Math.sin(p.hA[i] * RAD) * TH, hip[1] + Math.cos(p.hA[i] * RAD) * TH];
        const a2 = (p.hA[i] - p.kA[i]) * RAD;
        const fo = [k[0] + Math.sin(a2) * SH, k[1] + Math.cos(a2) * SH];
        return `M${R(hip[0])} ${R(hip[1])} L${R(k[0])} ${R(k[1])} L${R(fo[0])} ${R(fo[1])} l8 0`;
      };
      ch.legB.setAttribute("d", legPath(0));
      ch.legF.setAttribute("d", legPath(1));
      ch.torso.setAttribute("d", `M${R(hip[0])} ${R(hip[1])} L${R(neck[0])} ${R(neck[1])}`);
      if (ch.coat) ch.coat.setAttribute("d", `M${R(hip[0])} ${R(hip[1])} L${R(sh[0])} ${R(sh[1] + 6)}`);
      if (ch.shirt) ch.shirt.setAttribute("d", `M${R(hip[0])} ${R(hip[1])} L${R(sh[0])} ${R(sh[1] + 6)}`);
      if (ch.apron) ch.apron.setAttribute("d", `M${R(hip[0] + 6)} ${R(hip[1])} L${R(sh[0] + 6)} ${R(sh[1] + 20)}`);
      if (ch.pack) ch.pack.setAttribute("transform", `translate(${R(sh[0] - 22)} ${R(sh[1] + 4)}) rotate(${(lean / RAD).toFixed(1)})`);
      if (ch.tie) ch.tie.setAttribute("transform", `translate(${R(sh[0])} ${R(sh[1] + 6)})`);
      if (ch.scarf) ch.scarf.setAttribute("transform", `translate(${R(neck[0])} ${R(neck[1] + 2)})`);
      const hl = (NECK + HR);
      const ha = lean + p.tilt * RAD;
      const hc = [neck[0] + Math.sin(ha) * hl + p.hdx, neck[1] - Math.cos(ha) * hl + p.hdy];
      ch.head.setAttribute("transform", `translate(${R(hc[0])} ${R(hc[1])}) rotate(${(ha / RAD).toFixed(1)})`);
      const em = FACE[p.emo] || FACE.neutral;
      const er = em.big ? 4.8 : 3.4;
      ch.eyeL.setAttribute("r", er); ch.eyeR.setAttribute("r", er);
      const br = em.br;
      ch.browL.setAttribute("d", br ? `M-16 ${-13 + br[0] * 2} L-4 ${-13 - br[0] * 2}` : "M-16 -13 L-4 -13");
      ch.browR.setAttribute("d", br ? `M4 ${-13 - br[1] * 2} L16 ${-13 + br[1] * 2}` : "M4 -13 L16 -13");
      ch.browL.setAttribute("opacity", br ? 1 : 0); ch.browR.setAttribute("opacity", br ? 1 : 0);
      ch.mouth.setAttribute("d", em.m);
      const open = ch.id === speakerId ? clamp((env || 0) * 1.6, 0, 1) : 0;
      ch.talk.setAttribute("ry", (2 + 9 * open).toFixed(1));
      ch.talk.setAttribute("opacity", open > 0.12 ? 1 : 0);
      ch.mouth.setAttribute("opacity", open > 0.12 ? 0 : 1);
      // arms (IK blended over forward kinematics)
      const armCalc = (i) => {
        let s = p.sA[i], fa = p.fA[i];
        const ik = p.ik[i];
        if (ik && ik.w > 0.001) { s = lerp(s, ik.s, ik.w); fa = lerp(fa, ik.f, ik.w); }
        const e = [sh[0] + Math.sin(s * RAD) * UA, sh[1] + Math.cos(s * RAD) * UA];
        const h = [e[0] + Math.sin(fa * RAD) * FA, e[1] + Math.cos(fa * RAD) * FA];
        return { e, h, d: `M${R(sh[0])} ${R(sh[1])} L${R(e[0])} ${R(e[1])} L${R(h[0])} ${R(h[1])}` };
      };
      const aB = armCalc(0), aF = armCalc(1);
      ch.armB.setAttribute("d", aB.d);
      ch.armF.setAttribute("d", aF.d);
      if (p.fingers > 0) {
        let d = "";
        for (let k = 0; k < p.fingers; k++) d += `M${R(aF.h[0] - 7 + k * 3.5)} ${R(aF.h[1])} l${(k - (p.fingers - 1) / 2) * 3} -14 `;
        ch.fingers.setAttribute("d", d);
      } else ch.fingers.setAttribute("d", "");
      showMark(ch, t, hc[0] + 66 * sgn(f), hc[1] - 14, 0.9, sgn(f));
      ch.think.setAttribute("opacity", p.think > 0.3 ? 1 : 0);
      ch.think.setAttribute("transform", `translate(${R(hc[0] + 38)} ${R(hc[1] - 52)})`);
      ch.root.setAttribute("transform", `translate(${R(x)} ${FLOOR}) scale(${(f * K).toFixed(3)} ${K}) translate(0 ${-FLOOR}) rotate(${(p.rot).toFixed(1)} 0 ${FLOOR})`);
      ch.hand = [x + aF.h[0] * sgn(f) * K, FLOOR + (aF.h[1] - FLOOR) * K];
      ch.headW = [x + hc[0] * sgn(f) * K, FLOOR + (hc[1] - FLOOR) * K - HR * K - 6];
      ch.sh = sh;
    }

    const propWorld = (n, t) => {
      const pos = spots[n];
      let wx = pos[0], wy = pos[1];
      let best = null;
      for (const ch of chars) for (const e of ch.carryAll || ch.carry) { if (e.prop !== n || t < e.t || e.give) continue; if (!best || e.t >= best.e.t) best = { e, ch }; }
      if (best) {
        const { e, ch } = best;
        const ry = REST_Y[n] || 500;
        if (e.hold) { wx = ch.hand ? ch.hand[0] : wx; wy = ch.hand ? ch.hand[1] - 6 : wy; }
        else if (e.fly) {
          const k = clamp((t - e.fly.t0) / (e.fly.t1 - e.fly.t0), 0, 1);
          const sx0 = ch.xAt(e.t) + (ch.faceAt(e.t) >= 0 ? 1 : -1) * 40;
          wx = lerp(sx0, e.fly.x, k); wy = lerp(340, ry, k * k) - 120 * Math.sin(k * Math.PI);
        } else {
          const k = clamp((t - e.t) / 0.35, 0, 1);
          wx = e.x != null ? e.x : (ch.hand ? ch.hand[0] : wx); wy = lerp(ch.hand ? ch.hand[1] : ry - 60, ry, k * k);
        }
      }
      return [wx, wy];
    };

    let lastDraw = -1, framed = false;
    function frameProps() {                                                     // a prop the shot cuts by more than a quarter is not drawn at all (half a desk reads as a mistake)
      framed = true;
      const box = svg.getBoundingClientRect();
      if (!box.width) return;
      const scenery = new Set((S.set && S.set.scenery) || []);                 // what the kind of place brings and nothing names (the composer works it out): nobody placed it
      Object.keys(spriteOf).forEach((n) => {
        const r = spriteOf[n].getBoundingClientRect();
        if (!r.width || !r.height) return;
        const vis = Math.max(0, Math.min(r.right, box.right) - Math.max(r.left, box.left)) * Math.max(0, Math.min(r.bottom, box.bottom) - Math.max(r.top, box.top));
        if (vis / (r.width * r.height) < 0.75) {
          if (scenery.has(n)) { spriteOf[n].style.display = "none"; return; }  // set decoration the shot cuts is not drawn, for every plan: half a desk reads as a mistake, and no director put it there
          // a prop a director named in an action or the shot is kept in a scene an AI directed: the cut is only recorded (the facts tell the director)
          if (sc.directed) (window.__guard = window.__guard || []).push({ scene: sc.src || sc.id, type: "prop:" + n, rule: "cut-off", fix: "would-drop", directed: true });
          else { spriteOf[n].style.display = "none"; (window.__guard = window.__guard || []).push({ scene: sc.src || sc.id, type: "prop:" + n, rule: "cut-off", fix: "dropped" }); }
        }
      });
    }
    function draw(t) {
      const cam = camAt(t);
      world.setAttribute("transform", `translate(500 300) scale(${cam.z.toFixed(4)}) translate(${(-cam.cx).toFixed(2)} ${(-cam.cy).toFixed(2)})`);
      const sayAct = S.actions.find((q) => q.do === "say" && t >= q.start && t <= q.end);
      const speakerId = sayAct ? sayAct.who : (chars[0] ? chars[0].id : null);
      const env = X.envelopeAt && D.envelope ? X.envelopeAt(D.envelope, t) : 0.4 * (0.5 + 0.5 * Math.sin(t * 13));
      chars.forEach((ch) => drawChar(ch, t, speakerId, env));
      if (!framed) { names.forEach((n) => { const w = propWorld(n, t); spriteOf[n].setAttribute("transform", `translate(${R(w[0])} ${R(w[1])})`); }); frameProps(); }
      if (fxEls.length) drawFx(t);
      names.forEach((n) => {
        const w = propWorld(n, t);
        spriteOf[n].setAttribute("transform", `translate(${R(w[0])} ${R(w[1])})`);
      });
      if (boardText && spots[board]) {
        const wa = S.actions.filter((q) => q.do === "write_board" && q.start <= t).pop();
        const txt = wa ? (wa.bubble || "") : "";
        const k = wa ? clamp((t - wa.start) / Math.max(0.4, wa.end - wa.start), 0, 1) : 0;
        const shown = txt.slice(0, Math.ceil(txt.length * k));
        const lines = [];
        shown.split(" ").forEach((wd) => { const l = lines[lines.length - 1]; if (l !== undefined && (l + " " + wd).length <= 16) lines[lines.length - 1] = l + " " + wd; else lines.push(wd); });
        boardText.textContent = "";
        lines.slice(0, 4).forEach((ln, i) => { const ts = sv("tspan", { x: spots[board][0], y: spots[board][1] - 40 + i * 36 }, boardText); ts.textContent = ln; });
      }
      bubbles.forEach((b) => {
        const on = t >= b.a.start && t <= Math.max(b.a.end, b.a.start + 1.2) ? 1 : 0;
        if (on !== b.shown) { b.d.style.opacity = on; b.shown = on; }
        if (on && b.ch && b.ch.headW) {
          const px = toPx(cam, b.ch.headW[0] + (b.a.do === "say" ? 20 : 0), b.ch.headW[1] - (b.a.do === "hold_sign" ? 48 : 0));
          const bw = b.d.offsetWidth || rc.w * 0.6, bh = b.d.offsetHeight || 80;          // the whole bubble stays on screen, whatever its size
          const lo = bw / 2 + 24 - rc.l, hi = f.width - rc.l - bw / 2 - 24;              // the frame's edges (the stage can be inset in a wide video)
          b.d.style.left = clamp(px[0], lo, Math.max(lo, hi)) + "px";
          b.d.style.top = clamp(px[1], bh + 24 - rc.t, rc.h) + "px";
        }
      });
    }

    draw(t0);
    const proxy = { v: 0 };
    tl.fromTo(proxy, { v: 0 }, { v: 1, duration: span, ease: "none", onUpdate: function () { draw(t0 + this.ratio * span); }, onStart: function () { draw(t0); } }, t0);
    tl.call(() => draw(t1), null, t1 - 0.001);
  };
})();
