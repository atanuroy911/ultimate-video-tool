import test from 'node:test';
import assert from 'node:assert/strict';
const source = name => import(new URL(`../src/review/${name}.ts`, import.meta.url));
const ops = await source('layerOps');
const { pointerDrag } = await source('pointerDrag');
const doc = () => ({v:1,tracks:[{id:'v',kind:'visual',name:'Pictures',locked:false,hidden:false,muted:false}],clips:[
  {id:'c',track:'v',type:'media',media:'video',start:2,dur:4,in:3,fade_in:1,fade_out:1},
]});

test('trimming the start preserves the end and advances the source footage by the same amount', () => {
  const c = ops.trim(doc(),'c','start',3.275,10,12).clips[0];
  assert.equal(c.start,3.275); assert.equal(c.dur,2.725); assert.equal(c.in,4.275);
  assert.equal(c.start+c.dur,6);
});
test('trimming respects source and neighbouring clips; shortening keeps fades inside the clip', () => {
  const d=doc(); d.clips.push({...d.clips[0],id:'next',start:7,dur:2});
  assert.equal(ops.trim(d,'c','end',9,10,12).clips[0].dur,5);
  assert.equal(ops.trim(d,'c','end',9,10,6).clips[0].dur,3);
  const short=ops.trim(d,'c','end',2.4,10,12).clips[0];
  assert.ok(short.fade_in+short.fade_out<=short.dur+1e-9);
  assert.equal(ops.trim(d,'c','start',-5,10,12).clips[0].start,0);
});
test('split is exactly at the requested time and the second clip continues the same footage', () => {
  const r=ops.split(doc(),'c',3.137);
  const [a,b]=r.doc.clips;
  assert.equal(a.start+a.dur,3.137); assert.equal(b.start,3.137);
  assert.equal(b.in,4.137); assert.equal(a.dur+b.dur,4);
  assert.equal(a.fade_out,0); assert.equal(b.fade_in,0);
  assert.equal(ops.split(doc(),'c',1),null);
});
test('locked clips cannot be split, trimmed, moved or removed', () => {
  const d=doc(); d.tracks[0].locked=true;
  assert.equal(ops.split(d,'c',4),null);
  assert.equal(ops.trim(d,'c','end',3,10,12),d);
  assert.equal(ops.move(d,'c',0,'v',10),null);
  assert.equal(ops.remove(d,'c').clips.length,1);
  assert.equal(ops.duplicate(d,'c',10),null);
  assert.equal(ops.patchClip(d,'c',{opacity:0}).clips[0].opacity,undefined);
  assert.equal(ops.removeTrack(d,'v'),d);
});

function gesture() {
  globalThis.window=new EventTarget();
  const classes=new Set(), frames=new Map(); let frameId=0;
  globalThis.document={body:{classList:{add:c=>classes.add(c),remove:c=>classes.delete(c)}}};
  globalThis.requestAnimationFrame=f=>{frames.set(++frameId,f);return frameId;};
  globalThis.cancelAnimationFrame=id=>frames.delete(id);
  const send=(type,x=0,pointerId=1,key)=>{
    const e=new Event(type,{cancelable:true}); Object.assign(e,{clientX:x,clientY:0,pointerId,key}); window.dispatchEvent(e);
  };
  return {send,classes,frames,start:{clientX:0,clientY:0,pointerId:1,target:null}};
}
test('a fast drag saves the release coordinate even before the last frame runs', () => {
  const g=gesture(), positions=[]; let saved;
  pointerDrag(g.start,e=>positions.push(e.clientX),(_e,moved)=>{saved=positions.at(-1);assert.equal(moved,true);});
  g.send('pointermove',40); g.send('pointerup',57);
  assert.equal(saved,57); assert.deepEqual(positions,[57]); assert.equal(g.frames.size,0); assert.equal(g.classes.size,0);
});
test('cancelled drag restores instead of committing, and queued frames are discarded', () => {
  const g=gesture(); let saved=0,cancelled=0,moves=0;
  pointerDrag(g.start,()=>moves++,()=>saved++,()=>cancelled++);
  g.send('pointermove',50); g.send('keydown',0,1,'Escape'); g.send('pointerup',60);
  assert.equal(saved,0); assert.equal(cancelled,1); assert.equal(moves,0); assert.equal(g.frames.size,0);
});
test('release still saves a fast drag when no intermediate move event arrived', () => {
  const g=gesture(); let position, committed;
  pointerDrag(g.start,e=>position=e.clientX,(_e,moved)=>committed=moved);
  g.send('pointerup',37);
  assert.equal(position,37); assert.equal(committed,true);
});
test('a click is not a trim; other pointers cannot finish the current drag', () => {
  const g=gesture(); let moved, commits=0;
  pointerDrag(g.start,()=>{},(_e,m)=>{moved=m;commits++;});
  g.send('pointercancel',100,2);
  g.send('pointerup',100,2); assert.equal(commits,0);
  g.send('pointerup',0); assert.equal(moved,false); assert.equal(commits,1);
});
