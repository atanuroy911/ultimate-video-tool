import { Check, Cpu, FolderOpen, Image as ImageIcon, MessageSquare, Mic, PlayCircle, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import { Group, Row, Steps } from "../ds";
import { useT } from "../i18n";
import { toast } from "../store";
import { Seg, Spinner } from "../ui";

/* The first-run setup, as seven small steps (docs/plans/PLAN-ENGINES-AND-SETUP.MD 3.2). Leave at any step; it resumes where it stopped. */
type Mode = "local" | "remote" | "off";
interface Overview {
  step: string; done: boolean; choices: Record<string, Mode>; bundles: string[]; models_dir: string; steps: string[];
  hardware: { summary: string; disk_free_gb: number; ram_gb: number; data_dir: string; gpus: { name: string; memory_gb: number }[] };
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
  const [bundles, setBundles] = useState<string[]>(["pictures"]);
  const [urls, setUrls] = useState<Record<string, string>>({});
  useEffect(() => {
    get<Overview>("/api/setup").then((d) => {
      setO(d);
      setChoices({ ...d.recommended, ...d.choices });
      setDir(d.models_dir);
      setBundles(d.bundles);
    }).catch((e) => toast(e.message, "err"));
  }, []);
  if (!o) return <div className="ios-back"><div className="ios-sheet"><div className="ios-body"><Spinner /></div></div></div>;

  const remote = o.engines.filter((e) => choices[e.id] === "remote");
  const local = o.engines.filter((e) => choices[e.id] === "local" && e.installable);
  const saveChoices = () => put("/api/setup", { choices, models_dir: dir, bundles }).catch((e) => toast(e.message, "err"));

  const steps = [
    {
      title: t("setup.welcome"), icon: <Cpu size={26} />, subtitle: t("setup.welcome.sub"),
      body: (
        <Group title={t("setup.thiscomputer")}>
          <Row label={t("setup.whatcando")} stack><span className="bn">{o.hardware.summary}</span></Row>
          <Row label={t("setup.disk")}>{o.hardware.disk_free_gb} GB</Row>
          <Row label={t("setup.memory")}>{o.hardware.ram_gb} GB</Row>
        </Group>
      ),
    },
    {
      title: t("setup.storage"), icon: <FolderOpen size={26} />, subtitle: t("setup.storage.sub"),
      body: (
        <Group title={t("setup.folder")} note={t("setup.folder.note").replace("{gb}", String(o.hardware.disk_free_gb))}>
          <Row label={t("setup.modelsfolder")} stack>
            <input type="text" value={dir} placeholder={`${o.hardware.data_dir}/models`} onChange={(e) => setDir(e.target.value)} aria-label={t("setup.modelsfolder")} spellCheck={false} style={{ width: "100%" }} />
          </Row>
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
                <Seg<Mode> label={`${e.label}: where it runs`} value={choices[e.id] ?? "off"} onChange={(m) => setChoices({ ...choices, [e.id]: m })}
                  options={[{ value: "local", label: t("setup.local") }, { value: "remote", label: t("setup.remote") }, { value: "off", label: t("setup.off") }]} />
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
      body: <Install engines={local.map((e) => e.id)} bundles={bundles} />,
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
  return (
    <Steps label={t("setup.title")} steps={steps} start={Math.max(0, o.steps.indexOf(o.step))} onClose={() => { saveChoices(); onClose(); }}
      onStep={(i) => { saveChoices(); put("/api/setup", { step: o.steps[i] }).catch(() => {}); }}
      onDone={async () => { await saveChoices(); await put("/api/setup", { step: "done", done: true }).catch(() => {}); onClose(); }} />
  );
}

function Connect({ id, label, url, setUrl }: { id: string; label: string; url: string; setUrl: (u: string) => void }) {
  const t = useT();
  const [says, setSays] = useState("");
  const [busy, setBusy] = useState(false);
  const test = async () => {
    setBusy(true);
    try {
      const h = await post<{ ok: boolean; why_not: string; capabilities: string[]; gpu: string }>(`/api/engines/${id}/test`, { mode: "remote", url });
      if (h.ok) {
        await put(`/api/engines/${id}`, { mode: "remote", url });
        setSays(`${t("setup.connected")}${h.gpu ? ` (${h.gpu})` : ""}. ${t("setup.itcan")}: ${h.capabilities.join(", ") || t("setup.nothingyet")}.`);
      } else setSays(h.why_not || t("setup.noanswer"));
    } catch (e: any) {
      setSays(e.errors?.[0] || e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Group title={label}>
      <Row label={t("setup.address")} stack><input type="text" value={url} placeholder="http://192.168.1.20:8188" onChange={(e) => setUrl(e.target.value)} aria-label={`${label}: ${t("setup.address")}`} spellCheck={false} style={{ width: "100%" }} /></Row>
      <Row label=""><button className="btn sm" onClick={test} disabled={busy || !url.trim()}>{busy ? t("setup.testing") : t("setup.test")}</button> <span className="small" role="status">{says}</span></Row>
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

function Install({ engines, bundles }: { engines: string[]; bundles: string[] }) {
  const t = useT();
  const plain = (id: string) => { const k = "setup.p." + id; const v = t(k); return v === k ? id : v; };
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [job, setJob] = useState<{ id: string; status: string; frac: number; msg: string; error: string } | null>(null);
  useEffect(() => {
    if (engines.length) get<Plan[]>(`/api/setup/plan?engines=${engines.join(",")}&bundles=${bundles.join(",")}`).then(setPlans).catch((e) => toast(e.message, "err"));
  }, [engines.join(","), bundles.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!job || ["done", "error", "cancelled"].includes(job.status)) return;
    const t = setInterval(() => get(`/api/jobs/${job.id}`).then(setJob).catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!engines.length) return null;
  if (!plans) return <Spinner />;
  const problems = plans.flatMap((p) => p.problems);
  const total = plans.reduce((a, p) => a + p.total_gb, 0);
  const start = () => post<any>("/api/setup/install", { engines, bundles }).then(setJob).catch((e) => toast(e.errors?.[0] || e.message, "err", 8000));
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
      setSays((s) => ({ ...s, [id]: (r.ok ? "✓ " : "✗ ") + r.says }));
    } catch (e: any) {
      setSays((s) => ({ ...s, [id]: "✗ " + e.message }));
    }
  };
  if (!ids.length) return <p className="muted">{t("setup.nothingconnected")}</p>;
  return <>{ids.map((id) => <Group key={id} title={plain(id)}><Row label=""><button className="btn sm" onClick={() => run(id)}>{t("setup.tryit")}</button> <span className="small bn" role="status">{says[id]}</span></Row></Group>)}</>;
}
