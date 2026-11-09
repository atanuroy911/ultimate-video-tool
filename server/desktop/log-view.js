// The server log as a list people can read: one entry per event, sorted into kinds, with the noise folded away.
// parseLog() is pure (tested by test-log-view.js); renderLog() draws it into the log screen of server-manager.html.
(function (root) {
  const STAMP = /^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\]\s?(.*)$/;
  const REQUEST = /("(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) \S+ HTTP\/[\d.]+" \d{3})|"WebSocket \S+" \[(?:accepted|rejected)\]|^\s*(?:INFO:\s+)?connection (?:open|closed)\b|HTTP Request: (?:GET|POST|PUT|DELETE)|^"HTTP\/[\d.]+ \d{3}/;
  const PACKAGE = /^\s*[+\-~]\s+[\w.\-\[\]]+(==|\s@\s|\s\(from)|^\s*(?:Resolved|Prepared|Installed|Uninstalled|Audited|Downloaded|Building|Built)\s+\d*\s*\w*|^\s*added \d+ packages\b|^\s*(?:Downloading|Collecting)\s|^\s*(?:Using CPython|Creating virtual environment|Activate with)/i;
  const PROBLEM = /\b(?:ERROR|CRITICAL|FATAL|Traceback|Exception|failed|failure|cannot|could not|couldn't|not found)\b|" 5\d\d\b/i;
  const WARNING = /\bWARN(?:ING)?\b/i;

  function kindOf(text) {
    const first = text.split("\n", 1)[0];
    if (!/\s/.test(text.trim()) && text.trim().length < 48 && !PROBLEM.test(text)) return "install";   // a lone word or version: a fragment of an installer's progress output
    if (REQUEST.test(first)) return / 5\d\d\b/.test(first) ? "problem" : "request";
    if (PACKAGE.test(first)) return "install";
    if (PROBLEM.test(text)) return "problem";
    if (WARNING.test(first)) return "warning";
    return "event";
  }

  // "INFO:     Started server process [1]" -> "Started server process [1]"; rich's "[11/08/26 22:14:28] INFO     HTTP Request" -> "HTTP Request"
  function tidy(text) {
    return text
      .replace(/^\s*(?:INFO|DEBUG):\s+/, "")
      .replace(/^\s*\[\d\d\/\d\d\/\d\d \d\d:\d\d:\d\d\]\s+(?:INFO|DEBUG)\s+/, "")
      .replace(/^[ \t]*:\d+[ \t]*$/gm, "")                    // a source line number wrapped onto a line of its own
      .replace(/\n[ \t]{12,}/g, " ")                           // the rest of a wrapped line, indented under its message
      .replace(/[ \t]+\S+\.py(?::\d+)?[ \t]*$/gm, "")
      .replace(/[ \t]{2,}/g, " ")
      .replace(/\n\s*\n/g, "\n")
      .trim();
  }

  /** Raw log text -> [{time, kind, text, count?, items?}], oldest first. Lines without a time stamp belong to the entry above them.
   *  Runs of package-install lines become one entry ("Installed 115 parts"). */
  function parseLog(raw) {
    const out = [];
    let cur = null;
    for (const line of String(raw || "").replace(/\r/g, "").split("\n")) {
      const m = STAMP.exec(line);
      if (m) {
        if (cur) out.push(cur);
        cur = { time: m[1], text: m[2] };
      } else if (cur) {
        cur.text += "\n" + line;
      } else if (line.trim()) {
        cur = { time: "", text: line };
      }
    }
    if (cur) out.push(cur);
    const entries = [];
    for (const e of out) {
      // uvicorn writes several lines at once under one stamp: split those that are themselves log records
      const parts = e.text.split(/\n(?=(?:INFO|WARNING|ERROR|CRITICAL):\s)/);
      for (const part of parts) {
        if (!part.trim()) continue;
        const text0 = tidy(part);
        const kind = kindOf(text0);
        const text = text0;
        if (!text) continue;
        const last = entries[entries.length - 1];
        if (kind === "install" && last && last.kind === "install") {
          last.items.push(text);
          last.count += 1;
          last.text = `Installed ${last.count} parts`;
          continue;
        }
        entries.push(kind === "install" ? { time: e.time, kind, text: "Installed 1 part", items: [text], count: 1 } : { time: e.time, kind, text });
      }
    }
    for (const e of entries) if (e.kind === "install" && e.count === 1) { e.text = e.items[0]; delete e.items; }
    return entries;
  }

  function matches(entry, view, query) {
    if (view === "important" && (entry.kind === "request" || entry.kind === "install")) return false;
    if (view === "problems" && entry.kind !== "problem" && entry.kind !== "warning") return false;
    if (query) {
      const q = query.toLowerCase();
      return entry.text.toLowerCase().includes(q) || (entry.items || []).some((i) => i.toLowerCase().includes(q));
    }
    return true;
  }

  /** The entries a view shows, the newest `limit` of them, and how many were left out. */
  function select(entries, view, query, limit) {
    const shown = entries.filter((e) => matches(e, view, query));
    const hiddenRequests = view === "important" ? entries.filter((e) => e.kind === "request").length : 0;
    return { list: shown.slice(Math.max(0, shown.length - limit)), older: Math.max(0, shown.length - limit), total: shown.length, hiddenRequests,
             problems: entries.filter((e) => e.kind === "problem").length };
  }

  function when(iso) {
    if (!iso) return { day: "", clock: "" };
    const d = new Date(iso);
    if (isNaN(d)) return { day: "", clock: "" };
    return { day: d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" }), clock: d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }) };
  }

  /** Draws the entries into `list` (a <div>). Keeps the person's place unless they were at the bottom. */
  function renderLog(list, entries, opts) {
    const atBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 40;
    const sel = select(entries, opts.view, opts.query, opts.limit);
    const doc = list.ownerDocument;
    const el = (tag, cls, text) => { const n = doc.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
    const frag = doc.createDocumentFragment();
    if (sel.older) {
      const more = el("button", "plain log-more", `Show ${Math.min(sel.older, opts.step)} older`);
      more.onclick = () => opts.onMore();
      frag.append(more);
    }
    let day = "";
    for (const e of sel.list) {
      const t = when(e.time);
      if (t.day && t.day !== day) { day = t.day; frag.append(el("div", "log-day", day)); }
      const row = el("div", "log-row " + e.kind);
      row.append(el("span", "log-time", t.clock), el("span", "log-dot"));
      const body = el("div", "log-text");
      const [first, ...rest] = e.text.split("\n");
      if (e.items || rest.length > 3) {
        const d = el("details");
        d.append(el("summary", null, first));
        d.append(el("pre", null, (e.items || rest).join("\n")));
        body.append(d);
      } else body.textContent = e.text;
      row.append(body);
      frag.append(row);
    }
    if (!sel.list.length) frag.append(el("p", "log-empty", opts.query ? "Nothing matches that search." : opts.view === "problems" ? "No problems. The server is working normally." : "No log entries yet."));
    list.replaceChildren(frag);
    if (atBottom || opts.scrollToEnd) list.scrollTop = list.scrollHeight;
    return sel;
  }

  const api = { parseLog, select, renderLog, kindOf };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.LogView = api;
})(typeof window !== "undefined" ? window : globalThis);
