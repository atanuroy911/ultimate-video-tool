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
  function isEase(fn) { try { return typeof fn === "function" && fn.length <= 1 && typeof fn(0.5) === "number" && fn(0) === 0 && Math.abs(fn(1) - 1) < 1e-9; } catch (e) { return false; } }
  function hasFn(v, d) {
    if (d > 4 || v == null) return false;
    if (typeof v === "function") return !easeNames.has(v) && !isEase(v);
    if (typeof v === "object" && !v.nodeType) {
      if (typeof v.totalDuration === "function") return false;                // a timeline or tween GSAP linked in: not an option
      for (var k in v) if (k !== "parent" && k.charAt(0) !== "_" && hasFn(v[k], d + 1)) return true;
    }
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
    var o = {}; for (var k in v) o[k] = k === "ease" && typeof v[k] === "function" && easeNames.has(v[k]) ? easeNames.get(v[k]) : snap(v[k], d + 1); return o;
  }
  var easeNames = new Map(), allArgs = [];
  // The runtime plays its timeline while it builds (it measures where things land), which writes animation states into inline styles. The style of
  // every element just before the first play is its built style; an element made later is read when GSAP first touches it.
  function freezeAll() {
    var r = document.querySelector("[data-composition-id]");
    if (!r) return;
    r.querySelectorAll("*").forEach(function (el) { if (!firstStyle.has(el)) firstStyle.set(el, el.getAttribute("style")); });
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
          if (hasFn(a.slice(1), 0)) { rec.fn = true; rec.fnKeys = a.slice(1).reduce(function (k, v) { if (v && typeof v === "object") for (var x in v) if (x !== "parent" && x.charAt(0) !== "_" && hasFn(v[x], 1)) k.push(x); return k; }, []); }
        }
        if (m === "call") rec.fn = true;
        calls.get(tl).push(rec);
        allArgs.push(rec.args);
        var before = tl._recent;
        // GSAP gets the runtime's own objects (the runtime reads some back after GSAP changed them). GSAP turns an ease name into a function in the
        // object it is given; the name is kept for that function, so a later copy of the object still writes the name.
        var out = orig.apply(null, a);
        a.forEach(function (x, i) { var r = rec.args[i]; if (i && x && r && typeof r === "object" && typeof r.ease === "string" && typeof x.ease === "function") easeNames.set(x.ease, r.ease); });
        if (tl._recent && tl._recent !== before) rec.child = tl._recent;      // the tween or timeline this call put on the timeline (GSAP keeps the latest one)
        return out;
      };
    });
    ["time", "totalTime", "progress", "totalProgress", "seek", "play", "restart"].forEach(function (m) {   // the first time any timeline is played,
      var orig = tl[m];                                                                                   // every element's style is still as built
      if (typeof orig !== "function") return;
      tl[m] = function () { if (arguments.length || m === "play" || m === "restart") freezeAll(); return orig.apply(tl, arguments); };
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
      var out = orig.apply(null, a);
      if (m === "set") {                                                       // applied at once, so part of the built page: the remembered built style takes it in
        var touchedProps = new Set();
        cssOf(a[1], touchedProps, 0);
        els(a[0]).forEach(function (el) {
          if (!firstStyle.has(el)) return;                                     // not animated yet: its built style is read later, with this in it
          var b = document.createElement("div");
          b.setAttribute("style", firstStyle.get(el) || "");
          touchedProps.forEach(function (p) { var v = el.style.getPropertyValue(p); if (v) b.style.setProperty(p, v); else b.style.removeProperty(p); });
          firstStyle.set(el, b.getAttribute("style"));
        });
      }
      return out;
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
    if (typeof v === "function") {
      if (easeNames.has(v)) return JSON.stringify(easeNames.get(v));
      if (isEase(v)) lost.push({ what: "an ease without a name (GSAP's default is used)" });
      return "undefined";
    }
    if (v.nodeType === 1) return "$(" + JSON.stringify(idOf(v)) + ")";
    if (d > 6) return "null";
    if (Array.isArray(v)) return "[" + v.map(function (x) { return js(x, d + 1); }).join(",") + "]";
    if (made.has(v)) return null;                                           // handled by the caller
    // GSAP keeps its own links in an options object the runtime may reuse (parent, _-fields, timelines): they are not options and never written
    var gsapOwn = function (x) { return x && typeof x === "object" && typeof x.totalDuration === "function"; };
    return "{" + Object.keys(v).filter(function (k) { return typeof v[k] !== "function" && k !== "parent" && k.charAt(0) !== "_" && !gsapOwn(v[k]); }).map(function (k) { return JSON.stringify(k) + ":" + js(v[k], d + 1); }).join(",") + "}";
  }

  window.__vtBake = function () {
    // every ease name the page used (and GSAP's own), parsed by GSAP: a function GSAP put in place of a name is written as that name again
    var seenNames = new Set(["none", "linear"]);
    ["power0", "power1", "power2", "power3", "power4", "back", "elastic", "bounce", "circ", "expo", "sine"].forEach(function (b) { ["in", "out", "inOut"].forEach(function (d) { seenNames.add(b + "." + d); }); });
    (function walk(v, d) { if (!v || d > 6) return; if (typeof v === "string") return; if (Array.isArray(v)) return v.forEach(function (x) { walk(x, d + 1); }); if (typeof v === "object" && !v.nodeType && Object.getPrototypeOf(v) === Object.prototype) for (var k in v) { if (k === "ease" && typeof v[k] === "string") seenNames.add(v[k]); else walk(v[k], d + 1); } })(allArgs, 0);
    seenNames.forEach(function (n) { try { var fn = gsap.parseEase(n); if (typeof fn === "function" && !easeNames.has(fn)) easeNames.set(fn, n); } catch (e) { /* not an ease */ } });
    var root = window.__timelines && (window.__timelines.root || window.__timelines[Object.keys(window.__timelines)[0]]);
    if (!root) return { error: "the page made no timeline" };
    var names = new Map(), code = [], touched = new Set();
    var capLayer = document.querySelector("[data-composition-id] .cap-layer"), capCode = [];
    var isTL = function (x) { return x && typeof x.getChildren === "function"; };
    var isEl = function (x) { return x && x.nodeType === 1; };
    var at3 = function (n) { return Math.round(n * 10000) / 10000; };
    function clean(vars) {                                                   // the tween's options as GSAP holds them now, without its own links and timing
      var o = {};
      for (var k in vars) { if (k === "delay" || k === "parent" || k.charAt(0) === "_" || typeof vars[k] === "function" || k === "data") continue; o[k] = vars[k]; }
      return o;
    }
    // A count-up redraws a number from a callback on a plain object. Its effect is sampled: the root timeline is stepped through the tween 30 times a
    // second while the text it writes is watched, and each change becomes a plain text step at that moment.
    function sample(tw) {
      var keep = root.time(), from = tw.startTime(), dur = tw.duration(), seen = new Map(), last = new Map(), steps = [];
      var watchRoot = document.querySelector("[data-composition-id]");
      var obs = new MutationObserver(function () {});
      obs.observe(watchRoot, { characterData: true, childList: true, subtree: true });
      for (var k = 0; k <= Math.ceil(dur * 30) + 1; k++) {
        var t = from + Math.min(dur, k / 30);
        root.time(t);
        obs.takeRecords().forEach(function (m) { var el = m.type === "characterData" ? m.target.parentElement : m.target; if (isEl(el)) seen.set(el, el.textContent); });
        seen.forEach(function (txt, el) { if (last.get(el) !== txt) { last.set(el, txt); steps.push([el, t, txt]); } });
        seen.clear();
      }
      obs.disconnect();
      root.time(keep);
      return steps;
    }
    // S4 (PLAN-SCENE-TOOLS): each scene's time window, worked out before the code is written, so a scene's animation can go into the scene's own
    // composition (scenes/<id>.html) with its times counted from the scene's start. From its first tween (0 for the first scene) to the end of its
    // last one (the moment it is hidden), or to the end of the video; HyperFrames shows a timed element only inside its window.
    var rootEl = document.querySelector("[data-composition-id]");
    var total = Number(rootEl.getAttribute("data-duration")) || root.duration();
    var direct = root.getChildren(false, true, false);
    var win = new Map(), sceneCode = new Map(), early = [];
    [].slice.call(rootEl.querySelectorAll(".scene[data-scene]")).forEach(function (sc, i) {
      if (sc.querySelector("video[data-start], audio[data-start]")) return;  // a timed clip inside takes no timing from its wrapper (HyperFrames: video_nested_in_timed_element)
      var from = Infinity, to = -Infinity;
      direct.forEach(function (tw) {
        if (tw.targets().indexOf(sc) < 0) return;
        from = Math.min(from, tw.startTime());
        to = Math.max(to, tw.endTime());
      });
      if (!isFinite(from) || i === 0) from = 0;
      var hidden = direct.some(function (tw) { return tw.targets().indexOf(sc) >= 0 && tw.vars && (tw.vars.opacity === 0 || tw.vars.autoAlpha === 0 || tw.vars.visibility === "hidden"); });
      if (!hidden || !isFinite(to)) to = total;
      to = Math.min(total, to + 1 / 30);                                     // one frame more: never cut the last frame of a fade
      win.set(sc, { from: Math.round(from * 1000) / 1000, to: to, own: /^[A-Za-z0-9_-]+$/.test(sc.getAttribute("data-scene") || "") });
    });
    function elementsOf(x, acc) {                                            // every page element a tween or timeline moves
      if (isTL(x)) { x.getChildren(true, true, false).forEach(function (t) { elementsOf(t, acc); }); return acc; }
      (x.targets ? x.targets() : []).forEach(function (t) { if (isEl(t)) acc.push(t); });
      return acc;
    }
    // A step at the root that moves parts of two scenes at once (a transition such as the mosaic), or a scene's part and something outside every
    // scene, must stay in the root page with all it moves: those scenes keep living in the root page (a scene's own page is mounted after the root's
    // code has run, so the root could not reach its parts). Repeated until nothing changes, since keeping one scene can tie another to the root.
    var rootSteps = root.getChildren(false, true, true).map(function (ch) { var src = made.get(ch); return elementsOf(src ? src.of : ch, []); });
    for (var changed = true; changed;) {
      changed = false;
      rootSteps.forEach(function (els) {
        var inScenes = new Set(), outside = false;
        els.forEach(function (el) {
          var s = null;
          win.forEach(function (w, sc) { if (!s && w.own && sc.contains(el)) s = sc; });
          if (s) inScenes.add(s); else outside = true;
        });
        if (inScenes.size > 1 || (inScenes.size && outside)) inScenes.forEach(function (sc) { win.get(sc).own = false; changed = true; });
      });
    }
    var ownScenes = [];
    win.forEach(function (w, sc) { if (w.own) ownScenes.push(sc); });
    function sceneOf(els) {                                                  // the one scene holding every element, if it has its own composition
      if (!els.length) return null;
      var sc = ownScenes.find(function (s) { return s.contains(els[0]); });
      return sc && els.every(function (el) { return sc.contains(el); }) ? sc : null;
    }
    // A scene's own window starts at its earliest step (a part can start moving a moment before the scene's own entrance; the scene is still
    // invisible then, .scene starts at opacity 0), so no step of the scene is moved or cut.
    root.getChildren(false, true, true).forEach(function (ch, k) {
      var sc = sceneOf(rootSteps[k]);
      if (sc) win.get(sc).from = Math.min(win.get(sc).from, Math.floor(ch.startTime() * 1000) / 1000);
    });
    var out = code;                                                          // where the code goes: the root's, or a scene's
    function define(tl) {                                                    // writes a timeline (its children first when they are timelines) and returns its name
      if (names.has(tl)) return names.get(tl);
      var me = "t" + names.size;
      names.set(tl, me);
      var v = clean(tl.vars || {});
      if (tl !== root) v.paused = !!(tl.vars && tl.vars.paused);
      out.push("const " + me + " = gsap.timeline(" + (tl === root ? "{ paused: true }" : js(v)) + ");");
      var done = new Set(), list = [], recOf = new Map();
      (calls.get(tl) || []).forEach(function (c) { if (c.child && !done.has(c.child)) { done.add(c.child); list.push(c.child); recOf.set(c.child, c); } });
      tl.getChildren(false, true, true).forEach(function (ch) { if (!done.has(ch)) { done.add(ch); list.push(ch); } });   // made some other way
      var noDelay = function (o) { if (!o || typeof o !== "object" || Array.isArray(o)) return o; var r = {}; for (var k in o) if (k !== "delay") r[k] = o[k]; return r; };
      list.forEach(function (ch) {
        if (ch.parent !== tl) return;                                        // killed or moved since (settleEntrance replaces some entrances with a set)
        var start = at3(ch.startTime());                                     // where it is now (the runtime moves some tweens after making them)
        var src = made.get(ch);
        // at the root, a step that moves only one scene's parts goes to that scene's composition, its time counted from the scene's start
        var me2 = me, home = out, shift = 0;
        if (tl === root) {
          var sc = sceneOf(elementsOf(src ? src.of : ch, []));
          if (sc) {
            if (!sceneCode.has(sc)) sceneCode.set(sc, []);
            out = sceneCode.get(sc); me2 = "ts"; shift = win.get(sc).from;
            if (start < shift - 0.0005) early.push({ scene: sc.getAttribute("data-scene"), at: start, from: shift, set: ch.duration() === 0 });
          }
        }
        var at = function (t) { return at3(Math.max(0, t - shift)); };
        try {
          if (isTL(ch)) { out.push(me2 + ".add(" + define(ch) + "," + at(start) + ");"); return; }
          if (src) { out.push(me2 + ".add(" + define(src.of) + "." + src.m + "(" + src.args.map(function (a) { return js(a); }).join(",") + ")," + at(start) + ");"); return; }
          emit(ch, tl, me2, at, start);
        } finally { out = home; }
      });
      return me;
      function emit(ch, tl, me, at, start) {
        var targets = ch.targets(), rec = recOf.get(ch);
        if (!targets.length) { lost.push({ what: "a call", keys: "callback" }); return; }
        if (!targets.every(isEl)) {                                          // a plain object: a count-up
          var steps = tl === root ? sample(ch) : [];
          if (steps.length) {
            steps.forEach(function (s) {                                     // each text step goes to the page holding its element
              touched.add(s[0]);
              var sc = tl === root && me !== "ts" ? sceneOf([s[0]]) : null;
              var line = ".set([" + JSON.stringify(idOf(s[0])) + "].map($)," + JSON.stringify({ textContent: s[2] }) + ",";
              if (sc) {
                if (!sceneCode.has(sc)) sceneCode.set(sc, []);
                sceneCode.get(sc).push("ts" + line + at3(Math.max(0, s[1] - win.get(sc).from)) + ");");
              } else out.push(me + line + at(s[1]) + ");");
            });
          }
          else lost.push({ what: "a tween of something that is not on the page", keys: (rec && rec.fnKeys || []).join(",") });
          return;
        }
        if (!rec || !/^(to|from|fromTo|set)$/.test(rec.m)) { lost.push({ what: "a tween made another way", el: targets[0].className || targets[0].tagName }); return; }
        if (rec.fn) lost.push({ what: "a callback on a tween", keys: (rec.fnKeys || []).join(","), el: targets[0].className || targets[0].tagName });
        targets.forEach(function (el) { touched.add(el); });
        var opts = rec.args.slice(1, rec.m === "fromTo" ? 3 : 2).map(noDelay);     // the options as the runtime gave them (GSAP turns eases into functions in its copy)
        var line = "." + rec.m + "([" + targets.map(function (el) { return JSON.stringify(idOf(el)); }).join(",") + "].map($)," + opts.map(function (o) { return js(o); }).join(",") + "," + at(start) + ");";
        // a tween of caption parts only goes to the captions' own composition (same times: it starts at 0)
        if (capLayer && tl === root && targets.every(function (el) { return capLayer.contains(el); })) { capCode.push("tc" + line); return; }
        out.push(me + line);
      }
    }
    define(root);
    // the page as built, before the timeline moved anything: GSAP-set styles, attributes and text go back to what the builder wrote
    // (done on a copy of the page: the live page keeps the nodes the timeline holds)
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
    win.forEach(function (w, sc) {                                         // each scene copy gets its window (worked out above)
      var c = twin.get(sc);
      if (!c) return;
      c.setAttribute("data-start", String(w.from));
      c.setAttribute("data-duration", String(Math.round((w.to - w.from) * 1000) / 1000));
    });
    // A shorthand holding a variable with one side overridden (border: 5px solid var(--accent); border-top-color: transparent) cannot be written back
    // as text: the browser leaves its parts empty. Those parts get the value the page actually draws.
    twin.forEach(function (c, el) {
      var s = c.getAttribute("style");
      if (!s || !/:\s*;/.test(s)) return;
      var cs = getComputedStyle(el);
      c.setAttribute("style", s.replace(/([a-z-]+):\s*;/g, function (_, p) { var v = cs.getPropertyValue(p); return v ? p + ": " + v + ";" : ""; }));
    });
    // The captions become their own composition: their layer moves to compositions/captions.html and a full-frame host takes its place in the page (it stays
    // inside the root, so the caption styles and the theme's variables still apply). Without captions the video still draws; one bake serves both.
    var captions = null;
    if (capLayer && capCode.length && twin.get(capLayer)) {
      var capCopy = twin.get(capLayer);
      var host = document.createElement("div");
      host.id = "captions";
      host.setAttribute("data-composition-id", "captions");
      host.setAttribute("data-composition-src", "compositions/captions.html");
      host.setAttribute("data-start", "0");
      host.setAttribute("data-duration", String(total));
      host.setAttribute("style", "position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none");
      host.setAttribute("data-track-kind", "captions");                     // HyperFrames groups it on its caption track
      capCopy.parentNode.replaceChild(host, capCopy);
      captions = {
        html: capCopy.outerHTML,
        script: "{\n  const $ = (id) => document.getElementById(id);\n  const tc = gsap.timeline({ paused: true });\n  " + capCode.join("\n  ") +
          "\n  window.__timelines = window.__timelines || {};\n  window.__timelines.captions = tc;\n}",
        width: Number(rootEl.getAttribute("data-width")), height: Number(rootEl.getAttribute("data-height")), duration: total, tweens: capCode.length,
      };
    }
    // S4: each scene becomes its own composition (scenes/<id>.html, HyperFrames: nested_structure_needs_subcomposition). A full-frame host takes
    // its place in the page, at the same spot (same stacking) and with the scene's window; the scene inside starts at 0 on its own timeline.
    var scenes = [];
    win.forEach(function (w, sc) {
      var c = twin.get(sc);
      if (!w.own || !c || !c.parentNode) return;
      if (!c.id) c.id = idOf(sc);                                            // its readable id (given now if no step named it)
      if (!c.getAttribute("data-hf-id")) c.setAttribute("data-hf-id", "hf-" + c.id);
      var key = sc.id.replace(/-scene(?=-\d+$|$)/, ""), cid = "scene-" + key;     // "s4-scene" -> s4, "s4-scene-2" -> s4-2 (a scene's second page)
      var host = document.createElement("div");
      host.id = cid;
      host.setAttribute("data-composition-id", cid);
      host.setAttribute("data-composition-src", "scenes/" + key + ".html");
      host.setAttribute("data-start", c.getAttribute("data-start"));
      host.setAttribute("data-duration", c.getAttribute("data-duration"));
      host.setAttribute("style", "position:absolute;left:0;top:0;width:100%;height:100%");
      c.removeAttribute("data-start");
      c.removeAttribute("data-duration");
      c.parentNode.replaceChild(host, c);
      var lines = sceneCode.get(sc) || [];
      scenes.push({
        id: cid, file: key, html: c.outerHTML, tweens: lines.length,
        script: "{\n  const $ = (id) => document.getElementById(id);\n  const ts = gsap.timeline({ paused: true });\n  " + lines.join("\n  ") +
          "\n  window.__timelines = window.__timelines || {};\n  window.__timelines[" + JSON.stringify(cid) + "] = ts;\n}",
        width: Number(rootEl.getAttribute("data-width")), height: Number(rootEl.getAttribute("data-height")),
        duration: Number(host.getAttribute("data-duration")),
      });
    });
    var html = copy.outerHTML;
    var script = "const $ = (id) => document.getElementById(id);\n" + code.join("\n") + "\nwindow.__timelines = window.__timelines || {};\nwindow.__timelines[" + JSON.stringify(rootEl.getAttribute("data-composition-id") || "root") + "] = t0;";
    return { html: html, script: script, captions: captions, scenes: scenes, early: early, lost: lost, timelines: names.size, elements: touched.size };
  };
})();
