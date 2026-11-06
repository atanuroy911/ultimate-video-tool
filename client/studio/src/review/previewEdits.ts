import { hasTransform } from "./transformMath.ts";
type Edit = {kind:"element";scene:string;index:number;patch:Record<string,any>} | {kind:"edge";left:string;right:string;t:number} | {kind:"word";id:string;start:number;end:number;text?:string} | {kind:"action";scene:string;index:number;start:number;end:number} | {kind:"clear"};
const send = (detail:Edit) => window.dispatchEvent(new CustomEvent("vt-preview-edit",{detail}));
export const previewElement=(scene:string,index:number,patch:Record<string,any>)=>send({kind:"element",scene,index,patch});
export const previewEdge=(left:string,right:string,t:number)=>send({kind:"edge",left,right,t});
export const previewWord=(id:string,start:number,end:number,text?:string)=>send({kind:"word",id,start,end,text});
export const previewAction=(scene:string,index:number,start:number,end:number)=>send({kind:"action",scene,index,start,end});
export const clearPreview=()=>send({kind:"clear"});
export function applyPreviewEdit(data:any, edit:Edit):any {
  if(edit.kind==="clear") return data;
  const next=structuredClone(data);
  if(edit.kind==="edge") for(const sc of next.scenes) {
    if((sc.src||sc.id)===edit.left) sc.end=edit.t;
    if((sc.src||sc.id)===edit.right) sc.start=edit.t;
  }
  if(edit.kind==="element") for(const sc of next.scenes) if((sc.src||sc.id)===edit.scene) {
    sc.edited=true;
    sc.elements=sc.elements.map((el:any,i:number)=>{
      if((el._i??i)!==edit.index) return el;
      const e={...el,...edit.patch};
      if (el.keyframes?.length && !('keyframes' in edit.patch) && edit.patch.start!=null && edit.patch.end!=null) {
        const delta=edit.patch.start-(el.start??el.at);
        if (Math.abs((edit.patch.end-(el.end??el.until??sc.end))-delta)<.002)
          e.keyframes=el.keyframes.map((p:any)=>({...p,time:Math.round((p.time+delta)*1000)/1000}));
      }
      if(e.keyframes?.length || e.start!=null || e.end!=null || e.x!=null || e.y!=null || e.scale!==undefined && e.scale!==1 || e.rotation || e.opacity!==undefined && e.opacity!==1 || hasTransform(e.transform)) {
        e.free=true; e.at=e.start??e.at; e.until=e.end??e.until??sc.end;
      }
      return e;
    });
  }
  if(edit.kind==="action") for(const sc of next.scenes) if((sc.src||sc.id)===edit.scene && sc.stick?.actions?.[edit.index]) {
    Object.assign(sc.stick.actions[edit.index],{start:edit.start,end:edit.end,_timed:true});
  }
  if(edit.kind==="word") for(const chunk of next.captions) {
    const word=chunk.words.find((w:any)=>w.id===edit.id);
    if(word) {if(edit.text!==undefined) word.text=edit.text;word.start=edit.start;word.end=edit.end;chunk.start=Math.min(...chunk.words.map((w:any)=>w.start));chunk.end=Math.max(...chunk.words.map((w:any)=>w.end));}
  }
  return next;
}
