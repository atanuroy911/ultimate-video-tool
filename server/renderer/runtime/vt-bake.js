/* Bake (docs/plans/PLAN-OPENMOTION.MD, O3): the runtime builds the page as always; this records every GSAP call it makes, and window.__vtBake() writes
   the result out as plain HyperFrames source: the built DOM (each animated element with a stable id and data-hf-id) and the timeline as GSAP code that
   addresses those ids. The HyperFrames Studio can then select, move, retype and re-time every part, because every part is in the source.
   Loaded only by vt/bake.py, right after gsap.min.js and before vt.js. Anything that cannot be written as plain code (a callback) is listed in `lost`. */
(function () {
  var g = window.gsap;
  if (!g) return;
  var calls = new WeakMap();              // timeline -> [{m, targets, args}]
  var firstStyle = new WeakMap();         // element -> its style attribute before GSAP touched it
  var firstAttr = new WeakMap();          // element -> {attr: value} for attributes GSAP tweens (attr: {...})
  var firstText = new WeakMap();          // element -> textContent before a text tween
  var made = new WeakMap();               // tween made by timeline.tweenFromTo / tweenTo -> {of, m, args}
  var lost = [];
  var mkTimeline = g.timeline.bind(g);

  function els(t) {
    if (t == null) return [];
    if (typeof t === "string") { try { return [].slice.call(document.querySelectorAll(t)); } catch (e) { return []; } }
    if (t.nodeType === 1) return [t];
    if (typeof t === "object" && t.length != null) { var out = []; for (var i = 0; i < t.length; i++) out = out.concat(els(t[i])); return out; }
    return [];
  }
  function hasFn(v, d) {
    if (d > 4 || v == null) return false;
    if (typeof v === "function") return true;
    if (typeof v === "object" && !v.nodeType) { for (var k in v) if (hasFn(v[k], d + 1)) return true; }
    return false;
  }
  var props = new WeakMap();              // element -> the CSS properties GSAP animates on it (only these go back to their built value)
  var NOT_CSS = /^(duration|ease|delay|stagger|repeat|repeatDelay|yoyo|yoyoEase|immediateRender|overwrite|clearProps|attr|keyframes|startAt|runBackwards|paused|id|data|inherit|lazy|snap|modifiers|callbackScope|css|motionPath|innerText|textContent|innerHTML|reversed|easeEach|on[A-Z].*)$/;
  var TRANSFORM = /^(x|y|z|xPercent|yPercent|scale|scaleX|scaleY|scaleZ|rotation|rotate|rotationX|rotationY|rotationZ|rotateX|rotateY|rotateZ|skewX|skewY|transformPerspective|svgOrigin|force3D|smoothOrigin)$/;
  function cssOf(v, into, d) {
    if (!v || typeof v !== "object" || d > 3) return;
    for (var k in v) {
      if (k === "keyframes" || k === "startAt" || k === "css") { var kv = v[k]; if (Array.isArray(kv)) kv.forEach(function (x) { cssOf(x, into, d + 1); }); else cssOf(kv, into, d + 1); continue; }
      if (/^\d+(\.\d+)?%$/.test(k)) { cssOf(v[k], into, d + 1); continue; }
      if (NOT_CSS.test(k)) continue;
      if (TRANSFORM.test(k)) { ["transform", "translate", "rotate", "scale"].forEach(function (p) { into.add(p); }); continue; }
      if (k === "autoAlpha") { into.add("opacity"); into.add("visibility"); continue; }
      into.add(k.replace(/[A-Z]/g, function (m) { return "-" + m.toLowerCase(); }));
    }
  }
  function remember(list, vars) {
    list.forEach(function (el) {
      if (!firstStyle.has(el)) firstStyle.set(el, el.getAttribute("style"));
      var set = props.get(el) || new Set();
      cssOf(vars, set, 0);
      if (vars && vars.clearProps) String(vars.clearProps).split(",").forEach(function (p) { p = p.trim(); if (p && p !== "all") cssOf((function () { var o = {}; o[p] = 1; return o; })(), set, 0); });
      props.set(el, set);
      [vars].forEach(function (v) {
        if (!v || typeof v !== "object") return;
        if (v.attr && typeof v.attr === "object") {
          var a = firstAttr.get(el) || {};
          for (var k in v.attr) if (!(k in a)) a[k] = el.getAttribute(k);
          firstAttr.set(el, a);
        }
        if (("innerText" in v || "textContent" in v || "innerHTML" in v) && !firstText.has(el)) firstText.set(el, el.innerHTML);
      });
    });
  }
  function snap(v, d) {                                                     // the options as given: GSAP adds its own fields to them afterwards
    d = d || 0;
    if (v == null || typeof v !== "object" || v.nodeType || d > 6) return v;
    if (Array.isArray(v)) return v.map(function (x) { return snap(x, d + 1); });
    if (Object.getPrototypeOf(v) !== Object.prototype) return v;         // a timeline, a tween: kept as it is
    var o = {}; for (var k in v) o[k] = snap(v[k], d + 1); return o;
  }
  function wrap(tl) {
    calls.set(tl, []);
    ["to", "from", "fromTo", "set", "call", "add", "addLabel"].forEach(function (m) {
      var orig = tl[m].bind(tl);
      tl[m] = function () {
        var a = [].slice.call(arguments);
        var rec = { m: m, args: a.map(function (x, i) { return i === 0 ? x : snap(x); }) };
        if (m === "to" || m === "from" || m === "fromTo" || m === "set") {
          rec.targets = els(a[0]);
          remember(rec.targets, a[1]);
          if (m === "fromTo") remember(rec.targets, a[2]);
          if (hasFn(a.slice(1), 0)) rec.fn = true;
        }
        if (m === "call") rec.fn = true;
        calls.get(tl).push(rec);
        return orig.apply(null, a);
      };
    });
    ["tweenFromTo", "tweenTo"].forEach(function (m) {
      var orig = tl[m].bind(tl);
      tl[m] = function () { var a = [].slice.call(arguments); var tw = orig.apply(null, a); made.set(tw, { of: tl, m: m, args: a }); return tw; };
    });
    return tl;
  }
  g.timeline = function (v) { return wrap(mkTimeline(v)); };
  ["to", "from", "fromTo", "set"].forEach(function (m) {                   // gsap.set on its own (not on a timeline) applies at once: it is part of the built page
    var orig = g[m].bind(g);
    g[m] = function () {
      var a = [].slice.call(arguments);
      if (m !== "set") lost.push({ what: "gsap." + m + " outside a timeline", el: (els(a[0])[0] || {}).className || "" });
      return orig.apply(null, a);
    };
  });

  var used = {};
  function readable(el) {                                                    // "s4-definition", "s2-ring-2": the scene, then what the part is
    var sc = el.closest && el.closest("[data-scene]");
    var cls = [].slice.call(el.classList || []).filter(function (c) { return !/^(el|on|off|vt-|is-|text-look)/.test(c) || /^el-/.test(c); });
    var what = (cls.find(function (c) { return /^el-/.test(c); }) || cls[0] || el.tagName.toLowerCase()).replace(/^el-/, "").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase() || "part";
    if (el.hasAttribute && el.hasAttribute("data-scene") && el === sc) what = "scene";
    var base = (sc ? sc.getAttribute("data-scene") + "-" : "") + what;
    base = base.replace(/^[^A-Za-z]+/, "") || "part";
    var id;
    do { used[base] = (used[base] || 0) + 1; id = used[base] === 1 ? base : base + "-" + used[base]; } while (document.getElementById(id));
    return id;
  }
  function idOf(el) {
    if (!el.id) el.id = readable(el);
    if (!el.getAttribute("data-hf-id")) el.setAttribute("data-hf-id", "hf-" + el.id);
    return el.id;
  }
  function js(v, d) {                                                        // a value as JavaScript source (elements become lookups by id)
    d = d || 0;
    if (v == null || typeof v === "number" || typeof v === "boolean") return v === undefined ? "undefined" : JSON.stringify(v);
    if (typeof v === "string") return JSON.stringify(v);
    if (typeof v === "function") return "undefined";
    if (v.nodeType === 1) return "$(" + JSON.stringify(idOf(v)) + ")";
    if (d > 6) return "null";
    if (Array.isArray(v)) return "[" + v.map(function (x) { return js(x, d + 1); }).join(",") + "]";
    if (made.has(v)) return null;                                           // handled by the caller
    return "{" + Object.keys(v).filter(function (k) { return typeof v[k] !== "function"; }).map(function (k) { return JSON.stringify(k) + ":" + js(v[k], d + 1); }).join(",") + "}";
  }

  window.__vtBake = function () {
    var root = window.__timelines && (window.__timelines.root || window.__timelines[Object.keys(window.__timelines)[0]]);
    if (!root) return { error: "the page made no timeline" };
    var names = new Map(), order = [], code = [];
    function name(tl) { if (!names.has(tl)) { names.set(tl, "t" + names.size); order.push(tl); } return names.get(tl); }
    name(root);
    for (var i = 0; i < order.length; i++) {                                // a timeline added into another is written too (in the order met)
      (calls.get(order[i]) || []).forEach(function (c) {
        if (c.m === "add" && c.args[0] && typeof c.args[0] === "object") {
          var src = made.get(c.args[0]);
          if (src) name(src.of); else if (calls.has(c.args[0])) name(c.args[0]);
        }
      });
    }
    var touched = new Set();
    order.slice().reverse().forEach(function (tl) {                          // children first, so the parent can add them
      var me = names.get(tl);
      code.push("const " + me + " = gsap.timeline({ paused: true });");
      (calls.get(tl) || []).forEach(function (c) {
        if (c.fn) { lost.push({ what: c.m + " with a callback", el: c.targets && c.targets[0] ? (c.targets[0].className || c.targets[0].tagName) : "" }); }
        if (c.m === "call") return;
        if (c.m === "add") {
          var x = c.args[0], pos = c.args.length > 1 ? "," + js(c.args[1]) : "";
          if (typeof x === "string") { code.push(me + ".add(" + JSON.stringify(x) + pos + ");"); return; }
          var src = x && made.get(x);
          if (src) { code.push(me + ".add(" + names.get(src.of) + "." + src.m + "(" + src.args.map(function (a) { return js(a); }).join(",") + ")" + pos + ");"); return; }
          if (x && calls.has(x)) { code.push(me + ".add(" + names.get(x) + pos + ");"); return; }
          lost.push({ what: "add of something that is not a timeline" });
          return;
        }
        if (c.m === "addLabel") { code.push(me + ".addLabel(" + c.args.map(function (a) { return js(a); }).join(",") + ");"); return; }
        if (!c.targets.length) return;
        c.targets.forEach(function (el) { touched.add(el); });
        var tg = "[" + c.targets.map(function (el) { return JSON.stringify(idOf(el)); }).join(",") + "].map($)";
        var rest = c.args.slice(1).map(function (a) { return js(a); });
        code.push(me + "." + c.m + "(" + tg + "," + rest.join(",") + ");");
      });
    });
    // the page as built, before the timeline moved anything: GSAP-set styles, attributes and text go back to what the builder wrote
    // (done on a copy of the page: the live page keeps the nodes the timeline holds)
    var rootEl = document.querySelector("[data-composition-id]");
    var copy = rootEl.cloneNode(true);
    var twin = new Map();
    (function pair(a, b) { twin.set(a, b); for (var i = 0; i < a.children.length; i++) pair(a.children[i], b.children[i]); })(rootEl, copy);
    touched.forEach(function (el) {
      var c = twin.get(el);
      if (!c) return;                                                        // no longer on the page (built, then removed)
      // only what GSAP animates goes back to its built value; what the builder or the layout guard set (a fitted font size) stays
      var built = document.createElement("div");
      built.setAttribute("style", firstStyle.get(el) || "");
      (props.get(el) || new Set()).forEach(function (p) {
        var v = built.style.getPropertyValue(p);
        if (v) c.style.setProperty(p, v, built.style.getPropertyPriority(p)); else c.style.removeProperty(p);
      });
      if (c.getAttribute("style") === "") c.removeAttribute("style");
      var a = firstAttr.get(el);
      if (a) for (var k in a) { if (a[k] == null) c.removeAttribute(k); else c.setAttribute(k, a[k]); }
      if (firstText.has(el)) c.innerHTML = firstText.get(el);
    });
    // A shorthand holding a variable with one side overridden (border: 5px solid var(--accent); border-top-color: transparent) cannot be written back
    // as text: the browser leaves its parts empty. Those parts get the value the page actually draws.
    twin.forEach(function (c, el) {
      var s = c.getAttribute("style");
      if (!s || !/:\s*;/.test(s)) return;
      var cs = getComputedStyle(el);
      c.setAttribute("style", s.replace(/([a-z-]+):\s*;/g, function (_, p) { var v = cs.getPropertyValue(p); return v ? p + ": " + v + ";" : ""; }));
    });
    var html = copy.outerHTML;
    var script = "const $ = (id) => document.getElementById(id);\n" + code.join("\n") + "\nwindow.__timelines = { " + JSON.stringify(rootEl.getAttribute("data-composition-id") || "root") + ": t0 };";
    return { html: html, script: script, lost: lost, timelines: order.length, elements: touched.size };
  };
})();
