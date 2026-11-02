/* Infographic components (phase 2). Loaded after vt.js; registers into the same component table.
   Every builder returns { el, enter(tl, t, M, ctx, scene) } and only animates through the paused GSAP timeline. */
(function () {
  "use strict";
  const X = window.VTX;
  if (!X) return;
  const { C, h, rt, fit, popIn, svgIcon, idle } = X;
  const NS = "http://www.w3.org/2000/svg";
  const sv = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const BN = "০১২৩৪৫৬৭৮৯";
  const toLang = (s, bn) => (bn ? String(s).replace(/\d/g, (d) => BN[d]) : String(s));
  const isBn = (ctx, ...texts) => /[০-৯]/.test(texts.join("")) || (ctx.D.language === "bn" && !/\d/.test(texts.join("")));
  const parseNum = (str) => {
    const t = String(str).replace(/[০-৯]/g, (d) => BN.indexOf(d)).replace(/,/g, "");
    const m = /-?\d+(?:\.\d+)?/.exec(t);
    return m ? { n: parseFloat(m[0]), idx: m.index, len: m[0].length, src: t } : null;
  };
  const sticker = (ctx, key) => (ctx.D.stickers && key && ctx.D.stickers[key]) || "";

  /* count a number up inside an element while the timeline plays (works when seeking, too) */
  function countUp(tl, el, text, t, dur, bn) {
    const p = parseNum(text);
    if (!p) {
      el.textContent = text;
      return;
    }
    const dec = (String(p.src).slice(p.idx, p.idx + p.len).split(".")[1] || "").length;
    const pre = String(text).slice(0, String(text).search(/[0-9০-৯]/));
    const rest = String(text).slice(String(text).search(/[0-9০-৯]/)).replace(/^[0-9০-৯][0-9০-৯,.]*/, "");
    const o = { v: 0 };
    const render = () => (el.textContent = pre + toLang(o.v.toFixed(dec), bn) + rest);
    render();
    tl.to(o, { v: p.n, duration: dur, ease: "power2.out", onUpdate: render }, t);
    tl.set(o, { v: p.n }, t + dur + 0.001);
  }

  /* ---------------- ring ---------------- */
  C.ring = (d, ctx) => {
    const size = 420, r = 170, circ = 2 * Math.PI * r;
    const wrap = h("div", "ring");
    const box = h("div", "ring-box");
    const svg = sv("svg", { viewBox: "0 0 " + size + " " + size, class: "ring-svg" });
    sv("circle", { cx: size / 2, cy: size / 2, r, class: "ring-track" }, svg);
    const arc = sv("circle", { cx: size / 2, cy: size / 2, r, class: "ring-arc", "stroke-dasharray": circ, "stroke-dashoffset": circ, transform: "rotate(-90 " + size / 2 + " " + size / 2 + ")" }, svg);
    box.appendChild(svg);
    const bn = isBn(ctx, d.display || "", d.label || "");
    const val = h("div", "ring-val");
    box.appendChild(val);
    wrap.appendChild(box);
    let lab = null;
    if (d.label) {
      lab = rt("div", "ring-label", d.label);
      wrap.appendChild(lab);
    }
    const shown = d.display != null ? d.display : toLang(Math.round(d.value), bn) + "%";
    val.textContent = shown;
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(box, { opacity: 0, scale: 0.8 }, { opacity: 1, scale: 1, duration: M.dur, ease: M.ease }, t);
        tl.fromTo(arc, { attr: { "stroke-dashoffset": circ } }, { attr: { "stroke-dashoffset": circ * (1 - d.value / 100) }, duration: 1.1, ease: "power2.out" }, t + 0.15);
        countUp(tl, val, shown, t + 0.15, 1.1, bn);
        if (lab) tl.fromTo(lab, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: M.dur }, t + 0.5);
      },
    };
  };

  /* ---------------- line chart ---------------- */
  C.line_chart = (d, ctx) => {
    const W = 880, H = 520, padL = 40, padR = 40, padT = 60, padB = 90;
    const pts = d.points;
    const vals = pts.map((p) => p.value);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const span = hi - lo || 1;
    const xy = pts.map((p, i) => [padL + (i * (W - padL - padR)) / (pts.length - 1), padT + (1 - (p.value - lo) / span) * (H - padT - padB)]);
    const wrap = h("div", "linec");
    const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, class: "linec-svg" });
    for (let g = 0; g < 4; g++) sv("line", { x1: padL, x2: W - padR, y1: padT + (g * (H - padT - padB)) / 3, y2: padT + (g * (H - padT - padB)) / 3, class: "linec-grid" }, svg);
    const area = sv("path", { d: "M" + xy.map((q) => q.join(",")).join(" L") + " L" + xy[xy.length - 1][0] + "," + (H - padB) + " L" + xy[0][0] + "," + (H - padB) + " Z", class: "linec-area" }, svg);
    let len = 0;
    for (let i = 1; i < xy.length; i++) len += Math.hypot(xy[i][0] - xy[i - 1][0], xy[i][1] - xy[i - 1][1]);
    const line = sv("polyline", { points: xy.map((q) => q.join(",")).join(" "), class: "linec-line", "stroke-dasharray": len, "stroke-dashoffset": len }, svg);
    const dots = [], labs = [], vls = [];
    xy.forEach((q, i) => {
      dots.push(sv("circle", { cx: q[0], cy: q[1], r: 13, class: "linec-dot" }, svg));
      const l = sv("text", { x: q[0], y: H - padB + 56, class: "linec-x", "text-anchor": "middle" }, svg);
      l.textContent = pts[i].label;
      labs.push(l);
      const v = sv("text", { x: q[0], y: q[1] - 26, class: "linec-v", "text-anchor": "middle" }, svg);
      v.textContent = (Number.isInteger(pts[i].value) ? pts[i].value : pts[i].value.toFixed(1)) + (d.unit || "");
      vls.push(v);
    });
    wrap.appendChild(svg);
    let lab = null;
    if (d.label) {
      lab = rt("div", "linec-label", d.label);
      wrap.appendChild(lab);
    }
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(wrap, { opacity: 0 }, { opacity: 1, duration: 0.25 }, t);
        tl.fromTo(line, { attr: { "stroke-dashoffset": len } }, { attr: { "stroke-dashoffset": 0 }, duration: 1.4, ease: "power1.inOut" }, t + 0.1);
        tl.fromTo(area, { opacity: 0 }, { opacity: 1, duration: 0.8 }, t + 1.0);
        xy.forEach((q, i) => {
          const at = t + 0.1 + (1.4 * i) / (xy.length - 1);
          tl.fromTo(dots[i], { scale: 0, transformOrigin: q[0] + "px " + q[1] + "px" }, { scale: 1, duration: 0.3, ease: "back.out(2.5)" }, at);
          tl.fromTo([labs[i], vls[i]], { opacity: 0 }, { opacity: 1, duration: 0.3 }, at);
        });
        if (lab) tl.fromTo(lab, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: M.dur }, t + 0.4);
      },
    };
  };

  /* ---------------- steps ---------------- */
  C.steps = (d, ctx) => {
    const wrap = h("div", "steps" + (ctx.a169 ? " steps-row" : ""));
    const rows = d.items.map((it, i) => {
      const row = h("div", "step");
      const num = h("div", "step-num", toLang(i + 1, isBn(ctx, it.title, it.detail)));
      const body = h("div", "step-body");
      body.appendChild(rt("div", "step-title", it.title));
      if (it.detail) body.appendChild(rt("div", "step-detail", it.detail));
      row.appendChild(num);
      row.appendChild(body);
      const link = i < d.items.length - 1 ? h("i", "step-link") : null;
      if (link) row.appendChild(link);
      wrap.appendChild(row);
      return { row, num, body, link };
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        rows.forEach((r, i) => {
          const at = t + i * (M.stagger + 0.28);
          tl.fromTo(r.num, { opacity: 0, scale: 0.2 }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(2)" }, at);
          tl.fromTo(r.body, { opacity: 0, x: ctx.a169 ? 0 : 40, y: ctx.a169 ? 24 : 0 }, { opacity: 1, x: 0, y: 0, duration: M.dur, ease: "power2.out" }, at + 0.12);
          if (r.link) tl.fromTo(r.link, { scaleY: 0, scaleX: ctx.a169 ? 0 : 1 }, { scaleY: 1, scaleX: 1, duration: 0.3, ease: "none" }, at + 0.3);
        });
      },
    };
  };

  /* ---------------- timeline ---------------- */
  C.timeline = (d, ctx) => {
    const wrap = h("div", "tline" + (ctx.a169 ? " tline-row" : ""));
    const spine = h("i", "tline-spine");
    wrap.appendChild(spine);
    const evs = d.events.map((e) => {
      const row = h("div", "tl-ev");
      const dot = h("i", "tl-dot");
      const when = rt("div", "tl-when", e.when);
      const what = rt("div", "tl-what", e.what);
      const txt = h("div", "tl-txt");
      txt.appendChild(when);
      txt.appendChild(what);
      row.appendChild(dot);
      row.appendChild(txt);
      wrap.appendChild(row);
      return { row, dot, txt };
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(spine, { scaleY: 0, scaleX: ctx.a169 ? 0 : 1 }, { scaleY: 1, scaleX: 1, duration: 0.3 + evs.length * 0.45, ease: "none" }, t);
        evs.forEach((e, i) => {
          const at = t + 0.2 + i * 0.45;
          tl.fromTo(e.dot, { scale: 0 }, { scale: 1, duration: 0.3, ease: "back.out(3)" }, at);
          tl.fromTo(e.txt, { opacity: 0, x: ctx.a169 ? 0 : 30, y: ctx.a169 ? 20 : 0 }, { opacity: 1, x: 0, y: 0, duration: M.dur }, at + 0.05);
        });
      },
    };
  };

  /* ---------------- definition ---------------- */
  C.definition = (d, ctx) => {
    const wrap = h("div", "defn");
    const term = rt("div", "defn-term", d.term);
    const eq = h("div", "defn-eq", "=");
    const mean = rt("div", "defn-meaning", d.meaning);
    wrap.appendChild(term);
    wrap.appendChild(eq);
    wrap.appendChild(mean);
    fit(term, ctx.maxW - 100);
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(term, { opacity: 0, scale: 0.7, rotation: -4 }, { opacity: 1, scale: 1, rotation: 0, duration: M.dur + 0.1, ease: "back.out(1.8)" }, t);
        tl.fromTo(eq, { opacity: 0, scale: 0 }, { opacity: 1, scale: 1, duration: 0.25 }, t + 0.35);
        tl.fromTo(mean, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: M.dur + 0.1, ease: "power2.out" }, t + 0.5);
      },
    };
  };

  /* ---------------- checklist ---------------- */
  C.checklist = (d, ctx) => {
    const wrap = h("div", "chk");
    let ttl = null;
    if (d.title) {
      ttl = rt("div", "chk-title", d.title);
      wrap.appendChild(ttl);
    }
    const rows = d.items.map((txt) => {
      const row = h("div", "chk-row");
      const box = h("div", "chk-box");
      const svg = sv("svg", { viewBox: "0 0 40 40" }, box);
      const tick = sv("path", { d: "M8 21 L17 30 L33 11", class: "chk-tick", "stroke-dasharray": 40, "stroke-dashoffset": 40 }, svg);
      row.appendChild(box);
      row.appendChild(rt("div", "chk-text", txt));
      wrap.appendChild(row);
      return { row, box, tick };
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        if (ttl) tl.fromTo(ttl, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: M.dur }, t);
        rows.forEach((r, i) => {
          const at = t + 0.2 + i * 0.5;
          tl.fromTo(r.row, { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: M.dur, ease: "power2.out" }, at);
          tl.fromTo(r.tick, { attr: { "stroke-dashoffset": 40 } }, { attr: { "stroke-dashoffset": 0 }, duration: 0.3, ease: "power2.out" }, at + 0.25);
          tl.fromTo(r.box, { backgroundColor: "rgba(0,0,0,0)" }, { backgroundColor: "var(--accent)", duration: 0.2 }, at + 0.25);
        });
      },
    };
  };

  /* ---------------- pros / cons ---------------- */
  C.pros_cons = (d, ctx) => {
    const wrap = h("div", "pc");
    const col = (cls, items, title, mark) => {
      const c = h("div", "pc-col " + cls);
      c.appendChild(h("div", "pc-head", title || mark));
      const rows = items.map((t) => {
        const r = h("div", "pc-row");
        r.appendChild(h("span", "pc-mark", mark));
        r.appendChild(rt("span", "pc-text", t));
        c.appendChild(r);
        return r;
      });
      wrap.appendChild(c);
      return { c, rows };
    };
    const a = col("pc-pro", d.pros, d.pros_title, "✓");
    const b = col("pc-con", d.cons, d.cons_title, "✕");
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(a.c, { opacity: 0, x: -50 }, { opacity: 1, x: 0, duration: M.dur + 0.1, ease: M.ease }, t);
        a.rows.forEach((r, i) => tl.fromTo(r, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.3 }, t + 0.3 + i * 0.25));
        const t2 = t + 0.5 + a.rows.length * 0.25;
        tl.fromTo(b.c, { opacity: 0, x: 50 }, { opacity: 1, x: 0, duration: M.dur + 0.1, ease: M.ease }, t2 - 0.3);
        b.rows.forEach((r, i) => tl.fromTo(r, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.3 }, t2 + i * 0.25));
      },
    };
  };

  /* ---------------- stat row ---------------- */
  C.stat_row = (d, ctx) => {
    const wrap = h("div", "stats stats-" + d.stats.length);
    const cells = d.stats.map((s) => {
      const c = h("div", "stat");
      const v = h("div", "stat-val");
      c.appendChild(v);
      if (s.label) c.appendChild(rt("div", "stat-label", s.label));
      wrap.appendChild(c);
      fit(v, 380);
      return { c, v, s };
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        cells.forEach((x, i) => {
          const at = t + i * (M.stagger + 0.12);
          tl.fromTo(x.c, { opacity: 0, y: 40, scale: 0.85 }, { opacity: 1, y: 0, scale: 1, duration: M.dur + 0.1, ease: "back.out(1.7)" }, at);
          countUp(tl, x.v, x.s.value, at, 0.9, isBn(ctx, x.s.value));
        });
      },
    };
  };

  /* ---------------- question ---------------- */
  C.question = (d, ctx) => {
    const wrap = h("div", "qz");
    const badge = h("div", "qz-badge", "?");
    const text = rt("div", "qz-text", d.text);
    wrap.appendChild(badge);
    wrap.appendChild(text);
    const opts = (d.options || []).map((o, i) => {
      const e = h("div", "qz-opt");
      e.appendChild(h("span", "qz-letter", String.fromCharCode(65 + i)));
      e.appendChild(rt("span", "qz-otext", o));
      wrap.appendChild(e);
      return e;
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(badge, { opacity: 0, scale: 0, rotation: -40 }, { opacity: 1, scale: 1, rotation: 0, duration: M.dur + 0.15, ease: "back.out(2.4)" }, t);
        tl.fromTo(text, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: M.dur }, t + 0.2);
        opts.forEach((o, i) => tl.fromTo(o, { opacity: 0, x: -30 }, { opacity: 1, x: 0, duration: 0.3 }, t + 0.6 + i * 0.25));
        if (d.answer != null && opts[d.answer]) {
          const at = t + 0.9 + opts.length * 0.25 + 0.8;
          tl.to(opts[d.answer], { backgroundColor: "var(--accent)", color: "var(--hl-ink)", scale: 1.06, duration: 0.3, ease: "back.out(2)" }, at);
        }
      },
    };
  };

  /* ---------------- feature grid ---------------- */
  C.feature_grid = (d, ctx) => {
    const wrap = h("div", "fg fg-" + d.items.length);
    const cells = d.items.map((f) => {
      const c = h("div", "fg-card");
      const art = h("div", "fg-art");
      if (f.emoji && sticker(ctx, f.emoji)) art.innerHTML = sticker(ctx, f.emoji);
      else if (f.icon) art.appendChild(svgIcon(ctx.D, f.icon));
      c.appendChild(art);
      c.appendChild(rt("div", "fg-title", f.title));
      if (f.detail) c.appendChild(rt("div", "fg-detail", f.detail));
      wrap.appendChild(c);
      return { c, art };
    });
    return {
      el: wrap,
      enter(tl, t, M, c, sc) {
        cells.forEach((x, i) => {
          const at = t + i * (M.stagger + 0.14);
          tl.fromTo(x.c, { opacity: 0, y: 60, scale: 0.8 }, { opacity: 1, y: 0, scale: 1, duration: M.dur + 0.15, ease: "back.out(1.8)" }, at);
          tl.fromTo(x.art, { scale: 0.3, rotation: -15 }, { scale: 1, rotation: 0, duration: M.dur + 0.2, ease: "back.out(2.4)" }, at + 0.15);
        });
      },
    };
  };

  /* ---------------- call to action ---------------- */
  C.cta = (d, ctx) => {
    const wrap = h("div", "cta");
    const head = rt("div", "cta-head", d.headline);
    fit(head, ctx.maxW - 40);
    wrap.appendChild(head);
    let btn = null, sub = null;
    if (d.button) {
      btn = rt("div", "cta-btn", d.button);
      wrap.appendChild(btn);
    }
    if (d.sub) {
      sub = rt("div", "cta-sub", d.sub);
      wrap.appendChild(sub);
    }
    return {
      el: wrap,
      enter(tl, t, M, c, sc) {
        tl.fromTo(head, { opacity: 0, y: 50, scale: 0.9 }, { opacity: 1, y: 0, scale: 1, duration: M.dur + 0.1, ease: M.ease }, t);
        if (btn) {
          tl.fromTo(btn, { opacity: 0, scale: 0.5 }, { opacity: 1, scale: 1, duration: M.dur + 0.1, ease: "back.out(2.4)" }, t + 0.3);
          const end = sc ? sc.end : t + 4;
          const n = Math.max(0, Math.floor((end - t - 1.2) / 0.5) - (Math.floor((end - t - 1.2) / 0.5) % 2));
          if (n >= 2) tl.to(btn, { scale: 1.07, duration: 0.5, yoyo: true, repeat: n - 1, ease: "sine.inOut" }, t + 0.9);
        }
        if (sub) tl.fromTo(sub, { opacity: 0 }, { opacity: 1, duration: 0.4 }, t + 0.6);
      },
    };
  };

  /* ---------------- price tag ---------------- */
  C.price_tag = (d, ctx) => {
    const wrap = h("div", "price");
    const badge = h("div", "price-badge");
    let old = null;
    if (d.old_price) {
      old = h("div", "price-old");
      old.appendChild(rt("span", "price-old-t", d.old_price));
      old.appendChild(h("i", "price-strike"));
      badge.appendChild(old);
    }
    const now = rt("div", "price-now", d.price);
    badge.appendChild(now);
    wrap.appendChild(badge);
    let lab = null;
    if (d.label) {
      lab = rt("div", "price-label", d.label);
      wrap.appendChild(lab);
    }
    fit(now, ctx.maxW - 160);
    const strike = old && old.querySelector(".price-strike");
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(badge, { opacity: 0, scale: 0.3, rotation: -20 }, { opacity: 1, scale: 1, rotation: -4, duration: M.dur + 0.25, ease: "back.out(2.2)" }, t);
        if (strike) tl.fromTo(strike, { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: "power3.out" }, t + 0.5);
        if (lab) tl.fromTo(lab, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: M.dur }, t + 0.45);
      },
    };
  };
})();
