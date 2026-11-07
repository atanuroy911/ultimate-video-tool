import type { MotionPoint } from "../types";
import { POINT_KEYS, repositionTransform } from "./transformMath.ts";

/** Save a value at the playhead without changing any other animation points. */
export function saveMotionPoint(value: Record<string, any>, time: number, start: number, end: number, key?: keyof typeof POINT_KEYS): MotionPoint[] {
  const at = Math.round(Math.max(start, Math.min(end, time)) * 1000) / 1000;
  const pose: any = {time: at, ease: "smooth"};
  for (const name of Object.keys(POINT_KEYS) as (keyof typeof POINT_KEYS)[])
    pose[name] = value[name] ?? value.transform?.[name] ?? POINT_KEYS[name][2];
  let points: MotionPoint[] = value.keyframes ?? [];
  const current = sampleMotion(points, at, pose);
  if (key) (current as any)[key] = pose[key];
  const existing = points.findIndex(p => Math.abs(p.time - at) < .001);
  if (existing >= 0) return points.map((p, i) => i === existing ? current : p);
  if (points.length >= 100) return points;
  if (!points.length && at > start) points = [{...pose, time: start}];
  return [...points, current].sort((a,b) => a.time-b.time);
}

/** Reposition an entire animated path when the ordinary Position controls change. */
export function repositionMotion(value: Record<string,any>, patch: Record<string,any>, defaultY=.5): Record<string,any> {
  if (!value.keyframes?.length || 'keyframes' in patch) return patch;
  const limits={x:[-.5,1.5,.5],y:[-.5,1.5,defaultY],scale:[.05,5,1],rotation:[-360,360,0],opacity:[0,1,1]};
  const keys=Object.keys(limits).filter(k=>typeof patch[k]==='number');
  if(!keys.length && !('transform' in patch)) return patch;
  let points:Record<string,any>[]=value.keyframes.map((p:MotionPoint)=>{
    const next:Record<string,any>={...p};
    for(const key of keys as (keyof typeof limits)[]) {
      const [min,max,fallback]=limits[key];
      const previous=value[key]??fallback;
      next[key]=Math.max(min,Math.min(max,key==='scale'?p[key]*patch[key]/previous:p[key]+patch[key]-previous));
    }
    return next;
  });
  if('transform' in patch) points=repositionTransform(points,value.transform,patch.transform);        // stretch, slant, tilt and blur move the whole path too
  return {...patch,keyframes:points};
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
  for (const key of Object.keys(POINT_KEYS) as (keyof typeof POINT_KEYS)[]) {
    const from=(a as any)[key]??POINT_KEYS[key][2], to=(b as any)[key]??POINT_KEYS[key][2];
    (result as any)[key]=from+(to-from)*u;
  }
  return result;
}
