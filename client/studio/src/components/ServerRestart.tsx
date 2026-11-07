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
  try{await post("/api/system/restart");setState(s=>s?{...s,restarting:true}:s);toast("Restart requested. The app will reconnect when the server returns.");}
  catch(e:any){toast(e.message,"err");}
  finally{setSending(false);}
 };
 return <section className="card card-pad col" aria-label="Restart server" data-testid="server-restart">
  <strong>Restart the server</strong>
  <p className="small muted">{state.note}</p>
  {state.error&&<p role="alert">{state.error}</p>}
  {state.busy&&<p className="small muted">Wait for running and queued jobs to finish.</p>}
  {state.available&&<button className="btn" onClick={restart} disabled={sending||state.busy||state.restarting}>{state.restarting?"Restarting…":"Restart server"}</button>}
 </section>;
}
