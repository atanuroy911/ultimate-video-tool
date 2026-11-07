/* Motion on the video clock. Seekable in preview and export. */
(function () {
  const X = window.VTX;
  const eases = {linear:"none",smooth:"sine.inOut",in:"power2.in",out:"power2.out"};

  /* The look of an element a person (or a director) placed by hand: size, stretch, rotation, slant, flip, 3D tilt around a pivot, opacity, blur, blend, a crop with rounded corners and a
     corner-pin warp (plan step E17). One function builds it for the preview, the editor and the export, so they cannot differ. `position` carries what GSAP can animate (and
     keyframes tween it); `shape` sits inside it and carries the crop and the warp. */
  X.look = (position, shape, e, W, H) => {
    const t = e.transform || {}, s = e.scale ?? 1;
    gsap.set(position, {
      xPercent: -50, yPercent: -50, scaleX: s * (t.stretch_x ?? 1) * (t.flip_x ? -1 : 1), scaleY: s * (t.stretch_y ?? 1) * (t.flip_y ? -1 : 1), rotation: e.rotation || 0,
      skewX: t.skew_x || 0, skewY: t.skew_y || 0, rotationX: t.tilt_x || 0, rotationY: t.tilt_y || 0, transformPerspective: 1000,
      transformOrigin: ((t.pivot_x ?? .5) * 100) + "% " + ((t.pivot_y ?? .5) * 100) + "%", opacity: e.opacity ?? 1,
    });
    if (t.blur) position.style.filter = "blur(" + t.blur + "px)";
    if (t.blend && t.blend !== "normal") position.style.mixBlendMode = t.blend;
    if (shape && ((t.crop && t.crop.some((n) => n > 0)) || t.crop_radius || t.warp)) {
      shape.style.display = "block";
      if (t.crop_radius || (t.crop && t.crop.some((n) => n > 0))) shape.style.clipPath = "inset(" + (t.crop || [0,0,0,0]).map((n) => (n * 100).toFixed(2) + "%").join(" ") + (t.crop_radius ? " round " + (t.crop_radius * 50).toFixed(2) + "%" : "") + ")";
      if (t.warp) (X.lateLooks = X.lateLooks || []).push(() => X.warp(shape, t.warp));       // the corners are in pixels: the box is known once the fonts are in
    }
  };

  /* Corner pin: the box's four corners move by [dx, dy] (fractions of its own size) and the picture follows, as a projective transform. */
  X.warp = (shape, corners) => {
    const w = shape.offsetWidth, h = shape.offsetHeight;
    if (!w || !h) return;
    const src = [[0, 0], [w, 0], [w, h], [0, h]], dst = src.map(([x, y], i) => [x + corners[i][0] * w, y + corners[i][1] * h]);
    const A = [], b = [];
    for (let i = 0; i < 4; i++) {
      const [x, y] = src[i], [u, v] = dst[i];
      A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
      A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
    }
    const n = 8;
    for (let c = 0; c < n; c++) {                                              // Gauss-Jordan with the largest pivot
      let p = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
      [A[c], A[p]] = [A[p], A[c]]; [b[c], b[p]] = [b[p], b[c]];
      if (Math.abs(A[c][c]) < 1e-9) return;                                    // the corners fold over each other: leave it flat
      for (let r = 0; r < n; r++) {
        if (r === c) continue;
        const f = A[r][c] / A[c][c];
        for (let k = c; k < n; k++) A[r][k] -= f * A[c][k];
        b[r] -= f * b[c];
      }
    }
    const [a1, a2, a3, b1, b2, b3, c1, c2] = b.map((v, i) => v / A[i][i]);
    shape.style.transformOrigin = "0 0";
    shape.style.transform = `matrix3d(${a1},${b1},0,${c1},${a2},${b2},0,${c2},0,0,1,0,${a3},${b3},0,1)`;
  };

  X.keyframes = (tl, target, frames, W, H, flip) => {
    if(!frames?.length) return;
    const fx = flip && flip.x ? -1 : 1, fy = flip && flip.y ? -1 : 1;
    const state = p => ({left:p.x*W,top:p.y*H,scaleX:p.scale*(p.stretch_x??1)*fx,scaleY:p.scale*(p.stretch_y??1)*fy,rotation:p.rotation,skewX:p.skew_x??0,skewY:p.skew_y??0,
                         rotationX:p.tilt_x??0,rotationY:p.tilt_y??0,opacity:p.opacity,filter:"blur("+(p.blur??0)+"px)"});
    tl.set(target,state(frames[0]),0);
    for(let i=1;i<frames.length;i++) {
      const a=frames[i-1], b=frames[i];
      if(b.time<=0) {tl.set(target,state(b),0);continue;}
      if(b.ease==="hold") tl.set(target,state(b),b.time);
      else {
        const ease=gsap.parseEase(eases[b.ease]||"none"), clipped=Math.max(0,-a.time/(b.time-a.time)), progress=ease(clipped);
        const initial=state(a), finish=state(b);
        for(const key of Object.keys(initial)) if(typeof initial[key]==="number") initial[key]+=(finish[key]-initial[key])*progress;
        const segmentEase=clipped ? u=>(ease(clipped+(1-clipped)*u)-progress)/(1-progress||1) : ease;
        tl.fromTo(target,initial,{...finish,duration:b.time-Math.max(0,a.time),ease:segmentEase,immediateRender:false},Math.max(0,a.time));
      }
    }
  };
})();
