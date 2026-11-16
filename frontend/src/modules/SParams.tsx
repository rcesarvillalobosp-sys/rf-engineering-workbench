import { EduNote } from "../components/EduNote";
import { Plus, Trash2, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Plot, usePalette } from "../components/Plot";
import { ReportButton, decimate } from "../components/ReportButton";
import { SmithChart, type SmithCircle, type SmithTrace } from "../components/SmithChart";
import { Btn, Collapse, Empty, Field, Grid, Input, KV, Note, OriginBadge, PageHeader, Panel, Seg, Select, Table, useCall } from "../components/ui";
import { get, post } from "../lib/api";
import { arr, cx, fmt, hz, num, pairs, si } from "../lib/format";
import { useForm, useStore } from "../lib/store";
import { useTheme } from "../lib/theme";

type El = { kind: string; part: string; value: string; z0?: string; length?: string; vf?: string };
const DEF = {
  ds: 0, compare: [] as number[], view: "mag", mmPairs: "1-2, 3-4", mmShow: ["Sdd21", "Sdd11", "Scd21"] as string[], params: ["S11", "S21"] as string[], marker: "", rl: 10,
  circGains: "0, 3, 6", tdrParam: "S11", tdrMode: "lowpass", tdrWin: "kaiser", tdrVf: 0.66,
  simName: "Filtro paso bajo LC", simKind: "twoport", simExpr: "R(50)+L(15n)", simStart: "10MHz", simStop: "2GHz", simN: 401,
  simEls: [{ kind: "series", part: "L", value: "100n" }, { kind: "shunt", part: "C", value: "40p" }, { kind: "series", part: "L", value: "100n" }] as El[],
};

function elToApi(e: El) {
  if (e.part === "line") return { kind: "line", z0: e.z0 || "50", length_m: e.length || "0.1", vf: e.vf || "1" };
  return { kind: e.kind, part: e.part, value: e.value };
}
export function SParamsModule() {
  const T = useTheme();
  const PALETTE = usePalette();
  const [s, set] = useForm("sparams", DEF);
  const toast = useStore((st) => st.toast);
  const [list, setList] = useState<any[]>([]);
  const refresh = () => get("/datasets").then((l) => { setList(l); if (!l.some((d: any) => d.id === s.ds)) set({ ds: l[0]?.id ?? 0 }); }).catch(() => {});
  useEffect(() => { refresh(); }, []);
  const call = useCall(() => post("/sparams/analyze", { dataset_id: s.ds, marker_f: s.marker || null, rl_threshold_db: s.rl }), s.ds ? [s.ds, s.marker, s.rl] : null, 150);
  const r = call.data as any;
  const [cmp, setCmp] = useState<any[]>([]);
  useEffect(() => {
    Promise.all(s.compare.filter((c) => c !== s.ds).map((id) => post("/sparams/analyze", { dataset_id: id }).catch(() => null))).then((x) => setCmp(x.filter(Boolean)));
  }, [JSON.stringify(s.compare), s.ds]);
  const circles = useCall(() => post("/sparams/circles", { dataset_id: s.ds, f: s.marker || num(r?.f?.[Math.floor((r?.f?.length ?? 1) / 2)]), gains_db: s.circGains.split(",").map(Number).filter(Number.isFinite) }),
    r && r.nports === 2 && s.view === "stab" ? [s.ds, s.marker, s.circGains, r?.name] : null, 150);
  const mmPairs = () => s.mmPairs.split(",").map((x: string) => x.trim().split(/[-–]/).map(Number)).filter((p: number[]) => p.length === 2 && p.every(Number.isFinite));
  const mm = useCall(() => post("/sparams/mixed-mode", { dataset_id: s.ds, pairs: mmPairs() }), r && s.view === "mm" ? [s.ds, s.mmPairs] : null, 150);
  const tdr = useCall(() => post("/sparams/tdr", { dataset_id: s.ds, param: s.tdrParam, mode: s.tdrMode, window: s.tdrWin, vf: s.tdrVf }), r && s.view === "tdr" ? [s.ds, s.tdrParam, s.tdrMode, s.tdrWin, s.tdrVf] : null, 150);

  const names = r ? Object.keys(r.traces) : [];
  const shown = names.filter((n) => s.params.includes(n));
  const f = arr(r?.f);
  const mk = r?.marker;
  const fm = num(mk?.f);
  const markerShape = Number.isFinite(fm) ? [{ type: "line", x0: fm, x1: fm, yref: "paper", y0: 0, y1: 1, line: { color: T.warn, dash: "dot", width: 1 } }] : [];

  const data = useMemo((): Record<string, any[]> => {
    if (!r) return {};
    const base = (key: string, tr: (t: any) => number[], filter: (n: string) => boolean = () => true) => [
      ...shown.filter(filter).map((n, i) => ({ x: f, y: tr(r.traces[n]), name: `${n} · ${r.name}`, line: { width: 1.7, color: PALETTE[i % PALETTE.length] } })),
      ...cmp.flatMap((c, j) => shown.filter(filter).filter((n) => c.traces[n]).map((n) => ({ x: arr(c.f), y: tr(c.traces[n]), name: `${n} · ${c.name}`, line: { width: 1.2, dash: ["dash", "dot", "dashdot"][j % 3] } }))),
    ].map((t) => ({ ...t, meta: key }));
    const refl = (n: string) => n[1] === n[2];
    return {
      mag: base("mag", (t) => arr(t.db)),
      phase: base("phase", (t) => arr(t.deg)),
      vswr: base("vswr", (t) => arr(t.vswr).map((v) => Math.min(v, 50)), refl),
      rl: base("rl", (t) => arr(t.return_loss), refl),
      gd: base("gd", (t) => arr(t.group_delay).map((v) => v * 1e9)),
    };
  }, [r, cmp, JSON.stringify(shown)]);

  const smithTraces: SmithTrace[] = r ? [
    ...shown.filter((n) => n[1] === n[2]).map((n, i) => ({ pts: pairs(r.traces[n].x), color: PALETTE[i % PALETTE.length], width: 1.6, name: n })),
    ...cmp.flatMap((c, j) => shown.filter((n) => n[1] === n[2] && c.traces[n]).map((n) => ({ pts: pairs(c.traces[n].x), color: PALETTE[(j + 3) % PALETTE.length], width: 1.2, dash: true, name: `${n} ${c.name}` }))),
  ] : [];
  const smithPts = mk ? shown.filter((n) => n[1] === n[2] && mk.values[n]).map((n) => ({ g: [mk.values[n].x.re, mk.values[n].x.im] as [number, number], label: `${n}@m`, color: T.warn })) : [];

  const simulate = async () => {
    try {
      const body = s.simKind === "oneport" ? { name: s.simName, kind: "oneport", expr: s.simExpr, f_start: s.simStart, f_stop: s.simStop, n: s.simN }
        : { name: s.simName, kind: "twoport", elements: s.simEls.map(elToApi), f_start: s.simStart, f_stop: s.simStop, n: s.simN };
      const res = await post("/datasets/simulated", body);
      toast("ok", `Datos simulados generados: ${s.simName}`);
      await refresh();
      set({ ds: res.id });
    } catch (e: any) { toast("err", e.message); }
  };

  const cir = circles.data as any;
  const smithCircles: SmithCircle[] = cir ? [
    ...(cir.stability_circles.load ? [{ c: [cir.stability_circles.load.center.re, cir.stability_circles.load.center.im] as [number, number], r: num(cir.stability_circles.load.radius), color: T.err, label: "ΓL est.", dash: true }] : []),
    ...(cir.stability_circles.source ? [{ c: [cir.stability_circles.source.center.re, cir.stability_circles.source.center.im] as [number, number], r: num(cir.stability_circles.source.radius), color: T.violet, label: "ΓS est.", dash: true }] : []),
    ...cir.gain_circles.map((g: any) => ({ c: [g.center.re, g.center.im] as [number, number], r: num(g.radius), color: T.acc, label: `Gp ${g.gain_db} dB` })),
    ...cir.available_gain_circles.map((g: any) => ({ c: [g.center.re, g.center.im] as [number, number], r: num(g.radius), color: T.info, label: `Ga ${g.gain_db} dB` })),
  ] : [];

  const buildReport = () => {
    if (!r) return null;
    const results: [string, string][] = [];
    if (mk) for (const [n, v] of Object.entries<any>(mk.values)) results.push([`${n} @ ${hz(mk.f)}`, `${fmt(v.db, 5)} dB ∠ ${fmt(v.deg, 5)}°${v.z ? ` · Z = ${cx(v.z)}` : ""}${v.vswr != null ? ` · VSWR ${fmt(v.vswr, 4)}` : ""}`]);
    const s11 = r.traces.S11;
    s11?.bands?.forEach((b: any, i: number) => results.push([`Banda RL ≥ ${s.rl} dB #${i + 1}`, `${hz(b.f_low)} – ${hz(b.f_high)} (${hz(b.bw, 4)})`]));
    s11?.minima?.slice(0, 3).forEach((m: any, i: number) => results.push([`Mínimo |S11| #${i + 1}`, `${hz(m.f)} · ${fmt(m.value, 4)} dB`]));
    return {
      title: `Parámetros S — ${r.name}`, module: "S-Parameters", origin: r.origin, source_detail: r.origin_label,
      inputs: [["Conjunto de datos", r.name], ["Puertos", String(r.nports)], ["Z0", `${r.z0.join(", ")} Ω`], ["Rango", `${hz(f[0])} – ${hz(f[f.length - 1])} (${f.length} puntos)`]] as [string, string][],
      results,
      plots: [{ title: "Magnitud (dB)", ylabel: "dB", x: decimate(f), series: shown.map((n) => ({ name: n, y: decimate(arr(r.traces[n].db)) })) },
        { title: "Fase (°)", ylabel: "°", x: decimate(f), series: shown.map((n) => ({ name: n, y: decimate(arr(r.traces[n].deg)) })) }],
      smith: { z0: r.z0[0], points: smithPts.map((p) => ({ re: p.g[0], im: p.g[1], label: p.label })), traces: smithTraces.filter((t) => !t.dash).map((t) => ({ name: t.name, re: decimate(t.pts).map((p) => p[0]), im: decimate(t.pts).map((p) => p[1]) })) },
      notes: cmp.length ? [`Comparado con: ${cmp.map((c) => `${c.name} (${c.origin_label})`).join("; ")}`] : [],
    };
  };

  const ylab: Record<string, string> = { mag: "|S| (dB)", phase: "Fase (°)", vswr: "VSWR", rl: "Return Loss (dB)", gd: "Retardo de grupo (ns)" };

  return (
    <div>
      <PageHeader index={7} title="S-Parameters" desc="Análisis complejo de parámetros S: las magnitudes en dB se derivan de los datos complejos, nunca al revés. Haga clic en una gráfica para fijar el marcador." right={<>{r && <OriginBadge origin={r.origin} detail={r.origin_label} />}<ReportButton build={buildReport} disabled={!r} /></>} />
      <EduNote>Los parámetros S relacionan ondas: <b>S11</b> es la reflexión en el puerto 1 y <b>S21</b> la transmisión del puerto 1 al 2, con los demás puertos terminados en Z0. Son números complejos: la magnitud en dB (20·log10|S|) indica cuánta señal se refleja o pasa, y la fase el retardo. |S21| en dB negativo es pérdida de inserción; el retardo de grupo −dφ/dω indica cuánto tarda la envolvente en atravesar el dispositivo.</EduNote>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[330px_minmax(0,1fr)]">
        <div className="space-y-3">
          <Panel title="Datos">
            <Field label="Conjunto de datos"><Select value={String(s.ds)} onChange={(v) => set({ ds: Number(v) })} options={[{ value: "0", label: list.length ? "Seleccione…" : "Sin datos" }, ...list.map((d) => ({ value: String(d.id), label: `${d.name} · ${d.nports}P · ${d.origin}` }))]} /></Field>
            {r && <div className="mt-2 flex flex-wrap gap-1">{names.map((n) => (
              <button key={n} onClick={() => set({ params: s.params.includes(n) ? s.params.filter((p) => p !== n) : [...s.params, n] })} className={`rounded border px-2 py-0.5 font-mono text-2xs ${s.params.includes(n) ? "border-acc/60 bg-acc/10 text-acc" : "border-line2 text-dim"}`}>{r.labels?.[n] ?? n}</button>
            ))}</div>}
            <div className="mt-2.5"><Field label="Comparar con"><div className="max-h-28 space-y-0.5 overflow-auto">{list.filter((d) => d.id !== s.ds).map((d) => (
              <label key={d.id} className="flex items-center gap-2 text-[12px] text-dim"><input type="checkbox" className="accent-acc" checked={s.compare.includes(d.id)} onChange={(e) => set({ compare: e.target.checked ? [...s.compare, d.id] : s.compare.filter((x) => x !== d.id) })} /><span className="truncate">{d.name}</span><span className="ml-auto text-2xs text-faint">{d.origin}</span></label>
            ))}</div></Field></div>
            {cmp.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{cmp.map((c) => <OriginBadge key={c.name} origin={c.origin} detail={c.name} />)}</div>}
          </Panel>
          <Panel title="Marcador y bandas">
            <div className="grid grid-cols-2 gap-2.5">
              <Field label="Frecuencia marcador"><Input value={s.marker} placeholder="clic en gráfica" onChange={(e) => set({ marker: e.target.value })} /></Field>
              <Field label="Umbral RL" hint="Banda: RL ≥ umbral"><Input type="number" value={s.rl} suffix="dB" onChange={(e) => set({ rl: Number(e.target.value) })} /></Field>
            </div>
          </Panel>
          <Collapse title={<span className="flex items-center gap-2"><Wand2 className="h-3.5 w-3.5 text-acc" />Generar datos simulados (sin instrumento)</span>}>
            <div className="space-y-2">
              <Field label="Nombre"><Input mono={false} value={s.simName} onChange={(e) => set({ simName: e.target.value })} /></Field>
              <Seg small value={s.simKind} onChange={(v) => set({ simKind: v })} options={[{ value: "twoport", label: "2 puertos (cascada)" }, { value: "oneport", label: "1 puerto (expresión)" }]} />
              {s.simKind === "oneport" ? <Field label="Expresión a masa" hint="Ej.: R(50)+L(15n) · '||' paralelo"><Input value={s.simExpr} onChange={(e) => set({ simExpr: e.target.value })} /></Field> : (
                <div className="space-y-1">
                  {s.simEls.map((e, i) => (
                    <div key={i} className="grid grid-cols-[78px_64px_1fr_20px] gap-1">
                      <Select value={e.kind} onChange={(v) => set({ simEls: s.simEls.map((x, j) => j === i ? { ...x, kind: v } : x) })} options={[{ value: "series", label: "Serie" }, { value: "shunt", label: "Paralelo" }]} />
                      <Select value={e.part} onChange={(v) => set({ simEls: s.simEls.map((x, j) => j === i ? { ...x, part: v, kind: v === "line" ? "line" : x.kind === "line" ? "series" : x.kind } : x) })} options={[{ value: "L", label: "L" }, { value: "C", label: "C" }, { value: "R", label: "R" }, { value: "line", label: "Línea" }]} />
                      {e.part === "line" ? <Input value={`${e.z0 ?? 50},${e.length ?? 0.1},${e.vf ?? 1}`} title="Z0, longitud (m), vf" onChange={(ev) => { const [z0, length, vf] = ev.target.value.split(","); set({ simEls: s.simEls.map((x, j) => j === i ? { ...x, z0, length, vf } : x) }); }} />
                        : <Input value={e.value} onChange={(ev) => set({ simEls: s.simEls.map((x, j) => j === i ? { ...x, value: ev.target.value } : x) })} />}
                      <button className="text-faint hover:text-err" onClick={() => set({ simEls: s.simEls.filter((_, j) => j !== i) })}><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  ))}
                  <Btn small variant="subtle" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => set({ simEls: [...s.simEls, { kind: "series", part: "L", value: "10n" }] })}>Elemento (puerto 1 → 2)</Btn>
                </div>
              )}
              <div className="grid grid-cols-3 gap-1.5">
                <Field label="Inicio"><Input value={s.simStart} onChange={(e) => set({ simStart: e.target.value })} /></Field>
                <Field label="Fin"><Input value={s.simStop} onChange={(e) => set({ simStop: e.target.value })} /></Field>
                <Field label="Puntos"><Input type="number" value={s.simN} onChange={(e) => set({ simN: Number(e.target.value) })} /></Field>
              </div>
              <Btn variant="primary" small onClick={simulate}>Generar y guardar como «Simulado»</Btn>
              <p className="text-2xs text-faint">Los datos generados se etiquetan como simulados y nunca se presentan como medidas.</p>
            </div>
          </Collapse>
          {call.error && <Note kind="err">{call.error}</Note>}
        </div>
        <div className="space-y-3">
          {!r ? <Empty>Seleccione un conjunto de datos importado (Touchstone Importer), capturado (VNA) o genere datos simulados.</Empty> : (
            <>
              <Seg value={s.view} onChange={(v) => set({ view: v })} options={[
                { value: "mag", label: "Magnitud" }, { value: "phase", label: "Fase" }, { value: "smith", label: "Smith" }, { value: "vswr", label: "VSWR" }, { value: "rl", label: "Return Loss" },
                { value: "gd", label: "Retardo de grupo" }, ...(r.nports === 2 ? [{ value: "stab", label: "Estabilidad" }] : []), { value: "tdr", label: "TDR" }, ...(r.nports >= 4 && !r.labels ? [{ value: "mm", label: "Modo mixto" }] : []),
              ]} />
              {["mag", "phase", "vswr", "rl", "gd"].includes(s.view) && (
                <Panel pad={false}><Plot data={data[s.view] ?? []} height={380} onClickX={(x) => set({ marker: String(x) })}
                  layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: ylab[s.view] }, ...(s.view === "vswr" ? { range: [1, 10] } : {}) }, shapes: [...markerShape,
                    ...(s.view === "rl" || s.view === "mag" ? (r.traces.S11?.bands ?? []).map((b: any) => ({ type: "rect", x0: b.f_low, x1: b.f_high, yref: "paper", y0: 0, y1: 1, fillcolor: T.accSoft, line: { width: 0 } })) : [])] }} /></Panel>
              )}
              {s.view === "smith" && (
                <Panel pad={false}><div className="mx-auto aspect-square max-h-[620px] w-full max-w-[620px] p-2"><SmithChart z0={r.z0[0]} traces={smithTraces} points={smithPts} /></div>
                  {!smithTraces.length && <p className="px-3 pb-3 text-2xs text-faint">Active un parámetro de reflexión (S11, S22…) para verlo en la carta.</p>}</Panel>
              )}
              {s.view === "stab" && (
                <Grid cols="lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)]">
                  <div className="space-y-3">
                    <Panel title="Factores de estabilidad" sub="Rollett K y μ (Edwards–Sinsky)" pad={false}>
                      <Plot height={250} data={[{ x: f, y: arr(r.stability.k), name: "K" }, { x: f, y: arr(r.stability.mu), name: "μ" }]} onClickX={(x) => set({ marker: String(x) })}
                        layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "K, μ" } }, shapes: [...markerShape, { type: "line", xref: "paper", x0: 0, x1: 1, y0: 1, y1: 1, line: { color: T.err, dash: "dash", width: 1 } }] }} />
                    </Panel>
                    <Panel title="Ganancia máxima" pad={false}><Plot height={220} data={[{ x: f, y: arr(r.stability.mag_db), name: "MAG (K ≥ 1)" }, { x: f, y: arr(r.stability.msg_db), name: "MSG" }]} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "dB" } } }} /></Panel>
                    {cir && <Panel title={`A ${hz(cir.f)}`}>
                      <KV dense rows={[["K", fmt(cir.k, 5)], ["μ", fmt(cir.mu, 5)], ["|Δ|", fmt(Math.hypot(cir.delta.re, cir.delta.im), 5)], ["Estabilidad incondicional", cir.unconditionally_stable ? "Sí (μ > 1)" : "No"], ["MAG / MSG", `${fmt(cir.mag_db, 4)} / ${fmt(cir.msg_db, 4)} dB`],
                        ["ΓS, ΓL conjugados simultáneos", cir.conjugate_match ? `${cx(cir.conjugate_match.gamma_s, "")} · ${cx(cir.conjugate_match.gamma_l, "")}` : "No existe (K < 1 o |Γ| ≥ 1)"],
                        ["Región estable ΓL", cir.stability_circles.load ? (cir.stability_circles.load.stable_inside ? "Interior del círculo" : "Exterior del círculo") : "—"]]} />
                    </Panel>}
                  </div>
                  <Panel title="Círculos de estabilidad y ganancia" sub="Rojo: estabilidad en ΓL · violeta: en ΓS · verde Gp (ΓL) · azul Ga (ΓS)" pad={false}>
                    <div className="px-3 pt-2"><Field label="Ganancias (dB)"><Input value={s.circGains} onChange={(e) => set({ circGains: e.target.value })} /></Field></div>
                    <div className="aspect-square w-full p-1.5"><SmithChart z0={r.z0[0]} circles={smithCircles} points={cir?.conjugate_match ? [{ g: [cir.conjugate_match.gamma_l.re, cir.conjugate_match.gamma_l.im], label: "ΓL*", color: T.acc }, { g: [cir.conjugate_match.gamma_s.re, cir.conjugate_match.gamma_s.im], label: "ΓS*", color: T.info }] : []} /></div>
                    {circles.error && <Note kind="err" className="m-2">{circles.error}</Note>}
                  </Panel>
                </Grid>
              )}
              {s.view === "mm" && (
                <Panel title="Parámetros S en modo mixto" sub="Diferencial (d) y común (c) a partir de terminación simple" actions={mm.data && <Btn small onClick={() => post("/sparams/mixed-mode", { dataset_id: s.ds, pairs: mmPairs(), save: true }).then((x) => { toast("ok", `Guardado como conjunto derivado #${x.dataset_id}`); refresh(); }).catch((e) => toast("err", e.message))}>Guardar como conjunto</Btn>}>
                  <Field label="Pares diferenciales (positivo-negativo)" hint="Ej.: 1-2, 3-4 (convención de scikit-rf: puertos consecutivos)"><Input value={s.mmPairs} onChange={(e) => set({ mmPairs: e.target.value })} /></Field>
                  {mm.error && <Note kind="err" className="mt-2">{mm.error}</Note>}
                  {mm.data && (() => { const m = mm.data as any; const keys = Object.keys(m.traces); return (
                    <div className="mt-2">
                      <div className="flex flex-wrap gap-1">{keys.map((k) => <button key={k} onClick={() => set({ mmShow: s.mmShow.includes(k) ? s.mmShow.filter((x) => x !== k) : [...s.mmShow, k] })} className={`rounded border px-2 py-0.5 font-mono text-2xs ${s.mmShow.includes(k) ? "border-acc/60 bg-acc/10 text-acc" : "border-line2 text-dim"}`}>{k}</button>)}</div>
                      <Plot height={340} data={keys.filter((k) => s.mmShow.includes(k)).map((k) => ({ x: arr(m.f), y: arr(m.traces[k].db).map((v) => (Number.isFinite(v) ? Math.max(v, -120) : -120)), name: k }))} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "|S| (dB)" } } }} />
                      <p className="text-2xs text-faint">{m.note} Valores &lt; −120 dB (p. ej. conversión de modo nula en un par simétrico) se recortan sólo en la gráfica. Referencias: diferencial {fmt(m.z_ref.diferencial, 4)} Ω · común {fmt(m.z_ref.comun, 4)} Ω.</p>
                    </div>); })()}
                </Panel>
              )}
              {s.view === "tdr" && (
                <Panel title="Dominio del tiempo (TDR)" sub="Transformada inversa de Sii(f) con ventana">
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                    <Field label="Parámetro"><Select value={s.tdrParam} onChange={(v) => set({ tdrParam: v })} options={names.filter((n) => n[1] === n[2]).map((n) => ({ value: n, label: n }))} /></Field>
                    <Field label="Modo"><Select value={s.tdrMode} onChange={(v) => set({ tdrMode: v })} options={[{ value: "lowpass", label: "Low-pass (escalón → Z)" }, { value: "bandpass", label: "Band-pass (impulso)" }]} /></Field>
                    <Field label="Ventana"><Select value={s.tdrWin} onChange={(v) => set({ tdrWin: v })} options={[{ value: "kaiser", label: "Kaiser β=6" }, { value: "hann", label: "Hann" }, { value: "none", label: "Rectangular" }]} /></Field>
                    <Field label="vf del cable"><Input type="number" step="0.01" value={s.tdrVf} onChange={(e) => set({ tdrVf: Number(e.target.value) })} /></Field>
                  </div>
                  {tdr.error && <Note kind="err" className="mt-2">{tdr.error}</Note>}
                  {tdr.data && (() => { const t = tdr.data as any; return (
                    <div className="mt-2">
                      <p className="mb-1 text-2xs text-faint">Resolución ≈ {si(t.resolution_m, "m", 3)} · alcance sin ambigüedad ≈ {si(t.range_m, "m", 4)} · {t.warnings.join(" ")}</p>
                      <Plot height={320} data={s.tdrMode === "lowpass" ? [{ x: arr(t.distance), y: arr(t.z), name: "Z(d) (Ω)" }, { x: arr(t.distance), y: arr(t.step), name: "ρ escalón", yaxis: "y2", line: { dash: "dot", width: 1 } }]
                        : [{ x: arr(t.distance), y: arr(t.impulse_db), name: "|h(d)| (dB)" }]}
                        layout={{ xaxis: { title: { text: "Distancia (m), ida = c·vf·t/2" } }, yaxis: { title: { text: s.tdrMode === "lowpass" ? "Z (Ω)" : "dB" }, ...(s.tdrMode === "lowpass" ? { range: [0, 200] } : {}) }, ...(s.tdrMode === "lowpass" ? { yaxis2: { title: { text: "ρ" }, range: [-1.05, 1.05] } } : {}) }} />
                    </div>); })()}
                </Panel>
              )}
              <Grid cols="lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Panel title="Marcador" sub={mk ? `f = ${hz(mk.f, 7)}` : "Haga clic en una gráfica o escriba la frecuencia"}>
                  {mk ? <Table head={["Parám.", "|S| dB", "∠ °", "Re / Im", "Derivados"]} rows={Object.entries<any>(mk.values).map(([n, v]) => [n, fmt(v.db, 5), fmt(v.deg, 5), cx(v.x, "", 4),
                    v.z ? `Z=${cx(v.z, "Ω", 4)} · VSWR ${fmt(v.vswr, 4)} · RL ${fmt(v.return_loss, 4)} dB` : `IL ${fmt(v.insertion_loss, 4)} dB`])} /> : <p className="text-[12px] text-dim">Sin marcador.</p>}
                  {mk?.z_matrix && <div className="mt-2 text-2xs text-dim">Matriz Z (punto más cercano, Z = Z0(I+S)(I−S)⁻¹): {mk.z_matrix.re.map((row: number[], i: number) => <div key={i} className="font-mono">[{row.map((v, j) => `${fmt(v, 4)}${mk.z_matrix.im[i][j] < 0 ? "−" : "+"}j${fmt(Math.abs(mk.z_matrix.im[i][j]), 4)}`).join(" , ")}]</div>)}</div>}
                </Panel>
                <Panel title="Bandas y resonancias" sub={`Reflexión: RL ≥ ${s.rl} dB`}>
                  {names.filter((n) => n[1] === n[2]).map((n) => {
                    const t = r.traces[n];
                    return (
                      <div key={n} className="mb-2">
                        <div className="text-[12px] font-medium text-ink">{n}</div>
                        <div className="font-mono text-2xs text-dim">
                          {t.bands.length ? t.bands.map((b: any, i: number) => <div key={i}>Banda {hz(b.f_low, 5)} – {hz(b.f_high, 5)} · BW {hz(b.bw, 4)} ({fmt(num(b.fractional) * 100, 3)} %) · mejor {fmt(b.best, 4)} dB @ {hz(b.f_best, 5)}{b.open_low || b.open_high ? " · limitada por el rango de datos" : ""}</div>) : <div>Sin banda con RL ≥ {s.rl} dB.</div>}
                          {t.minima.slice(0, 3).map((m: any, i: number) => <div key={i}>Mínimo |{n}| {fmt(m.value, 4)} dB @ {hz(m.f, 6)}</div>)}
                          {t.x_zero_crossings.slice(0, 4).map((z: any, i: number) => <div key={i}>X = 0 @ {hz(z.f, 6)} ({z.kind})</div>)}
                        </div>
                      </div>
                    );
                  })}
                  {names.filter((n) => n[1] !== n[2] && s.params.includes(n)).map((n) => <div key={n} className="font-mono text-2xs text-dim">{n}: {r.traces[n].bands_3db.map((b: any) => `−3 dB ${hz(b.f_low, 4)} – ${hz(b.f_high, 4)}`).join(" · ") || "—"}</div>)}
                </Panel>
              </Grid>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
