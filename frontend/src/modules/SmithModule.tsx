import { EduNote } from "../components/EduNote";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ReportButton } from "../components/ReportButton";
import { SmithChart, type SmithPoint, type SmithTrace } from "../components/SmithChart";
import { Steps } from "../components/Steps";
import { Btn, Field, Input, KV, Note, OriginBadge, PageHeader, Panel, Seg, Toggle } from "../components/ui";
import { post } from "../lib/api";
import { cx, fmt, num, pairs, polar, si } from "../lib/format";
import type { P } from "../lib/smith";
import { useForm, useStore } from "../lib/store";
import { useTheme } from "../lib/theme";
import { usePalette } from "../components/Plot";

type Pt = { label: string; z: string };
const DEF = {
  z0: 50,
  f: "",
  pts: [{ label: "Z1", z: "80+j30" }] as Pt[],
  sel: 0,
  admittance: false,
  fine: false,
  showVswr: true,
  rotLen: 0,
  rotDir: "generator" as "generator" | "load",
};

export function SmithModule() {
  const T = useTheme();
  const PALETTE = usePalette();
  const [s, set] = useForm("smith", DEF);
  const toast = useStore((st) => st.toast);
  const [res, setRes] = useState<(any | null)[]>([]);
  const [errs, setErrs] = useState<(string | null)[]>([]);
  const [rot, setRot] = useState<any>(null);
  const [dragG, setDragG] = useState<P | null>(null);
  const sel = Math.min(s.sel, s.pts.length - 1);

  // Cálculo en el motor de todos los puntos
  useEffect(() => {
    let alive = true;
    const t = setTimeout(async () => {
      const out = await Promise.all(
        s.pts.map((p) => post("/rf/reflection", { z: p.z, z0: s.z0, f: s.f || null }).then((r) => [r, null] as const).catch((e) => [null, e.message] as const)),
      );
      if (!alive) return;
      setRes(out.map((o) => o[0]));
      setErrs(out.map((o) => o[1]));
    }, 180);
    return () => { alive = false; clearTimeout(t); };
  }, [JSON.stringify(s.pts), s.z0, s.f]);

  useEffect(() => {
    const p = s.pts[sel];
    if (!p || !s.rotLen) { setRot(null); return; }
    const t = setTimeout(() => post("/rf/line-rotate", { z: p.z, z0: s.z0, length_lambda: s.rotLen, toward: s.rotDir }).then(setRot).catch(() => setRot(null)), 120);
    return () => clearTimeout(t);
  }, [s.rotLen, s.rotDir, sel, JSON.stringify(s.pts[sel]), s.z0]);

  const cur = res[sel];
  const points: SmithPoint[] = useMemo(() => {
    const out: SmithPoint[] = [];
    s.pts.forEach((p, i) => {
      const r = res[i];
      if (!r?.gamma) return;
      const g: P = i === sel && dragG ? dragG : [r.gamma.re, r.gamma.im];
      out.push({ g, label: p.label, color: PALETTE[i % PALETTE.length], size: i === sel ? 0.026 : 0.02 });
    });
    if (rot?.gamma_end) out.push({ g: [rot.gamma_end.re, rot.gamma_end.im], label: `${s.pts[sel]?.label}'`, color: T.warn, hollow: true });
    return out;
  }, [res, sel, dragG, rot, s.pts]);
  const dragIndex = points.findIndex((p) => p.label === s.pts[sel]?.label);

  const traces: SmithTrace[] = rot ? [{ pts: pairs(rot.gamma), color: T.warn, dash: true, arrow: true, name: "Línea" }] : [];
  const vswr = s.showVswr && cur?.gamma_mag != null ? [num(cur.gamma_mag)] : [];

  const setPt = (i: number, patch: Partial<Pt>) => set({ pts: s.pts.map((p, j) => (j === i ? { ...p, ...patch } : p)) });

  const pick = async (g: P) => {
    try {
      const r = await post("/rf/reflection", { gamma: { re: g[0], im: g[1] }, z0: s.z0 });
      const z = r.z;
      const txt = z.inf ? "1e12" : `${Number(z.re.toPrecision(6))}${z.im < 0 ? "-" : "+"}j${Number(Math.abs(z.im).toPrecision(6))}`;
      setPt(sel, { z: txt });
    } catch (e: any) {
      toast("err", e.message);
    } finally {
      setDragG(null);
    }
  };

  const buildReport = () => {
    if (!cur) return null;
    return {
      title: `Carta de Smith — ${s.pts[sel].label} = ${s.pts[sel].z} Ω`,
      module: "Smith Chart",
      origin: "calculated" as const,
      inputs: [["Z0", `${s.z0} Ω`], ...s.pts.map((p) => [p.label, `${p.z} Ω`] as [string, string]), ...(s.f ? [["Frecuencia", s.f] as [string, string]] : [])] as [string, string][],
      results: [
        ["Z", cx(cur.z)], ["z normalizada", cx(cur.z_norm, "")], ["Γ", `${cx(cur.gamma, "")}  (${polar(cur.gamma)})`],
        ["VSWR", fmt(cur.vswr, 5)], ["Return Loss", `${fmt(cur.return_loss_db, 5)} dB`], ["Mismatch loss", `${fmt(cur.mismatch_loss_db, 4)} dB`],
        ["Potencia reflejada", `${fmt(cur.reflected_pct, 4)} %`],
      ] as [string, string][],
      steps: cur.trace,
      smith: { z0: s.z0, points: points.map((p) => ({ re: p.g[0], im: p.g[1], label: p.label })), traces: traces.map((t) => ({ name: t.name, re: t.pts.map((q) => q[0]), im: t.pts.map((q) => q[1]) })) },
    };
  };

  return (
    <div>
      <PageHeader index={2} title="Smith Chart" desc="Carta de Smith exacta: Γ = (Z − Z0)/(Z + Z0). Haga clic para situar el punto seleccionado, arrástrelo para moverlo, rueda para zoom y doble clic para restablecer." right={<><OriginBadge origin="calculated" /><ReportButton build={buildReport} disabled={!cur} /></>} />
      <EduNote>Cada punto de la carta es un coeficiente de reflexión Γ = (Z − Z0)/(Z + Z0). El <b>centro</b> es la adaptación perfecta (Z = Z0); el <b>borde</b> es |Γ| = 1 (reactancia pura, toda la potencia se refleja). La mitad <b>superior</b> es inductiva y la <b>inferior</b> capacitiva. Los círculos son de resistencia normalizada r constante y los arcos de reactancia x constante; el círculo discontinuo une los puntos con el mismo VSWR. Mueva el deslizador de línea para ver cómo gira la impedancia hacia el generador.</EduNote>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Panel pad={false} className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-4 border-b border-line px-3.5 py-2">
            <Toggle checked={s.admittance} onChange={(v) => set({ admittance: v })} label="Rejilla de admitancia (Y)" />
            <Toggle checked={s.fine} onChange={(v) => set({ fine: v })} label="Rejilla fina" />
            <Toggle checked={s.showVswr} onChange={(v) => set({ showVswr: v })} label="Círculo de VSWR" />
          </div>
          <div className="aspect-square max-h-[calc(100vh-190px)] w-full p-2">
            <SmithChart z0={s.z0} points={points} traces={traces} vswrCircles={vswr} admittance={s.admittance} fine={s.fine} dragIndex={dragIndex >= 0 ? dragIndex : undefined}
              onDrag={(g) => setDragG(g)} onPick={pick} />
          </div>
        </Panel>
        <div className="space-y-3">
          <Panel title="Referencia y frecuencia">
            <div className="grid grid-cols-2 gap-2.5">
              <Field label="Z0 de referencia" hint="Por defecto 50 Ω"><Input type="number" min={0.001} step="any" value={s.z0} suffix="Ω" onChange={(e) => set({ z0: Math.max(0.001, Number(e.target.value) || 50) })} /></Field>
              <Field label="Frecuencia (opcional)" hint="Para equivalentes L/C"><Input value={s.f} placeholder="p. ej. 433MHz" onChange={(e) => set({ f: e.target.value })} /></Field>
            </div>
          </Panel>
          <Panel title="Impedancias" sub="Formato: 80+j30 · 25-j10 · 100∠45 · j50" actions={<Btn small icon={<Plus className="h-3.5 w-3.5" />} disabled={s.pts.length >= 8} onClick={() => set({ pts: [...s.pts, { label: `Z${s.pts.length + 1}`, z: "50" }], sel: s.pts.length })}>Punto</Btn>}>
            <div className="space-y-1.5">
              {s.pts.map((p, i) => (
                <div key={i} className={`grid grid-cols-[14px_56px_1fr_24px] items-center gap-2 rounded px-1.5 py-1 ${i === sel ? "bg-acc/[0.07] ring-1 ring-acc/25" : ""}`} onClick={() => set({ sel: i })}>
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: PALETTE[i % PALETTE.length] }} />
                  <Input value={p.label} onChange={(e) => setPt(i, { label: e.target.value.slice(0, 8) })} className="px-1.5 py-1 text-[12px]" />
                  <div>
                    <Input value={p.z} suffix="Ω" onChange={(e) => setPt(i, { z: e.target.value })} className={`py-1 ${errs[i] ? "border-err/60" : ""}`} />
                  </div>
                  <button className="text-faint hover:text-err disabled:opacity-30" disabled={s.pts.length === 1} onClick={(e) => { e.stopPropagation(); set({ pts: s.pts.filter((_, j) => j !== i), sel: 0 }); }}><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              ))}
              {errs[sel] && <Note kind="err">{errs[sel]}</Note>}
            </div>
          </Panel>
          <Panel title={`Punto ${s.pts[sel]?.label ?? ""}`} sub="Resultados del motor RF">
            {cur ? (
              <KV dense rows={[
                ["Resistencia R", fmt(cur.z?.re, 6), "Ω"],
                ["Reactancia X", fmt(cur.z?.im, 6), "Ω"],
                ["Impedancia Z", cx(cur.z)],
                ["|Z| ∠ φ", cur.is_open ? "∞" : `${fmt(cur.z_mag, 5)} Ω ∠ ${fmt(cur.z_deg, 5)}°`],
                ["z normalizada", cx(cur.z_norm, "")],
                ["y normalizada", cx(cur.y_norm, "")],
                ["Admitancia Y", cx(cur.y, "S")],
                ["Γ (rectangular)", cx(cur.gamma, "")],
                ["|Γ| ∠ θ", polar(cur.gamma)],
                ["Return Loss", fmt(cur.return_loss_db, 5), "dB"],
                ["|S11|", fmt(cur.s11_db, 5), "dB"],
                ["VSWR", fmt(cur.vswr, 5), ": 1"],
                ["Mismatch loss", fmt(cur.mismatch_loss_db, 4), "dB"],
                ["Potencia reflejada", fmt(cur.reflected_pct, 4), "%"],
              ]} />
            ) : <p className="text-[12px] text-dim">Introduzca una impedancia válida.</p>}
            {cur?.equivalent?.series?.kind && (
              <Note className="mt-2">
                A {si(cur.equivalent.f, "Hz")}: R = {fmt(cur.z.re, 5)} Ω en serie con {cur.equivalent.series.kind} = {si(cur.equivalent.series.value, cur.equivalent.series.kind === "L" ? "H" : "F")}
                {cur.equivalent.parallel?.kind && <> · equivalente paralelo: R = {fmt(cur.equivalent.parallel.R, 5)} Ω ‖ {cur.equivalent.parallel.kind} = {si(cur.equivalent.parallel.value, cur.equivalent.parallel.kind === "L" ? "H" : "F")}</>}
                <div className="mt-0.5 text-2xs opacity-80">Equivalencia válida sólo a esa frecuencia.</div>
              </Note>
            )}
          </Panel>
          <Panel title="Desplazamiento por línea sin pérdidas" sub="Movimiento del punto sobre la carta">
            <div className="flex items-center gap-3">
              <input type="range" min={0} max={0.5} step={0.001} value={s.rotLen} onChange={(e) => set({ rotLen: Number(e.target.value) })} className="flex-1 accent-acc" />
              <span className="w-16 text-right font-mono text-[12px] text-ink">{s.rotLen.toFixed(3)} λ</span>
            </div>
            <div className="mt-2 flex items-center justify-between">
              <Seg small value={s.rotDir} onChange={(v) => set({ rotDir: v })} options={[{ value: "generator", label: "Hacia el generador" }, { value: "load", label: "Hacia la carga" }]} />
              {rot && <span className="font-mono text-[12px] text-warn">Z' = {cx(rot.z_end, "Ω", 5)}</span>}
            </div>
            {rot && <p className="mt-1.5 text-2xs text-faint">{rot.note}</p>}
          </Panel>
          <Steps steps={cur?.trace} />
        </div>
      </div>
    </div>
  );
}
