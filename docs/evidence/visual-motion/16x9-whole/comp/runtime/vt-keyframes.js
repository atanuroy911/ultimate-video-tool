/* Motion on the video clock. Seekable in preview and export. */
(function () {
  const X = window.VTX;
  const eases = {linear:"none",smooth:"sine.inOut",in:"power2.in",out:"power2.out"};
  X.keyframes = (tl, target, frames, W, H) => {
    if(!frames?.length) return;
    const state = p => ({left:p.x*W,top:p.y*H,scale:p.scale,rotation:p.rotation,opacity:p.opacity});
    tl.set(target,state(frames[0]),0);
    for(let i=1;i<frames.length;i++) {
      const a=frames[i-1], b=frames[i];
      if(b.time<=0) {tl.set(target,state(b),0);continue;}
      if(b.ease==="hold") tl.set(target,state(b),b.time);
      else {
        const ease=gsap.parseEase(eases[b.ease]||"none"), clipped=Math.max(0,-a.time/(b.time-a.time)), progress=ease(clipped);
        const initial=state(a), finish=state(b);
        for(const key of Object.keys(initial)) initial[key]+=(finish[key]-initial[key])*progress;
        const segmentEase=clipped ? u=>(ease(clipped+(1-clipped)*u)-progress)/(1-progress||1) : ease;
        tl.fromTo(target,initial,{...finish,duration:b.time-Math.max(0,a.time),ease:segmentEase,immediateRender:false},Math.max(0,a.time));
      }
    }
  };
})();
