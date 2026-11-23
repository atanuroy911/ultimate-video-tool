/* Video Tool runtime.
   Reads window.__VT__ (resolved composition data produced by vt/compose/composer.py),
   builds the DOM and ONE paused GSAP timeline, and registers it for HyperFrames
   (window.__timelines[compId]). The same page is used by the Studio preview (message API below). */
(function () {
  "use strict";

  const MOTION = {
    snappy: { ease: "power3.out", dur: 0.38, stagger: 0.09, from: { y: 46, scale: 0.9 } },
    smooth: { ease: "power2.inOut", dur: 0.65, stagger: 0.14, from: { y: 30, scale: 0.97 } },
    bouncy: { ease: "back.out(1.9)", dur: 0.55, stagger: 0.12, from: { y: 70, scale: 0.7 } },
  };

  const BN_DIGITS = "০১২৩৪৫৬৭৮৯";
  const toBn = (s) => String(s).replace(/\d/g, (d) => BN_DIGITS[d]);

  function h(tag, cls, content, attrs) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (content != null) {
      if (typeof content === "string") el.textContent = content;
      else if (content instanceof Node) el.appendChild(content);
    }
    if (attrs) for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
  }

  // Wrap runs of Latin text in <span lang="en"> so mixed Bangla/English lines can be styled.
  function rich(text) {
    const frag = document.createDocumentFragment();
    const parts = String(text).split(/([A-Za-z][A-Za-z0-9 .,'%&/+-]*[A-Za-z0-9%])/g);
    for (const p of parts) {
      if (!p) continue;
      if (/^[A-Za-z]/.test(p)) frag.appendChild(h("span", null, p, { lang: "en" }));
      else frag.appendChild(document.createTextNode(p));
    }
    return frag;
  }
  function rt(tag, cls, text) {
    const el = h(tag, cls);
    el.appendChild(rich(text));
    return el;
  }

  function svgIcon(D, name, extraCls) {
    const inner = (D.icons && D.icons[name]) || (D.icons && D.icons["circle-help"]) || "";
    const wrap = h("span");
    wrap.style.display = "contents";
    wrap.innerHTML =
      '<svg class="' + (extraCls || "") + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + inner + "</svg>";
    return wrap.firstChild;
  }

  /* ---------- text fitting (shrinks single-line text that overflows) ---------- */
  const fitQueue = [];
  function fit(el, maxW, minScale) {
    fitQueue.push({ el, maxW, minScale: minScale || 0.45 });
  }
  /* A scene with several pictures must stay inside the frame: shrink a stage's content only when it really overflows. offsetHeight ignores
     the entrance transforms, so the measurement is the same at any time. */
  function shrinkStages() {
    document.querySelectorAll("#root .stage").forEach((stage) => {
      stage.style.removeProperty("--s");
      let s = parseFloat(getComputedStyle(stage).getPropertyValue("--s")) || 1;
      for (let i = 0; i < 4; i++) {
        let worst = 1, stacked = 0, groups = 0;
        const column = getComputedStyle(stage).flexDirection === "column";                  // groups one above the other (a tall frame) share the stage's height; side by side each has all of it
        stage.querySelectorAll(":scope > .grp").forEach((g) => {
          const kids = Array.from(g.children).filter((k) => k.offsetHeight);
          const gap = parseFloat(getComputedStyle(g).rowGap) || 0;
          const need = kids.reduce((t, k) => t + k.offsetHeight, 0) + gap * Math.max(0, kids.length - 1);
          if (need > stage.clientHeight) worst = Math.min(worst, stage.clientHeight / need);
          if (need) { stacked += need; groups++; }
        });
        if (column && groups > 1) {
          const between = (parseFloat(getComputedStyle(stage).rowGap) || 0) * (groups - 1);
          if (stacked + between > stage.clientHeight) worst = Math.min(worst, stage.clientHeight / (stacked + between));
        }
        if (worst >= 0.995) break;
        s *= worst * 0.97;
        stage.style.setProperty("--s", String(s));
      }
      growStage(stage, s);
    });
  }

  /* Infographic scenes (one chart, one card...) grow to fill the stage instead of sitting small in the middle of it. */
  const SAFE_PORTRAIT = 420;
  const GROW = new Set(["ring", "line_chart", "steps", "timeline", "definition", "checklist", "pros_cons", "stat_row", "question", "feature_grid", "cta", "price_tag", "device",
    "speaker_card", "cartoon", "media_frame", "sticker", "keyword", "tag", "title", "flow", "cycle", "hierarchy", "venn", "funnel", "pyramid", "matrix", "pictogram", "gauge"]);
  const GROW_PLANNED = new Set(["value_card", "big_number", "compare", "list", "equation", "quote", "bar_chart", "icon_row", "icon"]);
  function growStage(stage, s0) {
    const els = Array.from(stage.querySelectorAll(".el"));
    const planned = stage.hasAttribute("data-arch");        // scenes drawn by the director may grow every card-like element; hand-made scenes only the new ones
    if (!els.length || !els.every((w) => { const k = (/el-(\w+)/.exec(w.className) || [])[1]; return GROW.has(k) || (planned && GROW_PLANNED.has(k)); })) return;
    let s = s0;
    for (let i = 0; i < 3; i++) {
      let needH = 0, needW = 0;
      stage.querySelectorAll(":scope > .grp").forEach((g) => {
        const kids = Array.from(g.children);
        const gap = parseFloat(getComputedStyle(g).rowGap) || 0;
        needH = Math.max(needH, kids.reduce((t, k) => t + k.offsetHeight, 0) + gap * Math.max(0, kids.length - 1));
        kids.forEach((k) => { needW = Math.max(needW, k.firstElementChild ? k.firstElementChild.scrollWidth : k.offsetWidth); });
      });
      if (!needH || !needW) return;
      const cap = els.length === 1 ? 2.6 : 1.7;                       // an element alone on screen may fill it
      const f = Math.min((0.9 * stage.clientHeight) / needH, (0.92 * stage.clientWidth) / needW, cap / (s / s0));
      if (f < 1.1 && i === 0) return;
      if (Math.abs(f - 1) < 0.04) return;
      s *= Math.max(0.5, f > 1 ? Math.min(f, 1.5) : f);
      stage.style.setProperty("--s", String(s));
    }
  }

  function runFit() {
    for (const f of fitQueue) {
      const el = f.el;
      el.style.fontSize = "";
      const base = parseFloat(getComputedStyle(el).fontSize);
      let size = base;
      let guard = 0;
      while (el.scrollWidth > f.maxW && size > base * f.minScale && guard++ < 40) {
        size *= 0.95;
        el.style.fontSize = size + "px";
      }
    }
  }

  /* ---------- components ---------- */
  // Each builder returns { el, enter(tl, t, M, ctx) }.
  const C = {};
  // shared with the phase-2 modules (vt-info.js, vt-cartoon.js, vt-media.js), which load after this file and add components to C
  window.VTX = { C, h, rt, fit, svgIcon, MOTION, popIn: (...a) => popIn(...a), idle: (...a) => idle(...a) };

  function popIn(tl, el, t, M, extra) {
    tl.fromTo(
      el,
      Object.assign({ opacity: 0 }, M.from, extra && extra.from),
      Object.assign({ opacity: 1, y: 0, scale: 1, duration: M.dur, ease: M.ease }, extra && extra.to),
      t
    );
  }

  C.title = (d, ctx) => {
    const el = rt("div", "title", d.text);
    fit(el, ctx.maxW);
    return { el, enter: (tl, t, M) => popIn(tl, el, t, M) };
  };

  C.shape = (d, ctx) => {
    const wrap = h("div", "geometric-visual");
    const size = Math.min(ctx.maxW, 720) * (d.width || 0.65);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 240 160");
    svg.setAttribute("width", String(size));
    svg.setAttribute("height", String(size * 2 / 3));
    const kind = d.shape || "rectangle";
    const mark = document.createElementNS(svg.namespaceURI, kind === "circle" ? "circle" : kind === "triangle" ? "polygon" : "rect");
    const attrs = kind === "circle" ? {cx:120,cy:80,r:72} : kind === "triangle" ? {points:"120,8 232,152 8,152"}
      : kind === "line" ? {x:8,y:74,width:224,height:12,rx:6} : {x:8,y:8,width:224,height:144,rx:d.rounded === false ? 0 : 20};
    Object.entries(attrs).forEach(([k,v]) => mark.setAttribute(k,String(v)));
    mark.setAttribute("fill", /^#[0-9a-f]{6}$/i.test(d.color) ? d.color : "#6366f1");
    svg.appendChild(mark); wrap.appendChild(svg);
    if(d.label) wrap.appendChild(rt("div", "geometric-label", d.label));
    return {el:wrap, enter:(tl,t,M)=>popIn(tl,wrap,t,M)};
  };

  C.value_card = (d, ctx) => {
    const wrap = h("div", "vcard");
    const box = h("div", "vcard-box");
    const val = rt("span", "vcard-val", d.value);
    box.appendChild(val);
    wrap.appendChild(box);
    let lab = null;
    if (d.label) {
      lab = rt("div", "vcard-label", d.label);
      wrap.appendChild(lab);
    }
    fit(val, ctx.maxW - 160);
    const tilt = ctx.tilt;
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(box, { opacity: 0, y: -60, scale: 0.85, rotation: tilt - 9 }, { opacity: 1, y: 0, scale: 1, rotation: tilt, duration: M.dur + 0.1, ease: M.ease }, t);
        if (lab) tl.fromTo(lab, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: M.dur, ease: "power2.out" }, t + 0.22);
      },
    };
  };

  C.big_number = (d, ctx) => {
    const wrap = h("div", "bignum");
    const row = h("div", "bignum-row");
    const val = rt("span", "bignum-val", d.value);
    row.appendChild(val);
    if (d.unit) row.appendChild(rt("span", "bignum-unit", d.unit));
    const bar = h("div", "bignum-bar");
    wrap.appendChild(row);
    wrap.appendChild(bar);
    let lab = null;
    if (d.label) {
      lab = rt("div", "bignum-label", d.label);
      wrap.appendChild(lab);
    }
    fit(val, ctx.maxW - 100);
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(row, { opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1, duration: M.dur + 0.1, ease: "back.out(1.6)" }, t);
        tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.4, ease: "power3.out" }, t + 0.25);
        if (lab) tl.fromTo(lab, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: M.dur, ease: "power2.out" }, t + 0.3);
      },
      hideInit: [bar, lab],
    };
  };

  C.arrow = (d) => {
    const wrap = h("div", "arrow");
    const dir = d.direction || "down";
    const rot = { down: 0, right: -90, up: 180, left: 90 }[dir] || 0;
    const holder = h("div");
    holder.innerHTML =
      '<svg viewBox="0 0 120 150"><path class="shaft" d="M60 8 L60 128"/><path class="head" d="M20 92 L60 134 L100 92"/></svg>';
    holder.style.transform = "rotate(" + rot + "deg)";
    wrap.appendChild(holder);
    let lab = null;
    if (d.label) {
      lab = rt("div", "arrow-label", d.label);
      wrap.appendChild(lab);
    }
    const shaft = holder.querySelector(".shaft");
    const head = holder.querySelector(".head");
    return {
      el: wrap,
      enter(tl, t, M) {
        tl.fromTo(wrap, { opacity: 0 }, { opacity: 1, duration: 0.08 }, t);
        tl.fromTo(shaft, { strokeDasharray: 130, strokeDashoffset: 130 }, { strokeDashoffset: 0, duration: 0.32, ease: "power2.out" }, t);
        tl.fromTo(head, { strokeDasharray: 120, strokeDashoffset: 120 }, { strokeDashoffset: 0, duration: 0.22, ease: "power2.out" }, t + 0.26);
        if (lab) tl.fromTo(lab, { opacity: 0 }, { opacity: 1, duration: 0.25 }, t + 0.3);
      },
    };
  };

  C.icon_row = (d, ctx) => {
    const wrap = h("div", "iconrow");
    const items = h("div", "iconrow-items");
    const n = Math.max(1, Math.min(8, d.count || 1));
    const kids = [];
    for (let i = 0; i < n; i++) {
      let k;
      if (!d.icon || d.icon === "coin") k = h("div", "coin", d.symbol || ctx.currency);
      else {
        k = h("div", "ico");
        k.appendChild(svgIcon(ctx.D, d.icon));
      }
      items.appendChild(k);
      kids.push(k);
    }
    wrap.appendChild(items);
    let lab = null;
    if (d.label) {
      lab = rt("div", "iconrow-label", d.label);
      wrap.appendChild(lab);
    }
    return {
      el: wrap,
      enter(tl, t, M) {
        kids.forEach((k, i) => tl.fromTo(k, { opacity: 0, scale: 0.2, y: 30 }, { opacity: 1, scale: 1, y: 0, duration: M.dur, ease: "back.out(2)" }, t + i * M.stagger));
        if (lab) tl.fromTo(lab, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: M.dur, ease: "power2.out" }, t + kids.length * M.stagger * 0.7 + 0.1);
      },
    };
  };

  C.tag = (d, ctx) => {
    const el = rt("div", "tag", d.text);
    fit(el, ctx.maxW - 40);
    return {
      el,
      enter(tl, t, M) {
        tl.fromTo(el, { opacity: 0, scale: 0.4, rotation: -10 }, { opacity: 1, scale: 1, rotation: 2, duration: M.dur + 0.05, ease: "back.out(2.2)" }, t);
      },
    };
  };

  C.compare = (d, ctx) => {
    const wrap = h("div", "cmp-wrap");
    const cmp = h("div", "cmp");
    const side = (s, cls) => {
      const e = h("div", "cmp-side " + cls);
      if (s.title) e.appendChild(rt("div", "cmp-title", s.title));
      const v = rt("div", "cmp-val", s.value || "");
      e.appendChild(v);
      fit(v, ctx.a169 ? 360 : 380);
      return e;
    };
    const a = side(d.left || {}, "a");
    const b = side(d.right || {}, "b");
    const vs = h("div", "cmp-vs", "VS");
    cmp.appendChild(a);
    cmp.appendChild(vs);
    cmp.appendChild(b);
    wrap.appendChild(cmp);
    let verdict = null;
    if (d.verdict) {
      verdict = rt("div", "tag", d.verdict);
      fit(verdict, ctx.maxW - 40);
      wrap.appendChild(verdict);
    }
    return {
      el: wrap,
      enter(tl, t, M) {
        const dx = ctx.a169 ? 200 : 0;
        const dy = ctx.a169 ? 0 : 140;
        tl.fromTo(a, { opacity: 0, x: -dx, y: -dy }, { opacity: 1, x: 0, y: 0, duration: M.dur + 0.1, ease: M.ease }, t);
        tl.fromTo(b, { opacity: 0, x: dx, y: dy }, { opacity: 1, x: 0, y: 0, duration: M.dur + 0.1, ease: M.ease }, t + M.stagger);
        tl.fromTo(vs, { opacity: 0, scale: 0 }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(2.5)" }, t + M.stagger * 2);
        if (verdict) tl.fromTo(verdict, { opacity: 0, scale: 0.5 }, { opacity: 1, scale: 1, duration: M.dur, ease: "back.out(2)" }, t + M.stagger * 4);
      },
    };
  };

  C.list = (d) => {
    const wrap = h("div", "list");
    const rows = (d.items || []).slice(0, 4).map((txt, i) => {
      const r = h("div", "list-item");
      r.appendChild(h("div", "list-num", toBn(i + 1)));
      r.appendChild(rt("div", "list-text", txt));
      wrap.appendChild(r);
      return r;
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        rows.forEach((r, i) => tl.fromTo(r, { opacity: 0, x: -120 }, { opacity: 1, x: 0, duration: M.dur, ease: M.ease }, t + i * (M.stagger + 0.12)));
      },
    };
  };

  C.equation = (d) => {
    const wrap = h("div", "eq");
    const parts = (d.parts || []).map((p) => {
      const kind = p.kind || (/^[+\-−×÷=]$/.test(p.text) ? "op" : "val");
      const e = rt("div", "eq-part " + kind, p.text);
      wrap.appendChild(e);
      return e;
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        parts.forEach((e, i) => tl.fromTo(e, { opacity: 0, scale: 0.5, y: 30 }, { opacity: 1, scale: 1, y: 0, duration: M.dur, ease: "back.out(2)" }, t + i * (M.stagger + 0.1)));
      },
    };
  };

  C.quote = (d) => {
    const wrap = h("div", "quote");
    wrap.appendChild(h("div", "quote-mark", "“"));
    wrap.appendChild(rt("div", "quote-text", d.text));
    if (d.by) wrap.appendChild(rt("div", "quote-by", "— " + d.by));
    return { el: wrap, enter: (tl, t, M) => popIn(tl, wrap, t, M) };
  };

  C.bar_chart = (d) => {
    const wrap = h("div", "bars");
    const bars = (d.bars || []).slice(0, 5);
    const max = Math.max(1, ...bars.map((b) => Number(b.value) || 0));
    const cols = bars.map((b) => {
      const col = h("div", "bar-col");
      const val = rt("div", "bar-val", b.display != null ? b.display : String(b.value));
      const track = h("div", "bar-track");
      const bar = h("div", "bar");
      bar.style.height = Math.max(4, ((Number(b.value) || 0) / max) * 100) + "%";
      track.appendChild(bar);
      col.appendChild(val);
      col.appendChild(track);
      const label = rt("div", "bar-label", b.label || "");
      col.appendChild(label);
      wrap.appendChild(col);
      return { col, bar, val, label };
    });
    return {
      el: wrap,
      enter(tl, t, M) {
        cols.forEach((c, i) => {
          const at = t + i * M.stagger * 1.3;
          tl.fromTo(c.label, { opacity: 0 }, { opacity: 1, duration: M.dur }, at);              // the label comes with its bar, not before the chart
          tl.fromTo(c.bar, { scaleY: 0 }, { scaleY: 1, duration: M.dur + 0.15, ease: "power3.out" }, at);
          tl.fromTo(c.val, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: M.dur, ease: "power2.out" }, at + 0.25);
        });
      },
    };
  };

  C.icon = (d, ctx) => {
    const wrap = h("div", "iconbig");
    const badge = h("div", "iconbig-badge");
    badge.appendChild(svgIcon(ctx.D, d.name));
    wrap.appendChild(badge);
    let lab = null;
    if (d.label) {
      lab = rt("div", "iconbig-label", d.label);
      wrap.appendChild(lab);
    }
    return {
      el: wrap,
      enter(tl, t, M, c, sc) {
        tl.fromTo(badge, { opacity: 0, scale: 0.3, rotation: -25 }, { opacity: 1, scale: 1, rotation: 0, duration: M.dur + 0.1, ease: "back.out(2)" }, t);
        idle(tl, badge, t + M.dur + 0.4, sc ? sc.end : t + 3, 10, 1.3);
        if (lab) tl.fromTo(lab, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: M.dur, ease: "power2.out" }, t + 0.2);
      },
    };
  };


  /* Gentle continuous motion so a held scene never looks frozen. Finite repeats: the timeline stays seekable. */
  function idle(tl, el, t0, t1, amp, dur) {
    const span = t1 - t0 - 0.25;
    if (!isFinite(span) || span < dur * 2) return;
    let n = Math.max(2, Math.floor(span / dur));
    if (n % 2 === 1) n -= 1;
    tl.to(el, { y: -amp, rotation: amp * 0.2, duration: dur, ease: "sine.inOut", yoyo: true, repeat: n - 1 }, t0);
  }

  C.sticker = (d, ctx) => {
    const wrap = h("div", "sticker");
    const art = h("div", "sticker-art");
    art.innerHTML = (ctx.D.stickers && ctx.D.stickers[d.emoji]) || "";
    wrap.appendChild(art);
    let lab = null;
    if (d.label) {
      lab = rt("div", "sticker-label", d.label);
      fit(lab, ctx.maxW - 80);
      wrap.appendChild(lab);
    }
    return {
      el: wrap,
      enter(tl, t, M, c, sc) {
        tl.fromTo(art, { opacity: 0, scale: 0.2, rotation: -18 }, { opacity: 1, scale: 1, rotation: 0, duration: M.dur + 0.25, ease: "back.out(2.4)" }, t);
        if (lab) tl.fromTo(lab, { opacity: 0, y: 24, scale: 0.8 }, { opacity: 1, y: 0, scale: 1, duration: M.dur, ease: "back.out(2)" }, t + 0.25);
        idle(tl, art, t + M.dur + 0.35, sc ? sc.end : t + 3, 14, 1.1);
      },
    };
  };

  C.keyword = (d, ctx) => {
    const wrap = h("div", "kw kw-" + (d.style || "underline"));
    let vis = null;
    if (d.emoji && ctx.D.stickers && ctx.D.stickers[d.emoji]) {
      vis = h("div", "kw-art");
      vis.innerHTML = ctx.D.stickers[d.emoji];
    } else if (d.icon) {
      vis = h("div", "kw-icon");
      vis.appendChild(svgIcon(ctx.D, d.icon));
    }
    if (vis) wrap.appendChild(vis);
    const word = h("div", "kw-word");
    const txt = rt("span", "kw-text", d.text);
    const bar = h("i", "kw-bar");
    word.appendChild(bar);
    word.appendChild(txt);
    wrap.appendChild(word);
    fit(txt, ctx.maxW - 40);
    return {
      el: wrap,
      enter(tl, t, M, c, sc) {
        const lead = vis ? 0.18 : 0;
        if (vis) {
          tl.fromTo(vis, { opacity: 0, scale: 0.3, y: -30, rotation: -14 }, { opacity: 1, scale: 1, y: 0, rotation: 0, duration: M.dur + 0.2, ease: "back.out(2.2)" }, t);
          idle(tl, vis, t + M.dur + 0.4, sc ? sc.end : t + 3, 12, 1.2);
        }
        tl.fromTo(txt, { opacity: 0, scale: 0.6, y: 40 }, { opacity: 1, scale: 1, y: 0, duration: M.dur + 0.1, ease: "back.out(1.8)" }, t + lead);
        tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.45, ease: "power3.out" }, t + lead + 0.22);
      },
    };
  };

  /* ---------- scene tone: rotates the accent colours so neighbouring scenes feel different ---------- */
  function hueShift(hex, deg) {
    const m = /^#([0-9a-f]{6})$/i.exec(String(hex || "").trim());
    if (!m || !deg) return hex;
    const n = parseInt(m[1], 16);
    let r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
    let hh = 0, s = 0;
    if (mx !== mn) {
      const dd = mx - mn;
      s = l > 0.5 ? dd / (2 - mx - mn) : dd / (mx + mn);
      hh = mx === r ? (g - b) / dd + (g < b ? 6 : 0) : mx === g ? (b - r) / dd + 2 : (r - g) / dd + 4;
      hh /= 6;
    }
    hh = (hh + deg / 360 + 1) % 1;
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    const f = (t) => {
      t = (t + 1) % 1;
      return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p;
    };
    const to = (v) => Math.round(v * 255).toString(16).padStart(2, "0");
    return "#" + to(f(hh + 1 / 3)) + to(f(hh)) + to(f(hh - 1 / 3));
  }
  /* ---------- readable text colours: an accent used as TEXT is darkened (or lightened) until it reaches the contrast the size needs ---------- */
  function rgbOf(hex) {
    const m = /^#([0-9a-f]{6})$/i.exec(String(hex || "").trim());
    if (!m) return null;
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function lumOf(rgb) {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
  }
  function ratioOf(a, b) { const la = lumOf(a), lb = lumOf(b), hi = Math.max(la, lb), lo = Math.min(la, lb); return (hi + 0.05) / (lo + 0.05); }
  function readable(color, grounds, min) {
    const c = rgbOf(color);
    const gs = grounds.map(rgbOf).filter(Boolean);
    if (!c || !gs.length) return color;
    const worst = (x) => Math.min.apply(null, gs.map((g) => ratioOf(x, g)));
    if (worst(c) >= min) return color;
    const avgL = gs.reduce((t, g) => t + lumOf(g), 0) / gs.length;
    const target = avgL > 0.4 ? [0, 0, 0] : [255, 255, 255];                    // light ground: darken the accent; dark ground: lighten it
    for (let i = 1; i <= 20; i++) {
      const k = i / 20, x = c.map((v, j) => Math.round(v + (target[j] - v) * k));
      if (worst(x) >= min) return "#" + x.map((v) => v.toString(16).padStart(2, "0")).join("");
    }
    return "#" + target.map((v) => v.toString(16).padStart(2, "0")).join("");
  }
  function textAccent(theme, acc) { return readable(acc, [theme.color.bg, theme.color.card], 4.5); }
  function onAccent(acc) { const c = rgbOf(acc); return !c ? "#fff" : ratioOf(c, [0, 0, 0]) >= ratioOf(c, [255, 255, 255]) ? "#111111" : "#ffffff"; }     // the ink that reads best on a filled accent shape

  function applyTone(el, theme, tone) {
    const c = theme.color;
    let acc, acc2;
    if (c.palette && c.palette.length > 1) {
      acc = c.palette[tone % c.palette.length];
      acc2 = c.palette[(tone + 1) % c.palette.length];
    } else {
      const swap = tone % 2 === 1, shift = tone >= 2 ? 38 * Math.floor(tone / 2) : 0;
      acc = hueShift(swap ? c.accent2 : c.accent, shift);
      acc2 = hueShift(swap ? c.accent : c.accent2, shift);
    }
    el.style.setProperty("--accent", acc);
    el.style.setProperty("--accent2", acc2);
    el.style.setProperty("--accent-text", textAccent(theme, acc));
    el.style.setProperty("--accent2-text", textAccent(theme, acc2));
    el.style.setProperty("--accent-on", onAccent(acc));
  }

  /* ---------- scene transitions ---------- */
  const TRANS = { cut: 0, fade: 0.3, slide_up: 0.4, slide_left: 0.4, zoom: 0.35, wipe: 0.45, whip: 0.35 };

  function sceneIn(tl, el, kind, t, W, H, wipeEl) {
    const d = TRANS[kind] != null ? TRANS[kind] : 0.3;
    switch (kind) {
      case "cut":
        tl.set(el, { opacity: 1 }, t);
        break;
      case "slide_up":
        tl.fromTo(el, { opacity: 0, y: H * 0.1 }, { opacity: 1, y: 0, duration: d, ease: "power3.out" }, t);
        break;
      case "slide_left":
        tl.fromTo(el, { opacity: 0, x: W * 0.14 }, { opacity: 1, x: 0, duration: d, ease: "power3.out" }, t);
        break;
      case "zoom":
        tl.fromTo(el, { opacity: 0, scale: 0.86 }, { opacity: 1, scale: 1, duration: d, ease: "power3.out" }, t);
        break;
      case "whip":
        tl.fromTo(el, { opacity: 0, x: W * 0.7 }, { opacity: 1, x: 0, duration: d, ease: "power4.out" }, t);
        break;
      case "wipe":
        tl.fromTo(wipeEl, { x: -W * 1.02 }, { x: 0, duration: d * 0.5, ease: "power2.in" }, t);
        tl.set(el, { opacity: 1 }, t + d * 0.5);
        tl.to(wipeEl, { x: W * 1.02, duration: d * 0.5, ease: "power2.out" }, t + d * 0.5);
        break;
      default:
        tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: d, ease: "power1.out" }, t);
    }
    return d;
  }

  /* ---------- build ---------- */
  let tl = null;
  let D = null;
  const state = { playing: false, t0: 0, from: 0, raf: 0 };

  function cssFamily(list) {
    return (list || []).map((f) => "'" + f + "'").join(",") + ",sans-serif";
  }

  function applyTheme(root, theme, format) {
    const c = theme.color,
      f = theme.font,
      s = theme.shape,
      st = root.style;
    const a169 = format.aspect === "16:9";
    const vars = {
      "--bg": c.bg, "--ink": c.ink, "--muted": c.muted, "--accent": c.accent, "--accent2": c.accent2, "--accent-text": textAccent(theme, c.accent), "--accent2-text": textAccent(theme, c.accent2), "--accent-on": onAccent(c.accent),
      "--card": c.card, "--card-border": c.card_border, "--cap-bg": c.caption_bg, "--cap-ink": c.caption_ink,
      "--hl-bg": c.highlight_bg, "--hl-ink": c.highlight_ink, "--tag-bg": c.tag_bg || c.accent2, "--tag-ink": c.tag_ink || c.ink,
      "--arc": c.arc || "rgba(0,0,0,0.07)",
      "--font-head": cssFamily(f.headline), "--font-body": cssFamily(f.body), "--font-num": cssFamily(f.numeral || f.headline),
      "--font-caption": cssFamily(f.caption || f.body),
      "--radius": s.radius + "px", "--stroke": s.stroke + "px",
      "--sh-x": s.shadow.x + "px", "--sh-y": s.shadow.y + "px", "--sh-color": s.shadow.color, "--sh-blur": (s.shadow.blur || 0) + "px",
      "--head-weight": f.headline_weight || 800,
      "--cap-weight": (theme.caption && theme.caption.weight) || 800,
      "--cap-size": ((theme.caption && theme.caption.size) || 60) + "px",
      "--grain": (theme.background && theme.background.grain != null ? theme.background.grain : 0.35),
      "--s": a169 ? 1.0 : format.aspect === "1:1" ? 0.84 : 1,
    };
    const cb = theme.caption && theme.caption.safe_bottom;
    // 9:16 captions never sit lower than 420 px from the bottom: TikTok, Reels and Shorts put their own text and buttons there
    if (cb) vars["--cap-bottom"] = (a169 ? cb.landscape : format.aspect === "1:1" ? Math.min(cb.portrait, 130) : Math.max(cb.portrait, SAFE_PORTRAIT)) + "px";
    for (const k in vars) st.setProperty(k, String(vars[k]));
  }

  function svgEl(tag, attrs) {
    const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  /* Returns the animatable layers: [{el, kind}] (see animateBackground). */
  function buildBackground(root, theme, W, H) {
    const bg = h("div", "bg");
    const B = theme.background || {};
    const kind = B.kind || "flat";
    const c = theme.color;
    const k = B.pattern != null ? B.pattern : 0.5;
    const line = c.arc || "rgba(0,0,0,0.08)";
    const layers = [];
    const add = (el, how) => {
      bg.appendChild(el);
      layers.push({ el: el, kind: how });
      return el;
    };
    if (kind === "gradient") bg.style.background = "linear-gradient(160deg," + c.bg + "," + (c.bg2 || c.accent) + ")";
    if (kind === "grid") add(h("div", "bg-grid"), "pan");
    if (kind === "paper") bg.appendChild(h("div", "bg-grain"));
    if (kind === "dots") {
      const d = add(h("div", "bg-pat"), "pan");
      d.style.opacity = String(0.25 + k * 0.75);
      d.style.backgroundImage = "radial-gradient(" + line + " 22%, transparent 24%)";
      d.style.backgroundSize = "64px 64px";
    }
    if (kind === "stripes") {
      const d = add(h("div", "bg-pat"), "pan");
      d.style.opacity = String(0.25 + k * 0.75);
      d.style.backgroundImage = "repeating-linear-gradient(135deg," + line + " 0 14px, transparent 14px 56px)";
    }
    if (kind === "checks") {
      const d = add(h("div", "bg-pat"), "pan");
      d.style.opacity = String(0.25 + k * 0.75);
      d.style.backgroundImage = "conic-gradient(" + line + " 25%, transparent 0 50%, " + line + " 0 75%, transparent 0)";
      d.style.backgroundSize = "140px 140px";
    }
    if (kind === "waves") {
      const svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, class: "bg-pat" });
      const g = svgEl("g", {});
      for (let i = 0; i < 9; i++) {
        const y = (H / 8) * i, a = 34 + (i % 3) * 14, wl = 360 + (i % 4) * 90;
        let dd = "M -" + wl + " " + y;
        for (let x = -wl; x <= W + wl * 2; x += wl) dd += " q " + wl / 4 + " -" + a + " " + wl / 2 + " 0 t " + wl / 2 + " 0";
        g.appendChild(svgEl("path", { d: dd, fill: "none", stroke: line, "stroke-width": 3 + k * 4, opacity: 0.35 + k * 0.65 }));
      }
      svg.appendChild(g);
      add(svg, "sway");
    }
    if (kind === "rings") {
      const svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, class: "bg-pat" });
      const g = svgEl("g", { "transform-origin": W * 0.5 + "px " + H * 0.42 + "px" });
      for (let i = 1; i <= 9; i++) g.appendChild(svgEl("circle", { cx: W * 0.5, cy: H * 0.42, r: i * Math.max(W, H) * 0.075, fill: "none", stroke: line, "stroke-width": 3 + k * 3, opacity: 0.3 + k * 0.7 }));
      svg.appendChild(g);
      add(svg, "breathe");
    }
    if (kind === "mesh" || kind === "aurora") {
      const blobs = [[c.accent, 0.2, 0.15, 0.55], [c.accent2, 0.85, 0.5, 0.5], [c.bg2 || c.accent, 0.3, 0.9, 0.6]];
      if (kind === "mesh") bg.style.background = "radial-gradient(60% 45% at 20% 12%," + c.accent + "55, transparent 70%), radial-gradient(55% 40% at 88% 48%," + c.accent2 + "55, transparent 70%), radial-gradient(70% 50% at 30% 92%," + (c.bg2 || c.accent) + "55, transparent 70%)";
      else
        blobs.forEach((b) => {
          const d = add(h("div", "bg-blob"), "drift");
          const r = Math.max(W, H) * b[3];
          d.style.cssText = "width:" + r + "px;height:" + r + "px;left:" + (W * b[1] - r / 2) + "px;top:" + (H * b[2] - r / 2) + "px;background:" + b[0] + ";opacity:" + (0.25 + k * 0.45);
        });
    }
    if (B.arcs) {
      const mk = (size, x, y) => {
        const a = h("div", "bg-arc");
        a.style.cssText = "width:" + size + "px;height:" + size + "px;left:" + x + "px;top:" + y + "px";
        add(a, "spin");
      };
      mk(W * 0.9, W * 0.45, -H * 0.12);
      mk(W * 0.75, -W * 0.4, H * 0.62);
    }
    root.appendChild(bg);
    return layers;
  }

  /* An element that is simply there: every fade-in it just added to the timeline is replaced by its finished state. Long moves (camera, lips, idling)
     keep running, unmoved in time, and a moment the director chose (data "chosen") stays. Later than the scene's start it pops in at its time. */
  function settleEntrance(tl, known, at, sceneStart, holder) {
    tl.getChildren(false, true, false).forEach((tw) => {
      const from = tw.vars && tw.vars.startAt;
      if (known.has(tw) || !from || from.opacity !== 0 || tw.vars.data === "chosen" || tw.startTime() > at + 1.2) return;
      const done = {};
      Object.keys(from).forEach((k) => { if (k in tw.vars) done[k] = tw.vars[k]; });
      const targets = tw.targets();
      tw.kill();
      gsap.set(targets, done);
    });
    if (holder && at > sceneStart + 0.06) { gsap.set(holder, { visibility: "hidden" }); tl.set(holder, { visibility: "visible" }, at); }
  }

  /* Slow, loop-free motion placed on the paused timeline, so previews and renders show the same frame at the same time. */
  function animateBackground(tl, layers, theme, duration) {
    if (!theme.background || !theme.background.animated) return;
    layers.forEach((L, i) => {
      const dir = i % 2 ? -1 : 1;
      if (L.kind === "pan") tl.fromTo(L.el, { backgroundPosition: "0px 0px" }, { backgroundPosition: 180 * dir + "px 180px", duration: duration, ease: "none" }, 0);
      else if (L.kind === "sway") tl.fromTo(L.el, { x: -60 }, { x: 60, duration: duration, ease: "sine.inOut" }, 0);
      else if (L.kind === "breathe") tl.fromTo(L.el, { scale: 0.94 }, { scale: 1.1, duration: duration, ease: "sine.inOut" }, 0);
      else if (L.kind === "spin") tl.fromTo(L.el, { rotation: 0 }, { rotation: 40 * dir, duration: duration, ease: "none" }, 0);
      else if (L.kind === "drift") tl.fromTo(L.el, { x: -120 * dir, y: -80 }, { x: 140 * dir, y: 100, duration: duration, ease: "sine.inOut" }, 0);
    });
  }

  function arrange(stage, wrappers, layout, a169) {
    const n = wrappers.length;
    const mk = (items) => {
      const g = h("div", "grp");
      items.forEach((w) => g.appendChild(w));
      return g;
    };
    if (n === 0) return;
    if (layout === "grid" || layout === "side" || layout === "lower" || layout === "upper") {      // phase-2 layouts: one group, arranged by CSS
      stage.appendChild(mk(wrappers));
      return;
    }
    if (a169) {
      if (n === 1) {
        stage.classList.add("single");
        stage.appendChild(mk(wrappers));
      } else if (layout === "split") {
        const k = Math.ceil(n / 2);
        stage.appendChild(mk(wrappers.slice(0, k)));
        stage.appendChild(mk(wrappers.slice(k)));
      } else {
        stage.appendChild(mk(wrappers.slice(0, 1)));
        stage.appendChild(mk(wrappers.slice(1)));
      }
    } else if (layout === "split" && n > 1) {
      const k = Math.ceil(n / 2);
      stage.appendChild(mk(wrappers.slice(0, k)));
      stage.appendChild(mk(wrappers.slice(k)));
    } else {
      stage.appendChild(mk(wrappers));
    }
  }

  function build(data) {
    (window.VTX.worldDisposers||[]).forEach(dispose=>dispose());window.VTX.worldDisposers=[];
    D = data;
    window.VTX.lateLooks = [];                                 // corner-pin warps wait for the fonts (their corners are in pixels of the box)
    window.__guard = [];                                       // what the layout guard did or would do, scene by scene (the stick scenes add their cut props while they draw)
    window.__guardDone = false;
    const fmt = D.format;
    const W = fmt.width,
      H = fmt.height;
    const a169 = fmt.aspect === "16:9";
    const root = document.getElementById("root");
    root.innerHTML = "";
    fitQueue.length = 0;
    if (window.VTX) { window.VTX.videos = []; window.VTX.nextVideoId = 0; window.VTX.inkRanges = []; window.VTX.stickState = {}; }
    root.className = a169 ? "a169" : fmt.aspect === "1:1" ? "a916 a11" : "a916";           // a square is a short portrait: same arrangement, smaller stage
    root.style.width = W + "px";
    root.style.height = H + "px";
    root.setAttribute("data-width", W);
    root.setAttribute("data-height", H);
    root.setAttribute("data-duration", D.duration);
    applyTheme(root, D.theme, fmt);
    const bgLayers = buildBackground(root, D.theme, W, H);

    const M = MOTION[(D.theme.motion && D.theme.motion.preset) || "snappy"] || MOTION.snappy;
    if (tl) tl.kill();
    tl = gsap.timeline({ paused: true });
    animateBackground(tl, bgLayers, D.theme, D.duration);

    const scenesLayer = h("div", "layer");
    root.appendChild(scenesLayer);
    const wipe = h("div", "wipe");

    const ctxBase = {
      D,
      a169,
      currency: (D.theme.currency || "৳"),
      tilt: (D.theme.shape && D.theme.shape.card_tilt) || 0,
    };

    const flowInfo = [];
    const freeVisuals = [];
    const freeActors = [];
    D.scenes.forEach((sc, si) => {
      const el = h("div", "scene");
      el.setAttribute("data-scene", sc.src || sc.id);          // a page of a scene answers to the scene the editor knows
      if (sc.tone) applyTone(el, D.theme, sc.tone);
      const stage = h("div", "stage " + (sc.layout || "stack"));
      if (sc.archetype) stage.setAttribute("data-arch", sc.archetype);
      if (sc.stage) {                                // a free rectangle chosen so that nothing sits on a person (vt/people.py): x, y, w, h as fractions of the frame
        const st = stage.style;
        st.left = Math.round(sc.stage[0] * W) + "px";
        st.top = Math.round(sc.stage[1] * H) + "px";
        st.width = Math.round(sc.stage[2] * W) + "px";
        st.height = Math.round(sc.stage[3] * H) + "px";
        st.right = "auto";
        st.bottom = "auto";
      }
      el.appendChild(stage);
      scenesLayer.appendChild(el);
      if (sc.archetype === "reel") el.classList.add("arch-reel");          // the reel look: one design for every scene (labels match the captions)
      if (sc.backdrop && window.VTX.backdrop) window.VTX.backdrop(el, sc, tl, D);
      if (sc.story && window.VTX.story) window.VTX.story(el, sc, tl, D);          // Cartoon 2: the story engine draws the whole frame (vt-story.js)
      if (sc.story_overlay && window.VTX.story)                                      // Cartoon 1 with story-engine extras drawn on top at their words
        window.VTX.story(el, { ...sc, story: { bg: { type: "plain", color: "transparent" }, items: sc.story_overlay, push: 0, tag: "" } }, tl, D, true);
      if (sc.stick && window.VTX.stick) {
        if(sc.stick.actions.some(a=>a._timed)) freeActors.push(sc);
        else window.VTX.stick(el, sc, tl, D);
      }

      const nEl = sc.elements.length;
      const wrappers = [];
      const jobs = [];
      flowInfo.push({ stage, jobs, sc });
      sc.elements.forEach((e, i) => {
        if(e.free) { freeVisuals.push({e, sc, i}); return; }
        const b = C[e.type];
        if (!b) return;
        const ctx = Object.assign({}, ctxBase, { maxW: a169 ? (nEl > 1 ? 740 : 1500) : 940 });
        const inst = b(e, ctx);
        const w = h("div", "el el-" + e.type);
        if(e.text_style) w.classList.add("text-look-"+e.text_style);
        if(e.ink) w.style.setProperty("--letter-ink",e.ink);
        if(e.letter_spacing) w.style.letterSpacing=e.letter_spacing+"em";
        w.setAttribute("data-el", String(e._i != null ? e._i : i));
        w.appendChild(inst.el);
        if(inst.backdrop) {
          w.style.cssText="position:absolute;inset:0;max-width:none";
          el.insertBefore(w,stage);
        } else {
          if (sc.layout === "hero" && i === 0) w.style.transform = "scale(1.18)";
          wrappers.push(w);
        }
        jobs.push({ inst, e, w });
      });
      arrange(stage, wrappers, sc.layout || "stack", a169);

      // scene visibility + transition
      const kind = sc.transition_in || "cut";
      const first = si === 0;
      let tdur = 0, own = null;
      if (first) tl.set(el, { opacity: 1 }, 0);
      else {
        const wipeEl = kind === "wipe" ? wipe : null;
        own = sc.tx && window.VTX.motionTrans ? window.VTX.motionTrans(sc.tx, tl, el, scenesLayer.children[si - 1], sc.start, W, H, si, sc.id) : null;   // a shot recipe (vt-motion.js)
        tdur = own != null ? own : sceneIn(tl, el, kind, sc.start, W, H, wipeEl);
      }
      // previous scene fades out while the new one comes in
      if (si > 0 && own != null) {                // the recipe animates the old scene itself: hide it only once the recipe is over (else its end state wins)
        const prev = scenesLayer.children[si - 1];
        tl.set(prev, { opacity: 0 }, sc.start + Math.max(own, 0.6) + 0.02);
      } else if (si > 0) {
        const prev = scenesLayer.children[si - 1];
        const od = Math.max(0.01, tdur * 0.8);
        if (kind === "wipe") tl.set(prev, { opacity: 0 }, sc.start + tdur * 0.5);
        else if (tdur === 0) tl.set(prev, { opacity: 0 }, sc.start);
        else tl.to(prev, { opacity: 0, duration: od, ease: "power1.in" }, sc.start);
      }

      jobs.forEach(({ inst, e, w }, ji) => {
        const at = Math.min(Math.max(e.at, sc.start + (first ? 0 : 0.05)), Math.max(sc.start, sc.end - 0.25));
        w._at = at;
        const customEntrance=e.entrance && e.entrance!=="auto";
        const opening = si === 0 && ji === 0 && at <= sc.start + 0.8;
        if (e.entrance === "none" || (opening && !customEntrance && e.type === "cartoon")) {
          // already in place. A cartoon opens this way too: skipping ahead in its timeline (below) would put its lips and pose cues ahead of the voice
          const known = new Set(tl.getChildren(false, true, false));
          inst.enter(tl, at, M, ctxBase, sc);
          settleEntrance(tl, known, at, sc.start, w);
        } else if (opening && !customEntrance) {
          // the very first frame is the thumbnail feeds show and the first thing a scroller sees: the opening picture is already in place at 0 s
          const sub = gsap.timeline({ paused: true });
          inst.enter(sub, 0, M, ctxBase, sc);
          const d = sub.duration();
          const lead = Math.min(0.7, d * 0.9);
          if (d > lead) tl.add(sub.tweenFromTo(lead, d, { ease: "none" }), 0);
          else { sub.progress(1); }
        } else inst.enter(tl, at, M, ctxBase, sc);
        const fx=customEntrance?(e.entrance==="none"?null:e.entrance):e.fx;
        if (fx && window.VTX.motionEnter && (customEntrance || !(si === 0 && ji === 0 && at <= sc.start + 0.8))) window.VTX.motionEnter(fx, tl, w, at, sc.id + ":" + ji);
        if (inst.hideInit) inst.hideInit.forEach((x) => x && gsap.set(x, { opacity: 0 }));
        if (typeof e.until === "number" && e.until < sc.end - 0.3) {
          // its line is over: it leaves and the picture behind gets the frame back (pacing.dwell; it used to stay until the scene ended)
          const out = Math.max(at + 0.6, e.until);
          // autoAlpha: hidden at the end of the fade, shown again when the playhead goes back. A separate set(visibility: hidden) after it was not
          // undone when HyperFrames seeks back from a later frame, so the card stayed hidden before its exit too (test_handback, 2026-11-24)
          tl.to(w, { autoAlpha: 0, scale: 0.96, duration: 0.28, ease: "power2.in" }, out);
        }
      });
      if (sc.moves && window.VTX.motionScene) window.VTX.motionScene(sc.moves, tl, el, sc, W, H);         // opening, outro, camera and rhythm moves
    });
    scenesLayer.appendChild(wipe);

    freeActors.forEach(sc=>{
      const host=h("div","scene");host.setAttribute("data-scene",sc.src||sc.id);host.style.pointerEvents="none";
      const start=Math.min(sc.start,...sc.stick.actions.filter(a=>a._timed).map(a=>a.start));
      const end=Math.min(D.duration,Math.max(sc.end,...sc.stick.actions.filter(a=>a._timed).map(a=>a.end)));
      root.appendChild(host);
      window.VTX.stick(host,{...sc,start,end,stick:{...sc.stick,t0:start,t1:end}},tl,D);
      tl.set(host,{opacity:1},start);tl.set(host,{opacity:0},end);
    });
    freeVisuals.forEach(({e, sc, i}) => {
      const build = C[e.type]; if(!build) return;
      const host = h("div", "scene vt-free-visual");
      host.setAttribute("data-scene", sc.src || sc.id);
      host.style.cssText = "opacity:1;pointer-events:none";
      if(sc.tone) applyTone(host, D.theme, sc.tone);
      const position = h("div", "free-position");
      position.style.cssText = "position:absolute;left:" + ((e.x ?? .5)*100) + "%;top:" + ((e.y ?? .45)*100) + "%;width:max-content;max-width:90%";
      const shape = h("div", "free-shape");                      // what the crop and the corner-pin warp act on; invisible (no box) when neither is used
      shape.style.display = "contents";
      window.VTX.look(position, shape, e, W, H);               // size, stretch, rotation, slant, flip, tilt, pivot, opacity, blur, blend, crop, warp (vt-keyframes.js)
      const wrap = h("div", "el el-"+e.type);
      if(e.text_style) wrap.classList.add("text-look-"+e.text_style);
      if(e.ink) wrap.style.setProperty("--letter-ink",e.ink);
      if(e.letter_spacing) wrap.style.letterSpacing=e.letter_spacing+"em";
      wrap.setAttribute("data-el", String(e._i ?? i));
      wrap.style.pointerEvents = "auto";
      const inst = build(e, {...ctxBase, maxW:a169 ? 1500 : 940});
      if(inst.backdrop) {
        position.style.maxWidth="none";
        position.style.width=W+"px";
        position.style.height=H+"px";
        position.style.top=((e.y ?? .5)*100)+"%";
      }
      wrap.appendChild(inst.el); shape.appendChild(wrap); position.appendChild(shape); host.appendChild(position); root.appendChild(host);
      const at=Math.max(0,e.at), end=Math.min(D.duration,e.until ?? D.duration);
      gsap.set(host,{visibility:"hidden"});
      tl.set(host,{visibility:"visible"},at);
      const known=new Set(tl.getChildren(false,true,false));
      inst.enter(tl,at,M,ctxBase,{...sc,start:at,end});
      if(e.entrance==="none" || ((!e.entrance || e.entrance==="auto") && e.type==="cartoon" && sc===D.scenes[0] && at<=sc.start+.8)) settleEntrance(tl,known,at,at,null);
      if(e.entrance && !["auto","none"].includes(e.entrance)) window.VTX.motionEnter(e.entrance,tl,wrap,at,sc.id+":"+i);
      if(e.keyframes?.length) window.VTX.keyframes(tl,position,e.keyframes,W,H,{x:!!(e.transform&&e.transform.flip_x),y:!!(e.transform&&e.transform.flip_y)});
      if(inst.hideInit) inst.hideInit.forEach(x=>x && gsap.set(x,{opacity:0}));
      tl.set(host,{visibility:"hidden"},end);
    });
    /* what the editor's hand needs while it drags (Studio: Preview.tsx):
       natural(scene, index): how big an element that automatic layout placed would be once it is hand-placed at size 1, so taking it over keeps its size;
       look(scene, index, e): move a hand-placed element to the new position, size and turn at once, without building the whole video again. */
    window.__vtFree = {
      natural: (sceneKey, index) => {
        // A source scene can be split across pages. The selected visual may be on a later page.
        const sc = D.scenes.find((s) => (s.src || s.id) === sceneKey && (s.elements || []).some((x, k) => (x._i ?? k) === index));
        const e = sc && (sc.elements || []).find((x, k) => (x._i ?? k) === index);
        const build = e && C[e.type];
        if (!build) return null;
        const host = h("div", "scene vt-free-visual");
        host.style.cssText = "opacity:1;pointer-events:none;visibility:hidden";
        if (sc.tone) applyTone(host, D.theme, sc.tone);
        const position = h("div", "free-position");
        position.style.cssText = "position:absolute;left:50%;top:50%;width:max-content;max-width:90%";
        const wrap = h("div", "el el-" + e.type);
        const inst = build(e, { ...ctxBase, maxW: a169 ? 1500 : 940 });
        wrap.appendChild(inst.el); position.appendChild(wrap); host.appendChild(position); root.appendChild(host);
        const b = wrap.getBoundingClientRect();
        host.remove();
        return b.width ? [b.width, b.height] : null;
      },
      look: (sceneKey, index, e) => {
        const el = document.querySelector('.scene[data-scene="' + sceneKey + '"] .el[data-el="' + index + '"]');
        const shape = el && el.closest(".free-shape");
        if (!shape || (e.keyframes && e.keyframes.length)) return false;          // not hand-placed yet, or animated: the caller builds the video again
        const position = shape.parentElement;
        position.style.left = ((e.x ?? .5) * 100) + "%";
        position.style.top = ((e.y ?? .45) * 100) + "%";
        window.VTX.look(position, shape, e, W, H);
        return true;
      },
    };
    if (D.layers && D.layers.length && window.VTX.layers) window.VTX.layers(root, tl, D, W, H);
    if (D.captions_enabled !== false) buildCaptions(root, tl, D, M, a169);

    // make the timeline exactly as long as the video
    tl.set(root, { opacity: 1 }, Math.max(0, D.duration - 0.001));

    window.__timelines = window.__timelines || {};
    window.__timelines[D.comp_id || "root"] = tl;
    tl.time(0);
    clipToWindow(root, D);



  /* C11: one stretch of the video (window.__VT_WINDOW = {start, end}), so the renderer draws only the designed scenes of a long talk and the rest
     is cut straight from the recording. The page lasts end - start; the whole timeline is played through a tween from start to end, and every
     timed media element is moved by -start (trimmed at the edges), so frame t of this page is frame start + t of the whole video. */
  function clipToWindow(root, D) {
    // C11: one or more stretches of the video played back to back (window.__VT_WINDOWS = [{start, end}, ...], or window.__VT_WINDOW = {start, end}),
    // so the renderer starts once for every designed stretch of a long talk. Timed media get one copy per stretch they show in.
    const ws = (window.__VT_WINDOWS || (window.__VT_WINDOW ? [window.__VT_WINDOW] : [])).filter((w) => w && w.end > w.start);
    window.__vtClipped = null;
    if (!ws.length) return;
    const offs = []; let total = 0;
    for (const w of ws) { offs.push(total); total += w.end - w.start; }
    root.setAttribute("data-duration", String(total));
    root.querySelectorAll("[data-start]").forEach((el) => {
      if (el === root) return;
      const s0 = +el.getAttribute("data-start"), d0 = +(el.getAttribute("data-duration") || 0), m0 = +(el.getAttribute("data-media-start") || 0);
      const parts = [];
      ws.forEach((w, k) => {
        const a = Math.max(s0, w.start), b = Math.min(s0 + d0, w.end);
        if (b - a > 0.001) parts.push({ s: offs[k] + (a - w.start), d: b - a, ms: m0 + (a - s0) });
      });
      if (!parts.length) { el.remove(); return; }
      parts.forEach((part, i) => {
        const node = i === 0 ? el : el.cloneNode(true);
        node.setAttribute("data-start", String(part.s));
        node.setAttribute("data-duration", String(part.d));
        if (el.hasAttribute("data-media-start")) node.setAttribute("data-media-start", String(part.ms));
        if (i > 0) el.parentNode.insertBefore(node, el.nextSibling);
      });
    });
    try {
      const outer = gsap.timeline({ paused: true });
      ws.forEach((w, k) => outer.add(tl.tweenFromTo(w.start, w.end, { duration: w.end - w.start, ease: "none", immediateRender: false }), offs[k]));
      outer.set(root, { opacity: 1 }, Math.max(0, total - 0.001));
      window.__timelines[D.comp_id || "root"] = outer;
      window.__vtClipped = outer;                                   // the page registers window.__vt.timeline() again after the build
      outer.time(0);
    } catch (e) { console.error("clipToWindow", e && e.stack || e); }
  }

    /* ---------- no empty frame: an element that has not entered yet takes no room ----------
       Layouts reserve a slot for every element of a scene, so the first element sat in the left half for seconds while the right half stayed empty until its word was spoken.
       Here the slots are worked out for the elements that are on screen at each moment: the first one starts centred and larger, and when the next one enters the ones already
       there glide to their new places (a pair of tweens on the same seekable timeline, so frame-exact rendering still works). */
    function flowStages() {
      flowInfo.forEach(({ stage, jobs }) => {
        const items = jobs.filter(j=>!j.inst.backdrop).map((j) => ({ w: j.w, at: j.w._at })).filter((x) => x.w && x.w.isConnected && typeof x.at === "number");
        const times = Array.from(new Set(items.map((x) => Math.round(x.at * 1000) / 1000))).sort((a, b) => a - b);
        if (items.length === 1) {                                                // one element in the whole scene: let it fill its stage instead of sitting small in a big frame
          const w = items[0].w, base = gsap.getProperty(w, "scale") || 1;
          const wide = stage.clientWidth > stage.clientHeight;
          const k = Math.min(1.6, (stage.clientHeight * 0.7) / Math.max(1, w.offsetHeight), (stage.clientWidth * (wide ? 0.5 : 0.8)) / Math.max(1, w.offsetWidth));
          if (k > 1.15) tl.set(w, { scale: base * k }, 0);
          return;
        }
        if (items.length < 2 || times.length < 2) return;                        // everything enters together: nothing to re-flow
        const groups = Array.from(stage.querySelectorAll(":scope > .grp"));
        const disp = new Map(items.map((x) => [x.w, getComputedStyle(x.w).display]));
        const gdisp = new Map(groups.map((g) => [g, getComputedStyle(g).display]));
        const here = (x, T) => x.at <= T + 1e-6;
        const setPhase = (T) => {
          items.forEach((x) => { x.w.style.display = here(x, T) ? disp.get(x.w) : "none"; });
          groups.forEach((g) => { g.style.display = Array.from(g.children).some((c) => c.style.display !== "none") ? gdisp.get(g) : "none"; });
        };
        const pos = (w) => ({ x: w.offsetLeft, y: w.offsetTop, w: w.offsetWidth, h: w.offsetHeight });
        const P = times.map((T) => {
          setPhase(T);
          const m = new Map();
          items.forEach((x) => here(x, T) && m.set(x.w, pos(x.w)));
          return m;
        });
        items.forEach((x) => { x.w.style.display = ""; });
        groups.forEach((g) => { g.style.display = ""; });
        // the starting state: only what enters first is there
        groups.forEach((g) => {
          const kids = Array.from(g.children);
          const first = kids.map((c) => items.find((x) => x.w === c)).filter(Boolean).map((x) => x.at);
          if (first.length && Math.min.apply(null, first) > times[0] + 1e-6) tl.set(g, { display: "none" }, 0);
        });
        items.forEach((x) => { if (x.at > times[0] + 1e-6) tl.set(x.w, { display: "none" }, 0); });
        times.forEach((T, j) => {
          if (j === 0) return;
          groups.forEach((g) => {
            const kids = Array.from(g.children).map((c) => items.find((x) => x.w === c)).filter(Boolean);
            if (kids.length && Math.abs(Math.min.apply(null, kids.map((x) => x.at)) - T) < 1e-3) tl.set(g, { display: gdisp.get(g) }, T);
          });
          items.forEach((x) => {
            if (Math.abs(x.at - T) < 1e-3) { tl.set(x.w, { display: disp.get(x.w) }, T); return; }
            if (x.at > T) return;
            const a = P[j - 1].get(x.w), b = P[j].get(x.w);
            if (!a || !b) return;
            const dx = a.x - b.x, dy = a.y - b.y;
            if (Math.abs(dx) + Math.abs(dy) > 2) tl.fromTo(x.w, { x: dx, y: dy }, { x: 0, y: 0, duration: 0.4, ease: "power2.out", immediateRender: false }, T);
          });
        });
        // alone on screen: larger (up to 1.7x), settling to its normal size when the next one arrives
        const alone = items.filter((x) => here(x, times[0]));
        if (alone.length === 1) {
          const w = alone[0].w, base = gsap.getProperty(w, "scale") || 1, r = P[0].get(w);
          const k = Math.min(1.7, (stage.clientHeight * 0.78) / Math.max(1, r.h), (stage.clientWidth * 0.5) / Math.max(1, r.w));
          if (k > 1.15) {
            tl.set(w, { scale: base * k }, 0);
            tl.to(w, { scale: base, duration: 0.4, ease: "power2.out" }, times[1]);
          }
        }
      });
    }

    let flowed = false;
    const finish = () => { runFit(); shrinkStages(); if (!flowed) { flowed = true; const cur = tl.time(); tl.time(0); flowStages(); tl.time(cur); } guardLayout(scenesLayer, W, H, tl, D); (window.VTX.lateLooks || []).forEach((f) => f()); };
    runFit();
    shrinkStages();
    if (document.fonts && document.fonts.status === "loaded") finish();
    else if (document.fonts && document.fonts.ready) document.fonts.ready.then(finish);
    else finish();
    return tl;
  }

  /* ---------- layout guard: what a careful editor checks on every frame before it ships ----------
     Measured on the laid-out page (offset geometry, so the entrance animations do not disturb it), per scene:
     1. cut off: an element more than 12 % outside the frame is shrunk to fit; an optional one (tag, sticker, icon) that would still
        be cut is dropped rather than shown half;
     2. overlap: two elements whose boxes overlap by more than 18 % of the smaller one (intersection over the smaller area): the one
        of lower rank goes (title > number card > keyword > quote > picture > tag);
     3. too small to read: a text element whose letters are under 26 px on the 1080-wide frame is dropped.
     Every decision is kept in window.__guard for the QA scripts and the call log (Details, Problems).
     A dropped element gets the class vt-gone (display none !important) and a shrunk one the CSS scale property: the timeline writes display when an element arrives and transform on every frame,
     which used to undo an inline display:none and a scale appended to transform.
     A scene an AI directed (scene.directed, set by the composer) is only measured: nothing is shrunk, hidden or dropped. The same findings are kept in
     window.__guard as "would-shrink", "would-drop" or "left", and frame-facts.mjs tells the director, who fixes its own plan (plan decision 1). */
  const RANK = { title: 9, value_card: 8, big_number: 8, stat_row: 8, price_tag: 8, bar_chart: 8, keyword: 7, question: 7, quote: 6, list: 6, sticker: 4, icon: 4, tag: 2 };
  const OPTIONAL = new Set(["tag", "sticker", "icon"]);
  function boxOf(node, upTo) {                     // the box as it is on screen (after re-flowing and entrances), in frame pixels
    const r = node.getBoundingClientRect(), f = upTo.getBoundingClientRect(), k = f.width ? upTo.offsetWidth / f.width : 1;
    const sc = parseFloat(getComputedStyle(node).getPropertyValue("--s")) || 1;
    return { x: (r.left - f.left) * k, y: (r.top - f.top) * k, w: r.width * k, h: r.height * k, s: sc };
  }
  /* Layout's job, before anything is judged, across the frame: what a group holds can be wider than the stage (a long word cannot wrap; a grid column grows to hold its widest
     item). The group is scaled down together, about the middle of what it holds, and moved back inside the stage. Nothing is hidden or dropped. The CSS scale and translate properties
     are used because the timeline rewrites transform and display on every frame, but not these. Measured on the scene's last frame, when everything has arrived. (Up and down is
     shrinkStages' job: it scales the whole stage.) */
  function fitGroups(stage) {
    const room = stage.getBoundingClientRect();
    if (!room.width) return;
    const alone = stage.querySelectorAll(":scope > .grp").length === 1;
    stage.querySelectorAll(":scope > .grp").forEach((g) => {
      ["scale", "translate", "transform-origin"].forEach((p) => g.style.removeProperty(p));
      const rs = Array.from(g.children).filter((c) => getComputedStyle(c).display !== "none").map((c) => {
        const r = c.getBoundingClientRect(), inner = c.firstElementChild, ir = inner ? inner.getBoundingClientRect() : r;     // what an element holds can reach past its own box
        return { left: Math.min(r.left, ir.left), top: Math.min(r.top, ir.top), right: Math.max(r.right, ir.left + (inner ? inner.scrollWidth : 0)), bottom: Math.max(r.bottom, ir.bottom) };
      }).filter((r) => r.right > r.left && r.bottom > r.top);
      if (!rs.length) return;
      const L = Math.min(...rs.map((r) => r.left)), R = Math.max(...rs.map((r) => r.right)), T = Math.min(...rs.map((r) => r.top)), B = Math.max(...rs.map((r) => r.bottom));
      const gr = g.getBoundingClientRect();
      if (L >= room.left - 2 && R <= room.right + 2) return;                                                               // it fits the stage (a group may reach into its neighbour's empty room)
      const k = Math.max(0.45, Math.min(1, room.width / (R - L)));                                                         // not below 45 %: smaller is not a fit, it is unreadable (the facts tell the director)
      const cx = (L + R) / 2, cy = (T + B) / 2;
      const dx = alone ? Math.max(0, room.left - (cx - (cx - L) * k)) - Math.max(0, cx + (R - cx) * k - room.right) : 0;          // a group with neighbours only shrinks: moving it could put it on one
      g.style.transformOrigin = (cx - gr.left).toFixed(1) + "px " + (cy - gr.top).toFixed(1) + "px";
      g.style.scale = k.toFixed(4);
      g.style.translate = dx.toFixed(1) + "px 0px";
    });
  }
  function guardLayout(layer, W, H, tl, D) {
    const log = (window.__guard = window.__guard || []);
    const keep = tl ? tl.time() : 0;
    Array.from(layer.querySelectorAll(":scope > .scene")).forEach((scene, si) => {
      const sd = D && D.scenes[si];
      if(sd && sd.edited) return;
      /* A scene an AI directed (sd.directed) keeps everything the director put on it: nothing is shrunk, hidden or dropped. What the guard WOULD have done is recorded
         ("would-shrink", "would-drop", "left") so the facts can tell the director, which fixes it itself (plan decision 1). Plans made by the rules keep the guard. */
      const directed = !!(sd && sd.directed), id = scene.dataset.scene;
      const said = (it, rule, fix, more) => { if (log.filter((g) => g.scene === id).length < 24) log.push({ scene: id, el: it.w.getAttribute("data-el"), type: it.type, rule, fix, ...(directed ? { directed: true } : {}), ...(more || {}) }); };
      if (tl && sd) tl.time(Math.max(sd.start, sd.end - 0.05));          // the scene's last frame: everything has entered and moved to its place
      scene.querySelectorAll(".stage").forEach(fitGroups);                // layout's job first (directed or not): fit by scaling together
      const els = Array.from(scene.querySelectorAll(".stage .el")).filter((w) => w.style.display !== "none" && !w.classList.contains("vt-gone"));
      const items = els.map((w) => ({ w, type: (/el-(\w+)/.exec(w.className) || [])[1] || "", b: boxOf(w, scene) }));
      items.forEach((it) => {
        const { x, y, w, h } = it.b;
        if (!w || !h) return;
        const outside = (Math.max(0, -x) + Math.max(0, x + w - W)) / w + (Math.max(0, -y) + Math.max(0, y + h - H)) / h;
        if (outside > 0.12) {
          const k = Math.min(W / w, H / h) * 0.92;
          if (k < 1 && k > 0.55) {
            if (directed) said(it, "cut-off", "would-shrink");
            else { it.w.style.scale = k.toFixed(3); said(it, "cut-off", "shrunk"); }       // the CSS scale property: the timeline rewrites `transform` on every frame and would undo a scale put there
          } else if (OPTIONAL.has(it.type)) {
            if (directed) said(it, "cut-off", "would-drop");
            else { it.w.classList.add("vt-gone"); it.gone = true; said(it, "cut-off", "dropped"); }
          } else if (directed) said(it, "cut-off", "left");
        }
        const fs = Array.from(it.w.querySelectorAll("*")).filter((n) => n.childNodes.length && Array.from(n.childNodes).some((c) => c.nodeType === 3 && c.nodeValue.trim())).map((n) => parseFloat(getComputedStyle(n).fontSize) || 99);
        if (it.type === "tag" && fs.length && Math.max(...fs) * (it.b.s || 1) < 26) {          // only text-only labels: a sticker is its picture, a diagram keeps its small print
          if (directed) said(it, "too-small", "would-drop");
          else { it.w.classList.add("vt-gone"); it.gone = true; said(it, "too-small", "dropped"); }
        }
      });
      for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
        const a = items[i], b = items[j];
        if (a.gone || b.gone) continue;
        const ix = Math.max(0, Math.min(a.b.x + a.b.w, b.b.x + b.b.w) - Math.max(a.b.x, b.b.x));
        const iy = Math.max(0, Math.min(a.b.y + a.b.h, b.b.y + b.b.h) - Math.max(a.b.y, b.b.y));
        const small = Math.max(1, Math.min(a.b.w * a.b.h, b.b.w * b.b.h));
        if ((ix * iy) / small > 0.18) {
          const lose = (RANK[a.type] || 5) >= (RANK[b.type] || 5) ? b : a, win = lose === a ? b : a;
          if (directed) said(lose, "overlap", "would-drop", { with: win.w.getAttribute("data-el") });
          else { lose.w.classList.add("vt-gone"); lose.gone = true; said(lose, "overlap", "dropped", { with: win.w.getAttribute("data-el") }); }
        }
      }
    });
    if (tl) tl.time(keep);
    window.__guardDone = true;
  }

  function buildCaptions(root, tl, data, M, a169) {
    const theme = data.theme;
    const style = (theme.caption && theme.caption.style) || "box";
    const reveal = (theme.caption && theme.caption.reveal) || "line";
    const popInk = (theme.color && (theme.color.highlight_bg || theme.color.accent)) || "#ffd400";
    const layer = h("div", "cap-layer");
    const wrap = h("div", "cap-wrap");
    layer.appendChild(wrap);
    root.appendChild(layer);
    if ((style === "underline" || style === "none") && window.VTX && window.VTX.inkRanges) {
      const base = (theme.color && theme.color.caption_ink) || "#111";
      window.VTX.inkRanges.forEach((r) => {
        tl.set(layer, { "--cap-ink": r.ink === "light" ? "#ffffff" : "#111111" }, r.t0);
        tl.set(layer, { "--cap-ink": base }, r.t1);
      });
    }
    data.captions.forEach((c) => {
      const box = h("div", "cap cap-" + style);
      if (c.y != null) box.style.bottom = Math.round(data.format.height * (1 - c.y) - parseFloat(getComputedStyle(layer).bottom)) + "px";   // this scene's director chose the height
      const inner = h("div", "cap-inner");
      box.appendChild(inner);
      const spans = c.words.map((w) => {
        const s = h("span", "w" + (w.hl ? " hl" : ""));
        let pill = null;
        if (w.hl) {
          pill = h("span", "pill");
          s.appendChild(pill);
        }
        s.appendChild(rich(w.text));
        inner.appendChild(s);
        inner.appendChild(document.createTextNode(" "));
        return { s, pill, w };
      });
      wrap.appendChild(box);
      tl.fromTo(box, { opacity: 0, y: 24, scale: 0.94 }, { opacity: 1, y: 0, scale: 1, duration: 0.18, ease: "power2.out" }, c.start);
      tl.set(box, { opacity: 0 }, Math.max(c.start + 0.2, c.end));
      spans.forEach(({ s, pill, w }) => {
        if (reveal === "words" && (style === "box" || style === "pill")) {      // the box fits the words said so far, never an empty box waiting for the rest of the line
          const shown = getComputedStyle(s).display;
          gsap.set(s, { display: "none" });
          tl.set(s, { display: shown }, Math.max(c.start, w.start));
        }
        if (reveal === "words") tl.fromTo(s, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.12, ease: "power2.out" }, Math.max(c.start, w.start));
        if (style === "pop" || style === "word" || style === "keyword") {      // the word being said lights up and bounces, then settles back (keyword: only the key word grows)
          const t0 = Math.max(c.start, w.start - 0.02);
          tl.fromTo(s, { color: "#ffffff", scale: 1 }, { color: popInk, scale: style === "word" ? 1.22 : 1.14, duration: 0.08, ease: "power2.out" }, t0);
          tl.to(s, { color: w.hl ? popInk : "#ffffff", scale: 1, duration: 0.1, ease: "power1.out" }, Math.max(t0 + 0.09, w.end));
        }
        if (pill && style !== "pop" && style !== "word" && style !== "keyword") {
          tl.fromTo(pill, { opacity: 0, scale: 0.2 }, { opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2.4)" }, Math.max(c.start, w.start - 0.06));
          tl.fromTo(s, { scale: 1 }, { scale: 1.06, duration: 0.12, yoyo: true, repeat: 1, ease: "power1.inOut" }, Math.max(c.start, w.start));
        }
      });
    });
  }

  /* ---------- preview API (Studio) ---------- */
  function seek(t) {
    if (!tl) return;
    tl.time(Math.max(0, Math.min(D.duration, t)));
    if (window.VTX.syncVideos) window.VTX.syncVideos(tl.time());
  }
  function tick() {
    if (!state.playing) return;
    const t = state.from + (performance.now() - state.t0) / 1000;
    if (t >= D.duration) {
      seek(D.duration);
      state.playing = false;
      window.parent.postMessage({ vt: "ended" }, "*");
      return;
    }
    seek(t);
    window.parent.postMessage({ vt: "time", t }, "*");
    state.raf = requestAnimationFrame(tick);
  }
  function play(from) {
    state.from = from != null ? from : tl ? tl.time() : 0;
    state.t0 = performance.now();
    state.playing = true;
    cancelAnimationFrame(state.raf);
    state.raf = requestAnimationFrame(tick);
  }
  function pause() {
    state.playing = false;
    cancelAnimationFrame(state.raf);
  }
  window.addEventListener("message", (ev) => {
    const m = ev.data;
    if (!m || !m.vt) return;
    if (m.vt === "seek") {
      pause();
      seek(m.t);
    } else if (m.vt === "play") play(m.t);
    else if (m.vt === "pause") pause();
    else if (m.vt === "pick") {
      // the Studio asks "what is at this point?" (frame coordinates): the visible element and scene under it
      const hit = (document.elementsFromPoint(m.x, m.y) || []).find((n) => {
        const sc = n.closest && n.closest(".scene");
        return sc && parseFloat(getComputedStyle(sc).opacity) > 0.4;
      });
      const sc = hit && hit.closest(".scene");
      const el = hit && hit.closest(".el");
      window.parent.postMessage({ vt: "picked", scene: sc ? sc.getAttribute("data-scene") : null, index: el ? parseInt(el.getAttribute("data-el"), 10) : null }, "*");
    } else if (m.vt === "look") {                                                    // a hand is dragging a hand-placed element: only that element is updated
      const ok = !!(window.__vtFree && window.__vtFree.look(m.scene, m.index, m.el || {}));
      window.parent.postMessage({ vt: "looked", ok, scene: m.scene, index: m.index }, "*");
    } else if (m.vt === "rect") {
      const el = document.querySelector('.scene[data-scene="' + m.scene + '"] .el[data-el="' + m.index + '"]');     // any page of the scene
      const b = el && el.getBoundingClientRect();
      let size = null, quad = null, free = false;
      if (el && b && b.width) {
        size = [el.offsetWidth, el.offsetHeight];                                   // its own size before any transform (what the corner pins are fractions of)
        const shape = el.closest(".free-shape");
        free = !!shape;
        if (shape) {                                                                // a hand-placed element: where its four corners really are, with rotation, tilt, slant and corner pin in
          const host = shape.style.display === "contents" ? shape.parentElement : shape;
          quad = [[0, 0], [1, 0], [1, 1], [0, 1]].map(([x, y]) => {
            const k = document.createElement("i");
            k.style.cssText = "position:absolute;width:0;height:0;pointer-events:none;left:" + x * 100 + "%;top:" + y * 100 + "%";
            host.appendChild(k);
            const r = k.getBoundingClientRect();
            k.remove();
            return [r.left, r.top];
          });
        }
      }
      const natural = el && !free && window.__vtFree ? window.__vtFree.natural(m.scene, m.index) : null;      // for an element layout placed: its size once hand-placed at size 1
      window.parent.postMessage({ vt: "rect", scene: m.scene, index: m.index, box: b && b.width ? [b.left, b.top, b.width, b.height] : null, size, quad, free, natural, frame: [innerWidth, innerHeight] }, "*");
    } else if (m.vt === "data") {
      const t = tl ? tl.time() : 0;
      build(m.data);
      seek(t);
    }
  });

  window.__vt = { build, seek, play, pause, timeline: () => window.__vtClipped || tl, get duration() { return D ? D.duration : 0; }, get time() { return tl ? tl.time() : 0; } };

  function boot() {
    if (window.__VT__) {
      build(window.__VT__);
      const q = new URLSearchParams(location.search);
      if (q.has("t")) seek(parseFloat(q.get("t")));
      window.parent !== window && window.parent.postMessage({ vt: "ready", duration: D.duration }, "*");
    }
  }
  // The page starts the build explicitly (window.VTX.start()) after every runtime script has loaded: a renderer may run scripts when the
  // document is already "ready", and building earlier would skip the components the extension scripts add.
  // Every font face is loaded before the build: text is fitted once, with the real fonts. Building first and fitting again when the fonts arrive
  // ended differently depending on how fast they loaded (a different text size in one render than in another).
  const fontsThenBoot = () => {
    const faces = document.fonts ? [...document.fonts] : [];
    if (!faces.length || document.fonts.status === "loaded" && faces.every((f) => f.status === "loaded")) return boot();
    Promise.all(faces.map((f) => f.load().catch(() => null))).then(boot, boot);
  };
  window.VTX.start = () => {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fontsThenBoot);
    else fontsThenBoot();
  };
})();
