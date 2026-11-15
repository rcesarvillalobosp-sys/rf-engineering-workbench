import { Pin, X } from "lucide-react";
import { useEffect, useState } from "react";
import { PALETTE, Plot } from "../components/Plot";
import { ReportButton, decimate } from "../components/ReportButton";
import { SmithChart } from "../components/SmithChart";
import { Steps } from "../components/Steps";
import { Btn, Field, Grid, Input, KV, Note, OriginBadge, PageHeader, Panel, Seg, Select, Stat, useCall } from "../components/ui";
import { get, post, type Origin } from "../lib/api";
import { arr, cx, fmt, hz, num, pairs } from "../lib/format";
import { useForm } from "../lib/store";

type Pinned = { label: string; origin: Origin; f: number[]; s11db: number[]; vswr: number[]; g: [number, number][] };
const DEF = {
  source: "model", kind: "series_rlc", f0: "433MHz", R: 42, Q: 14, fs: "380MHz", fe: "490MHz", ds: 0, port: 1,
  table: "400e6 30 -60\n420e6 38 -25\n433e6 45 2\n445e6 52 28\n460e6 60 55", z0: 50, vswrT: 2, pinned: [] as Pinned[],
  emKind: "dipole", emF: "433MHz", emL: "0.48", emUnit: "lambda", emR: "1m", emSigma: 5.8e7,
};

export function AntennaModule() {
  const [s, set] = useForm("antenna", DEF);
  const [list, setList] = useState<any[]>([]);
  useEffect(() => { get("/datasets").then(setList).catch(() => {}); }, []);
  const body = () => {
    const base = { z0: s.z0, vswr_threshold: s.vswrT };
    if (s.source === "dataset") return { ...base, source: "dataset", dataset_id: s.ds, port: s.port };
    if (s.source === "table") {
      const rows = s.table.split("\n").map((l) => l.trim().split(/[\s;,]+/)).filter((p) => p.length >= 3).map(([f, r, x]) => ({ f, r: Number(r), x: Number(x) }));
      return { ...base, source: "table", table: rows };
    }
    return { ...base, source: "model", model: { kind: s.kind, f0: s.f0, R: s.R, Q: s.Q, f_start: s.fs, f_stop: s.fe, n: 801 } };
  };
  const call = useCall(() => (s.source === "em"
    ? post("/antenna/em-model", { kind: s.emKind, f: s.emF, length: s.emL, length_unit: s.emUnit, radius: s.emR, sigma: s.emSigma, z0: s.z0, vswr_threshold: s.vswrT })
    : post("/antenna/analyze", body())),
    s.source === "dataset" && !s.ds ? null : [s.source, s.kind, s.f0, s.R, s.Q, s.fs, s.fe, s.ds, s.port, s.table, s.z0, s.vswrT, s.emKind, s.emF, s.emL, s.emUnit, s.emR, s.emSigma]);
  const em = r_em(call.data);
  const r = call.data as any;
  const f = arr(r?.f);
  const best = r?.best;
  const band = r?.bands?.find((b: any) => best && b.f_low <= num(best.f) && num(best.f) <= b.f_high) ?? r?.bands?.[0];

  const pin = () => r && set({ pinned: [...s.pinned, { label: r.label, origin: r.origin, f: decimate(f), s11db: decimate(arr(r.s11_db)), vswr: decimate(arr(r.vswr)), g: decimate(pairs(r.gamma)) }].slice(-6) });

  const buildReport = () => r && ({
    title: `Análisis de antena — ${r.label}`, module: "Antenna Analyzer", origin: r.origin, source_detail: r.source_detail,
    inputs: [["Fuente de datos", r.source_detail], ["Z0", `${s.z0} Ω`], ["Criterio de banda", `VSWR ≤ ${s.vswrT}`]] as [string, string][],
    results: [["Resonancia (mín. |S11|)", best ? `${hz(best.f, 6)} · ${fmt(best.s11_db, 4)} dB` : "—"], ["Z en resonancia", best ? cx(best.z) : "—"], ["VSWR mínimo", best ? fmt(best.vswr, 4) : "—"],
      ["Ancho de banda", band ? `${hz(band.f_low)} – ${hz(band.f_high)} (${hz(band.bw, 4)}, ${fmt(num(band.fractional) * 100, 4)} %)` : "No alcanza el criterio"], ["Q (Yaghjian–Best)", best?.q_z ? fmt(best.q_z, 4) : "—"],
      ...r.reactance_zero_crossings.slice(0, 3).map((z: any, i: number) => [`X = 0 #${i + 1}`, `${hz(z.f, 6)} (${z.kind})`] as [string, string]),
      ...(em ? [["Directividad (modelo EM)", `${fmt(em.directivity, 4)} (${fmt(em.directivity_dbi, 4)} dBi)`], ["Eficiencia de radiación (modelo)", `${fmt(em.efficiency * 100, 4)} %`],
        ["Ganancia (modelo EM)", `${fmt(em.gain_dbi, 4)} dBi`], ["Z_in a f (modelo)", cx(em.z_in)]] as [string, string][] : []),
      [em ? "No modelado" : "No disponible a partir de S11", r.not_available.join(", ")]] as [string, string][],
    plots: [{ title: "|S11| (dB)", ylabel: "dB", x: decimate(f), series: [{ name: "|S11|", y: decimate(arr(r.s11_db)) }, ...s.pinned.map((p) => ({ name: p.label, y: p.s11db }))] },
      { title: "VSWR", ylabel: "VSWR", x: decimate(f), series: [{ name: "VSWR", y: decimate(arr(r.vswr)).map((v) => Math.min(v, 20)) }] },
      { title: "Impedancia de entrada", ylabel: "Ω", x: decimate(f), series: [{ name: "R", y: decimate(arr(r.z.re)) }, { name: "X", y: decimate(arr(r.z.im)) }] }],
    smith: { z0: s.z0, points: [], traces: [{ name: r.label, re: decimate(pairs(r.gamma)).map((p) => p[0]), im: decimate(pairs(r.gamma)).map((p) => p[1]) }] },
    notes: em ? [em.model, ...em.warnings] : ["Ganancia, directividad, eficiencia y diagrama de radiación NO se derivan de S11: requieren medidas de campo o un modelo electromagnético."],
    ...(em ? { steps: em.trace } : {}),
  });

  return (
    <div>
      <PageHeader index={7} title="Antenna Analyzer" desc="Magnitudes de puerto de la antena: S11, VSWR, Return Loss, impedancia, resonancia, ancho de banda y Q." right={<>{r && <OriginBadge origin={r.origin} detail={r.source_detail} />}<ReportButton build={buildReport} disabled={!r} /></>} />
      <Note kind="warn" className="mb-3">Ganancia, directividad, eficiencia y diagrama de radiación no pueden obtenerse de S11 ni de la impedancia medida. Sólo se calculan con la fuente «Modelo EM (hilo)»: un modelo analítico de dipolos y monopolos delgados ideales (Balanis). Es un resultado de modelo, no una medición, y no incluye entorno, cable ni plano de masa finito.</Note>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[330px_minmax(0,1fr)]">
        <div className="space-y-3">
          <Panel title="Fuente de datos">
            <Seg small value={s.source} onChange={(v) => set({ source: v })} options={[{ value: "model", label: "Modelo equivalente" }, { value: "dataset", label: "Importado / medido" }, { value: "table", label: "Tabla Z(f)" }, { value: "em", label: "Modelo EM (hilo)" }]} />
            <div className="mt-2.5 space-y-2.5">
              {s.source === "model" && <>
                <Note>Modelo de circuito equivalente (simulado), no un modelo electromagnético. RLC serie ≈ dipolo/monopolo cerca de resonancia; RLC paralelo ≈ antirresonancia.</Note>
                <Field label="Modelo"><Select value={s.kind} onChange={(v) => set({ kind: v })} options={[{ value: "series_rlc", label: "RLC serie" }, { value: "parallel_rlc", label: "RLC paralelo" }]} /></Field>
                <div className="grid grid-cols-3 gap-2">
                  <Field label="f0"><Input value={s.f0} onChange={(e) => set({ f0: e.target.value })} /></Field>
                  <Field label="R (Ω)"><Input type="number" value={s.R} onChange={(e) => set({ R: Number(e.target.value) })} /></Field>
                  <Field label="Q"><Input type="number" value={s.Q} onChange={(e) => set({ Q: Number(e.target.value) })} /></Field>
                  <Field label="Inicio"><Input value={s.fs} onChange={(e) => set({ fs: e.target.value })} /></Field>
                  <Field label="Fin"><Input value={s.fe} onChange={(e) => set({ fe: e.target.value })} /></Field>
                </div>
              </>}
              {s.source === "dataset" && <div className="grid grid-cols-[1fr_70px] gap-2">
                <Field label="Conjunto de datos"><Select value={String(s.ds)} onChange={(v) => set({ ds: Number(v) })} options={[{ value: "0", label: list.length ? "Seleccione…" : "Sin datos importados" }, ...list.map((d) => ({ value: String(d.id), label: `${d.name} (${d.origin})` }))]} /></Field>
                <Field label="Puerto"><Input type="number" min={1} value={s.port} onChange={(e) => set({ port: Number(e.target.value) })} /></Field>
              </div>}
              {s.source === "em" && <>
                <Note>Modelo electromagnético analítico: hilo delgado con corriente sinusoidal; monopolo sobre plano de masa infinito y perfecto.</Note>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Antena"><Select value={s.emKind} onChange={(v) => set({ emKind: v })} options={[{ value: "dipole", label: "Dipolo (centro)" }, { value: "monopole", label: "Monopolo vertical" }]} /></Field>
                  <Field label="Frecuencia"><Input value={s.emF} onChange={(e) => set({ emF: e.target.value })} /></Field>
                  <Field label={s.emKind === "dipole" ? "Longitud total" : "Altura h"}><Input value={s.emL} onChange={(e) => set({ emL: e.target.value })} /></Field>
                  <Field label="Unidad"><Select value={s.emUnit} onChange={(v) => set({ emUnit: v })} options={[{ value: "lambda", label: "λ" }, { value: "m", label: "metros" }]} /></Field>
                  <Field label="Radio del hilo" hint="1m = 1 mm"><Input value={s.emR} onChange={(e) => set({ emR: e.target.value })} /></Field>
                  <Field label="Conductividad σ" hint="S/m (cobre 5.8e7)"><Input type="number" value={s.emSigma} onChange={(e) => set({ emSigma: Number(e.target.value) })} /></Field>
                </div>
              </>}
              {s.source === "table" && <Field label="f  R  X  (una fila por frecuencia)" hint="Frecuencia en Hz o con prefijo (433M)"><textarea value={s.table} onChange={(e) => set({ table: e.target.value })} rows={8} className="w-full rounded border border-line2 bg-panel2 p-2 font-mono text-[12px] text-ink outline-none focus:border-acc/70" /></Field>}
              <div className="grid grid-cols-2 gap-2">
                <Field label="Z0"><Input type="number" value={s.z0} suffix="Ω" onChange={(e) => set({ z0: Number(e.target.value) || 50 })} /></Field>
                <Field label="Criterio VSWR ≤"><Select value={String(s.vswrT)} onChange={(v) => set({ vswrT: Number(v) })} options={[{ value: "1.5", label: "1.5 : 1" }, { value: "2", label: "2 : 1 (RL 9.5 dB)" }, { value: "3", label: "3 : 1" }]} /></Field>
              </div>
            </div>
          </Panel>
          {call.error && <Note kind="err">{call.error}</Note>}
          <Panel title="Comparar diseños" actions={<Btn small icon={<Pin className="h-3.5 w-3.5" />} disabled={!r} onClick={pin}>Fijar actual</Btn>}>
            {s.pinned.length === 0 ? <p className="text-[12px] text-dim">Fije resultados para superponerlos (modelos, mediciones o archivos distintos).</p> : s.pinned.map((p, i) => (
              <div key={i} className="mb-1 flex items-center gap-2 text-[12px]">
                <span className="h-0.5 w-4" style={{ background: PALETTE[(i + 1) % PALETTE.length] }} />
                <span className="flex-1 truncate text-ink">{p.label}</span>
                <OriginBadge origin={p.origin} />
                <button className="text-faint hover:text-err" onClick={() => set({ pinned: s.pinned.filter((_, j) => j !== i) })}><X className="h-3.5 w-3.5" /></button>
              </div>
            ))}
          </Panel>
        </div>
        <div className="space-y-3">
          {r && em && (
            <Grid cols="lg:grid-cols-[minmax(0,1fr)_minmax(0,400px)]">
              <Panel title="Radiación (modelo EM analítico)" sub={em.model}>
                <Grid cols="grid-cols-2 lg:grid-cols-4">
                  <Stat label="Directividad" value={fmt(em.directivity_dbi, 4)} unit="dBi" tone="acc" sub={`D = ${fmt(em.directivity, 4)}`} />
                  <Stat label="Eficiencia" value={fmt(em.efficiency * 100, 4)} unit="%" sub={`R_L = ${fmt(em.rl_max, 3)} Ω (ref. I máx.)`} />
                  <Stat label="Ganancia" value={fmt(em.gain_dbi, 4)} unit="dBi" tone="warn" />
                  <Stat label="Z_in a f" value={`${fmt(em.z_in.re, 4)}${em.z_in.im < 0 ? "−" : "+"}j${fmt(Math.abs(em.z_in.im), 4)}`} unit="Ω" sub={`${fmt(em.L_over_lambda, 4)} λ (dipolo equivalente)`} />
                </Grid>
                {em.warnings.map((w: string, i: number) => <Note key={i} kind="warn" className="mt-2">{w}</Note>)}
                <div className="mt-2"><Steps steps={em.trace} title="Desarrollo del modelo" /></div>
              </Panel>
              <Panel title="Diagrama de radiación (plano E)" sub="dB normalizados · θ desde el eje del hilo" pad={false}>
                <Plot height={380} data={[{ type: "scatterpolar", mode: "lines", theta: [...arr(em.pattern.theta_deg), ...arr(em.pattern.theta_deg).map((x) => 360 - x).reverse()],
                  r: [...arr(em.pattern.db), ...arr(em.pattern.db).reverse()], line: { color: "#2fe39a", width: 2 }, fill: "toself", fillcolor: "rgba(47,227,154,0.08)", name: "|E| (dB)" }]}
                  layout={{ showlegend: false, margin: { l: 30, r: 30, t: 20, b: 20 }, polar: { bgcolor: "#070c0e", angularaxis: { rotation: 90, direction: "clockwise", gridcolor: "#15222a", tickfont: { size: 9, color: "#7f9089" } },
                    radialaxis: { range: [-40, 0], gridcolor: "#15222a", tickfont: { size: 9, color: "#7f9089" }, ticksuffix: " dB" } } }} />
                {em.kind === "monopole" && <p className="px-3 pb-2 text-2xs text-faint">Monopolo: sólo existe radiación en el semiespacio superior (θ ≤ 90°).</p>}
              </Panel>
            </Grid>
          )}
          {r && <>
            <Grid cols="grid-cols-2 lg:grid-cols-5">
              <Stat label="Resonancia (mín. |S11|)" value={best ? hz(best.f, 6) : "—"} tone="acc" />
              <Stat label="|S11| mínimo" value={best ? fmt(best.s11_db, 4) : "—"} unit="dB" sub={best ? `VSWR ${fmt(best.vswr, 4)}` : undefined} />
              <Stat label={`BW VSWR ≤ ${s.vswrT}`} value={band ? hz(band.bw, 4) : "—"} sub={band ? `${fmt(num(band.fractional) * 100, 4)} % · ${hz(band.f_low, 5)} – ${hz(band.f_high, 5)}` : "No alcanza el criterio"} tone="warn" />
              <Stat label="Z en resonancia" value={best ? `${fmt(best.z.re, 4)}${best.z.im < 0 ? "−" : "+"}j${fmt(Math.abs(best.z.im), 3)}` : "—"} unit="Ω" />
              <Stat label="Q (Yaghjian–Best)" value={best?.q_z ? fmt(best.q_z, 4) : "—"} sub={best?.fbw_estimate_from_q ? `FBW estimada ${fmt(best.fbw_estimate_from_q * 100, 3)} %` : undefined} />
            </Grid>
            <Grid>
              <Panel title="|S11| y VSWR" pad={false}><Plot height={270} data={[{ x: f, y: arr(r.s11_db), name: `|S11| ${r.label}` }, ...s.pinned.map((p, i) => ({ x: p.f, y: p.s11db, name: p.label, line: { dash: "dash", width: 1.2, color: PALETTE[(i + 1) % PALETTE.length] } }))]}
                layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "|S11| (dB)" } }, shapes: band ? [{ type: "rect", x0: band.f_low, x1: band.f_high, yref: "paper", y0: 0, y1: 1, fillcolor: "rgba(47,227,154,0.06)", line: { width: 0 } }] : [] }} /></Panel>
              <Panel title="Impedancia de entrada" pad={false}><Plot height={270} data={[{ x: f, y: arr(r.z.re), name: "R" }, { x: f, y: arr(r.z.im), name: "X" }]} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "Ω" } }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: "#4c5c56", width: 1 } }] }} /></Panel>
            </Grid>
            <Grid cols="lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
              <Panel title="Carta de Smith" pad={false}><div className="aspect-square w-full p-1.5"><SmithChart z0={s.z0} vswrCircles={[(s.vswrT - 1) / (s.vswrT + 1)]}
                traces={[{ pts: pairs(r.gamma), color: "#2fe39a", width: 1.8 }, ...s.pinned.map((p, i) => ({ pts: p.g, color: PALETTE[(i + 1) % PALETTE.length], width: 1.2, dash: true }))]} /></div>
                <p className="px-3 pb-2 text-2xs text-faint">Círculo discontinuo: VSWR = {s.vswrT} (|Γ| = {fmt((s.vswrT - 1) / (s.vswrT + 1), 4)}). Puntos dentro → adaptación aceptable.</p></Panel>
              <div className="space-y-3">
                <Panel title="VSWR" pad={false}><Plot height={200} data={[{ x: f, y: arr(r.vswr).map((v) => Math.min(v, 20)), name: "VSWR", line: { color: "#f0b44c" } }]} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "VSWR" }, range: [1, 8] }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: s.vswrT, y1: s.vswrT, line: { color: "#ff7a8a", dash: "dash", width: 1 } }] }} /></Panel>
                <Panel title="Puntos de adaptación y resonancias">
                  <KV dense rows={[
                    ...r.bands.map((b: any, i: number) => [`Banda #${i + 1}`, `${hz(b.f_low, 5)} – ${hz(b.f_high, 5)}`, `${fmt(num(b.fractional) * 100, 3)} %`] as any),
                    ...r.reactance_zero_crossings.map((z: any, i: number) => [`X = 0 #${i + 1}`, hz(z.f, 6), z.kind] as any),
                    ...r.minima.slice(0, 3).map((m: any, i: number) => [`Mínimo #${i + 1}`, hz(m.f, 6), `${fmt(m.value, 4)} dB`] as any),
                  ]} />
                </Panel>
              </div>
            </Grid>
          </>}
        </div>
      </div>
    </div>
  );
}

/** Bloque del modelo EM (sólo presente con la fuente «Modelo EM»). */
function r_em(d: any) {
  return d?.em ?? null;
}
