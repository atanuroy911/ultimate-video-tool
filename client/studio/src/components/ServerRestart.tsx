import { useEffect, useState } from "react";
import { get, post } from "../api";
import { toast } from "../store";

interface Status { available:boolean;busy:boolean;restarting:boolean;note:string;error?:string }
export default function ServerRestart() {
 const [state,setState]=useState<Status|null>(null),[sending,setSending]=useState(false);
 useEffect(()=>{
  let live=true;
  const read=()=>get<Status>("/api/system/restart").then(s=>{if(live)setState(s);}).catch(()=>{});
  read();const timer=setInterval(()=>{if(!document.hidden)read();},2000);
  return()=>{live=false;clearInterval(timer);};
 },[]);
 if(!state)return null;
 const restart=async()=>{
  setSending(true);
  try{await post("/api/system/restart");setState(s=>s?{...s,restarting:true}:s);toast("Restarting. The app reconnects by itself.");}
  catch(e:any){toast(e.message,"err");}
  finally{setSending(false);}
 };
 if(!state.available)return null;                          // restarting is done in the server app on that computer: nothing to offer here
 return <section className="card card-pad row" aria-label="Restart server" data-testid="server-restart" style={{gap:16,alignItems:"center",flexWrap:"wrap"}}>
  <span className="col grow" style={{gap:2,minWidth:220}}>
   <strong>Restart server</strong>
   <span className="small muted">{state.busy?"Available when no videos are being made.":state.note}</span>
   {state.error&&<span className="small" role="alert" style={{color:"var(--err)"}}>{state.error}</span>}
  </span>
  <button className="btn" onClick={restart} disabled={sending||state.busy||state.restarting}>{state.restarting?"Restarting…":"Restart"}</button>
 </section>;
}
