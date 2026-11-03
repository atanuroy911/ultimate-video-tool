/* Diagrams (phase 2b): flowchart, cycle, hierarchy, Venn, funnel, pyramid, 2x2 matrix, pictogram, gauge.
   Geometry lives in a fixed coordinate box (percent positions + SVG viewBox), so every diagram scales cleanly and animates on the paused timeline. */
(function () {
  "use strict";
  const X = window.VTX;
  if (!X) return;
  const { C, h, rt, fit } = X;
  const NS = "http://www.w3.org/2000/svg";
  const sv = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const BN = "০১২৩৪৫৬৭৮৯";
  const toLang = (s, bn) => (bn ? String(s).replace(/\d/g, (d) => BN[d]) : String(s));
  const isBn = (ctx, ...t) => /[০-৯]/.test(t.join("")) || (ctx.D.language === "bn" && !/\d/.test(t.join("")));

  /* a label positioned by percentages inside a diagram box */
  function label(parent, cls, text, x, y, w) {
    const e = rt("div", "dg-label " + cls, text);
    e.style.left = x + "%";
    e.style.top = y + "%";
    if (w) e.style.width = w + "%";
    parent.appendChild(e);
    return e;
  }
  function frame(w, hgt, cls) {
    const box = h("div", "dg " + (cls || ""));
    box.style.setProperty("--ar", w + " / " + hgt);
    const svg = sv("svg", { viewBox: "0 0 " + w + " " + hgt, class: "dg-svg", preserveAspectRatio: "none" });
    box.appendChild(svg);
    return { box, svg };
  }
  const arrowHead = (svg, x, y, ang, cls) => {
    const a = (ang * Math.PI) / 180;
    const p = [[0, 0], [-26, -13], [-26, 13]].map(([px, py]) => [x + px * Math.cos(a) - py * Math.sin(a), y + px * Math.sin(a) + py * Math.cos(a)]);
    return sv("polygon", { points: p.map((q) => q.join(",")).join(" "), class: cls || "dg-head" }, svg);
  };

  /* ---------------- flowchart ---------------- */
  C.flow = (d, ctx) => {
    const wrap = h("div", "fl" + (ctx.a169 ? " fl-row" : ""));
    const parts = [];
    d.nodes.forEach((n, i) => {
      const box = h("div", "fl-node fl-" + n.kind);
      box.appendChild(rt("span", "fl-text", n.text));
      wrap.appendChild(box);
      let link = null;
      if (i < d.nodes.length - 1) {
        link = h("div", "fl-link");
        link.appendChild(h("i", "fl-line"));
        link.appendChild(h("i", "fl-tip"));
        wrap.appendChild(link);
      }
      parts.push({ box, link });
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        parts.forEach((p, i) => {
          const at = t + i * 0.55;
          tl.fromTo(p.box, { opacity: 0, scale: 0.6, y: 20 }, { opacity: 1, scale: 1, y: 0, duration: M.dur, ease: "back.out(1.8)" }, at);
          if (p.link) {
            const line = p.link.querySelector(".fl-line"), tip = p.link.querySelector(".fl-tip");
            tl.fromTo(line, ctx.a169 ? { scaleX: 0 } : { scaleY: 0 }, ctx.a169 ? { scaleX: 1, duration: 0.3, ease: "none" } : { scaleY: 1, duration: 0.3, ease: "none" }, at + 0.3);
            tl.fromTo(tip, { opacity: 0 }, { opacity: 1, duration: 0.1 }, at + 0.55);
          }
        });
      },
    };
  };

  /* ---------------- cycle ---------------- */
  C.cycle = (d, ctx) => {
    const W = 1000, Hh = 1000, cx = 500, cy = 500, r = 330;
    const { box, svg } = frame(W, Hh, "dg-square");
    const n = d.items.length;
    const pos = d.items.map((_, i) => {
      const a = (-90 + (360 * i) / n) * (Math.PI / 180);
      return { a, x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
    });
    const arcs = [];
    for (let i = 0; i < n; i++) {
      const a0 = pos[i].a + 0.38, a1 = pos[(i + 1) % n].a + (i === n - 1 ? 2 * Math.PI : 0) - 0.38;
      const p0 = [cx + r * Math.cos(a0), cy + r * Math.sin(a0)], p1 = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)];
      const path = sv("path", { d: "M" + p0.join(",") + " A" + r + "," + r + " 0 0 1 " + p1.join(","), class: "dg-arc", fill: "none" }, svg);
      const len = r * (a1 - a0);
      path.setAttribute("stroke-dasharray", len);
      path.setAttribute("stroke-dashoffset", len);
      const head = arrowHead(svg, p1[0], p1[1], (a1 * 180) / Math.PI + 90, "dg-head");
      arcs.push({ path, head, len });
    }
    const nodes = d.items.map((t, i) => label(box, "dg-node", t, (pos[i].x / W) * 100, (pos[i].y / Hh) * 100, 27));
    let mid = null;
    if (d.center) mid = label(box, "dg-center", d.center, 50, 50, 34);
    return {
      el: box,
      enter(tl, t, M) {
        nodes.forEach((nd, i) => {
          const at = t + i * 0.5;
          tl.fromTo(nd, { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(2)" }, at);
          tl.fromTo(arcs[i].path, { attr: { "stroke-dashoffset": arcs[i].len } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.4, ease: "none" }, at + 0.25);
          tl.fromTo(arcs[i].head, { opacity: 0 }, { opacity: 1, duration: 0.1 }, at + 0.62);
        });
        if (mid) tl.fromTo(mid, { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: M.dur }, t + n * 0.5);
      },
    };
  };

  /* ---------------- hierarchy ---------------- */
  C.hierarchy = (d, ctx) => {
    const W = 1000, Hh = 760;
    const { box, svg } = frame(W, Hh, "dg-wide");
    const nb = d.branches.length;
    const rootEl = label(box, "dg-node dg-root", d.root, 50, 10, 38);
    const items = [];
    d.branches.forEach((b, i) => {
      const bx = ((i + 0.5) / nb) * 100;
      const line = sv("path", { d: "M500,110 V230 H" + (bx * W) / 100 + " V300", class: "dg-edge", fill: "none" }, svg);
      const len = 120 + Math.abs((bx * W) / 100 - 500) + 70;
      line.setAttribute("stroke-dasharray", len);
      line.setAttribute("stroke-dashoffset", len);
      const be = label(box, "dg-node dg-branch", b.text, bx, 47, Math.min(30, 90 / nb));
      const leaves = (b.children || []).map((c, k) => {
        const ly = 70 + k * 15;
        const l2 = sv("line", { x1: (bx * W) / 100, y1: 0.47 * Hh + 36, x2: (bx * W) / 100, y2: (ly / 100) * Hh - 10, class: "dg-edge dg-spine" }, svg);
        return { el: label(box, "dg-node dg-leaf", c, bx, ly, Math.min(28, 86 / nb)), l2 };
      });
      items.push({ line, len, be, leaves });
    });
    return {
      el: box,
      enter(tl, t, M) {
        tl.fromTo(rootEl, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(1.8)" }, t);
        items.forEach((b, i) => {
          const at = t + 0.4 + i * 0.5;
          tl.fromTo(b.line, { attr: { "stroke-dashoffset": b.len } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.35, ease: "none" }, at);
          tl.fromTo(b.be, { opacity: 0, y: 20, scale: 0.8 }, { opacity: 1, y: 0, scale: 1, duration: M.dur, ease: "back.out(1.6)" }, at + 0.3);
          b.leaves.forEach((lf, k) => {
            tl.fromTo(lf.l2, { opacity: 0 }, { opacity: 1, duration: 0.2 }, at + 0.6 + k * 0.2);
            tl.fromTo(lf.el, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: M.dur }, at + 0.7 + k * 0.2);
          });
        });
      },
    };
  };

  /* ---------------- Venn ---------------- */
  C.venn = (d, ctx) => {
    const W = 1000, Hh = d.sets.length === 3 ? 900 : 640;
    const { box, svg } = frame(W, Hh, "dg-wide");
    const R = d.sets.length === 3 ? 270 : 280;
    const centers = d.sets.length === 3 ? [[390, 330], [610, 330], [500, 560]] : [[370, 320], [630, 320]];
    const fills = ["var(--accent)", "var(--accent2)", "#3b82f6"];
    const circles = centers.map(([x, y], i) => sv("circle", { cx: x, cy: y, r: R, class: "dg-venn", style: "fill:" + fills[i] }, svg));
    const labs = d.sets.map((t, i) => {
      const dx = d.sets.length === 3 ? [-130, 130, 0][i] : [-150, 150][i];
      const dy = d.sets.length === 3 ? [-60, -60, 110][i] : [0, 0][i];
      return label(box, "dg-node dg-set", t, ((centers[i][0] + dx) / W) * 100, ((centers[i][1] + dy) / Hh) * 100, 22);
    });
    let ov = null;
    if (d.overlap) ov = label(box, "dg-node dg-overlap", d.overlap, 50, d.sets.length === 3 ? 41 : 50, 20);
    return {
      el: box,
      enter(tl, t, M) {
        circles.forEach((c, i) => {
          tl.fromTo(c, { opacity: 0, scale: 0.4, transformOrigin: centers[i][0] + "px " + centers[i][1] + "px" }, { opacity: 1, scale: 1, duration: M.dur + 0.2, ease: "back.out(1.5)" }, t + i * 0.45);
          tl.fromTo(labs[i], { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: M.dur }, t + 0.3 + i * 0.45);
        });
        if (ov) tl.fromTo(ov, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(2)" }, t + d.sets.length * 0.45 + 0.2);
      },
    };
  };

  /* ---------------- funnel ---------------- */
  C.funnel = (d, ctx) => {
    const W = 1000, rows = d.stages.length, rowH = 150, Hh = rows * rowH + 20;
    const { box, svg } = frame(W, Hh, "dg-wide");
    const top = 960, bottom = 380;
    const w = (i) => top - ((top - bottom) * i) / rows;
    const polys = d.stages.map((s, i) => {
      const w0 = w(i), w1 = w(i + 1), y0 = 10 + i * rowH, y1 = y0 + rowH - 8;
      const pts = [[500 - w0 / 2, y0], [500 + w0 / 2, y0], [500 + w1 / 2, y1], [500 - w1 / 2, y1]];
      const p = sv("polygon", { points: pts.map((q) => q.join(",")).join(" "), class: "dg-fun dg-fun-" + (i % 4) }, svg);
      return p;
    });
    const labs = d.stages.map((s, i) => {
      const e = h("div", "dg-label dg-funlabel");
      e.style.left = "50%";
      e.style.top = ((10 + i * rowH + rowH / 2 - 4) / Hh) * 100 + "%";
      e.style.width = "70%";
      e.classList.add("dg-fl-c" + (i % 4));
      e.appendChild(rt("span", "dg-fl-text", s.label));
      if (s.value) e.appendChild(rt("span", "dg-fl-val", s.value));
      box.appendChild(e);
      return e;
    });
    return {
      el: box,
      enter(tl, t, M) {
        polys.forEach((p, i) => {
          tl.fromTo(p, { opacity: 0, y: -30 }, { opacity: 1, y: 0, duration: M.dur, ease: "power2.out" }, t + i * 0.5);
          tl.fromTo(labs[i], { opacity: 0 }, { opacity: 1, duration: 0.3 }, t + i * 0.5 + 0.25);
        });
      },
    };
  };

  /* ---------------- pyramid ---------------- */
  C.pyramid = (d, ctx) => {
    const W = 1000, n = d.levels.length, rowH = 150, Hh = n * rowH + 20;
    const { box, svg } = frame(W, Hh, "dg-wide");
    const baseW = 560, cx = 290;
    const polys = d.levels.map((t, i) => {
      const y0 = 10 + i * rowH, y1 = y0 + rowH - 8;
      const wTop = (baseW * i) / n + (i === 0 ? 0 : 0), wBot = (baseW * (i + 1)) / n;
      const pts = [[cx - wTop / 2, y0], [cx + wTop / 2, y0], [cx + wBot / 2, y1], [cx - wBot / 2, y1]];
      const p = sv("polygon", { points: pts.map((q) => q.join(",")).join(" "), class: "dg-fun dg-fun-" + (i % 4) }, svg);
      const line = sv("line", { x1: cx + (wTop + wBot) / 4, y1: (y0 + y1) / 2, x2: 640, y2: (y0 + y1) / 2, class: "dg-edge" }, svg);
      const lab = label(box, "dg-pylabel", t, 66, ((y0 + y1) / 2 / Hh) * 100, 32);
      return { p, line, lab, y: (y0 + y1) / 2 };
    });
    return {
      el: box,
      enter(tl, t, M) {
        // build from the base up: the foundation first
        polys.slice().reverse().forEach((o, k) => {
          const at = t + k * 0.5;
          tl.fromTo(o.p, { opacity: 0, scaleY: 0.3, transformOrigin: "50% 100%" }, { opacity: 1, scaleY: 1, duration: M.dur, ease: "back.out(1.4)" }, at);
          tl.fromTo(o.line, { opacity: 0 }, { opacity: 1, duration: 0.2 }, at + 0.2);
          tl.fromTo(o.lab, { opacity: 0, x: 20 }, { opacity: 1, x: 0, duration: M.dur }, at + 0.25);
        });
      },
    };
  };

  /* ---------------- 2 x 2 matrix ---------------- */
  C.matrix = (d, ctx) => {
    const wrap = h("div", "mx");
    const grid = h("div", "mx-grid");
    const cells = d.quadrants.map((q, i) => {
      const c = h("div", "mx-cell" + (d.highlight === i ? " mx-hl" : ""));
      c.appendChild(rt("span", "mx-text", q));
      grid.appendChild(c);
      return c;
    });
    const yl = d.y_label ? rt("div", "mx-y", "↑ " + d.y_label) : null;
    const xl = d.x_label ? rt("div", "mx-x", d.x_label + " →") : null;
    if (yl) wrap.appendChild(yl);
    wrap.appendChild(grid);
    if (xl) wrap.appendChild(xl);
    return {
      el: wrap,
      enter(tl, t, M) {
        if (yl) tl.fromTo(yl, { opacity: 0 }, { opacity: 1, duration: 0.3 }, t);
        if (xl) tl.fromTo(xl, { opacity: 0 }, { opacity: 1, duration: 0.3 }, t + 0.1);
        cells.forEach((c, i) => tl.fromTo(c, { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(1.7)" }, t + 0.2 + i * 0.25));
        if (d.highlight != null && cells[d.highlight]) tl.fromTo(cells[d.highlight], { scale: 1 }, { scale: 1.07, duration: 0.3, yoyo: true, repeat: 1, ease: "sine.inOut" }, t + 1.4);
      },
    };
  };

  /* ---------------- pictogram ---------------- */
  C.pictogram = (d, ctx) => {
    const wrap = h("div", "pg");
    const cols = d.total <= 5 ? d.total : d.total <= 10 ? 5 : d.total <= 12 ? 6 : d.total <= 16 ? 8 : 10;
    const grid = h("div", "pg-grid");
    grid.style.setProperty("--cols", cols);
    const art = (ctx.D.stickers && ctx.D.stickers[d.emoji || "1f9d1"]) || "";
    const figs = [];
    for (let i = 0; i < d.total; i++) {
      const f = h("div", "pg-fig");
      f.innerHTML = art;
      grid.appendChild(f);
      figs.push(f);
    }
    wrap.appendChild(grid);
    let lab = null;
    if (d.label) {
      lab = rt("div", "pg-label", d.label);
      wrap.appendChild(lab);
    }
    return {
      el: wrap,
      enter(tl, t, M) {
        figs.forEach((f, i) => {
          tl.fromTo(f, { opacity: 0, scale: 0.3, y: 20 }, { opacity: 0.28, scale: 1, y: 0, duration: 0.25, ease: "back.out(2)" }, t + i * 0.04);
          f.style.filter = "grayscale(1)";
        });
        const t2 = t + d.total * 0.04 + 0.3;
        figs.slice(0, d.highlighted).forEach((f, i) => {
          tl.to(f, { opacity: 1, filter: "grayscale(0)", scale: 1.12, duration: 0.2, ease: "back.out(2.2)" }, t2 + i * 0.12);
          tl.to(f, { scale: 1, duration: 0.15 }, t2 + i * 0.12 + 0.2);
        });
        if (lab) tl.fromTo(lab, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: M.dur }, t2 + 0.2);
      },
    };
  };

  /* ---------------- gauge ---------------- */
  C.gauge = (d, ctx) => {
    const W = 1000, Hh = 760, cx = 500, cy = 520, R = 400, r0 = 270;
    const { box, svg } = frame(W, Hh, "dg-wide");
    const arc = (a0, a1, cls) => {
      const p = (a, rr) => [cx + rr * Math.cos((a * Math.PI) / 180), cy + rr * Math.sin((a * Math.PI) / 180)];
      const s0 = p(a0, R), s1 = p(a1, R), e1 = p(a1, r0), e0 = p(a0, r0);
      return sv("path", { d: "M" + s0 + " A" + R + "," + R + " 0 0 1 " + s1 + " L" + e1 + " A" + r0 + "," + r0 + " 0 0 0 " + e0 + " Z", class: cls }, svg);
    };
    const zones = [arc(180, 240, "dg-zone dg-z0"), arc(240, 300, "dg-zone dg-z1"), arc(300, 360, "dg-zone dg-z2")];
    const needle = sv("g", { class: "dg-needle" }, svg);
    sv("polygon", { points: cx - 16 + "," + cy + " " + (cx + 16) + "," + cy + " " + cx + "," + (cy - R + 20), class: "dg-needle-body" }, needle);
    sv("circle", { cx, cy, r: 34, class: "dg-hub" }, svg);
    const bn = isBn(ctx, d.display || "", d.label || "");
    const val = h("div", "dg-gauge-val");
    const shown = d.display != null ? d.display : toLang(Math.round(d.value), bn);
    val.textContent = shown;
    box.appendChild(val);
    let lab = null;
    if (d.label) lab = label(box, "dg-gauge-label", d.label, 50, 93, 80);
    const lo = d.low ? label(box, "dg-gauge-end", d.low, 16, 72, 20) : null;
    const hi = d.high ? label(box, "dg-gauge-end", d.high, 84, 72, 20) : null;
    return {
      el: box,
      enter(tl, t, M) {
        zones.forEach((z, i) => tl.fromTo(z, { opacity: 0 }, { opacity: 1, duration: 0.3 }, t + i * 0.15));
        const ang = -90 + (d.value / 100) * 180;
        tl.fromTo(needle, { rotation: -90, svgOrigin: cx + " " + cy }, { rotation: ang, svgOrigin: cx + " " + cy, duration: 1.3, ease: "elastic.out(1, 0.6)" }, t + 0.5);
        tl.fromTo(val, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(2)" }, t + 0.9);
        [lab, lo, hi].forEach((e) => e && tl.fromTo(e, { opacity: 0 }, { opacity: 1, duration: 0.4 }, t + 0.6));
      },
    };
  };
})();
