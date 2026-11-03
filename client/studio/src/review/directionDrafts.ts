export type Direction = {instructions:string;director:string;director_model:string;picture_prompt:string;picture_recipe:string;video_prompt:string;video_workflow:string;source_image:string;voice_engine:string;voice:string;narration:string};
type Draft = {revision:number;direction:Direction};
const fields = ['instructions','director','director_model','picture_prompt','picture_recipe','video_prompt','video_workflow','source_image','voice_engine','voice','narration'] as const;
const memory = new Map<string,string>();

/** Per-tab recovery, scoped to the selected server as well as project/scene. */
export class DirectionDrafts {
  private server:string;
  private storage:Pick<Storage,'getItem'|'setItem'|'removeItem'>|null;
  constructor(server:string, storage:Pick<Storage,'getItem'|'setItem'|'removeItem'>|null) { this.server=server;this.storage=storage; }
  private key(base:string, kind:string) { return `uvt:direction:v1:${encodeURIComponent(this.server)}:${base}:${kind}`; }
  private read(key:string) { try { return this.storage?.getItem(key) ?? memory.get(key); } catch { return memory.get(key); } }
  private write(key:string,value:string|null) {
    if(value===null)memory.delete(key);else memory.set(key,value);
    try { if(value===null)this.storage?.removeItem(key);else this.storage?.setItem(key,value); } catch { /* Private/full storage still keeps tool-switch recovery. */ }
  }
  draft(base:string):Draft|null {
    try {
      const value=JSON.parse(this.read(this.key(base,'draft'))||'null');
      return value && Number.isSafeInteger(value.revision) && value.revision>=0 && fields.every(field=>typeof value.direction?.[field]==='string') ? value : null;
    } catch { return null; }
  }
  save(base:string,draft:Draft|null) { this.write(this.key(base,'draft'),draft?JSON.stringify(draft):null); }
  job(base:string):string|null { const value=this.read(this.key(base,'job'));return value && /^[a-zA-Z0-9_-]{1,100}$/.test(value)?value:null; }
  track(base:string,id:string|null) { this.write(this.key(base,'job'),id); }
}
