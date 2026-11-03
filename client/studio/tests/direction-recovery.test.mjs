import test from 'node:test';
import assert from 'node:assert/strict';
import { DirectionDrafts } from '../src/review/directionDrafts.ts';

const scene='/api/projects/disposable/scenes/s1';
const direction={instructions:'Keep this writing',director:'configured',director_model:'',picture_prompt:'A plant',picture_recipe:'',video_prompt:'',video_workflow:'ltx23_i2v',source_image:'',voice_engine:'auto',voice:'auto',narration:'A little water.'};
const storage=()=>{const values=new Map();return {values,getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};};

test('unsaved directions and a generation survive a new panel instance with the original revision',()=>{
  const disk=storage();
  const first=new DirectionDrafts('server-a',disk);
  first.save(scene,{revision:7,direction});first.track(scene,'generation-42');
  const reloaded=new DirectionDrafts('server-a',disk);
  assert.deepEqual(reloaded.draft(scene),{revision:7,direction});
  assert.equal(reloaded.job(scene),'generation-42');
  reloaded.save(scene,null);reloaded.track(scene,null);
  assert.equal(new DirectionDrafts('server-a',disk).draft(scene),null);
  assert.equal(new DirectionDrafts('server-a',disk).job(scene),null);
  assert.equal(disk.values.size,0);
});

test('identical scene IDs on different processing servers never share drafts or jobs',()=>{
  const disk=storage();const first=new DirectionDrafts('server-one',disk),other=new DirectionDrafts('server-two',disk);
  first.save(scene,{revision:0,direction});first.track(scene,'job-one');
  assert.equal(other.draft(scene),null);assert.equal(other.job(scene),null);
  assert.equal(first.draft(scene+'/different'),null);
});

test('damaged recovery data is ignored and disabled storage keeps in-session writing',()=>{
  const disk=storage();const drafts=new DirectionDrafts('corrupt-test',disk);
  drafts.save(scene,{revision:2,direction});
  const key=[...disk.values.keys()][0];disk.values.set(key,'{"revision":3,"direction":{"instructions":"partial"}}');
  assert.equal(drafts.draft(scene),null);disk.values.set(key,'not json');assert.equal(drafts.draft(scene),null);
  const blocked={getItem(){throw Error('blocked');},setItem(){throw Error('full');},removeItem(){throw Error('blocked');}};
  const fallback=new DirectionDrafts('private-test',blocked);fallback.save(scene,{revision:4,direction});
  assert.deepEqual(new DirectionDrafts('private-test',blocked).draft(scene),{revision:4,direction});
  fallback.save(scene,null);assert.equal(fallback.draft(scene),null);
});
