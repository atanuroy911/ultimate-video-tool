// HyperFrames runtime for Cartoon 2 (built to runtime/vt-story.js by ../build.mjs). Pattern of vt-stick.js: the scene is a pure function of time,
// one paused-timeline tween per scene calls draw(t), so seeking any frame gives the same picture.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import { SPEC, STORE, setSpeak } from './data';
import { StoryScene, stageFor } from './StoryScene';

declare global { interface Window { VTX: any } }

function envelopeAt(env: any, t: number) {
  if (!env || !env.v || !env.v.length) return 0;
  return env.v[Math.max(0, Math.min(env.v.length - 1, Math.round(t / env.dt)))];
}

export function prepare(D: any, sc: any) {
  SPEC.characters = D.story_cast || {};
  setSpeak(sc.story.speak || {});
  STORE.lang = D.language || 'en';
  STORE.loud = (t: number) => envelopeAt(D.envelope, t);
  STORE.fonts = D.story_fonts || STORE.fonts;
  Object.assign(STORE.stage, stageFor(D.format.width, D.format.height));
  STORE.uid = 'st-' + (sc.src || sc.id);
}

(function () {
  const X = window.VTX;
  if (!X) return;
  X.story = function (sceneEl: HTMLElement, sc: any, tl: any, D: any, overlay = false) {
    const host = document.createElement('div');
    host.className = overlay ? 'story-overlay' : 'story-stage';
    Object.assign(host.style, { position: 'absolute', inset: '0', overflow: 'hidden', pointerEvents: 'none', zIndex: overlay ? '6' : '0' });
    if (overlay) sceneEl.appendChild(host); else sceneEl.insertBefore(host, sceneEl.firstChild);
    const root = createRoot(host);
    const W = D.format.width, H = D.format.height;
    const scene = { s: sc.start, e: sc.end, bg: sc.story.bg, push: sc.story.push, tag: sc.story.tag, elements: sc.story.items || [] };
    let last = -1;
    const draw = (t: number) => {
      const q = Math.round(t * 30) / 30;                       // one drawing per video frame
      if (q === last) return;
      last = q;
      prepare(D, sc);
      flushSync(() => root.render(<StoryScene scene={scene} t={q} width={W} height={H} chrome={!overlay} />));
    };
    draw(sc.start);
    const span = Math.max(0.001, sc.end - sc.start), proxy = { v: 0 };
    tl.fromTo(proxy, { v: 0 }, { v: 1, duration: span, ease: 'none', onUpdate: function (this: any) { draw(sc.start + this.ratio * span); }, onStart: () => draw(sc.start) }, sc.start);
    tl.call(() => draw(sc.end - 0.001), null, sc.end - 0.001);
  };
})();
