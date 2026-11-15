import { useEffect, useMemo, useState } from "react";
import { Plot } from "../components/Plot";
import { ReportButton, decimate } from "../components/ReportButton";
import { SmithChart } from "../components/SmithChart";
import { Steps } from "../components/Steps";
import { Field, Grid, Input, KV, Note, OriginBadge, PageHeader, Panel, Seg, Select, Stat, Toggle, useCall } from "../components/ui";
import { get, post } from "../lib/api";
import { arr, cx, fmt, num, pairs, polar, si } from "../lib/format";
import { useForm } from "../lib/store";

const DEF = {
  lineType: "ideal", z0: 50, vf: 0.66, D: "2.95m", d: "0.9m", er: 2.25, W: "3.06m", h: "1.6m", erM: 4.4, cable: "", tM: "35u", tand: 0.02, rough: "0", lossModel: true, attenRef: "",
  f: "145MHz", length: 3.2, unit: "m", atten: 0.1, load: "arbitrary", zl: "100+j50", p_inc: 10, pos: 1,
};

export function TLineModule() {
  const [s, set] = useForm("tline", DEF);
  const [cables, setCables] = useState<any[]>([]);
  useEffect(() => { get("/library?category=coax").then((r) => setCables(r.items)).catch(() => {}); }, []);
  const geo = useCall(() => {
    const p = s.lineType === "coax" ? { kind: "coax", D: s.D, d: s.d, er: s.er } : s.lineType === "twowire" ? { kind: "twowire", D: s.D, d: s.d, er: s.er } : { kind: "microstrip", W: s.W, h: s.h, er: s.erM, f: s.f, t: s.tM, tand: s.tand, rough: s.rough };
    return post("/tline/geometry", p);
  }, ["coax", "twowire", "microstrip"].includes(s.lineType) ? [s.lineType, s.D, s.d, s.er, s.W, s.h, s.erM, s.f, s.tM, s.tand, s.rough] : null);
  const g = geo.data as any;
  const z0 = ["coax", "twowire", "microstrip"].includes(s.lineType) && g ? num(g.z0) : s.z0;
  const vf = ["coax", "twowire", "microstrip"].includes(s.lineType) && g ? num(g.vf) : s.vf;
  const useModelLoss = s.lineType === "microstrip" && s.lossModel && g?.atten_db_per_m != null;
  const atten = useModelLoss ? num(g.atten_db_per_m) : s.atten;
  const attenRef = useModelLoss ? null : s.attenRef || null;
  const call = useCall(
    () => post("/tline/analyze", { z0, f: s.f, length: s.length, length_unit: s.unit, vf, atten_db_per_m: atten, atten_ref_hz: attenRef, load: s.load, zl: s.zl, p_inc: s.p_inc }),
    [z0, vf, s.f, s.length, s.unit, atten, attenRef, s.load, s.zl, s.p_inc],
  );
  const r = call.data as any;
  const prof = r?.profile;
  const d = arr(prof?.d);
  const idx = Math.max(0, Math.min(d.length - 1, Math.round(s.pos * (d.length - 1))));
  const at = prof ? { d: d[idx], z: { re: prof.z.re[idx], im: prof.z.im[idx], inf: prof.z.re[idx] == null }, g: { re: prof.gamma.re[idx], im: prof.gamma.im[idx] } } : null;

  const plots = useMemo(() => {
    if (!prof) return null;
    return {
      vi: [{ x: d, y: arr(prof.v_rel), name: "|V(d)| / |V⁺|" }, { x: d, y: arr(prof.i_rel).map((v) => v * z0), name: "|I(d)|·Z0 / |V⁺|" }],
      rx: [{ x: d, y: arr(prof.z.re).map((v) => (Math.abs(v) > 1e5 ? NaN : v)), name: "R(d)" }, { x: d, y: arr(prof.z.im).map((v) => (Math.abs(v) > 1e5 ? NaN : v)), name: "X(d)" }],
      fz: [{ x: arr(r.freq_sweep.f), y: arr(r.freq_sweep.zin.re), name: "R in" }, { x: arr(r.freq_sweep.f), y: arr(r.freq_sweep.zin.im), name: "X in" }],
    };
  }, [prof, r, z0]);

  const cursor = Number.isFinite(d[idx]) ? [{ type: "line", x0: d[idx], x1: d[idx], yref: "paper", y0: 0, y1: 1, line: { color: "#f0b44c", dash: "dot", width: 1 } }] : [];
  const loadLabel = { open: "Circuito abierto", short: "Cortocircuito", matched: "Adaptada (ZL = Z0)", arbitrary: `ZL = ${s.zl} Ω` }[s.load as "open"];

  const buildReport = () => r && ({
    title: `Línea de transmisión — ${loadLabel}`, module: "Transmission Lines", origin: "calculated" as const,
    inputs: [["Z0", `${fmt(z0, 5)} Ω`], ["Factor de velocidad", fmt(vf, 4)], ["Frecuencia", s.f], ["Longitud", `${s.length} ${s.unit === "lambda" ? "λ" : s.unit === "deg" ? "°" : "m"}`], ["Atenuación", r?.atten_db_per_m != null ? `${fmt(r.atten_db_per_m, 4)} dB/m a ${s.f}${useModelLoss ? " (modelo microstrip)" : attenRef ? ` (escalada desde ${attenRef})` : ""}` : `${s.atten} dB/m`], ["Carga", loadLabel], ["Potencia incidente", `${s.p_inc} W`]] as [string, string][],
    results: [["λ", si(r.lambda, "m", 5)], ["β", `${fmt(r.beta, 5)} rad/m`], ["α", `${fmt(r.alpha, 5)} Np/m`], ["θ", `${fmt(r.theta_deg, 5)}° (${fmt(r.length_lambda, 5)} λ)`], ["ΓL", polar(r.gamma_load)], ["Γin", polar(r.gamma_in)], ["Zin", cx(r.zin)],
      ["VSWR carga / entrada", `${fmt(r.vswr_load, 4)} / ${fmt(r.vswr_in, 4)}`], ["Return Loss entrada", `${fmt(r.return_loss_in_db, 4)} dB`], ["P reflejada / carga / pérdidas", `${fmt(r.p_reflected, 4)} / ${fmt(r.p_load, 4)} / ${fmt(r.p_line_loss, 4)} W`]] as [string, string][],
    steps: r.trace,
    smith: { z0, points: [{ re: r.gamma_load.re, im: r.gamma_load.im, label: "ZL" }, { re: r.gamma_in.re, im: r.gamma_in.im, label: "Zin" }], traces: [{ name: "Γ(d)", re: decimate(pairs(prof.gamma)).map((p) => p[0]), im: decimate(pairs(prof.gamma)).map((p) => p[1]) }] },
    plots: [{ title: "Onda estacionaria de tensión", xlabel: "d desde la carga (m)", ylabel: "|V|/|V+|", x_is_freq: false, x: decimate(d), series: [{ name: "|V|", y: decimate(arr(prof.v_rel)) }] }],
    notes: ["Balance de potencia bajo la hipótesis de generador adaptado a Z0 que entrega la potencia incidente indicada."],
  });

  return (
    <div>
      <PageHeader index={5} title="Transmission Lines" desc="Propagación, transformación de impedancias y onda estacionaria. d se mide desde la carga hacia el generador." right={<><OriginBadge origin="calculated" /><ReportButton build={buildReport} disabled={!r} /></>} />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-3">
          <Panel title="Línea">
            <Field label="Tipo de línea"><Select value={s.lineType} onChange={(v) => set({ lineType: v })} options={[{ value: "ideal", label: "Genérica (Z0, vf)" }, { value: "coax", label: "Coaxial (geometría)" }, { value: "microstrip", label: "Microstrip" }, { value: "twowire", label: "Bifilar" }, { value: "cable", label: "Cable de la biblioteca" }]} /></Field>
            <div className="mt-2.5 grid grid-cols-2 gap-2.5">
              {s.lineType === "ideal" && <>
                <Field label="Z0"><Input type="number" value={s.z0} suffix="Ω" onChange={(e) => set({ z0: Number(e.target.value) || 50 })} /></Field>
                <Field label="Factor de velocidad"><Input type="number" step="0.01" value={s.vf} onChange={(e) => set({ vf: Number(e.target.value) })} /></Field>
              </>}
              {(s.lineType === "coax" || s.lineType === "twowire") && <>
                <Field label={s.lineType === "coax" ? "D (blindaje int.)" : "D (entre centros)"} hint="m, mm (2.95m = 2.95 mm)"><Input value={s.D} onChange={(e) => set({ D: e.target.value })} /></Field>
                <Field label="d (conductor)"><Input value={s.d} onChange={(e) => set({ d: e.target.value })} /></Field>
                <Field label="εr dieléctrico"><Input type="number" step="0.01" value={s.er} onChange={(e) => set({ er: Number(e.target.value) })} /></Field>
              </>}
              {s.lineType === "microstrip" && <>
                <Field label="W (pista)"><Input value={s.W} onChange={(e) => set({ W: e.target.value })} /></Field>
                <Field label="h (sustrato)"><Input value={s.h} onChange={(e) => set({ h: e.target.value })} /></Field>
                <Field label="εr sustrato" hint="a 1 GHz"><Input type="number" step="0.01" value={s.erM} onChange={(e) => set({ erM: Number(e.target.value) })} /></Field>
                <Field label="t (cobre)" hint="35u = 1 oz · 0 = ideal"><Input value={s.tM} onChange={(e) => set({ tM: e.target.value })} /></Field>
                <Field label="tan δ" hint="a 1 GHz"><Input type="number" step="0.001" min={0} value={s.tand} onChange={(e) => set({ tand: Number(e.target.value) })} /></Field>
                <Field label="Rugosidad RMS"><Input value={s.rough} onChange={(e) => set({ rough: e.target.value })} /></Field>
                <div className="col-span-2"><Toggle checked={s.lossModel} onChange={(v) => set({ lossModel: v })} label="Usar las pérdidas calculadas por el modelo" /></div>
              </>}
              {s.lineType === "cable" && (
                <Field label="Cable" className="col-span-2">
                  <Select value={s.cable} onChange={(v) => { const c = cables.find((x) => String(x.id) === v); set({ cable: v, ...(c ? { z0: c.extra.z0, vf: c.extra.vf, ...(c.extra.atten_db_per_100m != null ? { atten: c.extra.atten_db_per_100m / 100, attenRef: c.extra.atten_ref_hz ? String(c.extra.atten_ref_hz) : "" } : {}) } : {}) }); }}
                    options={[{ value: "", label: "Seleccione…" }, ...cables.map((c) => ({ value: String(c.id), label: `${c.name} · ${c.extra.z0} Ω · vf ${c.extra.vf}` }))]} />
                </Field>
              )}
            </div>
            {g && ["coax", "twowire", "microstrip"].includes(s.lineType) && <Note className="mt-2">Z0 = {fmt(g.z0, 5)} Ω · vf = {fmt(g.vf, 4)} · εeff = {fmt(g.eps_eff, 4)}{g.f != null && <> a {s.f}</>}
              {g.quasi_static && <div className="text-2xs opacity-80">Cuasi-estático (t = 0, sin dispersión): Z0 = {fmt(g.quasi_static.z0, 5)} Ω · εeff = {fmt(g.quasi_static.eps_eff, 4)}</div>}
              {g.alpha_c_db_m != null && <div className="text-2xs opacity-80">Pérdidas: conductor {fmt(g.alpha_c_db_m, 4)} dB/m · dieléctrico {fmt(g.alpha_d_db_m, 4)} dB/m · total {fmt(g.atten_db_per_m, 4)} dB/m</div>}
              <div className="text-2xs opacity-80">{g.formula}</div></Note>}
            {s.lineType === "cable" && (() => { const c = cables.find((x) => String(x.id) === s.cable); return c && c.extra.atten_db_per_100m == null
              ? <Note kind="warn" className="mt-2">Este cable no tiene atenuación en la biblioteca: introdúzcala abajo o edítela en Component Library con el dato del fabricante.</Note>
              : c ? <Note className="mt-2">Atenuación de la biblioteca: {c.extra.atten_db_per_100m} dB/100 m{c.extra.atten_ref_hz ? ` a ${si(c.extra.atten_ref_hz, "Hz")}, escalada con √f` : ""}.</Note> : null; })()}
            {geo.error && <Note kind="err" className="mt-2">{geo.error}</Note>}
          </Panel>
          <Panel title="Condiciones">
            <div className="grid grid-cols-2 gap-2.5">
              <Field label="Frecuencia"><Input value={s.f} onChange={(e) => set({ f: e.target.value })} /></Field>
              <Field label="Atenuación" hint={attenRef ? "dB/m a la frecuencia de referencia" : "dB/m a esta frecuencia"}><Input type="number" step="0.01" min={0} disabled={useModelLoss} value={useModelLoss ? Number(atten.toPrecision(4)) : s.atten} onChange={(e) => set({ atten: Number(e.target.value) })} /></Field>
              <Field label="Frec. de referencia α" hint="Opcional: escala α con √(f/f_ref)"><Input value={s.attenRef} disabled={useModelLoss} placeholder="—" onChange={(e) => set({ attenRef: e.target.value })} /></Field>
              <Field label="Longitud"><Input type="number" step="any" value={s.length} onChange={(e) => set({ length: Number(e.target.value) })} /></Field>
              <Field label="Unidad"><Select value={s.unit} onChange={(v) => set({ unit: v })} options={[{ value: "m", label: "metros" }, { value: "lambda", label: "λ" }, { value: "deg", label: "grados eléctricos" }]} /></Field>
              <Field label="Potencia incidente"><Input type="number" value={s.p_inc} suffix="W" onChange={(e) => set({ p_inc: Number(e.target.value) })} /></Field>
            </div>
            <div className="mt-2.5"><Field label="Terminación"><Seg small value={s.load} onChange={(v) => set({ load: v })} options={[{ value: "open", label: "Abierto" }, { value: "short", label: "Corto" }, { value: "matched", label: "Adaptada" }, { value: "arbitrary", label: "ZL arbitraria" }]} /></Field></div>
            {s.load === "arbitrary" && <div className="mt-2"><Field label="ZL"><Input value={s.zl} suffix="Ω" onChange={(e) => set({ zl: e.target.value })} /></Field></div>}
          </Panel>
          {call.error && <Note kind="err">{call.error}</Note>}
        </div>
        <div className="space-y-3">
          {r && (
            <>
              <Grid cols="grid-cols-2 lg:grid-cols-5">
                <Stat label="λ en la línea" value={si(r.lambda, "m", 4)} />
                <Stat label="Longitud eléctrica" value={fmt(r.theta_deg, 5)} unit="°" sub={`${fmt(r.length_lambda, 4)} λ`} />
                <Stat label="Zin" value={r.zin?.inf ? "∞" : `${fmt(r.zin.re, 4)}${r.zin.im < 0 ? "−" : "+"}j${fmt(Math.abs(r.zin.im), 4)}`} unit="Ω" tone="acc" />
                <Stat label="VSWR entrada" value={fmt(r.vswr_in, 4)} sub={`en carga ${fmt(r.vswr_load, 4)}`} tone="warn" />
                <Stat label="Potencia en carga" value={fmt(r.p_load, 4)} unit="W" sub={`reflejada ${fmt(r.p_reflected, 3)} W · pérdidas ${fmt(r.p_line_loss, 3)} W`} />
              </Grid>
              <Grid cols="lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
                <Panel title="Γ a lo largo de la línea" sub="Carga → generador" pad={false}>
                  <div className="aspect-square w-full p-1.5">
                    <SmithChart z0={z0} traces={[{ pts: pairs(prof.gamma), color: "#58b4ff", width: 1.8, arrow: true }]}
                      points={[{ g: [r.gamma_load.re, r.gamma_load.im], label: "ZL", color: "#f0b44c" }, { g: [r.gamma_in.re, r.gamma_in.im], label: "Zin", color: "#2fe39a" }, ...(at?.g.re != null ? [{ g: [at.g.re, at.g.im] as [number, number], label: "d", color: "#ff7a8a", hollow: true }] : [])]} />
                  </div>
                </Panel>
                <div className="space-y-3">
                  <Panel title="Posición sobre la línea">
                    <input type="range" min={0} max={1} step={0.001} value={s.pos} onChange={(e) => set({ pos: Number(e.target.value) })} className="w-full accent-[#2fe39a]" />
                    {at && <KV dense rows={[["d (desde la carga)", si(at.d, "m", 5), `${fmt(at.d / num(r.lambda), 4)} λ`], ["Z(d)", at.z.inf ? "∞" : cx(at.z as any)], ["Γ(d)", polar(at.g as any)]]} />}
                  </Panel>
                  <Panel title="Constantes y reflexión">
                    <KV dense rows={[["β", fmt(r.beta, 6), "rad/m"], ["α", fmt(r.alpha, 6), "Np/m"], ["γ", cx(r.gamma, "1/m")], ["v_p", si(r.vp, "m/s", 5)], ["ΓL", polar(r.gamma_load)], ["Γin", polar(r.gamma_in)], ["RL entrada", fmt(r.return_loss_in_db, 5), "dB"]]} />
                  </Panel>
                </div>
              </Grid>
              {plots && (
                <Grid>
                  <Panel title="Onda estacionaria" sub="Envolventes normalizadas a la onda incidente en la carga" pad={false}><Plot data={plots.vi} height={240} layout={{ xaxis: { title: { text: "d desde la carga (m)" } }, yaxis: { title: { text: "Relativo" } }, shapes: cursor }} /></Panel>
                  <Panel title="Impedancia a lo largo de la línea" pad={false}><Plot data={plots.rx} height={240} layout={{ xaxis: { title: { text: "d desde la carga (m)" } }, yaxis: { title: { text: "Ω" } }, shapes: cursor }} /></Panel>
                  <Panel title="Zin frente a frecuencia" sub="Misma longitud física" pad={false}><Plot data={plots.fz} height={240} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "Ω" } } }} /></Panel>
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
