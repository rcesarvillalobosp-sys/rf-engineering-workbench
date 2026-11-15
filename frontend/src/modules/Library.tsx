import { Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Plot } from "../components/Plot";
import { Btn, Empty, Field, Input, KV, Note, PageHeader, Panel, Select, Table, useCall } from "../components/ui";
import { del, get, post, put } from "../lib/api";
import { arr, si } from "../lib/format";
import { useStore } from "../lib/store";

const EMPTY = { category: "inductor", name: "", value: "", unit: "H", tolerance_pct: "", q_factor: "", q_freq_hz: "", esr_ohm: "", srf_hz: "", manufacturer: "", part_number: "", notes: "" };
const UNIT: Record<string, string> = { resistor: "Ω", inductor: "H", capacitor: "F", varcap: "F", transformer: "", tline: "Ω", coax: "Ω" };

export function LibraryModule() {
  const toast = useStore((s) => s.toast);
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const [data, setData] = useState<any>(null);
  const [sel, setSel] = useState<any>(null);
  const [edit, setEdit] = useState<any>(null);
  const load = () => get(`/library?${new URLSearchParams({ ...(cat ? { category: cat } : {}), ...(q ? { q } : {}) })}`).then(setData).catch((e) => toast("err", e.message));
  useEffect(() => { load(); }, [cat, q]);
  const kind = sel && ({ resistor: "R", inductor: "L", capacitor: "C", varcap: "C" } as any)[sel.category];
  const model = useCall(() => post("/component/impedance", { kind, value: sel.value, q: sel.q_factor, q_freq: sel.q_freq_hz, esr: sel.esr_ohm, srf: sel.srf_hz,
    f_start: 1e6, f_stop: sel.srf_hz ? sel.srf_hz * 3 : 3e9, n: 601 }), sel && kind && sel.value ? [sel?.id] : null, 50);

  const save = async () => {
    const body: any = { ...edit, unit: UNIT[edit.category] };
    for (const k of ["tolerance_pct", "q_factor", "esr_ohm"]) body[k] = body[k] === "" ? null : Number(body[k]);
    for (const k of ["value", "q_freq_hz", "srf_hz"]) body[k] = body[k] === "" ? null : body[k];
    for (const k of ["manufacturer", "part_number", "notes"]) body[k] = body[k] || null;
    try {
      if (edit.id) await put(`/library/${edit.id}`, body); else await post("/library", body);
      toast("ok", "Componente guardado");
      setEdit(null);
      load();
    } catch (e: any) { toast("err", e.message); }
  };

  const items: any[] = data?.items ?? [];
  const m = model.data as any;
  return (
    <div>
      <PageHeader index={8} title="Component Library" desc="Componentes ideales y modelos reales (Q, ESR, SRF). Los componentes genéricos no tienen fabricante; añada piezas reales con datos de su hoja de características." right={<Btn variant="primary" small icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setEdit({ ...EMPTY })}>Nuevo componente</Btn>} />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Panel title={`Componentes (${items.length})`} actions={<div className="flex gap-2"><Select value={cat} onChange={setCat} options={[{ value: "", label: "Todas las categorías" }, ...Object.entries<string>(data?.categories ?? {}).map(([v, l]) => ({ value: v, label: l }))]} /><Input mono={false} placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)} /></div>}>
          <div className="max-h-[calc(100vh-230px)] overflow-auto">
            <Table head={["Nombre", "Valor", "Tol.", "Q", "ESR", "SRF", "Modelo", "Origen", ""]} active={items.findIndex((i) => i.id === sel?.id)} onRow={(i) => setSel(items[i])}
              rows={items.map((c) => [<span className="font-sans">{c.name}</span>, c.category === "coax" || c.category === "tline" ? `${c.extra?.z0} Ω · vf ${c.extra?.vf}` : si(c.value, c.unit ?? "", 4), c.tolerance_pct != null ? `±${c.tolerance_pct}%` : "—",
                c.q_factor ?? "—", c.esr_ohm != null ? `${c.esr_ohm} Ω` : "—", c.srf_hz ? si(c.srf_hz, "Hz", 4) : "—",
                <span className={c.model === "real" ? "text-warn" : "text-dim"}>{c.model === "real" ? "Real" : "Ideal"}</span>, <span className="text-dim">{c.source === "generico" ? "Genérico" : "Usuario"}</span>,
                <span className="flex gap-1.5"><button className="text-faint hover:text-acc" onClick={(e) => { e.stopPropagation(); setEdit({ ...EMPTY, ...Object.fromEntries(Object.entries(c).map(([k, v]) => [k, v ?? ""])) }); }}><Pencil className="h-3.5 w-3.5" /></button>
                  <button className="text-faint hover:text-err" onClick={async (e) => { e.stopPropagation(); if (confirm(`¿Eliminar «${c.name}»?`)) { await del(`/library/${c.id}`); load(); } }}><Trash2 className="h-3.5 w-3.5" /></button></span>])} />
          </div>
        </Panel>
        <div className="space-y-3">
          {edit && (
            <Panel title={edit.id ? "Editar componente" : "Nuevo componente"}>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Categoría"><Select value={edit.category} onChange={(v) => setEdit({ ...edit, category: v })} options={Object.entries<string>(data?.categories ?? {}).map(([v, l]) => ({ value: v, label: l }))} /></Field>
                <Field label={`Valor (${UNIT[edit.category] || "—"})`} hint="Admite prefijos: 12n, 4.7p, 1k"><Input value={edit.value} onChange={(e) => setEdit({ ...edit, value: e.target.value })} /></Field>
                <Field label="Nombre" className="col-span-2"><Input mono={false} value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
                <Field label="Tolerancia (±%)"><Input value={edit.tolerance_pct} onChange={(e) => setEdit({ ...edit, tolerance_pct: e.target.value })} /></Field>
                <Field label="Factor Q"><Input value={edit.q_factor} onChange={(e) => setEdit({ ...edit, q_factor: e.target.value })} /></Field>
                <Field label="Frecuencia del Q"><Input value={edit.q_freq_hz} placeholder="p. ej. 100M" onChange={(e) => setEdit({ ...edit, q_freq_hz: e.target.value })} /></Field>
                <Field label="ESR (Ω)"><Input value={edit.esr_ohm} onChange={(e) => setEdit({ ...edit, esr_ohm: e.target.value })} /></Field>
                <Field label="SRF"><Input value={edit.srf_hz} placeholder="p. ej. 2.4G" onChange={(e) => setEdit({ ...edit, srf_hz: e.target.value })} /></Field>
                <Field label="Fabricante"><Input mono={false} value={edit.manufacturer} onChange={(e) => setEdit({ ...edit, manufacturer: e.target.value })} /></Field>
                <Field label="Referencia" className="col-span-2"><Input value={edit.part_number} onChange={(e) => setEdit({ ...edit, part_number: e.target.value })} /></Field>
                {(edit.category === "coax" || edit.category === "tline") && (
                  <div className="col-span-2 grid grid-cols-2 gap-2 rounded border border-line p-2">
                    {([["z0", "Z0 (Ω)", "50"], ["vf", "Factor de velocidad", "0.66"], ["atten_db_per_100m", "Atenuación (dB/100 m)", "hoja de datos"], ["atten_ref_hz", "a la frecuencia", "p. ej. 100M"]] as const).map(([k, l, ph]) => (
                      <Field key={k} label={l}><Input value={edit.extra?.[k] ?? ""} placeholder={ph} onChange={(e) => setEdit({ ...edit, extra: { ...(edit.extra || {}), [k]: e.target.value } })} /></Field>
                    ))}
                    <p className="col-span-2 text-2xs text-faint">Con atenuación y frecuencia de referencia, Transmission Lines la escala como α(f) = α_ref·√(f/f_ref) (pérdidas de conductor).</p>
                  </div>
                )}
                <Field label="Notas / fuente de los datos" className="col-span-2"><Input mono={false} value={edit.notes} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} /></Field>
              </div>
              <Note className="mt-2">Introduzca sólo datos de la hoja de características del fabricante. Con Q, ESR o SRF el componente se trata como modelo real.</Note>
              <div className="mt-2 flex gap-2"><Btn variant="primary" small onClick={save}>Guardar</Btn><Btn small variant="subtle" onClick={() => setEdit(null)}>Cancelar</Btn></div>
            </Panel>
          )}
          {sel ? (
            <Panel title={sel.name} sub={sel.source === "generico" ? "Componente genérico" : "Añadido por el usuario"}>
              <KV dense rows={[["Categoría", data?.categories?.[sel.category]], ["Valor", si(sel.value, sel.unit ?? "", 5)], ["Tolerancia", sel.tolerance_pct != null ? `±${sel.tolerance_pct} %` : "—"], ["Q", sel.q_factor != null ? `${sel.q_factor}${sel.q_freq_hz ? ` @ ${si(sel.q_freq_hz, "Hz")}` : ""}` : "—"],
                ["ESR", sel.esr_ohm != null ? `${sel.esr_ohm} Ω` : "—"], ["SRF", sel.srf_hz ? si(sel.srf_hz, "Hz", 5) : "—"], ["Modelo", sel.model === "real" ? "Real (parásitos)" : "Ideal"], ["Fabricante / ref.", [sel.manufacturer, sel.part_number].filter(Boolean).join(" · ") || "—"],
                ...(sel.extra && Object.keys(sel.extra).length ? Object.entries<any>(sel.extra).map(([k, v]) => [k, v == null ? "no especificado" : String(v)] as [string, string]) : [])]} />
              {sel.notes && <p className="mt-2 text-[12px] text-dim">{sel.notes}</p>}
              {m && <div className="mt-2">
                <Plot height={220} data={[{ x: arr(m.f), y: arr(m.ideal.mag), name: "|Z| ideal", line: { dash: "dot", width: 1.2 } }, { x: arr(m.f), y: arr(m.real.mag), name: "|Z| modelo real", line: { width: 1.8 } }]}
                  layout={{ xaxis: { type: "log", title: { text: "Frecuencia (Hz)" } }, yaxis: { type: "log", title: { text: "|Z| (Ω)" } } }} />
                {m.notes.map((n: string, i: number) => <p key={i} className="text-2xs text-faint">{n}</p>)}
              </div>}
              {kind && (sel.category === "inductor" || sel.category === "capacitor") && <p className="mt-2 text-2xs text-faint">Los diseños de adaptación pueden ajustarse a los valores de esta biblioteca («Valores normalizados → Biblioteca» en Matching Designer).</p>}
            </Panel>
          ) : <Empty>Seleccione un componente para ver su modelo |Z(f)|.</Empty>}
        </div>
      </div>
    </div>
  );
}
