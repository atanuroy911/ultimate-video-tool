import { Check, Images } from "lucide-react";
import { useState } from "react";
import { get, put } from "../api";
import { useFetch } from "../hooks";
import { toast } from "../store";
import { Field } from "../ui";

/** Optional: free API keys for Pexels and Pixabay stock photos and videos. Kept on this computer; sent only to their own provider. */
export default function StockKeys() {
  const st = useFetch<Record<string, boolean>>("/api/stock/status");
  const [pexels, setPexels] = useState("");
  const [pixabay, setPixabay] = useState("");

  const save = async (patch: Record<string, string>) => {
    try {
      const cur = await get<Record<string, unknown>>("/api/settings");
      await put("/api/settings", { ...cur, ...patch });
      st.refetch();
      toast("Saved", "ok", 1500);
    } catch (e: any) {
      toast(e.message, "err");
    }
  };

  return (
    <section className="card card-pad col" style={{ gap: 12 }} aria-label="Stock media">
      <div className="row wrap">
        <h2 className="grow"><Images size={18} style={{ verticalAlign: -3 }} /> Find free pictures and clips</h2>
        <span className={`chip ${st.data && Object.values(st.data).some(Boolean) ? "ok" : ""}`}>
          {st.data && Object.values(st.data).some(Boolean) ? <><Check size={12} /> On</> : "Not set up"}
        </span>
      </div>
      <p className="muted" style={{ margin: 0 }}>
        Search Pexels and Pixabay from the media bin. Each needs a free key from its own site (pexels.com/api, pixabay.com/api/docs).
        Keys are kept on your server and sent only to that site. Credits are added to every export.
      </p>
      <div className="row wrap" style={{ gap: 12, alignItems: "flex-end" }}>
        <Field label={`Pexels key${st.data?.pexels ? " (saved)" : ""}`}>
          <input type="password" value={pexels} onChange={(e) => setPexels(e.target.value)} onBlur={() => pexels && save({ pexels_key: pexels.trim() }).then(() => setPexels(""))} placeholder={st.data?.pexels ? "••••••••" : "Paste key"} autoComplete="off" style={{ minWidth: 240 }} />
        </Field>
        <Field label={`Pixabay key${st.data?.pixabay ? " (saved)" : ""}`}>
          <input type="password" value={pixabay} onChange={(e) => setPixabay(e.target.value)} onBlur={() => pixabay && save({ pixabay_key: pixabay.trim() }).then(() => setPixabay(""))} placeholder={st.data?.pixabay ? "••••••••" : "Paste key"} autoComplete="off" style={{ minWidth: 240 }} />
        </Field>
        {st.data?.pexels && <button className="btn sm ghost" onClick={() => save({ pexels_key: "" })}>Remove Pexels key</button>}
        {st.data?.pixabay && <button className="btn sm ghost" onClick={() => save({ pixabay_key: "" })}>Remove Pixabay key</button>}
      </div>
    </section>
  );
}
