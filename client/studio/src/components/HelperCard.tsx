import { Check, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useT } from "../i18n";
import { toast } from "../store";
import { Spinner } from "../ui";

/** The helper on this PC (client/desktop/helper.js): the small program that keeps Claude and Codex ready for the person's servers, even when the app is closed.
 *  The desktop app offers it to the page as window.vtDesktop.helper; in a plain browser there is no helper to show, so the card says the app is needed. */
type Assistant = { found: boolean; logged_in: boolean; version: string; reason: string };
type HelperState = {
  running: boolean;
  version?: string;
  servers?: { server: string; connected: boolean; state: string; last_error: string }[];
  assistants?: Record<string, Assistant>;
  autostart: boolean;
  installed: boolean;
};
type Bridge = {
  status: () => Promise<HelperState>;
  start: () => Promise<HelperState>;
  stop: () => Promise<HelperState>;
  refresh: () => Promise<HelperState>;
  removeServer: (address: string) => Promise<HelperState>;
  setAutostart: (on: boolean) => Promise<HelperState>;
};
const bridge = (): Bridge | undefined => (window as any).vtDesktop?.helper;
const NAMES: Record<string, string> = { claude: "Claude", codex: "Codex" };
const plain = (address: string) => address.replace(/^https?:\/\//, "");

function AssistantRow({ kind, a }: { kind: string; a: Assistant }) {
  const t = useT();
  const checking = !a.found && a.reason === "Checking…";
  return (
    <li data-testid={`helper-${kind}`}>
      <span className="col grow" style={{ gap: 2, minWidth: 0 }}>
        <strong>{NAMES[kind] || kind}</strong>
        {a.found && a.logged_in && a.version && <span className="small muted">{a.version}</span>}
        {a.found && !a.logged_in && <span className="small muted">{a.reason}</span>}
      </span>
      {checking ? <Spinner /> : a.found && a.logged_in ? <span className="chip ok"><Check size={12} /> {t("helper.ready")}</span>
        : a.found ? <span className="chip warn">{t("helper.sign_in")}</span> : <span className="chip">{t("helper.not_installed")}</span>}
    </li>
  );
}

export default function HelperCard() {
  const t = useT();
  const [s, setS] = useState<HelperState | null>(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => { bridge()?.status().then(setS).catch(() => setS(null)); }, []);
  useEffect(() => {
    if (!bridge()) return;
    load();
    const timer = window.setInterval(load, 4000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!bridge()) {
    return (
      <section className="card card-pad col helper-card" aria-labelledby="helper-title" data-testid="helper-card" data-state="no-app">
        <h2 id="helper-title">{t("helper.title")}</h2>
        <p className="muted" style={{ margin: 0 }}>{t("helper.needs_app")}</p>
      </section>
    );
  }
  const act = async (name: string, run: () => Promise<HelperState>) => {
    setBusy(name);
    try {
      setS(await run());
    } catch (e: any) {
      toast(String(e?.message || e).replace(/^Error invoking remote method '[^']+': (?:Error: )?/, ""), "err", 8000);
    } finally {
      setBusy("");
    }
  };
  const b = bridge()!;
  const servers = s?.servers || [];
  const toggle = () => { if (s && s.installed && !busy) act("autostart", () => b.setAutostart(!s.autostart)); };
  return (
    <section className="card card-pad col helper-card" aria-labelledby="helper-title" data-testid="helper-card" data-state={s ? (s.running ? "running" : "stopped") : "loading"} style={{ gap: 14 }}>
      <div className="row" style={{ gap: 10, alignItems: "center" }}>
        <h2 id="helper-title" className="grow">{t("helper.title")}</h2>
        <span role="status">
          {!s ? <Spinner /> : s.running ? <span className="chip ok" data-testid="helper-state"><span className="dot ok" /> {t("helper.running")}</span> : <span className="chip warn" data-testid="helper-state">{t("helper.stopped")}</span>}
        </span>
      </div>
      <p className="muted" style={{ margin: 0 }}>{t("helper.what")}</p>

      {s && !s.running && (
        <div className="col" style={{ gap: 8 }}>
          <p className="small muted" style={{ margin: 0 }}>{t("helper.stop_note")}</p>
          <div><button className="btn primary" disabled={!!busy} onClick={() => act("start", b.start)} data-testid="helper-start">{busy === "start" ? <Spinner /> : t("helper.start")}</button></div>
        </div>
      )}

      {s?.running && (
        <>
          <div className="col" style={{ gap: 4 }}>
            <h3 className="helper-heading">{t("helper.servers")}</h3>
            {servers.length === 0 ? <p className="small muted" style={{ margin: 0 }}>{t("helper.no_servers")}</p> : (
              <ul className="helper-list" data-testid="helper-servers">
                {servers.map((v) => (
                  <li key={v.server} className="helper-server">
                    <span className="helper-address">{plain(v.server)}</span>
                    <button className="btn sm ghost" disabled={!!busy} onClick={() => act("remove", () => b.removeServer(v.server))} aria-label={`${t("helper.remove")}: ${plain(v.server)}`}>{t("helper.remove")}</button>
                    <span className="helper-status">
                      {v.connected ? <span className="chip ok"><Check size={12} /> {t("helper.connected")}</span>
                        : v.state === "connecting" && !v.last_error ? <span className="chip"><Spinner size={12} /> {t("helper.connecting")}</span> : <span className="chip warn">{t("helper.unreachable")}</span>}
                      {!v.connected && v.last_error && <span className="small muted">{v.last_error}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="col" style={{ gap: 4 }}>
            <h3 className="helper-heading">{t("helper.on_this_pc")}</h3>
            <ul className="helper-list" data-testid="helper-assistants">
              {Object.entries(s.assistants || {}).map(([kind, a]) => <AssistantRow key={kind} kind={kind} a={a} />)}
            </ul>
          </div>
        </>
      )}

      {s && (
        <div className={`switch-row${s.installed ? "" : " off"}`} onClick={toggle}>
          <span className="col grow" style={{ gap: 2, minWidth: 0 }}>
            <span id="helper-keep" style={{ fontWeight: 600 }}>{t("helper.keep")}</span>
            <span className="small muted">{s.installed ? t("helper.keep.sub") : t("helper.keep.dev")}</span>
          </span>
          <button type="button" role="switch" aria-checked={s.autostart} aria-labelledby="helper-keep" className="switch" disabled={!s.installed || !!busy}
            onClick={(e) => { e.stopPropagation(); toggle(); }} data-testid="helper-autostart" />
        </div>
      )}

      {s?.running && (
        <div className="row" style={{ gap: 8 }}>
          <button className="btn sm" disabled={!!busy} onClick={() => act("refresh", b.refresh)} data-testid="helper-refresh">{busy === "refresh" ? <Spinner /> : <><RefreshCw size={13} /> {t("helper.check_again")}</>}</button>
          <button className="btn sm ghost" disabled={!!busy} onClick={() => act("stop", b.stop)} data-testid="helper-stop">{busy === "stop" ? <Spinner /> : t("helper.stop")}</button>
        </div>
      )}
    </section>
  );
}
