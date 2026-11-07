import test from 'node:test';
import assert from 'node:assert/strict';
const {applyGesture,turned,reach,bearing}=await import('../src/review/gestures.ts');
const {tidy,hasTransform,withTransform,corners,cropOf,repositionTransform,POINT_KEYS}=await import('../src/review/transformMath.ts');
const {applyPreviewEdit}=await import('../src/review/previewEdits.ts');
const {repositionMotion,sampleMotion}=await import('../src/review/motionMath.ts');
const {saveMotionPoint}=await import('../src/review/motionMath.ts');
const start=(el={},extra={})=>({el:{type:'title',at_word:'w1',...el},center:[540,960],frame:[1080,1920],size:[400,100],...extra});
const near=(a,b,t=1e-3)=>assert.ok(Math.abs(a-b)<=t,`${a} is not ${b}`);

test('nothing set is not a transform, and defaults are dropped from what is set',()=>{
 assert.equal(tidy(null),null);assert.equal(tidy({}),null);assert.equal(tidy({stretch_x:1,flip_x:false,crop:[0,0,0,0],blend:'normal',pivot_x:.5}),null);
 assert.deepEqual(tidy({stretch_x:1.5,skew_y:0,flip_y:true}),{stretch_x:1.5,flip_y:true});
 assert.equal(hasTransform({blur:3}),true);assert.equal(hasTransform({blur:0}),false);
});

test('a value diamond saves the full current pose, including static effects, at the playhead',()=>{
 const el={x:.3,y:.4,scale:1.2,transform:{stretch_x:2,tilt_y:30,blur:4}};
 const points=saveMotionPoint(el,1,0,4,'tilt_y');
 assert.deepEqual(points.map(p=>p.time),[0,1]);
 for(const p of points) {near(p.stretch_x,2);near(p.tilt_y,30);near(p.blur,4);near(p.x,.3);}
 const changed=saveMotionPoint({...el,keyframes:points,transform:{...el.transform,tilt_y:50}},1,0,4,'tilt_y');
 assert.equal(changed.length,2);near(changed[0].tilt_y,30);near(changed[1].tilt_y,50);
 assert.equal(saveMotionPoint(el,99,0,4,'x').at(-1).time,4);
});

test('corner pin follows the pointer through a projective tilt and slant',()=>{
 const size=[400,100],warp=[[.1,0],[0,0],[0,0],[0,0]];
 const local=[[40,0],[400,0],[400,100],[0,100]];
 const project=([x,y])=>[(1.1*x+.3*y+200)/(1+.001*x),(.2*x+.9*y+300)/(1+.001*x)];
 const quad=local.map(project),from=quad[1],target=project([420,12]);
 const p=applyGesture(start({transform:{warp,tilt_y:40,skew_x:20}},{quad,size}),{kind:'pin',corner:1,dx:target[0]-from[0],dy:target[1]-from[1]});
 near(p.transform.warp[1][0],.05);near(p.transform.warp[1][1],.12);
 assert.deepEqual(p.transform.warp[0],warp[0]);
});
test('changing one thing keeps the others, and giving the default takes it away',()=>{
 const el=withTransform({type:'title',at_word:'w1'},{tilt_x:30});assert.deepEqual(el.transform,{tilt_x:30});
 const two=withTransform(el,{skew_x:10});assert.deepEqual(two.transform,{tilt_x:30,skew_x:10});
 assert.equal(withTransform(withTransform(el,{tilt_x:0}),{}).transform,null);
 assert.deepEqual(corners(null),[[0,0],[0,0],[0,0],[0,0]]);assert.deepEqual(cropOf({crop:[.1,0,0,.2]}),[.1,0,0,.2]);
});
test('an element with something set is a hand-placed one in the live preview, and one with nothing set is not',()=>{
 const data=()=>({scenes:[{id:'s1',start:0,end:4,elements:[{type:'title',at:1,_i:0}]}],captions:[]});
 const a=applyPreviewEdit(data(),{kind:'element',scene:'s1',index:0,patch:{transform:{stretch_x:2}}}).scenes[0].elements[0];
 assert.equal(a.free,true);assert.equal(a.until,4);
 const b=applyPreviewEdit(data(),{kind:'element',scene:'s1',index:0,patch:{transform:null}}).scenes[0].elements[0];
 assert.equal(b.free,undefined);
 const c=applyPreviewEdit(data(),{kind:'element',scene:'s1',index:0,patch:{transform:{blur:0,stretch_y:1}}}).scenes[0].elements[0];
 assert.equal(c.free,undefined,'a transform that is all defaults changes nothing');
});
test('moving takes the element where it is first, then moves it by the distance, and stays on the frame',()=>{
 const p=applyGesture(start(),{kind:'move',dx:108,dy:-192});near(p.x,.6);near(p.y,.4);
 const q=applyGesture(start({x:.5,y:.2}),{kind:'move',dx:0,dy:-1e6});assert.equal(q.y,0);
 const r=applyGesture(start({x:.9,y:.5}),{kind:'move',dx:1e6,dy:0});assert.equal(r.x,1);
});
test('resizing multiplies the size, keeps the place, and stays in the range the server takes',()=>{
 const p=applyGesture(start({x:.3,y:.6,scale:1.5}),{kind:'scale',factor:2});near(p.scale,3);near(p.x,.3);near(p.y,.6);
 assert.equal(applyGesture(start({scale:4}),{kind:'scale',factor:10}).scale,5);assert.equal(applyGesture(start({scale:.1}),{kind:'scale',factor:.01}).scale,.05);
 const first=applyGesture(start({},{center:[270,480]}),{kind:'scale',factor:1.2});near(first.x,.25);near(first.y,.25);          // not placed yet: it takes over where it is (a quarter across, a quarter down), so it does not jump
 const moved=applyGesture(start({},{center:[810,1440]}),{kind:'move',dx:0,dy:0});near(moved.x,.75);near(moved.y,.75)
});
test('turning adds the angle and wraps around instead of running past a half turn',()=>{
 near(applyGesture(start({rotation:170}),{kind:'rotate',degrees:30}).rotation,-160);near(applyGesture(start({rotation:-170}),{kind:'rotate',degrees:-30}).rotation,160);
 near(applyGesture(start({rotation:10}),{kind:'rotate',degrees:15}).rotation,25);
 near(turned(350,10),20);near(turned(10,350),-20);near(reach([3,4],[0,0]),5);near(bearing([0,1],[0,0]),90);
});
test('a corner pin moves the corner by the hand, taken back through size and turn into a fraction of the box',()=>{
 const plain=applyGesture(start(),{kind:'pin',corner:0,dx:40,dy:10}).transform.warp;
 near(plain[0][0],40/400);near(plain[0][1],10/100);assert.deepEqual(plain[1],[0,0]);
 const big=applyGesture(start({scale:2}),{kind:'pin',corner:2,dx:80,dy:0}).transform.warp;near(big[2][0],80/2/400);            // twice the size: half the distance in the element's own terms
 const turnedBy=applyGesture(start({rotation:90}),{kind:'pin',corner:1,dx:0,dy:50}).transform.warp;near(turnedBy[1][0],50/400,1e-3);near(turnedBy[1][1],0,1e-3);    // its own x axis now points down the screen
 const twice=applyGesture(start({transform:{warp:[[.1,0],[0,0],[0,0],[0,0]]}}),{kind:'pin',corner:0,dx:40,dy:0}).transform.warp;near(twice[0][0],.2);
 assert.equal(applyGesture(start(),{kind:'pin',corner:3,dx:1e6,dy:-1e6}).transform.warp[3][0],1,'a corner cannot leave the range the server takes');
 near(applyGesture(start({transform:{flip_x:true}}),{kind:'pin',corner:0,dx:40,dy:0}).transform.warp[0][0],-40/400);                // mirrored: the hand and the box go opposite ways
});
test('the whole animated path follows a change of stretch, slant, tilt and blur from the Position tab',()=>{
 const value={x:.5,y:.5,keyframes:[{time:0,x:.2,y:.5,scale:1,rotation:0,opacity:1,stretch_x:1,ease:'linear'},{time:2,x:.8,y:.5,scale:1,rotation:0,opacity:1,stretch_x:2,skew_x:10,ease:'linear'}],transform:null};
 const moved=repositionMotion(value,{transform:{stretch_x:1.5,skew_x:5,blur:4}},.45);
 assert.deepEqual(moved.keyframes.map(p=>p.stretch_x),[1.5,3]);assert.deepEqual(moved.keyframes.map(p=>p.skew_x),[5,15]);assert.deepEqual(moved.keyframes.map(p=>p.blur),[4,4]);
 const still=repositionMotion({keyframes:[]},{transform:{blur:3}},.45);assert.deepEqual(still,{transform:{blur:3}});
 assert.deepEqual(repositionTransform([{stretch_x:1}],null,null),[{stretch_x:1}]);
});
test('a point written before these values existed still means what it meant, and the new values are sampled on the same clock',()=>{
 const a={time:0,x:.2,y:.5,scale:1,rotation:0,opacity:1,ease:'linear'},b={time:2,x:.8,y:.5,scale:1,rotation:0,opacity:1,stretch_x:3,tilt_x:40,blur:10,ease:'linear'};
 const mid=sampleMotion([a,b],1,a);near(mid.stretch_x,2);near(mid.tilt_x,20);near(mid.blur,5);near(mid.skew_x,0);near(mid.x,.5);
 assert.ok(Object.keys(POINT_KEYS).every(k=>k in mid),'a saved point holds every value');
});
