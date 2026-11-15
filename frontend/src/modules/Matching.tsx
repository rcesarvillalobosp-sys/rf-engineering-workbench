import { motion } from "motion/react";
import { Dices } from "lucide-react";
import { useMemo, useState } from "react";
import { PALETTE, Plot } from "../components/Plot";
import { ReportButton, decimate } from "../components/ReportButton";
import { Ladder, elementsToLadder } from "../components/Schematic";
import { SmithChart, type SmithTrace } from "../components/SmithChart";
import { Steps } from "../components/Steps";
import { Btn, Field, Grid, Input, KV, Note, OriginBadge, PageHeader, Panel, Seg, Select, Stat, useCall } from "../components/ui";
import { post } from "../lib/api";
import { arr, cx, fmt, hz, num, pairs, si } from "../lib/format";
import { useForm } from "../lib/store";

const METHODS = [
  { value: "L", label: "Red L" }, { value: "PI", label: "Red Pi" }, { value: "T", label: "Red T" },
  { value: "QWT", label: "λ/4" }, { value: "STUB1", label: "Stub simple" }, { value: "STUB2", label: "Doble stub" },
];

/** Residuos de coma flotante (|x| < 1e-9 dB) se muestran como 0. */
/** Presentación: una adaptación exacta da |Γ| → 0 (−∞ dB); se recorta a −80 dB sólo en la gráfica. */
const floorDb = (v: number) => (Number.isFinite(v) ? Math.max(v, -80) : -80);
const tiny = (v: any) => (typeof v === "number" && Math.abs(v) < 1e-9 ? 0 : v);

const DEF = {
  method: "L", zl: "25-j40", zs: "50", f0: "433MHz", z0: 50, q_net: 4, comp_q: "", stub: "short", vf: 1,
  vswr_target: 2, span: 0.5, load_model: "series_equiv", d1_lambda: 0.1, spacing_lambda: 0.125, snap: "none", sel: 0,
  tol_l: 5, tol_c: 5, tol_len: 1, mc_n: 500, mc_dist: "uniform",
};

export function MatchingModule() {
  const [s, set] = useForm("matching", DEF);
  const lumped = ["L", "PI", "T"].includes(s.method);
  const call = useCall(
    () => post("/match/design", {
      method: s.method, zl: s.zl, zs: s.zs, f0: s.f0, z0: s.z0, q_net: s.q_net, comp_q: s.comp_q ? Number(s.comp_q) : null, stub: s.stub,
      vf: s.vf, vswr_target: s.vswr_target, span: s.span, load_model: s.load_model, d1_lambda: s.d1_lambda, spacing_lambda: s.spacing_lambda,
      snap: lumped ? s.snap : "none",
    }),
    [s.method, s.zl, s.zs, s.f0, s.z0, s.q_net, s.comp_q, s.stub, s.vf, s.vswr_target, s.span, s.load_model, s.d1_lambda, s.spacing_lambda, s.snap],
    350,
  );
  const r = call.data as any;
  const sols: any[] = r?.solutions ?? [];
  const sel = Math.min(s.sel, Math.max(sols.length - 1, 0));
  const sol = sols[sel];
  const [mc, setMc] = useState<any>(null);
  const [mcErr, setMcErr] = useState<string | null>(null);
  const [mcLoad, setMcLoad] = useState(false);

  const runMC = async () => {
    if (!sol) return;
    setMcLoad(true);
    setMcErr(null);
    try {
      setMc(await post("/match/tolerance", { elements: sol.elements, zl: s.zl, zs: s.zs, f0: s.f0, span: Math.min(s.span, 0.3), load_model: s.load_model,
        tol_l: s.tol_l, tol_c: s.tol_c, tol_len: s.tol_len, n: s.mc_n, dist: s.mc_dist, vswr_target: s.vswr_target }));
    } catch (e: any) { setMcErr(e.message); } finally { setMcLoad(false); }
  };

  const smith = useMemo(() => {
    if (!r || !sol) return null;
    const traces: SmithTrace[] = sol.trajectory_gamma.map((seg: any, i: number) => ({ pts: pairs(seg.gamma), color: PALETTE[(i + 1) % PALETTE.length], width: 2.2, arrow: true, name: seg.label }));
    traces.push({ pts: pairs(sol.sweep.gamma_ref), color: "#4c5c56", width: 1, dash: true, name: "Zin(f)" });
    const pts = [
      { g: [r.load_gamma.re, r.load_gamma.im] as [number, number], label: "ZL", color: "#f0b44c" },
      { g: [r.target_gamma.re, r.target_gamma.im] as [number, number], label: "Zs*", color: "#2fe39a", hollow: true, size: 0.03 },
    ];
    return { traces, pts };
  }, [r, sol]);

  const f = arr(sol?.sweep?.f);
  const plotData = sol ? [
    { x: f, y: arr(sol.sweep.s11_db).map(floorDb), name: "|Γ| (dB) ideal", line: { width: 1.8 } },
    ...(sol.snapped ? [{ x: arr(sol.snapped.sweep.f), y: arr(sol.snapped.sweep.s11_db).map(floorDb), name: `|Γ| (dB) ${sol.snapped.series}`, line: { width: 1.4, dash: "dash" } }] : []),
    { x: f, y: arr(sol.sweep.vswr).map((v) => Math.min(v, 20)), name: "VSWR", yaxis: "y2", line: { width: 1.2, color: "#f0b44c" } },
  ] : [];
  const bw = sol?.bandwidth;
  const f0 = num(r?.f0);
  const lam = num(r?.lambda_m);

  const buildReport = () => {
    if (!r || !sol) return null;
    const res: [string, string][] = [
      ["Solución", sol.topology], ...sol.description.map((d: string, i: number) => [`Elemento ${i + 1}`, d] as [string, string]),
      ["Γ antes / después", `${fmt(Math.hypot(r.gamma_before.re, r.gamma_before.im), 4)} / ${fmt(Math.hypot(sol.gamma_after.re, sol.gamma_after.im), 3)}`],
      ["VSWR antes / después (f0)", `${fmt(r.vswr_before, 4)} / ${fmt(sol.vswr_after, 5)}`],
      ["Ganancia de transductor a f0", `${fmt(tiny(sol.transducer_gain_db_f0), 4)} dB`],
      ["Ancho de banda VSWR ≤ " + s.vswr_target, bw ? `${hz(bw.f_low)} – ${hz(bw.f_high)} (${fmt(bw.fractional * 100, 4)} %)` : "No alcanza el objetivo"],
    ];
    if (r.bode_fano) res.push(["Límite Bode–Fano", `${hz(r.bode_fano.max_bw)} (${fmt(r.bode_fano.max_fractional_bw * 100, 4)} %)`]);
    if (sol.snapped) res.push([`Con valores ${sol.snapped.series}`, `VSWR(f0) = ${fmt(sol.snapped.vswr_after, 4)}`]);
    return {
      title: `Red de adaptación ${r.method_name} — ZL = ${s.zl} Ω`, module: "Matching Designer", origin: "calculated" as const,
      inputs: [["ZL", `${s.zl} Ω`], ["Zs", `${s.zs} Ω`], ["f0", s.f0], ["Método", r.method_name], ["Modelo de carga", s.load_model === "constant" ? "ZL constante" : "R + L/C serie equivalente"],
        ...(lumped && s.comp_q ? [["Q de componentes", s.comp_q]] : []), ...(s.method === "PI" || s.method === "T" ? [["Q de la red", String(s.q_net)]] : [])] as [string, string][],
      results: res, steps: r.trace,
      smith: { z0: s.z0, points: smith!.pts.map((p) => ({ re: p.g[0], im: p.g[1], label: p.label })), traces: smith!.traces.slice(0, -1).map((t) => ({ name: t.name, re: t.pts.map((q) => q[0]), im: t.pts.map((q) => q[1]) })) },
      plots: [{ title: "Respuesta en frecuencia", ylabel: "|Γ| (dB)", x: decimate(f), series: [{ name: "|Γ| dB", y: decimate(arr(sol.sweep.s11_db)) }, { name: "VSWR", y: decimate(arr(sol.sweep.vswr)) }] }],
      notes: [r.narrowband_warning, ...(mc ? [`Monte Carlo (${mc.n} muestras, ${mc.dist}): rendimiento VSWR ≤ ${s.vswr_target} a f0 = ${fmt(mc.yield_f0 * 100, 4)} %, VSWR p95 = ${fmt(mc.vswr_f0.p95, 4)}`] : [])],
    };
  };

  return (
    <div>
      <PageHeader index={4} title="Matching Designer" desc="Diseño de redes de adaptación con verificación numérica de cada solución. Objetivo: Zin = Zs* (adaptación conjugada)." right={<><OriginBadge origin="calculated" /><ReportButton build={buildReport} disabled={!sol} /></>} />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-3">
          <Panel title="Especificación">
            <div className="grid grid-cols-2 gap-2.5">
              <Field label="Carga ZL"><Input value={s.zl} suffix="Ω" onChange={(e) => set({ zl: e.target.value })} /></Field>
              <Field label="Fuente Zs"><Input value={s.zs} suffix="Ω" onChange={(e) => set({ zs: e.target.value })} /></Field>
              <Field label="Frecuencia f0"><Input value={s.f0} onChange={(e) => set({ f0: e.target.value })} /></Field>
              <Field label="Z0 (carta / líneas)"><Input type="number" value={s.z0} suffix="Ω" onChange={(e) => set({ z0: Number(e.target.value) || 50 })} /></Field>
            </div>
            <div className="mt-3"><Field label="Método"><Seg small value={s.method} onChange={(v) => set({ method: v, sel: 0 })} options={METHODS} /></Field></div>
            <div className="mt-2.5 grid grid-cols-2 gap-2.5">
              {(s.method === "PI" || s.method === "T") && <Field label="Q de la red" hint="Mayor Q → menor ancho de banda"><Input type="number" step="0.1" value={s.q_net} onChange={(e) => set({ q_net: Number(e.target.value) })} /></Field>}
              {lumped && <Field label="Q de L y C" hint="Vacío = ideal"><Input value={s.comp_q} placeholder="ideal" onChange={(e) => set({ comp_q: e.target.value })} /></Field>}
              {lumped && <Field label="Valores normalizados"><Select value={s.snap} onChange={(v) => set({ snap: v })} options={[{ value: "none", label: "Exactos" }, { value: "E12", label: "Serie E12" }, { value: "E24", label: "Serie E24" }, { value: "library", label: "Biblioteca" }]} /></Field>}
              {(s.method === "STUB1" || s.method === "STUB2") && <Field label="Terminación del stub"><Select value={s.stub} onChange={(v) => set({ stub: v })} options={[{ value: "short", label: "Cortocircuito" }, { value: "open", label: "Abierto" }]} /></Field>}
              {!lumped && <Field label="Factor de velocidad"><Input type="number" step="0.01" min={0.05} max={1} value={s.vf} onChange={(e) => set({ vf: Number(e.target.value) })} /></Field>}
              {s.method === "STUB2" && <>
                <Field label="d1 (carga → stub 1)" hint="en λ"><Input type="number" step="0.01" value={s.d1_lambda} onChange={(e) => set({ d1_lambda: Number(e.target.value) })} /></Field>
                <Field label="Separación stubs" hint="λ/8 o 3λ/8 típicas"><Select value={String(s.spacing_lambda)} onChange={(v) => set({ spacing_lambda: Number(v) })} options={[{ value: "0.125", label: "λ/8" }, { value: "0.375", label: "3λ/8" }, { value: "0.0625", label: "λ/16" }]} /></Field>
              </>}
            </div>
          </Panel>
          <Panel title="Banda y modelo de carga">
            <div className="grid grid-cols-2 gap-2.5">
              <Field label="VSWR objetivo"><Input type="number" step="0.1" min={1.01} value={s.vswr_target} onChange={(e) => set({ vswr_target: Number(e.target.value) })} /></Field>
              <Field label="Barrido ± fracción f0"><Input type="number" step="0.05" min={0.05} max={0.95} value={s.span} onChange={(e) => set({ span: Number(e.target.value) })} /></Field>
            </div>
            <div className="mt-2.5"><Field label="Variación de ZL con f" hint="ZL sólo se conoce a f0: el modelo afecta al ancho de banda"><Select value={s.load_model} onChange={(v) => set({ load_model: v })} options={[{ value: "series_equiv", label: "R + L/C serie equivalente a f0" }, { value: "constant", label: "ZL constante (no físico)" }]} /></Field></div>
          </Panel>
          {call.error && <Note kind="err">{call.error}</Note>}
          {r && <Note kind="warn">{r.narrowband_warning}</Note>}
        </div>
        <div className="space-y-3">
          {r && (
            <Grid cols="grid-cols-2 lg:grid-cols-5">
              <Stat label="|Γ| antes" value={fmt(Math.hypot(r.gamma_before.re, r.gamma_before.im), 4)} tone="err" />
              <Stat label="VSWR antes" value={fmt(r.vswr_before, 4)} tone="err" />
              <Stat label="VSWR después (f0)" value={sol ? fmt(sol.vswr_after, 5) : "—"} tone="acc" />
              <Stat label={`BW VSWR ≤ ${s.vswr_target}`} value={bw ? fmt(bw.fractional * 100, 3) : "—"} unit="%" sub={bw ? `${hz(bw.f_low, 5)} – ${hz(bw.f_high, 5)}${bw.edge_limited ? " (límite de barrido)" : ""}` : "No alcanza el objetivo"} />
              <Stat label="Bode–Fano máx." value={r.bode_fano ? fmt(r.bode_fano.max_fractional_bw * 100, 3) : "∞"} unit="%" sub={r.bode_fano ? `Q_L = ${fmt(r.bode_fano.q_load, 4)} (${r.bode_fano.equivalent})` : "Carga resistiva"} tone="warn" />
            </Grid>
          )}
          {sols.length > 0 && (
            <Panel title={`Soluciones (${sols.length})`} sub="Seleccione una para ver trayectoria y respuesta">
              <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                {sols.map((so, i) => (
                  <motion.button key={i} whileHover={{ y: -1 }} onClick={() => set({ sel: i })} className={`rounded border p-2.5 text-left transition-colors ${i === sel ? "border-acc/60 bg-acc/[0.06]" : "border-line hover:border-line2"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[12px] font-medium text-ink">#{i + 1} · {so.topology}</span>
                      <span className="font-mono text-2xs text-acc">VSWR {fmt(so.vswr_after, 4)}</span>
                    </div>
                    <div className="mt-1 rounded bg-[#060a0c] px-1 py-0.5"><Ladder items={elementsToLadder(so.elements, lam)} left={{ kind: "source", label: "Zs" }} right={{ kind: "load", label: "ZL" }} height={140} /></div>
                    <div className="mt-1 space-y-0.5 font-mono text-2xs text-dim">
                      {so.description.map((d: string, j: number) => <div key={j}>{d}</div>)}
                      <div>BW: {so.bandwidth ? `${fmt(so.bandwidth.fractional * 100, 3)} % (${hz(so.bandwidth.bw, 4)})` : "—"} · G_T(f0) = {fmt(tiny(so.transducer_gain_db_f0), 3)} dB</div>
                      {so.snapped && <div className="text-warn">Con {so.snapped.series}: {so.snapped.description.join(" · ")} → VSWR(f0) = {fmt(so.snapped.vswr_after, 4)}</div>}
                    </div>
                  </motion.button>
                ))}
              </div>
            </Panel>
          )}
          {sol && smith && (
            <Grid cols="lg:grid-cols-[minmax(0,460px)_minmax(0,1fr)]">
              <Panel title="Trayectoria en la carta" sub="Desde ZL hacia la fuente, elemento a elemento" pad={false}>
                <div className="aspect-square w-full p-1.5"><SmithChart z0={s.z0} traces={smith.traces} points={smith.pts} admittance /></div>
                <div className="space-y-0.5 border-t border-line px-3 py-2 text-2xs">
                  {sol.trajectory_gamma.map((seg: any, i: number) => <div key={i} className="flex items-center gap-2"><span className="h-0.5 w-4" style={{ background: PALETTE[(i + 1) % PALETTE.length] }} /><span className="text-dim">{seg.label}</span></div>)}
                </div>
              </Panel>
              <div className="space-y-3">
                <Panel title="Respuesta en frecuencia" sub="Γ respecto a la fuente (onda de potencia)" pad={false}>
                  <Plot data={plotData} height={270} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "|Γ| (dB)" } }, yaxis2: { title: { text: "VSWR" }, range: [1, 10] },
                    shapes: [{ type: "line", x0: f0, x1: f0, yref: "paper", y0: 0, y1: 1, line: { color: "#2fe39a", dash: "dot", width: 1 } }, ...(bw ? [{ type: "rect", x0: bw.f_low, x1: bw.f_high, yref: "paper", y0: 0, y1: 1, fillcolor: "rgba(47,227,154,0.06)", line: { width: 0 } }] : [])] }} />
                </Panel>
                <Panel title="Ganancia de transductor" sub={lumped && s.comp_q ? `Componentes con Q = ${s.comp_q}` : "Componentes ideales: 0 dB a f0"} pad={false}>
                  <Plot data={[{ x: f, y: arr(sol.sweep.gt_db), name: "G_T (dB)" }]} height={200} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "G_T (dB)" } } }} />
                </Panel>
              </div>
            </Grid>
          )}
          {sol && (
            <Panel title="Análisis de tolerancias (Monte Carlo)" sub="Dispersión del VSWR por tolerancias de componentes y longitudes" actions={<Btn small variant="primary" loading={mcLoad} icon={<Dices className="h-3.5 w-3.5" />} onClick={runMC}>Simular</Btn>}>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                <Field label="Tol. L (±%)"><Input type="number" value={s.tol_l} onChange={(e) => set({ tol_l: Number(e.target.value) })} /></Field>
                <Field label="Tol. C (±%)"><Input type="number" value={s.tol_c} onChange={(e) => set({ tol_c: Number(e.target.value) })} /></Field>
                <Field label="Tol. longitud (±%)"><Input type="number" value={s.tol_len} onChange={(e) => set({ tol_len: Number(e.target.value) })} /></Field>
                <Field label="Muestras"><Input type="number" value={s.mc_n} onChange={(e) => set({ mc_n: Number(e.target.value) })} /></Field>
                <Field label="Distribución"><Select value={s.mc_dist} onChange={(v) => set({ mc_dist: v })} options={[{ value: "uniform", label: "Uniforme" }, { value: "gaussian", label: "Gaussiana (tol = 3σ)" }]} /></Field>
              </div>
              {mcErr && <Note kind="err" className="mt-2">{mcErr}</Note>}
              {mc && (
                <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[220px_1fr_1fr]">
                  <KV dense rows={[["Rendimiento VSWR ≤ " + s.vswr_target, `${fmt(mc.yield_f0 * 100, 4)} %`], ["VSWR medio (f0)", fmt(mc.vswr_f0.mean, 4)], ["VSWR mediana", fmt(mc.vswr_f0.p50, 4)], ["VSWR p95", fmt(mc.vswr_f0.p95, 4)], ["VSWR máximo", fmt(mc.vswr_f0.max, 4)]]} />
                  <Plot height={210} data={[{ type: "bar", x: arr(mc.hist.edges).slice(0, -1).map((e, i) => (e + arr(mc.hist.edges)[i + 1]) / 2), y: arr(mc.hist.counts), marker: { color: "#2fe39a" }, name: "Muestras" }]} layout={{ hovermode: "closest", xaxis: { title: { text: "VSWR a f0" } }, yaxis: { title: { text: "N" } }, bargap: 0.05 }} />
                  <Plot height={210} data={[
                    { x: arr(mc.f), y: arr(mc.envelope.p95), name: "p95", line: { color: "#ff7a8a", width: 1 } },
                    { x: arr(mc.f), y: arr(mc.envelope.p50), name: "mediana", line: { color: "#2fe39a", width: 1.6 } },
                    { x: arr(mc.f), y: arr(mc.envelope.p5), name: "p5", line: { color: "#58b4ff", width: 1 } },
                  ]} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "VSWR" }, range: [1, 5] } }} />
                </div>
              )}
            </Panel>
          )}
          {r?.bode_fano && (
            <Note kind="info">
              Límite de Bode–Fano: con la carga modelada como {r.bode_fano.equivalent} (Q_L = {fmt(r.bode_fano.q_load, 4)}), ninguna red sin pérdidas puede mantener VSWR ≤ {s.vswr_target} en más de {hz(r.bode_fano.max_bw, 4)} ({fmt(r.bode_fano.max_fractional_bw * 100, 4)} %). Fórmula: {r.bode_fano.formula}. Para banda ancha se requieren redes de varias secciones o reducir el objetivo de VSWR.
            </Note>
          )}
          {Number.isFinite(lam) && !lumped && <p className="text-2xs text-faint">λ en la línea a f0 = {si(lam, "m", 5)} (vf = {s.vf}).</p>}
          <Steps steps={r?.trace} />
          {sol && <p className="text-2xs text-faint">Γ antes: {cx(r.gamma_before, "")} · Zin(f0) de la solución: {cx(sol.zin_f0)}</p>}
        </div>
      </div>
    </div>
  );
}
