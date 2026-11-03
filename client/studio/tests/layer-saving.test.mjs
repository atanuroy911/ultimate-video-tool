import test from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import React from 'react';

// Node's native TypeScript loader, with the same extensionless imports as Vite.
registerHooks({ resolve(id, context, next) {
  try { return next(id, context); }
  catch (error) { if (id.startsWith('.')) return next(`${id}.ts`, context); throw error; }
} });
globalThis.localStorage = { getItem: () => null };
const { useLayers } = await import('../src/review/useLayers.ts');
const { emitChanged } = await import('../src/store.ts');

// A deterministic hook runner: real useLayers, API client and change bus, with
// deferred HTTP responses. No browser, wall-clock sleeps or network required.
function mount() {
  const slots = [], effects = [], requests = [];
  let index = 0, value, edits = 0;
  const equal = (a,b) => a?.length === b?.length && a.every((x,i) => Object.is(x,b[i]));
  const dispatcher = {
    useState(initial) {
      const i=index++; slots[i] ??= { value: typeof initial === 'function' ? initial() : initial };
      return [slots[i].value, next => { slots[i].value=typeof next==='function' ? next(slots[i].value) : next; }];
    },
    useRef(initial) { const i=index++; return slots[i] ??= {current:initial}; },
    useCallback(fn,deps) {
      const i=index++; if (!slots[i] || !equal(slots[i].deps,deps)) slots[i]={fn,deps}; return slots[i].fn;
    },
    useEffect(fn,deps) {
      const i=index++;
      if (!slots[i] || !equal(slots[i].deps,deps)) effects.push(() => { slots[i]?.cleanup?.(); slots[i]={deps,cleanup:fn()}; });
    },
  };
  const previousFetch=globalThis.fetch;
  globalThis.fetch=(url,options) => new Promise(resolve => requests.push({url,options,reply(doc,status=200) {
    resolve(new Response(JSON.stringify(status===200 ? {doc,duration:10,can_undo:true,can_redo:false} : {detail:'Rejected edit'}),{status}));
  }}));
  const render=() => {
    const internals=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
    const previous=internals.ReactCurrentDispatcher.current;
    index=0; internals.ReactCurrentDispatcher.current=dispatcher;
    try { value=useLayers('qa',()=>edits++); }
    finally { internals.ReactCurrentDispatcher.current=previous; }
    effects.splice(0).forEach(fn=>fn());
    return value;
  };
  return {render,requests,get edits(){return edits;},close(){slots.forEach(s=>s?.cleanup?.());globalThis.fetch=previousFetch;}};
}
const settle=() => new Promise(resolve=>setImmediate(resolve));
const doc=n=>({v:1,tracks:[],clips:[{id:'draft',text:`version ${n}`}]});

test('a GET started before typing cannot overwrite the newer local draft', async () => {
  const h=mount(); try {
    h.render().setLocal(doc(2));
    h.requests.shift().reply(doc(1)); await settle();
    assert.deepEqual(h.render().doc,doc(2));
  } finally {h.close();}
});

test('an earlier save cannot reset a second drag; final release saves the latest draft', async () => {
  const h=mount(); try {
    h.render(); h.requests.shift().reply(doc(0)); await settle();
    h.render().commit(doc(1));
    const first=h.requests.shift();
    h.render().hold(true); h.render().setLocal(doc(2));
    first.reply(doc(1)); await settle();
    assert.deepEqual(h.render().doc,doc(2));
    h.render().hold(false); h.render().commit();
    const last=h.requests.shift(); assert.deepEqual(JSON.parse(last.options.body).doc,doc(2));
    last.reply(doc(2)); await settle();
    assert.deepEqual(h.render().doc,doc(2)); assert.equal(h.edits,2);
  } finally {h.close();}
});

test('returning to the last saved value while a PUT is in flight still saves that return', async () => {
  const h=mount(); try {
    h.render(); h.requests.shift().reply(doc(0)); await settle();
    h.render().commit(doc(1)); const first=h.requests.shift();
    h.render().commit(doc(0)); first.reply(doc(1)); await settle();
    const last=h.requests.shift(); assert.ok(last);
    assert.deepEqual(JSON.parse(last.options.body).doc,doc(0));
    last.reply(doc(0)); await settle(); assert.deepEqual(h.render().doc,doc(0));
  } finally {h.close();}
});

test('server change notifications leave an unsaved text/slider draft alone', async () => {
  const h=mount(); try {
    h.render(); h.requests.shift().reply(doc(0)); await settle();
    h.render().setLocal(doc(1)); emitChanged('qa');
    assert.equal(h.requests.length,0); assert.deepEqual(h.render().doc,doc(1));
  } finally {h.close();}
});

test('a no-op save queued behind the same document adds no phantom undo step', async () => {
  const h=mount(); try {
    h.render(); h.requests.shift().reply(doc(0)); await settle();
    h.render().commit(doc(1)); const first=h.requests.shift();
    h.render().commit(doc(1)); first.reply(doc(1)); await settle();
    h.requests.shift().reply(doc(1)); await settle();
    assert.equal(h.edits,1);
  } finally {h.close();}
});
