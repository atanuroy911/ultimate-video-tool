/* Which graphics cards Video Tool may use, for the server's own pages (the overview at / and Server settings at /manage): the same question and the same answers as the Studio's
   Server page (vt/gpuassign.py, /api/system/gpus). Put <div data-gpu-choice></div> where it belongs. Plain English, text set with textContent only. */
(function () {
  const css = document.createElement('style');
  css.textContent = `
.gc{display:flex;flex-direction:column;gap:10px}.gc h2{margin:0}.gc p{margin:0}.gc .gc-note{padding:10px 14px;border-radius:12px;background:#e8f1fd;color:#14305a;font-size:14px;line-height:1.45}
.gc .gc-warn{background:#fff3da;color:#5a3a00}.gc ul{list-style:none;margin:0;padding:0}.gc li{display:flex;align-items:center;gap:12px;min-height:44px;padding:8px 0;border-top:1px solid #e3e8f0}
.gc li:first-child{border-top:0}.gc li.gc-engine{flex-wrap:wrap}.gc li.gc-engine .gc-text{flex:1 1 260px}.gc .gc-text{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}.gc .gc-small{font-size:13px;color:#66748c}
.gc button.gc-switch{position:relative;flex:none;width:46px;height:28px;padding:0;border:0;border-radius:999px;background:#d6dbe4;cursor:pointer;transition:background .2s}
.gc button.gc-switch::after{content:"";position:absolute;top:2px;left:2px;width:24px;height:24px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.35);transition:transform .2s}
.gc button.gc-switch[aria-checked="true"]{background:#34c759}.gc button.gc-switch[aria-checked="true"]::after{transform:translateX(18px)}.gc button.gc-switch:disabled{opacity:.5;cursor:default}
.gc button.gc-switch:focus-visible,.gc button.gc-btn:focus-visible{outline:3px solid #2563eb;outline-offset:2px}.gc .gc-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.gc button.gc-btn{min-height:44px;padding:0 16px;border:0;border-radius:10px;background:#e9edf4;color:#1c2941;font:600 14px system-ui,sans-serif;cursor:pointer;align-self:flex-start}.gc button.gc-btn:disabled{opacity:.5}
.gc .gc-err{color:#ae382b}@media (prefers-reduced-motion:reduce){.gc button.gc-switch,.gc button.gc-switch::after{transition:none}}`;
  document.head.append(css);

  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
  async function api(route, method, body) {
    const r = await fetch(route, { method: method || 'GET', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'This could not be saved.');
    return d;
  }
  const understood = (d) => d && Array.isArray(d.cards) && typeof d.needs_choice === 'boolean' && d.cards.every((c) => Array.isArray(c.using));
  const using = (c) => c.using.length
    ? c.using.map((p) => (p.ours ? 'Video Tool is using ' + (p.gb ? p.gb + ' GB' : 'it') + '.' : p.label + ' is using ' + (p.gb ? p.gb + ' GB' : 'it') + '.')).join(' ')
    : 'Nothing else is using it.';
  const ENGINE = { ollama: 'Language AI (Ollama)', comfy: 'Pictures & clips (ComfyUI)' };

  function mount(root) {
    root.classList.add('gc');
    const live = el('p', '', 'gc-sr'); live.setAttribute('role', 'status'); live.setAttribute('aria-atomic', 'true');
    let data = null, saving = false, failed = '';
    const say = (text) => { live.textContent = text; };

    async function load() {
      const was = JSON.stringify([data, failed]);
      try { const d = await api('/api/system/gpus'); data = understood(d) ? d : null; failed = data ? '' : 'this server is older than this page'; } catch (e) { failed = e.message; }
      if (JSON.stringify([data, failed]) !== was || !root.firstChild) render();                  // the same answer redraws nothing: a switch someone is on keeps the keyboard
    }
    async function save(patch, message) {
      saving = true; render();
      try { const d = await api('/api/system/gpu', 'PUT', patch); data = understood(d) ? d : data; say(message(data)); failed = ''; } catch (e) { failed = e.message; }
      saving = false; render();
    }
    const on = () => (data ? data.cards.filter((c) => c.allowed) : []);
    const allowedNames = () => on().map((c) => c.name).join(', ') || 'no card';

    let lastFocus = '';                                                                          // the control the keyboard was on, until it can be given back (it is disabled while saving)
    function render() {
      const inside = document.activeElement && root.contains(document.activeElement);
      if (inside && document.activeElement.dataset.testid) lastFocus = document.activeElement.dataset.testid;
      else if (!inside && document.activeElement !== document.body) lastFocus = '';              // the person went somewhere else: leave them there
      draw();
      const back = lastFocus && root.querySelector('[data-testid="' + lastFocus + '"]');
      if (back && !back.disabled) { back.focus(); lastFocus = ''; }
    }
    function draw() {
      root.replaceChildren();
      root.append(el('h2', 'Graphics cards'));
      if (!data) {
        root.append(el('p', failed ? 'This server cannot choose graphics cards yet. Update the server to use this. (' + failed + ')' : 'Reading the graphics cards…', failed ? 'gc-err' : 'gc-small'), live);
        return;
      }
      if (!data.cards.length) { root.append(el('p', 'This computer has no NVIDIA graphics card, so rendering and speech recognition run on the processor.', 'gc-small'), live); return; }
      root.append(el('p', 'Video Tool only uses the cards you switch on. The other cards stay free for your own programs.'));
      if (data.needs_choice) {
        const note = el('div', undefined, 'gc-note'); note.setAttribute('role', 'note'); note.dataset.testid = 'gpu-needs-choice';
        note.append(el('p', 'Nobody has chosen yet. Until you do, Video Tool uses one card only: ' + allowedNames() + '.'));
        const keep = el('button', 'Keep this', 'gc-btn'); keep.disabled = saving; keep.dataset.testid = 'gpu-keep';
        keep.onclick = () => save({ allowed: on().map((c) => c.uuid) }, () => 'Video Tool may now use: ' + allowedNames() + '.');
        note.append(keep); root.append(note);
      } else if (!on().length) {
        const w = el('p', 'No card is switched on, so Video Tool does everything on the processor. That works, but it is much slower.', 'gc-note gc-warn'); w.setAttribute('role', 'note'); root.append(w);
      }
      if (data.restart_needed) { const n = el('p', 'Programs that Video Tool already started keep their old cards until the server is restarted.', 'gc-note'); n.setAttribute('role', 'note'); root.append(n); }
      root.append(el('h3', 'Switch on the cards Video Tool may use'));
      const list = el('ul'); list.dataset.testid = 'gpu-cards';
      for (const c of data.cards) {
        const li = el('li'); li.dataset.testid = 'gpu-card-' + c.index;
        const text = el('span', undefined, 'gc-text');
        text.append(el('strong', 'GPU ' + c.index + ': ' + c.name), el('span', c.free_gb + ' of ' + c.total_gb + ' GB free', 'gc-small'), el('span', using(c), 'gc-small'));
        const sw = el('button', undefined, 'gc-switch'); sw.type = 'button'; sw.setAttribute('role', 'switch'); sw.setAttribute('aria-checked', String(c.allowed));
        sw.setAttribute('aria-label', 'Video Tool may use this card: ' + c.name); sw.disabled = saving; sw.dataset.testid = 'gpu-switch-' + c.index;
        sw.onclick = () => save({ allowed: c.allowed ? on().filter((x) => x.uuid !== c.uuid).map((x) => x.uuid) : on().map((x) => x.uuid).concat(c.uuid) }, () => 'Video Tool may now use: ' + allowedNames() + '.');
        li.append(text, sw); list.append(li);
      }
      root.append(list);
      const rows = (data.engines || []);
      if (rows.length) {
        root.append(el('h3', 'Programs Video Tool works with'));
        const ul = el('ul'); ul.dataset.testid = 'gpu-engines';
        for (const e of rows) {
          const li = el('li', undefined, 'gc-engine'); li.dataset.testid = 'engine-' + e.id;
          const t = el('span', undefined, 'gc-text'); t.append(el('strong', ENGINE[e.id] || e.label), el('span', e.message, 'gc-small'));
          if (e.offer_own && !e.own_installed) t.append(el('span', "Video Tool's own copy is not installed yet. Install it under Engines.", 'gc-small'));
          li.append(t);
          if (e.offer_own && e.own_installed) {
            const b = el('button', "Use Video Tool's own copy", 'gc-btn'); b.dataset.testid = 'engine-' + e.id + '-own';
            b.onclick = async () => { b.disabled = true; try { await api('/api/system/engine-own', 'POST', { engine: e.id }); say("Video Tool's own " + (ENGINE[e.id] || e.id) + ' is starting. It takes a minute.'); await load(); } catch (x) { failed = x.message; render(); } };
            li.append(b);
          }
          ul.append(li);
        }
        root.append(ul);
      }
      if (failed) root.append(el('p', failed, 'gc-err'));
      root.append(live);
    }
    load();
    setInterval(() => { if (!saving && !document.hidden) load(); }, 6000);
  }

  window.vtGpuChoice = { mount };
  for (const root of document.querySelectorAll('[data-gpu-choice]')) mount(root);
})();
