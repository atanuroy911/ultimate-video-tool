import { useEffect, useRef, useState } from "react";
import { get } from "../api";
const samples=new Map<string,Promise<{url:string}>>();
export default function ElementExample({kind,variant=""}:{kind:string;variant?:string}) {
  const key=`${kind}:${variant}`;
  const [url,setUrl]=useState("");const [error,setError]=useState("");const frame=useRef<HTMLIFrameElement>(null);
  useEffect(()=>{let live=true;setUrl("");setError("");if(!samples.has(key)) samples.set(key,get<{url:string}>(`/api/elements/${kind}/preview?variant=${encodeURIComponent(variant)}`).catch(e=>{samples.delete(key);throw e;}));
    samples.get(key)!.then(data=>{if(live) setUrl(data.url);}).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[key,kind,variant]);
  const play=()=>frame.current?.contentWindow?.postMessage(window.matchMedia("(prefers-reduced-motion: reduce)").matches?{vt:"seek",t:1.5}:{vt:"play",t:0},window.location.origin);
  useEffect(()=>{if(!url) return;const loop=window.setInterval(play,4000);return()=>window.clearInterval(loop);},[url]);
  return <div className="element-example">{error?<p role="status">Example unavailable: {error}</p>:url?<iframe ref={frame} title={`${kind.replace(/_/g," ")} animated example`} src={url} onLoad={play} tabIndex={-1}/>:<p role="status">Loading example…</p>}</div>;
}
