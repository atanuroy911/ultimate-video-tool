import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

test('every video occurrence has a stable unique DOM id for renderer frame injection',()=>{
  const X={C:{}};
  const context={window:{VTX:X},document:{createElement:tag=>({tag,style:{},setAttribute(){}})}};
  vm.runInNewContext(fs.readFileSync(new URL('../../../server/renderer/runtime/vt-media.js',import.meta.url),'utf8'),context);
  const data={media:{source:{kind:'video',src:'media/source.mp4'}}};
  const first=X.mediaNode(data,'source','background').node;
  const second=X.mediaNode(data,'source','layer').node;
  assert.match(first.id,/^vt-video-/);
  assert.notEqual(first.id,second.id,'Repeated use of one media item must not share an injection target');
  X.nextVideoId=0;
  assert.equal(X.mediaNode(data,'source','background').node.id,first.id,'Rebuilding the same composition has deterministic ids');
});
