import { Check, Cpu, FolderOpen, Gauge, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Group, Row, Steps } from "../ds";
import { useT } from "../i18n";
import { toast } from "../store";
import { Seg, Spinner } from "../ui";
import FolderPicker from "./FolderPicker";
import GpuChoice from "./GpuChoice";
import PrepareComfy from "./PrepareComfy";

/* Four steps on the computer that makes the videos (it may be this one or another); leaving keeps the choices.
   Words: "this computer" when the person sits at it, else its name. Never "server", "engine" or "processing". */
type Mode = "local" | "remote" | "off";
interface ModelOption { id: string; label: string; note?: string; download_gb: number; fits: boolean; speed: string; recommended: boolean; why: string }
interface Overview {
  step: string; done: boolean; choices: Record<string, Mode>; bundles: string[]; models_dir: string; install_dir:string; steps: string[];
  picture_model?: string; language_model?: string; same_computer?: boolean;
  server:{name:string;data_dir:string;os:string};existing:Record<string,string[]>;
  hardware: { summary: string; disk_free_gb: number; ram_gb: number; data_dir: string; gpus: {index:number; name: string; memory_gb: number }[] };
  recommended: Record<string, Mode>;
  engines: { id: string; label: string; about: string; installable: boolean; mode: Mode }[];
  models?: { card: { name: string; gb: number }; pictures: ModelOption[]; language: ModelOption[]; clips: { fits: boolean; why: string }; picture_default: string; language_default: string };
}
interface Plan { engine: string; items: { name: string; size_gb: number; what: string; done: boolean }[]; notes: string[]; problems: string[]; total_gb: number }

const CLIPS_GB = 40;
const ABOUT: Record<string, string> = {
  ollama: "Plans each video and writes its script. It runs the free program Ollama.",
  comfy: "Draws a picture for every sentence of your video. It runs the free program ComfyUI.",
};
const OFF_NOTE: Record<string, string> = {
  ollama: "Without it, videos are planned by simple built-in rules or by Claude or Codex if you connect them.",
  comfy: "Without it, each picture becomes a card with the key words, and the video is still made.",
};

export default function SetupWizard({ onClose }: { onClose: () => void }) {
  const t = useT();
  const plain = (id: string, fallback: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? fallback : v; };
  const [o, setO] = useState<Overview | null>(null);
  const [choices, setChoices] = useState<Record<string, Mode>>({});
  const [dir, setDir] = useState("");
  const [programDir,setProgramDir]=useState('');
  const [bundles, setBundles] = useState<string[]>(["pictures"]);
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [pictureModel, setPictureModel] = useState("");
  const [languageModel, setLanguageModel] = useState("");
  useEffect(() => {
    get<Overview>("/api/setup").then((d) => {
      setO(d);
      // "I already have it" is only suggested when one was found; otherwise install it when a model fits this card, else leave it for later
      const found=(id:string)=>!!d.existing?.[id]?.length;
      const fitsHere=(id:string)=>id==='comfy'?!!d.models?.pictures.some(p=>p.fits):true;
      const suggested=Object.fromEntries(Object.entries(d.recommended).map(([id,mode])=>[id,mode==='remote'&&!found(id)?(fitsHere(id)?'local':'off'):mode]));
      const initial={ ...suggested,...Object.fromEntries(Object.entries(d.existing||{}).filter(([,urls])=>urls.length).map(([id])=>[id,'remote'])), ...d.choices };
      setChoices(Object.fromEntries(Object.entries(initial).filter(([id])=>d.engines.some(e=>e.id===id))) as Record<string,Mode>);
      setUrls(Object.fromEntries(Object.entries(d.existing||{}).filter(([,urls])=>urls.length).map(([id,urls])=>[id,urls[0]])));
      setDir(d.models_dir);
      setProgramDir(d.install_dir||'');
      const clipsOk = d.models?.clips.fits ?? true;
      setBundles((Array.isArray(d.bundles)?d.bundles:["pictures"]).filter((b) => b !== "clips" || clipsOk));
      const pic = d.models?.pictures.find((p) => p.id === d.picture_model && p.fits) ? d.picture_model! : d.models?.picture_default || "";
      setPictureModel(pic);
      setLanguageModel(d.models?.language.some((m) => m.id === d.language_model) ? d.language_model! : d.models?.language_default || "");
    }).catch((e) => toast(e.message, "err"));
  }, []);
  if (!o) return <div className="ios-back"><div className="ios-sheet"><div className="ios-body"><Spinner /></div></div></div>;

  const here = !!o.same_computer;
  const name = o.server?.name || "the video computer";
  const where = here ? "this computer" : name;
  const remote = o.engines.filter((e) => choices[e.id] === "remote");
  const local = o.engines.filter((e) => choices[e.id] === "local" && e.installable);
  const saveChoices = () => put("/api/setup", { choices, models_dir: dir, install_dir:programDir, bundles, picture_model: pictureModel, language_model: languageModel });
  const m = o.models;
  const cardGb = m?.card.gb || 0;
  const pick = (list: ModelOption[] | undefined, id: string) => list?.find((x) => x.id === id);
  const downloadGb = Math.round(
    (choices.ollama === "local" ? (pick(m?.language, languageModel)?.download_gb ?? 3.3) + 1.5 : 0) +
    (choices.comfy === "local" ? (pick(m?.pictures, pictureModel)?.download_gb ?? 14) + 6 + (bundles.includes("clips") ? CLIPS_GB : 0) : 0));
  const gpuText = o.hardware.gpus.length ? o.hardware.gpus.map((g) => `${g.name} (${g.memory_gb} GB)`).join(" · ") : "None: pictures will be slow";

  const engineCard = (e: Overview["engines"][number]) => {
    const mode = choices[e.id] ?? "off";
    const models = e.id === "comfy" ? m?.pictures : m?.language;
    const chosen = e.id === "comfy" ? pictureModel : languageModel;
    const setChosen = e.id === "comfy" ? setPictureModel : setLanguageModel;
    return (
      <Group key={e.id} title={`${plain(e.id, e.label)} (${e.id === "comfy" ? "ComfyUI" : "Ollama"})`}>
        <div className="ios-row"><span className="small muted">{ABOUT[e.id] ?? e.about}</span></div>
        <Row label="How to get it" stack>
          <Seg<Mode> label={`${plain(e.id, e.label)}: how to get it`} value={mode} onChange={(v) => setChoices({ ...choices, [e.id]: v })}
            options={[{ value: "local", label: "Install it" }, { value: "remote", label: "I already have it" }, { value: "off", label: "Not now" }]} />
          <span className="small muted">
            {mode === "local" ? `Video Tool downloads it and sets it up on ${where}.` : mode === "remote" ? "You connect it in step 3." : OFF_NOTE[e.id]}
          </span>
        </Row>
        {mode === "local" && models && models.length > 0 && (
          <Row label={cardGb ? `Model for your ${cardGb} GB graphics card` : "Model"} stack>
            <ModelList name={`model-${e.id}`} options={models} value={chosen} onChange={setChosen} cardGb={cardGb} />
          </Row>
        )}
        {e.id === "comfy" && mode === "local" && (
          <Row label="Also" stack>
            <label className="row" style={{ gap: 8, opacity: m?.clips.fits === false ? 0.6 : 1 }}>
              <input type="checkbox" disabled={m?.clips.fits === false} checked={bundles.includes("clips")}
                onChange={(ev) => setBundles(ev.target.checked ? [...bundles.filter((b) => b !== "clips"), "clips"] : bundles.filter((b) => b !== "clips"))} />
              Animate short moving clips (about {CLIPS_GB} GB more)
            </label>
            {m?.clips.fits === false && <span className="small muted">{m.clips.why}</span>}
          </Row>
        )}
      </Group>
    );
  };

  const steps = [
    {
      title: here ? "Set up this computer" : `Set up ${name}`, icon: <Cpu size={26} />,
      subtitle: here
        ? "Video Tool uses two AI programs to make your videos. Choose how to get each one. You can change this later."
        : `${name} is the computer that makes your videos. Everything you choose here goes on ${name}, not on the computer you are using now.`,
      body: (
        <>
          <Group title={here ? "This computer" : name}>
            <Row label={o.hardware.gpus.length > 1 ? "Graphics cards" : "Graphics card"}>{gpuText}</Row>
            <Row label="Memory">{o.hardware.ram_gb} GB</Row>
            <Row label="Free space">{o.hardware.disk_free_gb} GB</Row>
          </Group>
          {o.engines.map(engineCard)}
        </>
      ),
    },
    {
      title: "Where to save downloads", icon: <FolderOpen size={26} />,
      subtitle: (local.length ? `The AI models you chose need about ${downloadGb} GB. Choose a drive with room for them.` : "Nothing is being installed, so this can stay as it is.")
        + (here ? "" : ` These are folders on ${name}.`),
      body: (
        <Group note={remote.length ? "Programs you already have keep their own folders." : undefined}>
          <Row label="Downloads folder" stack>
            <FolderPicker value={dir} placeholder={`${o.hardware.data_dir}${o.server?.os === "Windows" ? "\\" : "/"}models`} onChange={setDir} label="Downloads folder" where={where} />
            <span className="small muted">The AI models go here. They are large.</span>
          </Row>
          <details className="setup-more">
            <summary className="small">Keep the programs in a different folder</summary>
            <Row label="Programs folder" stack>
              <FolderPicker value={programDir} placeholder={`${o.hardware.data_dir}${o.server?.os === "Windows" ? "\\" : "/"}engines`} onChange={setProgramDir} label="Programs folder" where={where} />
            </Row>
          </details>
        </Group>
      ),
    },
    {
      title: local.length && remote.length ? "Connect and install" : remote.length ? "Connect what you have" : "Install", icon: <Sparkles size={26} />,
      subtitle: [remote.length ? "Check the address of each program you already have, then press Connect." : "", local.length ? "Here is what will download. Nothing starts until you press Install." : "",
        !local.length && !remote.length ? "Nothing to install or connect. You can set this up later on the Server page." : ""].filter(Boolean).join(" "),
      body: (
        <>
          {remote.map((e) => <Connect key={e.id} id={e.id} label={plain(e.id, e.label)} url={urls[e.id] ?? ""} setUrl={(u) => setUrls({ ...urls, [e.id]: u })} where={where} />)}
          <Install engines={local.map((e) => e.id)} bundles={bundles} modelsDir={dir} installDir={programDir} pictureModel={pictureModel} languageModel={languageModel} />
        </>
      ),
    },
    {
      title: "Check it works", icon: <Check size={26} />, subtitle: "A quick test of each AI program.",
      body: (
        <>
          <Try ids={o.engines.filter((e) => choices[e.id] && choices[e.id] !== "off").map((e) => e.id)} />
          <Group title={t("setup.summary")}>{o.engines.map((e) => <Row key={e.id} label={plain(e.id, e.label)}>{({ local: "Installed by Video Tool", remote: "Uses the one you have", off: "Not set up" } as Record<string, string>)[choices[e.id] ?? "off"]}</Row>)}</Group>
        </>
      ),
    },
  ];
  const manyCards=o.hardware.gpus.length>=2;                       // with two or more cards the person decides which ones Video Tool may use (nothing to ask with one)
  const cardsStep={title:t("gpu.setup.title"),subtitle:t("gpu.setup.sub"),icon:<Gauge size={26}/>,body:(go:{next:()=>void})=><GpuChoice mode="setup" onAnswered={go.next} onSkip={go.next}/>};
  const visibleSteps=[steps[0],...(manyCards?[cardsStep]:[]),steps[1],steps[2],steps[3]];
  const stateSteps=manyCards?['choose','cards','storage','install','try']:['choose','storage','install','try'];
  const at=(name:string)=>Math.max(0,stateSteps.indexOf(name));
  const initial=o.step==='welcome'||o.step==='choose'?0:o.step==='cards'?at('cards'):o.step==='storage'?at('storage'):o.step==='connect'||o.step==='install'?at('install'):at('try');
  return <Steps label={here ? "Set up this computer" : `Set up ${name}`} steps={visibleSteps} start={initial} headerDone={false} doneLabel="Finish"
    onClose={()=>{saveChoices().then(onClose).catch(e=>toast(e.message,'err'));}}
    onStep={i=>{saveChoices().then(()=>put('/api/setup',{step:stateSteps[i]})).catch(e=>toast(e.message,'err'));}}
    onDone={async()=>{try{await saveChoices();await put('/api/setup',{step:'done',done:true});onClose();}catch(e:any){toast(e.message,'err');}}}/>;
}

/* Every model that can be installed, marked against the card: runs well, works but slowly, or too big (greyed, with why). */
function ModelList({ name, options, value, onChange, cardGb }: { name: string; options: ModelOption[]; value: string; onChange: (id: string) => void; cardGb: number }) {
  return (
    <div className="model-list" role="radiogroup" aria-label="Model">
      {options.map((x) => {
        const fit = !x.fits ? { cls: "no", text: x.why }
          : x.speed === "fast" ? { cls: "fast", text: cardGb ? `Runs well on your ${cardGb} GB card` : "Runs well here" }
          : { cls: "slow", text: x.why || (cardGb ? `Works on your ${cardGb} GB card, but slowly` : "Works here, but slowly") };
        return (
          <label key={x.id} className={`model-opt ${value === x.id ? "on" : ""} ${x.fits ? "" : "off"}`}>
            <input type="radio" name={name} value={x.id} checked={value === x.id} disabled={!x.fits} onChange={() => onChange(x.id)} />
            <span className="grow">
              <strong>{x.label}{x.recommended && <span className="chip accent" style={{ marginLeft: 8 }}>Best for this computer</span>}</strong>
              <span className={`model-fit ${fit.cls}`}>{fit.text}</span>
            </span>
            <span className="model-size">{x.download_gb} GB</span>
          </label>
        );
      })}
    </div>
  );
}

function Connect({ id, label, url, setUrl, where }: { id: string; label: string; url: string; setUrl: (u: string) => void; where: string }) {
  const t = useT();
  const [says, setSays] = useState("");
  const [busy, setBusy] = useState(false);
  const [connectedUrl,setConnectedUrl]=useState('');
  const [needsModel,setNeedsModel]=useState(false),[modelJob,setModelJob]=useState<any>(null);
  useEffect(()=>{if(!modelJob||['done','error','cancelled'].includes(modelJob.status))return;const timer=setInterval(()=>get<any>(`/api/jobs/${modelJob.id}`).then(j=>{setModelJob(j);if(j.status==='done'){setNeedsModel(false);setSays('Model ready.');}if(j.status==='error')setSays(j.error);}).catch(()=>{}),1500);return()=>clearInterval(timer);},[modelJob?.id,modelJob?.status]);
  const test = async () => {
    setBusy(true);
    try {
      const h = await post<{ ok: boolean; why_not: string; capabilities: string[]; gpu: string;models?:any[] }>(`/api/engines/${id}/test`, { mode: "remote", url });
      if (h.ok) {
        await put(`/api/engines/${id}`, { mode: "remote", url });
        setNeedsModel(id==='ollama'&&!h.models?.length);
        const names:Record<string,string>={'llm.chat':'plan and write','llm.vision':'look at pictures','image.generate':'draw pictures','video.generate':'animate clips','voice.speak':'speak'};
        const abilities=h.capabilities.map(c=>names[c]).filter(Boolean);
        setSays(`Connected${h.gpu ? `, using the ${h.gpu}` : ''}. ${abilities.length?'It can '+abilities.join(', ')+'.':'It has no models yet.'}`);
        setConnectedUrl(url);
      } else setSays(h.why_not || t("setup.noanswer"));
    } catch (e: any) {
      setSays(e.errors?.[0] || e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Group title={`Your ${label} (${id === 'comfy' ? 'ComfyUI' : 'Ollama'})`}>
      <Row label={t("setup.address")} stack><input type="text" value={url} placeholder={id==='ollama'?'http://127.0.0.1:11434':'http://127.0.0.1:8188'} onChange={(e) => {setUrl(e.target.value);setConnectedUrl('');setSays('');setNeedsModel(false);}} aria-label={`${label}: ${t("setup.address")}`} spellCheck={false} style={{ width: "100%" }} /><span className="small muted">{url ? `Found on ${where}. Change it only if the program runs on a different computer.` : `Type the address the program shows when it starts, such as ${id==='ollama'?'http://127.0.0.1:11434':'http://127.0.0.1:8188'}.`}</span></Row>
      <div className="ios-row engine-test">
        <button className="btn sm" onClick={test} disabled={busy || !url.trim()}>{busy ? t("setup.testing") : 'Connect'}</button>
        {says && <p className={`status-line ${connectedUrl ? "ok" : "bad"}`} role="status"><i aria-hidden />{says}</p>}
      </div>
      {needsModel&&<Row label="It has no model yet" stack><span className="small muted">The model goes into this Ollama's own model folder.</span><button className="btn" disabled={!!modelJob&&!['error','cancelled'].includes(modelJob.status)} onClick={()=>post('/api/setup/ollama-model').then(setModelJob).catch(e=>toast(e.message,'err'))}>Download recommended model</button>{modelJob&&<span className="small">{Math.round((modelJob.frac||0)*100)}% · {modelJob.msg||modelJob.status}</span>}</Row>}
      {id==='comfy'&&connectedUrl&&<PrepareComfy key={connectedUrl} url={connectedUrl}/>}
    </Group>
  );
}


function Install({ engines, bundles,modelsDir,installDir,pictureModel,languageModel }: { engines: string[]; bundles: string[];modelsDir:string;installDir:string;pictureModel:string;languageModel:string }) {
  const t = useT();
  const plain = (id: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? id : v; };
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [job, setJob] = useState<{ id: string; status: string; frac: number; msg: string; error: string } | null>(null);
  useEffect(() => {
    if (engines.length) get<Plan[]>(`/api/setup/plan?engines=${engines.join(",")}&bundles=${bundles.join(",")}&models_dir=${encodeURIComponent(modelsDir)}&install_dir=${encodeURIComponent(installDir)}&picture_model=${encodeURIComponent(pictureModel)}&language_model=${encodeURIComponent(languageModel)}`).then(setPlans).catch((e) => toast(e.message, "err"));
  }, [engines.join(","), bundles.join(","),modelsDir,installDir,pictureModel,languageModel]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!job || ["done", "error", "cancelled"].includes(job.status)) return;
    const t = setInterval(() => get(`/api/jobs/${job.id}`).then(setJob).catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!engines.length) return null;
  if (!plans) return <p className="small muted row" style={{ gap: 8 }}><Spinner size={14} /> Working out what to download…</p>;
  const problems = plans.flatMap((p) => p.problems);
  const total = plans.reduce((a, p) => a + p.total_gb, 0);
  const start = () => post<any>("/api/setup/install", { engines, bundles,models_dir:modelsDir,install_dir:installDir,picture_model:pictureModel,language_model:languageModel }).then(setJob).catch((e) => toast(e.errors?.[0] || e.message, "err", 8000));
  return (
    <>
      {plans.map((p) => (
        <Group key={p.engine} title={plain(p.engine)} note={p.notes.join(" ")}>
          {p.items.map((i) => <Row key={i.name} label={i.name}>{i.done ? t("setup.already") : `${i.size_gb} GB`}</Row>)}
        </Group>
      ))}
      {problems.map((x, i) => <p key={i} className="small" style={{ color: "var(--err)" }}>{x}</p>)}
      <p className="small muted">{t("setup.aboutgb").replace("{gb}", total.toFixed(0))}</p>
      {!job && <button className="btn primary" onClick={start} disabled={problems.length > 0} data-testid="setup-start">{total > 0 ? `Install · ${total.toFixed(0)} GB` : t("setup.start")}</button>}
      {job && <p className="small" role="status">{job.status === "error" ? job.error : job.status === "done" ? t("setup.finished") : `${Math.round(job.frac * 100)}% · ${job.msg}`}</p>}
    </>
  );
}

function Try({ ids }: { ids: string[] }) {
  const t = useT();
  const plain = (id: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? id : v; };
  const [says, setSays] = useState<Record<string, string>>({});
  const run = async (id: string) => {
    setSays((s) => ({ ...s, [id]: t("setup.trying") }));
    try {
      const r = await post<{ ok: boolean; says: string }>(`/api/setup/try/${id}`);
      setSays((s) => ({ ...s, [id]: (r.ok ? "Works. " : "Problem: ") + r.says }));
    } catch (e: any) {
      setSays((s) => ({ ...s, [id]: "Problem: " + e.message }));
    }
  };
  if (!ids.length) return <p className="muted">{t("setup.nothingconnected")}</p>;
  return <>{ids.map((id) => <Group key={id} title={plain(id)}><Row label=""><button className="btn sm" onClick={() => run(id)}>{t("setup.tryit")}</button> <span className="small bn" role="status">{says[id]}</span></Row></Group>)}</>;
}
