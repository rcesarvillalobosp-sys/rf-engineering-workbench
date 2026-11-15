import { useMemo } from "react";
import { Plot } from "../components/Plot";
import { ReportButton, decimate } from "../components/ReportButton";
import { Ladder, type LadderItem } from "../components/Schematic";
import { SmithChart } from "../components/SmithChart";
import { Steps } from "../components/Steps";
import { Field, Grid, Input, KV, Note, OriginBadge, PageHeader, Panel, Seg, Select, Stat, Toggle, useCall } from "../components/ui";
import { post } from "../lib/api";
import { arr, cx, fmt, num, pairs, si } from "../lib/format";
import { useForm } from "../lib/store";

const TOPOS = [
  ["R", "Resistencia pura"], ["L", "Inductancia pura"], ["C", "Capacitancia pura"],
  ["RL_series", "RL serie"], ["RL_parallel", "RL paralelo"], ["RC_series", "RC serie"], ["RC_parallel", "RC paralelo"],
  ["LC_series", "LC serie"], ["LC_parallel", "LC paralelo"], ["RLC_series", "RLC serie"], ["RLC_parallel", "RLC paralelo"],
] as const;

const EXAMPLES = ["R(50) + (L(10n) || C(4.7p))", "(R(1k) || C(2p)) + L(3.3n)", "R(10) + L(100n) + C(25.3p)", "Z(30,-15) || L(22n)"];

const DEF = {
  mode: "preset" as "preset" | "network",
  topology: "RLC_series",
  R: "10", L: "100n", C: "25p", f: "100MHz", z0: 50, v: 1,
  start: "10MHz", stop: "1GHz", n: 601, log: true,
  expr: EXAMPLES[0], fN: "1GHz", startN: "100MHz", stopN: "3GHz",
};

function ladderFor(topo: string, R: string, L: string, C: string): { items: LadderItem[]; right: "short" | "open" } {
  const base = topo.split("_")[0];
  const parts = (["R", "L", "C"] as const).filter((p) => base.includes(p));
  const label = (p: string) => (p === "R" ? `${R} Ω` : p === "L" ? `${L}H` : `${C}F`);
  if (topo.endsWith("parallel")) return { items: parts.map((p) => ({ type: "shunt", part: p, label: label(p) })), right: "open" };
  return { items: parts.map((p) => ({ type: "series", part: p, label: label(p) })), right: "short" };
}

export function ImpedanceModule() {
  const [s, set] = useForm("impedance", DEF);
  const preset = useCall(
    () => post("/circuit/analyze", { topology: s.topology, f: s.f, R: s.R || 0, L: s.L || 0, C: s.C || 0, z0: s.z0, v_rms: s.v, sweep: { start: s.start, stop: s.stop, n: s.n, log: s.log } }),
    s.mode === "preset" ? [s.topology, s.R, s.L, s.C, s.f, s.z0, s.v, s.start, s.stop, s.n, s.log, s.mode] : null,
  );
  const net = useCall(
    () => post("/circuit/network", { expr: s.expr, f: s.fN, z0: s.z0, sweep: { start: s.startN, stop: s.stopN, n: 601, log: s.log } }),
    s.mode === "network" ? [s.expr, s.fN, s.z0, s.startN, s.stopN, s.log, s.mode] : null,
  );
  const call = s.mode === "preset" ? preset : net;
  const r = call.data as any;
  const uses = s.topology.split("_")[0];
  const sch = ladderFor(s.topology, s.R, s.L, s.C);
  const sw = r?.sweep;
  const f = arr(sw?.f);
  const refl = r?.reflection;

  const plots = useMemo(() => {
    if (!sw) return null;
    return {
      zmag: [{ x: f, y: arr(sw.z_mag), name: "|Z|", line: { width: 1.6 } }, { x: f, y: arr(sw.z_deg), name: "∠Z (°)", yaxis: "y2", line: { width: 1.2, dash: "dot" } }],
      rx: [{ x: f, y: arr(sw.z.re), name: "R" }, { x: f, y: arr(sw.z.im), name: "X" }],
    };
  }, [sw]);
  const fx = num(s.mode === "preset" ? r?.f : r?.f);

  const buildReport = () => {
    if (!r) return null;
    const isP = s.mode === "preset";
    const results: [string, string][] = [["Z", cx(r.z)], ["|Z| ∠ φ", `${fmt(r.z_mag, 6)} Ω ∠ ${fmt(r.z_deg, 5)}°`]];
    if (r.y) results.push(["Y", cx(r.y, "S")]);
    if (isP) {
      if (r.xl != null) results.push(["X_L", `${fmt(r.xl, 6)} Ω`]);
      if (r.xc != null) results.push(["X_C", `${fmt(r.xc, 6)} Ω`]);
      if (r.p != null) results.push(["P / Q / |S|", `${fmt(r.p, 5)} W / ${fmt(r.q, 5)} var / ${fmt(r.s, 5)} VA`]);
      if (r.f0) results.push(["f0", si(r.f0, "Hz", 6)]);
      if (r.q_factor) results.push(["Q / BW", `${fmt(r.q_factor, 5)} / ${si(r.bw_3db, "Hz", 5)}`]);
    }
    if (refl) results.push(["Γ / VSWR / RL", `${cx(refl.gamma, "")} / ${fmt(refl.vswr, 4)} / ${fmt(refl.return_loss_db, 4)} dB`]);
    return {
      title: isP ? `Análisis de circuito — ${r.topology_name}` : `Red — ${r.text}`,
      module: "Impedance Analyzer", origin: "calculated" as const,
      inputs: (isP ? [["Topología", r.topology_name], ["R", `${s.R} Ω`], ["L", `${s.L}H`], ["C", `${s.C}F`], ["f", s.f], ["V", `${s.v} V rms`], ["Z0", `${s.z0} Ω`]]
        : [["Expresión", s.expr], ["f", s.fN], ["Z0", `${s.z0} Ω`]]) as [string, string][],
      results, steps: r.trace,
      plots: sw ? [{ title: "|Z| frente a frecuencia", ylabel: "|Z| (Ω)", x: decimate(f), series: [{ name: "|Z|", y: decimate(arr(sw.z_mag)) }] },
        { title: "R y X frente a frecuencia", ylabel: "Ω", x: decimate(f), series: [{ name: "R", y: decimate(arr(sw.z.re)) }, { name: "X", y: decimate(arr(sw.z.im)) }] }] : [],
      smith: sw ? { z0: s.z0, points: refl ? [{ re: refl.gamma.re, im: refl.gamma.im, label: "f" }] : [], traces: [{ name: "Barrido", re: pairs(sw.gamma).map((p) => p[0]), im: pairs(sw.gamma).map((p) => p[1]) }] } : undefined,
    };
  };

  return (
    <div>
      <PageHeader index={3} title="Impedance Analyzer" desc="Impedancia, admitancia, potencias, resonancia y Q de circuitos R-L-C con desarrollo paso a paso. Convención e^{+jωt}: X_L > 0, X_C < 0." right={<><OriginBadge origin="calculated" /><ReportButton build={buildReport} disabled={!r} /></>} />
      <div className="mb-3"><Seg value={s.mode} onChange={(v) => set({ mode: v })} options={[{ value: "preset", label: "Circuitos predefinidos" }, { value: "network", label: "Red personalizada (combinaciones)" }]} /></div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-3">
          {s.mode === "preset" ? (
            <Panel title="Circuito">
              <Field label="Topología"><Select value={s.topology} onChange={(v) => set({ topology: v })} options={TOPOS.map(([v, l]) => ({ value: v, label: l }))} /></Field>
              <div className="mt-2.5 rounded border border-line bg-[#060a0c] p-2"><Ladder items={sch.items} left={{ kind: "port", label: "Zin" }} right={{ kind: sch.right }} height={140} /></div>
              <div className="mt-2.5 grid grid-cols-3 gap-2">
                <Field label="R" hint="Ω"><Input value={s.R} disabled={!uses.includes("R")} onChange={(e) => set({ R: e.target.value })} /></Field>
                <Field label="L" hint="H (10n, 1.5u)"><Input value={s.L} disabled={!uses.includes("L")} onChange={(e) => set({ L: e.target.value })} /></Field>
                <Field label="C" hint="F (4.7p, 10n)"><Input value={s.C} disabled={!uses.includes("C")} onChange={(e) => set({ C: e.target.value })} /></Field>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2">
                <Field label="Frecuencia"><Input value={s.f} onChange={(e) => set({ f: e.target.value })} /></Field>
                <Field label="Z0 ref."><Input type="number" value={s.z0} suffix="Ω" onChange={(e) => set({ z0: Number(e.target.value) || 50 })} /></Field>
                <Field label="Tensión" hint="V rms"><Input type="number" value={s.v} onChange={(e) => set({ v: Number(e.target.value) || 1 })} /></Field>
              </div>
            </Panel>
          ) : (
            <Panel title="Red personalizada" sub="'+' serie · '||' paralelo · R() L() C() Z(re,im)">
              <Field label="Expresión"><Input value={s.expr} onChange={(e) => set({ expr: e.target.value })} /></Field>
              <div className="mt-1.5 flex flex-wrap gap-1">{EXAMPLES.map((e) => <button key={e} onClick={() => set({ expr: e })} className="rounded border border-line px-1.5 py-0.5 font-mono text-2xs text-dim hover:border-acc/40 hover:text-acc">{e}</button>)}</div>
              {r?.text && <div className="mt-2 rounded bg-[#060a0c] px-2 py-1.5 font-mono text-[12px] text-acc">{r.text}</div>}
              <div className="mt-2.5 grid grid-cols-2 gap-2">
                <Field label="Frecuencia"><Input value={s.fN} onChange={(e) => set({ fN: e.target.value })} /></Field>
                <Field label="Z0 ref."><Input type="number" value={s.z0} suffix="Ω" onChange={(e) => set({ z0: Number(e.target.value) || 50 })} /></Field>
              </div>
            </Panel>
          )}
          <Panel title="Barrido de frecuencia">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Inicio"><Input value={s.mode === "preset" ? s.start : s.startN} onChange={(e) => set(s.mode === "preset" ? { start: e.target.value } : { startN: e.target.value })} /></Field>
              <Field label="Fin"><Input value={s.mode === "preset" ? s.stop : s.stopN} onChange={(e) => set(s.mode === "preset" ? { stop: e.target.value } : { stopN: e.target.value })} /></Field>
            </div>
            <div className="mt-2"><Toggle checked={s.log} onChange={(v) => set({ log: v })} label="Escala logarítmica" /></div>
          </Panel>
          {call.error && <Note kind="err">{call.error}</Note>}
        </div>
        <div className="space-y-3">
          {r && (
            <>
              <Grid cols="grid-cols-2 lg:grid-cols-4">
                <Stat label="|Z|" value={fmt(r.z_mag, 5)} unit="Ω" tone="acc" />
                <Stat label="Fase φ" value={fmt(r.z_deg, 5)} unit="°" sub={r.character ? `Carácter ${r.character}` : undefined} />
                <Stat label="VSWR (Z0)" value={refl ? fmt(refl.vswr, 4) : "∞"} tone="warn" />
                <Stat label="Return Loss" value={refl ? fmt(refl.return_loss_db, 4) : "0"} unit="dB" />
              </Grid>
              <Grid cols="lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_300px]">
                <Panel title="Impedancia y admitancia">
                  <KV dense rows={[
                    ["Z", cx(r.z)],
                    ["Admitancia Y", r.y ? cx(r.y, "S") : "—"],
                    ["Conductancia G", r.y ? fmt(r.y.re, 6) : "—", "S"],
                    ["Susceptancia B", r.y ? fmt(r.y.im, 6) : "—", "S"],
                    ...(s.mode === "preset" ? [
                      ["ω", fmt(r.omega, 6), "rad/s"],
                      ...(r.xl != null ? [["X_L", fmt(r.xl, 6), "Ω"]] : []),
                      ...(r.xc != null ? [["X_C", fmt(r.xc, 6), "Ω"]] : []),
                    ] as any : []),
                    ["Γ (respecto a Z0)", refl ? cx(refl.gamma, "") : "1 (abierto)"],
                  ]} />
                </Panel>
                {s.mode === "preset" ? (
                  <Panel title="Potencias y resonancia" sub={`Fuente ideal ${s.v} V rms`}>
                    <KV dense rows={[
                      ["Potencia activa P", fmt(r.p, 6), "W"],
                      ["Potencia reactiva Q", fmt(r.q, 6), "var"],
                      ["Potencia aparente |S|", fmt(r.s, 6), "VA"],
                      ["Factor de potencia", fmt(r.pf, 5)],
                      ["Corriente |I|", r.i ? fmt(Math.hypot(r.i.re, r.i.im), 6) : "—", "A"],
                      ["f0 resonancia", r.f0 ? si(r.f0, "Hz", 6) : "—"],
                      ["Factor Q", r.q_factor ? fmt(r.q_factor, 5) : "—"],
                      ["BW −3 dB", r.bw_3db ? si(r.bw_3db, "Hz", 5) : "—"],
                    ]} />
                  </Panel>
                ) : (
                  <Panel title="Árbol de la red"><pre className="max-h-64 overflow-auto font-mono text-2xs text-dim">{JSON.stringify(r.tree, null, 1)}</pre></Panel>
                )}
                <Panel title="Carta de Smith" sub="Barrido y punto a f" pad={false}>
                  <div className="aspect-square w-full p-1.5">
                    <SmithChart z0={s.z0} traces={sw ? [{ pts: pairs(sw.gamma), color: "#58b4ff", width: 1.4 }] : []} points={refl ? [{ g: [refl.gamma.re, refl.gamma.im], label: "f", color: "#2fe39a" }] : []} />
                  </div>
                </Panel>
              </Grid>
              {plots && (
                <Grid>
                  <Panel title="|Z| y fase" pad={false}><Plot data={plots.zmag} height={260} layout={{ xaxis: { type: s.log ? "log" : "linear", title: { text: "Frecuencia (Hz)" } }, yaxis: { type: "log", title: { text: "|Z| (Ω)" } }, yaxis2: { title: { text: "Fase (°)" }, range: [-95, 95] }, shapes: Number.isFinite(fx) ? [{ type: "line", x0: fx, x1: fx, yref: "paper", y0: 0, y1: 1, line: { color: "#2fe39a", dash: "dot", width: 1 } }] : [] }} /></Panel>
                  <Panel title="Resistencia y reactancia" pad={false}><Plot data={plots.rx} height={260} layout={{ xaxis: { type: s.log ? "log" : "linear", title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "Ω" } } }} /></Panel>
                </Grid>
              )}
            </>
          )}
          <Steps steps={r?.trace} />
        </div>
      </div>
    </div>
  );
}
