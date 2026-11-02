import test from 'node:test';
import assert from 'node:assert/strict';
const {applyPreviewEdit}=await import('../src/review/previewEdits.ts');
const {newSceneElement}=await import('../src/review/componentOps.ts');
const data=()=>({scenes:[{id:'s1',start:0,end:2,elements:[{type:'title',text:'Old',at:0,_i:0}]},{id:'s2',start:2,end:5,elements:[]}],captions:[{start:0,end:1,words:[{id:'w1',text:'walk',start:0,end:1}]}]});
test('a visual draft keeps its exact range even beyond its original scene and leaves saved data untouched',()=>{
 const d=data();const n=applyPreviewEdit(d,{kind:'element',scene:'s1',index:0,patch:{start:2.137,end:4.321,x:.2,opacity:.5,text:'New'}});
 assert.equal(n.scenes[0].elements[0].at,2.137);assert.equal(n.scenes[0].elements[0].until,4.321);assert.equal(n.scenes[0].elements[0].free,true);assert.equal(d.scenes[0].elements[0].text,'Old');
});
test('scene-edge preview updates both neighbours at exactly the chosen instant',()=>{
 const d=applyPreviewEdit(data(),{kind:'edge',left:'s1',right:'s2',t:1.137});assert.equal(d.scenes[0].end,1.137);assert.equal(d.scenes[1].start,1.137);
});
test('caption typing and timing update the live data by stable word id',()=>{
 const d=applyPreviewEdit(data(),{kind:'word',id:'w1',text:'run',start:1.237,end:1.937});assert.deepEqual(d.captions[0].words[0],{id:'w1',text:'run',start:1.237,end:1.937});
});
test('library insertion clones its starter and uses actual project media',()=>{
 const spec={type:'media_frame',starter:{type:'media_frame',at_word:'w99',media:'sample',caption:'Picture'}};
 const el=newSceneElement(spec,'w2',[{id:'real-video',kind:'video'}]);assert.equal(el.media,'real-video');assert.equal(el.at_word,'w2');assert.equal(spec.starter.media,'sample');assert.throws(()=>newSceneElement(spec,'w2',[]),/Add a picture/);
});
