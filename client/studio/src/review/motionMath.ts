import type { MotionPoint } from "../types";

/** Reposition an entire animated path when the ordinary Position controls change. */
export function repositionMotion(value: Record<string,any>, patch: Record<string,any>, defaultY=.5): Record<string,any> {
  if (!value.keyframes?.length || 'keyframes' in patch) return patch;
  const limits={x:[-.5,1.5,.5],y:[-.5,1.5,defaultY],scale:[.05,5,1],rotation:[-360,360,0],opacity:[0,1,1]};
  const keys=Object.keys(limits).filter(k=>typeof patch[k]==='number');
  if(!keys.length) return patch;
  return {...patch,keyframes:value.keyframes.map((p:MotionPoint)=>{
    const next={...p};
    for(const key of keys as (keyof typeof limits)[]) {
      const [min,max,fallback]=limits[key];
      const previous=value[key]??fallback;
      next[key]=Math.max(min,Math.min(max,key==='scale'?p[key]*patch[key]/previous:p[key]+patch[key]-previous));
    }
    return next;
  })};
}

/** Same easing and absolute clock as the exported GSAP animation. */
export function sampleMotion(points: MotionPoint[], time: number, fallback: MotionPoint): MotionPoint {
  if (!points.length) return {...fallback,time};
  if (time <= points[0].time) return {...points[0],time};
  const i = points.findIndex(p => p.time >= time);
  if (i < 0) return {...points[points.length-1],time};
  const a=points[i-1], b=points[i], t=(time-a.time)/(b.time-a.time);
  const u=b.ease==='hold'?(t<1?0:1):b.ease==='smooth'?(1-Math.cos(Math.PI*t))/2:b.ease==='in'?t*t*t:b.ease==='out'?1-(1-t)**3:t;
  const result={...b,time};
  for (const key of ['x','y','scale','rotation','opacity'] as const) result[key]=a[key]+(b[key]-a[key])*u;
  return result;
}
