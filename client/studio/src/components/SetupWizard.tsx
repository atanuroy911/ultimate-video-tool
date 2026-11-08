import { Check, Cpu, FolderOpen, Gauge, Image as ImageIcon, MessageSquare, Mic, PlayCircle, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Group, Row, Steps } from "../ds";
import { useT } from "../i18n";
import { toast } from "../store";
import { Seg, Spinner } from "../ui";
import GpuChoice from "./GpuChoice";
import PrepareComfy from "./PrepareComfy";

/* Four steps on the selected processing server; leaving preserves the choices. */
type Mode = "local" | "remote" | "off";
interface Overview {
  step: string; done: boolean; choices: Record<string, Mode>; bundles: string[]; models_dir: string; install_dir:string; steps: string[];
  server:{name:string;data_dir:string;os:string};existing:Record<string,string[]>;
  hardware: { summary: string; disk_free_gb: number; ram_gb: number; data_dir: string; gpus: {index:number; name: string; memory_gb: number }[] };
  recommended: Record<string, Mode>;
  engines: { id: string; label: string; about: string; installable: boolean; mode: Mode }[];
}
interface Plan { engine: string; items: { name: string; size_gb: number; what: string; done: boolean }[]; notes: string[]; problems: string[]; total_gb: number }

export default function SetupWizard({ onClose }: { onClose: () => void }) {
  const t = useT();
  const plain = (id: string, fallback: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? fallback : v; };
  const [o, setO] = useState<Overview | null>(null);
  const [choices, setChoices] = useState<Record<string, Mode>>({});
  const [dir, setDir] = useState("");
  const [programDir,setProgramDir]=useState('');
  const [bundles, setBundles] = useState<string[]>(["pictures"]);
  const [urls, setUrls] = useState<Record<string, string>>({});
  useEffect(() => {
    get<Overview>("/api/setup").then((d) => {
      setO(d);
      const initial={ ...d.recommended,...Object.fromEntries(Object.entries(d.existing||{}).filter(([,urls])=>urls.length).map(([id])=>[id,'remote'])), ...d.choices };
      setChoices(Object.fromEntries(Object.entries(initial).filter(([id])=>d.engines.some(e=>e.id===id))) as Record<string,Mode>);
      setUrls(Object.fromEntries(Object.entries(d.existing||{}).filter(([,urls])=>urls.length).map(([id,urls])=>[id,urls[0]])));
      setDir(d.models_dir);
      setProgramDir(d.install_dir||'');
      setBundles(Array.isArray(d.bundles)?d.bundles:["pictures"]);
    }).catch((e) => toast(e.message, "err"));
  }, []);
  if (!o) return <div className="ios-back"><div className="ios-sheet"><div className="ios-body"><Spinner /></div></div></div>;

  const remote = o.engines.filter((e) => choices[e.id] === "remote");
  const local = o.engines.filter((e) => choices[e.id] === "local" && e.installable);
  const saveChoices = () => put("/api/setup", { choices, models_dir: dir, install_dir:programDir, bundles });

  const steps = [
    {
      title: `Set up ${o.server?.name||'your server'}`, icon: <Cpu size={26} />, subtitle: 'Choose the AI programs it uses. Anything you install goes on the server, not on this computer.',
      body: (
        <Group title="The server">
          <Row label={o.hardware.gpus.length>1?'Graphics cards':'Graphics card'}>{o.hardware.gpus.length?o.hardware.gpus.map(g=>`${g.name} (${g.memory_gb} GB)`).join(' · '):'None (uses the processor)'}</Row>
          <Row label={t("setup.disk")}>{o.hardware.disk_free_gb} GB</Row>
          <Row label={t("setup.memory")}>{o.hardware.ram_gb} GB</Row>
        </Group>
      ),
    },
    {
      title: t("setup.storage"), icon: <FolderOpen size={26} />, subtitle: 'New programs and models are saved here. Programs you already have stay where they are.',
      body: (
        <Group title={t("setup.folder")} note={t("setup.folder.note").replace("{gb}", String(o.hardware.disk_free_gb))}>
          <Row label={t("setup.modelsfolder")} stack>
            <input type="text" value={dir} placeholder={`${o.hardware.data_dir}/models`} onChange={(e) => setDir(e.target.value)} aria-label={t("setup.modelsfolder")} spellCheck={false} style={{ width: "100%" }} />
          </Row>
          <Row label="Programs folder" stack><input value={programDir} onChange={e=>setProgramDir(e.target.value)} placeholder={`${o.hardware.data_dir}/engines`} aria-label="Programs folder" spellCheck={false}/></Row>
        </Group>
      ),
    },
    {
      title: t("setup.choose"), icon: <Sparkles size={26} />, subtitle: t("setup.choose.sub"),
      body: (
        <>
          {o.engines.map((e) => (
            <Group key={e.id} title={plain(e.id, e.label)} note={e.about}>
              <Row label={t("setup.choosehow")} stack>
                <Seg<Mode> label={`${e.label}: how`} value={choices[e.id] ?? "off"} onChange={(m) => setChoices({ ...choices, [e.id]: m })}
                  options={[{ value: "local", label: 'Install' }, { value: "remote", label: 'Use one I have' }, { value: "off", label: 'Skip' }]} />
              </Row>
              {e.id === "comfy" && choices.comfy === "local" && (
                <Row label={t("setup.alsoinstall")} stack>
                  <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={bundles.includes("clips")} onChange={(ev) => setBundles(ev.target.checked ? [...bundles, "clips"] : bundles.filter((b) => b !== "clips"))} /> {t("setup.clips")}</label>
                </Row>
              )}
            </Group>
          ))}
        </>
      ),
    },
    {
      title: t("setup.connect"), icon: <PlayCircle size={26} />, subtitle: remote.length ? t("setup.connect.sub") : t("setup.connect.none"),
      body: (
        <>
          {remote.length > 0 && <Hub onPaired={(names) => setChoices((c) => ({ ...c, ...Object.fromEntries(names.map((n) => [n, "remote" as Mode])) }))} />}
          {remote.map((e) => <Connect key={e.id} id={e.id} label={plain(e.id, e.label)} url={urls[e.id] ?? ""} setUrl={(u) => setUrls({ ...urls, [e.id]: u })} />)}
        </>
      ),
    },
    {
      title: t("setup.install"), icon: <Cpu size={26} />, subtitle: local.length ? t("setup.install.sub") : "—",
      body: <Install engines={local.map((e) => e.id)} bundles={bundles} modelsDir={dir} installDir={programDir}/>,
    },
    {
      title: t("setup.try"), icon: <Check size={26} />, subtitle: t("setup.try.sub"),
      body: <Try ids={o.engines.filter((e) => choices[e.id] && choices[e.id] !== "off").map((e) => e.id)} />,
    },
    {
      title: t("setup.done"), icon: <Check size={26} />, subtitle: t("setup.done.sub"),
      body: <Group title={t("setup.summary")}>{o.engines.map((e) => <Row key={e.id} label={plain(e.id, e.label)}>{t("setup.at." + (choices[e.id] ?? "off"))}</Row>)}</Group>,
    },
  ];
  const manyCards=o.hardware.gpus.length>=2;                       // with two or more cards the person decides which ones Video Tool may use (nothing to ask with one)
  const cardsStep={title:t("gpu.setup.title"),subtitle:t("gpu.setup.sub"),icon:<Gauge size={26}/>,body:(go:{next:()=>void})=><GpuChoice mode="setup" onAnswered={go.next} onSkip={go.next}/>};
  const visibleSteps=[
    {...steps[0],body:<>{steps[0].body}{steps[2].body}</>},
    ...(manyCards?[cardsStep]:[]),
    {...steps[1],title:'Where to keep downloads'},
    {...steps[4],title:'Connect and install',subtitle:'Connect the programs you have. Check what will download before installing.',body:<>{remote.map(e=><Connect key={e.id} id={e.id} label={plain(e.id,e.label)} url={urls[e.id]??''} setUrl={u=>setUrls({...urls,[e.id]:u})}/>)}{steps[4].body}</>},
    {...steps[5],title:'Try it',body:<>{steps[5].body}{steps[6].body}</>},
  ];
  const stateSteps=manyCards?['choose','cards','storage','install','try']:['choose','storage','install','try'];
  const at=(name:string)=>Math.max(0,stateSteps.indexOf(name));
  const initial=o.step==='welcome'||o.step==='choose'?0:o.step==='cards'?at('cards'):o.step==='storage'?at('storage'):o.step==='connect'||o.step==='install'?at('install'):at('try');
  return <Steps label="Server setup" steps={visibleSteps} start={initial} headerDone={false}
    onClose={()=>{saveChoices().then(onClose).catch(e=>toast(e.message,'err'));}}
    onStep={i=>{saveChoices().then(()=>put('/api/setup',{step:stateSteps[i]})).catch(e=>toast(e.message,'err'));}}
    onDone={async()=>{try{await saveChoices();await put('/api/setup',{step:'done',done:true});onClose();}catch(e:any){toast(e.message,'err');}}}/>;
}

function Connect({ id, label, url, setUrl }: { id: string; label: string; url: string; setUrl: (u: string) => void }) {
  const t = useT();
  const [says, setSays] = useState("");
  const [busy, setBusy] = useState(false);
  const [connectedUrl,setConnectedUrl]=useState('');
  const [needsModel,setNeedsModel]=useState(false),[modelJob,setModelJob]=useState<any>(null);
  useEffect(()=>{if(!modelJob||['done','error','cancelled'].includes(modelJob.status))return;const timer=setInterval(()=>get<any>(`/api/jobs/${modelJob.id}`).then(j=>{setModelJob(j);if(j.status==='done'){setNeedsModel(false);setSays('Language model ready.');}if(j.status==='error')setSays(j.error);}).catch(()=>{}),1500);return()=>clearInterval(timer);},[modelJob?.id,modelJob?.status]);
  const test = async () => {
    setBusy(true);
    try {
      const h = await post<{ ok: boolean; why_not: string; capabilities: string[]; gpu: string;models?:any[] }>(`/api/engines/${id}/test`, { mode: "remote", url });
      if (h.ok) {
        await put(`/api/engines/${id}`, { mode: "remote", url });
        setNeedsModel(id==='ollama'&&!h.models?.length);
        const names:Record<string,string>={'llm.chat':'planning and writing','llm.vision':'understanding pictures','image.generate':'pictures','video.generate':'moving clips','voice.speak':'voices'};
        const abilities=h.capabilities.map(c=>names[c]).filter(Boolean);
        setSays(`Connected${h.gpu ? ` on ${h.gpu}` : ''}. ${abilities.length?'It can do '+abilities.join(', ')+'.':'It has no models yet.'}`);
        setConnectedUrl(url);
      } else setSays(h.why_not || t("setup.noanswer"));
    } catch (e: any) {
      setSays(e.errors?.[0] || e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Group title={label}>
      <Row label={t("setup.address")} stack><input type="text" value={url} placeholder={id==='ollama'?'http://127.0.0.1:11434':'http://127.0.0.1:8188'} onChange={(e) => {setUrl(e.target.value);setConnectedUrl('');setSays('');setNeedsModel(false);}} aria-label={`${label}: ${t("setup.address")}`} spellCheck={false} style={{ width: "100%" }} /><span className="small muted">Leave it as it is when the program runs on the server itself.</span></Row>
      <div className="ios-row engine-test">
        <button className="btn sm" onClick={test} disabled={busy || !url.trim()}>{busy ? t("setup.testing") : 'Connect'}</button>
        {says && <p className={`status-line ${connectedUrl ? "ok" : "bad"}`} role="status"><i aria-hidden />{says}</p>}
      </div>
      {needsModel&&<Row label="No language model yet" stack><span className="small muted">It downloads into this Ollama's own model folder.</span><button className="btn" disabled={!!modelJob&&!['error','cancelled'].includes(modelJob.status)} onClick={()=>post('/api/setup/ollama-model').then(setModelJob).catch(e=>toast(e.message,'err'))}>Download recommended model</button>{modelJob&&<span className="small">{Math.round((modelJob.frac||0)*100)}% · {modelJob.msg||modelJob.status}</span>}</Row>}
      {id==='comfy'&&connectedUrl&&<PrepareComfy key={connectedUrl} url={connectedUrl}/>}
    </Group>
  );
}

/* A computer that runs the Video Tool Engine offers everything at one address: trade its one-time code and Language AI and Pictures connect too. */
function Hub({ onPaired }: { onPaired: (names: string[]) => void }) {
  const t = useT();
  const [url, setUrl] = useState("");
  const [code, setCode] = useState("");
  const [says, setSays] = useState("");
  const [busy, setBusy] = useState(false);
  const pair = async () => {
    setBusy(true);
    try {
      const r = await post<{ also_connected?: string[] }>("/api/engines/vtengine/pair", { url, code: code.trim() });
      const names = r.also_connected ?? [];
      setSays(names.length ? t("setup.hub.done").replace("{what}", names.map((n) => plainName(t, n)).join(", ")) : t("setup.hub.voices"));
      onPaired(names);
    } catch (e: any) {
      setSays(e.errors?.[0] || e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Group title={t("setup.hub")} note={t("setup.hub.note")}>
      <Row label={t("setup.address")} stack><input type="text" value={url} placeholder="http://192.168.1.20:8790" onChange={(e) => setUrl(e.target.value)} aria-label={`${t("setup.hub")}: ${t("setup.address")}`} spellCheck={false} style={{ width: "100%" }} /></Row>
      <Row label={t("setup.code")} stack><input type="text" value={code} placeholder="a1b2-c3d4-e5f6" onChange={(e) => setCode(e.target.value)} aria-label={t("setup.code")} spellCheck={false} style={{ width: "100%" }} /></Row>
      <Row label=""><button className="btn sm" onClick={pair} disabled={busy || !url.trim() || !code.trim()} data-testid="hub-pair">{busy ? t("setup.testing") : t("setup.pair")}</button> <span className="small" role="status">{says}</span></Row>
    </Group>
  );
}
const plainName = (t: (k: string) => string, id: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? id : v; };

function Install({ engines, bundles,modelsDir,installDir }: { engines: string[]; bundles: string[];modelsDir:string;installDir:string }) {
  const t = useT();
  const plain = (id: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? id : v; };
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [job, setJob] = useState<{ id: string; status: string; frac: number; msg: string; error: string } | null>(null);
  useEffect(() => {
    if (engines.length) get<Plan[]>(`/api/setup/plan?engines=${engines.join(",")}&bundles=${bundles.join(",")}&models_dir=${encodeURIComponent(modelsDir)}&install_dir=${encodeURIComponent(installDir)}`).then(setPlans).catch((e) => toast(e.message, "err"));
  }, [engines.join(","), bundles.join(","),modelsDir,installDir]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!job || ["done", "error", "cancelled"].includes(job.status)) return;
    const t = setInterval(() => get(`/api/jobs/${job.id}`).then(setJob).catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!engines.length) return null;
  if (!plans) return <Spinner />;
  const problems = plans.flatMap((p) => p.problems);
  const total = plans.reduce((a, p) => a + p.total_gb, 0);
  const start = () => post<any>("/api/setup/install", { engines, bundles,models_dir:modelsDir,install_dir:installDir }).then(setJob).catch((e) => toast(e.errors?.[0] || e.message, "err", 8000));
  return (
    <>
      {plans.map((p) => (
        <Group key={p.engine} title={plain(p.engine)} note={p.notes.join(" ")}>
          {p.items.map((i) => <Row key={i.name} label={i.name}>{i.done ? t("setup.already") : `${i.size_gb} GB`}</Row>)}
        </Group>
      ))}
      {problems.map((x, i) => <p key={i} className="small" style={{ color: "var(--err)" }}>{x}</p>)}
      <p className="small muted">{t("setup.aboutgb").replace("{gb}", total.toFixed(0))}</p>
      {!job && <button className="btn primary" onClick={start} disabled={problems.length > 0} data-testid="setup-start">{t("setup.start")}</button>}
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
