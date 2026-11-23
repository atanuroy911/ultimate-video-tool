/* The visual editor's bridge into a code-native shot (docs/plans/PLAN-CODE-NATIVE-EDITOR.MD, C3).
   Added only to the editing preview, never to a render. The shot runs in a sandboxed frame with no access to the Studio; the Studio talks to it
   through these messages:
     {vt:"shot-seek", t}                 show the moment t (seconds)
     {vt:"shot-pick", x, y}              which element is at this point (shot pixels)  -> {vt:"shot-picked", id, rect}
     {vt:"shot-rect", id}                where an element is now                         -> {vt:"shot-rect", id, rect}
     {vt:"shot-overrides", overrides}    show these edits live (the saved file is checked by the server; this is only the preview)
   On load it says {vt:"shot-ready", ids, duration, width, height}. */
(function () {
  "use strict";
  var STYLE = { color: ["color", ""], background: ["background", ""], fontSize: ["font-size", "px"], fontWeight: ["font-weight", ""],
                fontFamily: ["font-family", ""], letterSpacing: ["letter-spacing", "px"], opacity: ["opacity", ""] };
  var root = document.querySelector("[data-composition-id]");
  var rootId = root ? root.getAttribute("data-composition-id") : "root";
  var originalText = {};
  var applied = { knobs: {}, elements: {} };

  function timeline() { return (window.__timelines || {})[rootId]; }
  function el(id) { return document.querySelector('[data-vt-id="' + String(id).replace(/[^A-Za-z0-9_-]/g, "") + '"]'); }
  function rectOf(e) { var r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }
  function say(msg) { parent.postMessage(msg, "*"); }

  function clear() {
    Object.keys(applied.knobs || {}).forEach(function (k) { document.documentElement.style.removeProperty(k); });
    Object.keys(applied.elements || {}).forEach(function (id) {
      var e = el(id);
      if (!e) return;
      ["translate", "scale", "rotate", "display"].concat(Object.keys(STYLE).map(function (s) { return STYLE[s][0]; })).forEach(function (p) { e.style.removeProperty(p); });
      if (id in originalText) e.textContent = originalText[id];
    });
  }

  function apply(o) {
    clear();
    o = o || {};
    Object.keys(o.knobs || {}).forEach(function (k) { if (/^--[A-Za-z0-9_-]+$/.test(k)) document.documentElement.style.setProperty(k, String(o.knobs[k]), "important"); });
    Object.keys(o.elements || {}).forEach(function (id) {
      var e = el(id), v = o.elements[id] || {};
      if (!e) return;
      if (v.hidden) e.style.setProperty("display", "none", "important");
      if (v.x != null || v.y != null) e.style.setProperty("translate", (+v.x || 0) + "px " + (+v.y || 0) + "px", "important");
      if (v.scale != null) e.style.setProperty("scale", String(+v.scale), "important");
      if (v.rotate != null) e.style.setProperty("rotate", (+v.rotate) + "deg", "important");
      Object.keys(v.style || {}).forEach(function (n) {
        if (!STYLE[n]) return;
        var val = v.style[n];
        e.style.setProperty(STYLE[n][0], typeof val === "number" ? val + STYLE[n][1] : String(val), "important");
      });
      if (typeof v.text === "string") {
        if (!(id in originalText)) originalText[id] = e.textContent;
        e.textContent = v.text;
      }
    });
    applied = o;
  }

  window.addEventListener("message", function (ev) {
    if (ev.source !== parent || !ev.data || typeof ev.data.vt !== "string") return;
    var m = ev.data, tl = timeline();
    if (m.vt === "shot-seek" && tl) { tl.seek(Math.max(0, +m.t || 0), false); }
    else if (m.vt === "shot-overrides") { apply(m.overrides); }
    else if (m.vt === "shot-pick") {
      var hit = document.elementFromPoint(+m.x || 0, +m.y || 0);
      var picked = hit && hit.closest ? hit.closest("[data-vt-id]") : null;
      say({ vt: "shot-picked", id: picked ? picked.getAttribute("data-vt-id") : null, rect: picked ? rectOf(picked) : null });
    } else if (m.vt === "shot-rect") {
      var e = el(m.id);
      say({ vt: "shot-rect", id: m.id, rect: e ? rectOf(e) : null });
    }
  });

  var ids = Array.prototype.map.call(document.querySelectorAll("[data-vt-id]"), function (e) { return e.getAttribute("data-vt-id"); });
  ids.forEach(function (id) { var e = el(id); if (e) originalText[id] = e.textContent; });
  var texts = {};                                       // only elements that are plain text can have their text edited (replacing a row's text would drop its parts)
  ids.forEach(function (id) { var e = el(id); if (e && e.children.length === 0) texts[id] = e.textContent; });
  var colours = {};                                     // the colour each element is drawn in now, so the editor's colour picker starts there
  function hex(c) { var m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(c || ""); return m ? "#" + [m[1], m[2], m[3]].map(function (n) { return (+n).toString(16).padStart(2, "0"); }).join("") : null; }
  ids.forEach(function (id) { var e = el(id); if (e) colours[id] = hex(getComputedStyle(e).color); });
  say({ vt: "shot-ready", ids: ids, texts: texts, colours: colours, duration: root ? +root.getAttribute("data-duration") : 0,
        width: root ? +root.getAttribute("data-width") : 0, height: root ? +root.getAttribute("data-height") : 0 });
})();
