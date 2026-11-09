import { Check, CircleCheck, CircleSlash, CircleX, Clapperboard, Download, Gauge, HardDrive, Image as ImageIcon, Link2, Lock, MemoryStick, PenLine, SlidersHorizontal, Sparkles } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { get, post, put } from "../api";
import { Group, Row, Steps } from "../ds";
import { useT } from "../i18n";
import { toast } from "../store";
import { Spinner } from "../ui";
import FolderPicker from "./FolderPicker";
import GpuChoice from "./GpuChoice";
import ModelList, { FitIcon, fitWords, type ModelOption } from "./ModelList";
import PrepareComfy from "./PrepareComfy";

/* Setup for lazy people: the first screen already holds the answer (what fits this computer), one button installs it, the next screen shows it
   happening and the last one checks it by itself. Everything else waits behind "Choose myself".
   Words: "this computer" when the person sits at it, else its name. Never "server", "engine" or "processing". */
type Mode = "local" | "remote" | "off";
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
interface Job { id: string; kind?: string; status: string; frac: number; msg: string; error: string; stage?: string }

const CLIPS_GB = 40;
const ABOUT: Record<string, string> = { ollama: "Plans each video and writes its script.", comfy: "Draws a picture for every sentence." };
const PROGRAM: Record<string, string> = { ollama: "Ollama", comfy: "ComfyUI" };
const ICON: Record<string, ReactNode> = { ollama: <PenLine size={20} />, comfy: <ImageIcon size={20} /> };
const OFF_NOTE: Record<string, string> = {
  ollama: "Videos are planned by simple rules, or by Claude or Codex if you connect them.",
  comfy: "Each picture becomes a card with the key words. The video is still made.",
};
export const gb = (n: number) => (n >= 100 ? String(Math.round(n)) : n > 0 ? n.toFixed(1).replace(/\.0$/, "") : "0") + " GB";   // one decimal below 100, so the rows add up to the total
const running = (j: Job | null) => !!j && ["queued", "running"].includes(j.status);

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
  const [custom, setCustom] = useState(false);
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [jobChecked, setJobChecked] = useState(false);
  const [planTick, setPlanTick] = useState(0);
  useEffect(() => {
    get<Overview>("/api/setup").then((d) => {
      setO(d);
      // what is already on the computer is used; otherwise install it when a model fits this card, else leave it for later
      const found=(id:string)=>!!d.existing?.[id]?.length;
      const fitsHere=(id:string)=>id==='comfy'?!!d.models?.pictures.some(p=>p.fits):true;
      const suggested=Object.fromEntries(Object.entries(d.recommended).map(([id,mode])=>[id,mode==='remote'&&!found(id)?(fitsHere(id)?'local':'off'):mode]));
      const initial={ ...suggested,...Object.fromEntries(Object.entries(d.existing||{}).filter(([,urls])=>urls.length).map(([id])=>[id,'remote'])), ...d.choices };
      setChoices(Object.fromEntries(Object.entries(initial).filter(([id])=>d.engines.some(e=>e.id===id))) as Record<string,Mode>);
      setUrls(Object.fromEntries(Object.entries(d.existing||{}).filter(([,urls])=>urls.length).map(([id,urls])=>[id,urls[0]])));
      const sep0 = d.server?.os === "Windows" ? "\\" : "/";
      setDir(d.models_dir || `${d.server?.data_dir || d.hardware.data_dir}${sep0}models`);
      setProgramDir(d.install_dir || `${d.server?.data_dir || d.hardware.data_dir}${sep0}engines`);
      const clipsOk = d.models?.clips.fits ?? true;
      setBundles((Array.isArray(d.bundles)?d.bundles:["pictures"]).filter((b) => b !== "clips" || clipsOk));
      // a saved model is kept only when it runs well (an old default that only works slowly gives way to the one that fits)
      const pics = d.models?.pictures || [];
      const saved = pics.find((p) => p.id === d.picture_model && p.fits);
      const best = pics.find((p) => p.id === d.models?.picture_default);
      setPictureModel(saved && (saved.speed === "fast" || best?.speed !== "fast") ? saved.id : d.models?.picture_default || "");
      setLanguageModel(d.models?.language.some((m) => m.id === d.language_model) ? d.language_model! : d.models?.language_default || "");
    }).catch((e) => toast(e.message, "err"));
    get<Job[]>("/api/jobs").then((js) => setJob(js.find((j) => j.kind === "setup" && running(j)) || null)).catch(() => {}).finally(() => setJobChecked(true));   // an install already under way
  }, []);
  const local = o ? o.engines.filter((e) => choices[e.id] === "local" && e.installable) : [];
  const localIds = local.map((e) => e.id).join(",");
  useEffect(() => {                                                  // what would download, from the computer itself (sizes, what is already there)
    if (!o) return;
    if (!localIds) { setPlans([]); return; }
    setPlans(null);
    const base = o.server?.data_dir || o.hardware.data_dir, sl = o.server?.os === "Windows" ? "\\" : "/";
    const md = dir === `${base}${sl}models` ? "" : dir, pd = programDir === `${base}${sl}engines` ? "" : programDir;     // the default folders go as "" (they stay the default)
    const q = `/api/setup/plan?engines=${localIds}&bundles=${bundles.join(",")}&models_dir=${encodeURIComponent(md)}&install_dir=${encodeURIComponent(pd)}&picture_model=${encodeURIComponent(pictureModel)}&language_model=${encodeURIComponent(languageModel)}`;
    const timer = setTimeout(() => get<Plan[]>(q).then(setPlans).catch((e) => toast(e.message, "err")), 250);
    return () => clearTimeout(timer);
  }, [o, localIds, bundles.join(","), dir, programDir, pictureModel, languageModel, planTick]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (job?.status === "done") setPlanTick((n) => n + 1); }, [job?.status]);
  useEffect(() => {
    if (!running(job)) return;
    const timer = setInterval(() => get<Job>(`/api/jobs/${job!.id}`).then(setJob).catch(() => {}), 1500);
    return () => clearInterval(timer);
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!o || !jobChecked) return <div className="ios-back"><div className="ios-sheet"><div className="ios-body"><Spinner /></div></div></div>;

  const here = !!o.same_computer;
  const name = o.server?.name || "the video computer";
  const where = here ? "this computer" : name;
  const remote = o.engines.filter((e) => choices[e.id] === "remote");
  const sep = o.server?.os === "Windows" ? "\\" : "/";
  const defaultDir = `${o.server?.data_dir || o.hardware.data_dir}${sep}models`, defaultProgramDir = `${o.server?.data_dir || o.hardware.data_dir}${sep}engines`;
  const dirOut = dir === defaultDir ? "" : dir, programDirOut = programDir === defaultProgramDir ? "" : programDir;
  const saveChoices = () => put("/api/setup", { choices, models_dir: dirOut, install_dir: programDirOut, bundles, picture_model: pictureModel, language_model: languageModel });
  const m = o.models;
  const cardGb = m?.card.gb || 0;
  const pick = (list: ModelOption[] | undefined, id: string) => list?.find((x) => x.id === id);
  const totalGb = (plans || []).reduce((a, p) => a + p.total_gb, 0);
  const problems = (plans || []).flatMap((p) => p.problems);
  const start = async () => {
    await saveChoices();
    const j = await post<Job>("/api/setup/install", { engines: local.map((e) => e.id), bundles, models_dir: dirOut, install_dir: programDirOut, picture_model: pictureModel, language_model: languageModel });
    setJob(j);
  };
  const setMode = (id: string, v: Mode) => setChoices({ ...choices, [id]: v });

  /* one line per AI program: what it does, what this computer gets (model + how well it runs), the size */
  const summary = (e: Overview["engines"][number]) => {
    const mode = choices[e.id] ?? "off";
    const x = e.id === "comfy" ? pick(m?.pictures, pictureModel) : pick(m?.language, languageModel);
    const have = mode === "local" && plans?.find((p) => p.engine === e.id)?.total_gb === 0;      // already installed: nothing left to download
    const status = have && x ? <><CircleCheck size={14} aria-hidden /> {x.label}<span className="muted"> · installed</span></>
      : mode === "local" && x ? <><FitIcon x={x} /> {x.label}<span className="muted"> · {x.speed === "fast" && x.note ? x.note : fitWords(x, cardGb)}</span></>
      : mode === "remote" ? <><Link2 size={14} aria-hidden /> Uses the {PROGRAM[e.id]} {urls[e.id] ? `found on ${where}` : "you already have"}</>
      : <><CircleSlash size={14} aria-hidden /> Not now. {OFF_NOTE[e.id]}</>;
    return (
      <div key={e.id} className={`pick-row ${mode === "off" ? "off" : ""}`} data-testid={`pick-${e.id}`}>
        <span className={`pick-icon ${e.id}`} aria-hidden>{ICON[e.id]}</span>
        <span className="pick-main">
          <strong>{plain(e.id, e.label)}</strong>
          <span className="small muted">{ABOUT[e.id]}</span>
          <span className={`pick-status ${have ? "fast" : mode === "local" && x ? (x.speed === "fast" ? "fast" : "slow") : ""}`}>{status}</span>
        </span>
        {mode === "local" && x && !have && <span className="pick-size" title="The program and its model">{gb(plans?.find((p) => p.engine === e.id)?.total_gb ?? x.download_gb)}</span>}
      </div>
    );
  };
  const clipsRow = choices.comfy === "local" && (
    <div className={`pick-row ${m?.clips.fits === false ? "off" : ""}`} data-testid="pick-clips">
      <span className="pick-icon clips" aria-hidden><Clapperboard size={20} /></span>
      <span className="pick-main">
        <strong>Moving clips</strong>
        <span className="small muted">Turns some pictures into short moving shots.</span>
        {m?.clips.fits === false
          ? <span className="pick-status"><Lock size={14} aria-hidden /> {m.clips.why}</span>
          : <label className="pick-status"><input type="checkbox" checked={bundles.includes("clips")}
              onChange={(ev) => setBundles(ev.target.checked ? [...bundles.filter((b) => b !== "clips"), "clips"] : bundles.filter((b) => b !== "clips"))} /> Add them (about {CLIPS_GB} GB more)</label>}
      </span>
    </div>
  );
  const chooser = (e: Overview["engines"][number]) => {
    const mode = choices[e.id] ?? "off";
    const models = e.id === "comfy" ? m?.pictures : m?.language;
    return (
      <Group key={e.id} title={`${plain(e.id, e.label)} (${PROGRAM[e.id]})`}>
        <div className="ios-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
          <div className="choice-pills" role="radiogroup" aria-label={`${plain(e.id, e.label)}: how to get it`}
            onKeyDown={(ev) => {                                       // a radio group: arrows choose, only the chosen one is in the Tab order
              const order: Mode[] = ["local", "remote", "off"], k = order.indexOf(mode);
              const step = ev.key === "ArrowRight" || ev.key === "ArrowDown" ? 1 : ev.key === "ArrowLeft" || ev.key === "ArrowUp" ? -1 : 0;
              if (!step) return;
              ev.preventDefault();
              const to = order[(k + step + order.length) % order.length], box = ev.currentTarget;   // currentTarget is gone after the handler
              setMode(e.id, to);
              requestAnimationFrame(() => box.querySelector<HTMLElement>(`[data-mode="${to}"]`)?.focus());
            }}>
            {([["local", <Download size={16} />, "Install it"], ["remote", <Link2 size={16} />, "I already have it"], ["off", <CircleSlash size={16} />, "Not now"]] as const).map(([v, icon, label]) => (
              <button key={v} type="button" role="radio" data-mode={v} aria-checked={mode === v} tabIndex={mode === v ? 0 : -1} className={mode === v ? "on" : ""} onClick={() => setMode(e.id, v)}>{icon}{label}</button>
            ))}
          </div>
          <span className="small muted">{mode === "local" ? `Video Tool downloads it and sets it up on ${where}.` : mode === "remote" ? "You connect it on the next screen." : OFF_NOTE[e.id]}</span>
          {mode === "local" && models && models.length > 0 && (
            <ModelList name={`model-${e.id}`} options={models} value={e.id === "comfy" ? pictureModel : languageModel} onChange={e.id === "comfy" ? setPictureModel : setLanguageModel} cardGb={cardGb} />
          )}
        </div>
      </Group>
    );
  };
  const nothing = !local.length && !remote.length;
  const ready = !local.length || job?.status === "done" || (plans !== null && totalGb === 0);
  // leaving early keeps every choice; say where to come back
  const closeWith = (note = "Your choices are kept. Open Set up again from the banner or the Server page.") => {
    saveChoices().then(() => { toast(note); onClose(); }).catch((e: any) => toast(e.message, "err"));
  };
  const gpu = o.hardware.gpus[0];

  const steps = [
    {
      next: { hidden: true },
      title: here ? "Set up the AI on this computer" : `Set up the AI on ${name}`, icon: <Sparkles size={26} />,
      subtitle: here ? "We picked what fits this computer. Press Install and Video Tool does the rest."
        : `We picked what fits ${name}, the computer that makes your videos. Everything goes there, not on the computer you are using now.`,
      body: (go: { next: () => void }) => (
        <>
          <div className="hw-strip" aria-label={here ? "This computer" : name}>
            <span><Gauge size={16} aria-hidden /> {gpu ? `${gpu.name.replace(/^NVIDIA (GeForce )?/, "")} · ${gpu.memory_gb} GB` : "No graphics card"}</span>
            <span><MemoryStick size={16} aria-hidden /> {Math.round(o.hardware.ram_gb)} GB memory</span>
            <span><HardDrive size={16} aria-hidden /> {Math.round(o.hardware.disk_free_gb)} GB free</span>
          </div>
          <div className="pick-list">
            {o.engines.map(summary)}
            {clipsRow}
          </div>
          <div className="pick-row folder" data-testid="pick-folder">
            <span className="pick-icon folder" aria-hidden><HardDrive size={20} /></span>
            <span className="pick-main">
              <strong>Saves downloads to</strong>
              <FolderPicker value={dir} placeholder={`${o.hardware.data_dir}${sep}models`} onChange={setDir} label="Downloads folder" where={where} />
            </span>
          </div>
          {problems.map((x, i) => <p key={i} className="small status-line bad" role="alert"><i aria-hidden />{x}</p>)}
          <div className="setup-go">
            {local.length > 0 && plans !== null && plans.length > 0 && totalGb === 0 && !running(job)
              ? <button type="button" className="btn primary lg" data-testid="setup-go" onClick={() => Promise.resolve(saveChoices()).then(go.next).catch((e: any) => toast(e.message, "err"))}><CircleCheck size={18} aria-hidden /> Everything is installed · Continue</button>
              : running(job) ? <button type="button" className="btn primary lg" onClick={go.next}><Spinner size={16} /> Installing… see how far it is</button>
              : <button type="button" className="btn primary lg" data-testid="setup-go" disabled={plans === null || problems.length > 0}
                  onClick={() => (local.length ? start().then(go.next) : Promise.resolve(saveChoices()).then(go.next)).catch((e: any) => toast(e.errors?.[0] || e.message, "err", 8000))}>
                  {local.length ? <><Download size={18} aria-hidden /> {plans === null ? "Working out the size…" : `Install everything · ${gb(totalGb)}`}</>
                    : nothing ? "Continue without AI" : <><Link2 size={18} aria-hidden /> Connect what I have</>}
                </button>}
            <button type="button" className="btn ghost" aria-expanded={custom} onClick={() => setCustom(!custom)}><SlidersHorizontal size={16} aria-hidden /> {custom ? "Hide the choices" : "Choose myself"}</button>
          </div>
          {custom && (
            <div className="setup-custom">
              {o.engines.map(chooser)}
              <Group title="Programs folder" note="Only if the programs should not go next to the downloads.">
                <div className="ios-row"><FolderPicker value={programDir} placeholder={`${o.hardware.data_dir}${sep}engines`} onChange={setProgramDir} label="Programs folder" where={where} /></div>
              </Group>
            </div>
          )}
        </>
      ),
    },
    {
      next: !local.length || job?.status === "done" || totalGb === 0 ? undefined
        : running(job) ? { label: "Close, it keeps going", primary: false, onClick: () => closeWith("The install keeps going. Open Set up again any time to see it.") }
        : { label: "Do it later", primary: false, onClick: () => closeWith() },
      title: job?.status === "done" ? "Installed" : running(job) ? "Installing" : remote.length && !local.length ? "Connect what you have" : "Install",
      icon: <Download size={26} />,
      subtitle: running(job) ? "You can close this window. It keeps going and you can come back here any time." : job?.status === "done" ? "Everything is in place. Continue to check that it works."
        : nothing ? "Nothing to install or connect. You can set this up later on the Server page." : "",
      body: (
        <>
          {remote.map((e) => <Connect key={e.id} id={e.id} label={plain(e.id, e.label)} url={urls[e.id] ?? ""} setUrl={(u) => setUrls({ ...urls, [e.id]: u })} where={where} />)}
          {local.length > 0 && <Install plans={plans} job={job} total={totalGb} problems={problems} onStart={() => start().catch((e: any) => toast(e.errors?.[0] || e.message, "err", 8000))}
            onCancel={() => job && post(`/api/jobs/${job.id}/cancel`).then(() => get<Job>(`/api/jobs/${job.id}`).then(setJob)).catch((e) => toast(e.message, "err"))} />}
        </>
      ),
    },
    {
      locked: ready ? undefined : "install first",
      title: "Check it works", icon: <Check size={26} />, subtitle: "Video Tool asks each AI program for a tiny piece of work.",
      body: <Try ids={o.engines.filter((e) => choices[e.id] && choices[e.id] !== "off").map((e) => e.id)} waiting={running(job)} />,
    },
  ];
  const manyCards=o.hardware.gpus.length>=2;                       // with two or more cards the person first decides which ones Video Tool may use
  const cardsStep={title:t("gpu.setup.title"),subtitle:t("gpu.setup.sub"),icon:<Gauge size={26}/>,body:(go:{next:()=>void})=><GpuChoice mode="setup" onAnswered={go.next} onSkip={go.next}/>};
  const visibleSteps=manyCards?[cardsStep,...steps]:steps;
  const stateSteps=manyCards?['cards','choose','install','try']:['choose','install','try'];
  const at=(n:string)=>Math.max(0,stateSteps.indexOf(n));
  const initial=running(job)?at('install'):o.step==='cards'?at('cards'):o.step==='connect'||o.step==='install'?at('install'):o.step==='try'||o.step==='done'?at('try'):at(manyCards?'cards':'choose');
  return <Steps label={here ? "Set up this computer" : `Set up ${name}`} steps={visibleSteps} start={initial} headerDone={false} doneLabel="Finish"
    onClose={()=>closeWith(running(job)?"The install keeps going. Open Set up again any time to see it.":undefined)}
    onStep={i=>{saveChoices().then(()=>put('/api/setup',{step:stateSteps[i]})).catch(e=>toast(e.message,'err'));}}
    onDone={async()=>{try{await saveChoices();await put('/api/setup',{step:'done',done:true});onClose();}catch(e:any){toast(e.message,'err');}}}/>;
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
  const usual = id === "ollama" ? "http://127.0.0.1:11434" : "http://127.0.0.1:8188";
  useEffect(() => { if (!url) setUrl(usual); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const tried = useRef(false);
  useEffect(() => { if (url && !tried.current) { tried.current = true; test(); } }, []); // eslint-disable-line react-hooks/exhaustive-deps -- a found program connects by itself
  return (
    <Group title={`Your ${label} (${id === 'comfy' ? 'ComfyUI' : 'Ollama'})`}>
      <Row label={t("setup.address")} stack><input type="text" value={url} onChange={(e) => {setUrl(e.target.value);setConnectedUrl('');setSays('');setNeedsModel(false);}} aria-label={`${label}: ${t("setup.address")}`} spellCheck={false} style={{ width: "100%" }} /><span className="small muted">{url === usual ? `The usual address on ${where}. Change it only if the program runs elsewhere, then press Connect.` : url ? `Found on ${where}. Change it only if the program runs on a different computer.` : "Type the address the program shows when it starts, then press Connect."}</span></Row>
      <div className="ios-row engine-test">
        <button className="btn sm" onClick={test} disabled={busy || !url.trim()}>{busy ? t("setup.testing") : connectedUrl ? "Connect again" : 'Connect'}</button>
        {says && <p className={`status-line ${connectedUrl ? "ok" : "bad"}`} role="status"><i aria-hidden />{says}</p>}
      </div>
      {needsModel&&<Row label="It has no model yet" stack><span className="small muted">The model goes into this Ollama's own model folder.</span><button className="btn" disabled={!!modelJob&&!['error','cancelled'].includes(modelJob.status)} onClick={()=>post('/api/setup/ollama-model').then(setModelJob).catch(e=>toast(e.message,'err'))}><Download size={16} aria-hidden /> Download the recommended model</button>{modelJob&&<span className="small">{Math.round((modelJob.frac||0)*100)}% · {modelJob.msg||modelJob.status}</span>}</Row>}
      {id==='comfy'&&connectedUrl&&<PrepareComfy key={connectedUrl} url={connectedUrl}/>}
    </Group>
  );
}

/* What downloads, then the install itself: one bar, the step it is on, and Cancel. */
function Install({ plans, job, total, problems, onStart, onCancel }: { plans: Plan[] | null; job: Job | null; total: number; problems: string[]; onStart: () => void; onCancel: () => void }) {
  const t = useT();
  const plain = (id: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? id : v; };
  if (!plans) return <p className="small muted row" style={{ gap: 8 }}><Spinner size={14} /> Working out what to download…</p>;
  const list = (
    <details className="setup-more" open={!job}>
      <summary className="small">What downloads ({gb(total)})</summary>
      {plans.map((p) => (
        <Group key={p.engine} title={plain(p.engine)} note={p.notes.join(" ")}>
          {p.items.map((i) => <Row key={i.name} label={<span className="row" style={{ gap: 6 }}>{i.done ? <CircleCheck size={14} className="ok-icon" aria-hidden /> : <Download size={14} aria-hidden />}{i.name}</span>}>{i.done ? t("setup.already") : gb(i.size_gb)}</Row>)}
        </Group>
      ))}
    </details>
  );
  if (!job && total === 0 && !problems.length) return <p className="status-line ok" role="status" data-testid="setup-nothing-left"><i aria-hidden />Everything is already installed. Continue to check that it works.</p>;
  if (!job) return (
    <>
      {list}
      {problems.map((x, i) => <p key={i} className="small status-line bad" role="alert"><i aria-hidden />{x}</p>)}
      <button className="btn primary lg" onClick={onStart} disabled={problems.length > 0} data-testid="setup-start"><Download size={18} aria-hidden /> {total > 0 ? `Install · ${gb(total)}` : t("setup.start")}</button>
    </>
  );
  const pct = Math.round((job.frac || 0) * 100);
  const state = job.status === "done" ? "ok" : job.status === "error" ? "bad" : job.status === "cancelled" ? "" : "busy";
  return (
    <>
      <div className={`install-card ${state}`} role="status" data-testid="setup-progress">
        <span className="install-icon" aria-hidden>{state === "ok" ? <CircleCheck size={28} /> : state === "bad" ? <CircleX size={28} /> : job.status === "cancelled" ? <CircleSlash size={28} /> : <Spinner size={24} />}</span>
        <span className="pick-main">
          <strong>{state === "ok" ? "All installed" : state === "bad" ? "The install stopped" : job.status === "cancelled" ? "Stopped" : `${job.stage ? plain(job.stage) + " · " : ""}${pct}%`}</strong>
          <span className="small muted">{state === "bad" ? job.error : state === "ok" ? "Continue to check that it works." : job.msg || "Starting…"}</span>
          {state === "busy" && <progress max={100} value={pct} aria-label="Install progress" />}
        </span>
      </div>
      {state === "busy" && <button type="button" className="btn ghost" onClick={onCancel}>Stop the install</button>}
      {(state === "bad" || job.status === "cancelled") && <button type="button" className="btn primary" onClick={onStart}><Download size={16} aria-hidden /> Try again (finished parts are kept)</button>}
      {list}
    </>
  );
}

/* The check runs by itself when the screen opens; a tick or a cross per program. */
function Try({ ids, waiting }: { ids: string[]; waiting: boolean }) {
  const t = useT();
  const plain = (id: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? id : v; };
  const [says, setSays] = useState<Record<string, { ok?: boolean; text: string; image?: string }>>({});
  const run = async (id: string) => {
    setSays((s) => ({ ...s, [id]: { text: t("setup.trying") } }));
    try {
      const r = await post<{ ok: boolean; says: string; image?: string }>(`/api/setup/try/${id}`);
      setSays((s) => ({ ...s, [id]: { ok: r.ok, text: r.says, image: r.image } }));
    } catch (e: any) {
      setSays((s) => ({ ...s, [id]: { ok: false, text: e.message } }));
    }
  };
  useEffect(() => { if (!waiting) ids.forEach(run); }, [waiting, ids.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!ids.length) return <p className="muted">{t("setup.nothingconnected")}</p>;
  if (waiting) return <p className="small muted row" style={{ gap: 8 }}><Spinner size={14} /> Waiting for the install to finish…</p>;
  return (
    <div className="pick-list">
      {ids.map((id) => {
        const s = says[id];
        return (
          <div key={id} className="pick-row" data-testid={`try-${id}`}>
            <span className={`pick-icon ${id}`} aria-hidden>{ICON[id]}</span>
            <span className="pick-main">
              <strong>{plain(id)}</strong>
              <span className={`pick-status ${s?.ok ? "fast" : s?.ok === false ? "bad" : ""}`}>
                {!s || s.ok === undefined ? <><Spinner size={14} /> {id === "comfy" ? "Drawing a test picture… the first one can take a minute" : s?.text || t("setup.trying")}</> : s.ok ? <><CircleCheck size={14} aria-hidden /> Works. {s.text}</> : <><CircleX size={14} aria-hidden /> {s.text}</>}
              </span>
              {s?.image && <img className="try-picture" src={s.image} alt="The test picture Video Tool drew" />}
            </span>
            {s && s.ok !== undefined && <button className="btn sm" onClick={() => run(id)}>Again</button>}
          </div>
        );
      })}
    </div>
  );
}
