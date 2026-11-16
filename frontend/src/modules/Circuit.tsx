import { ArrowDown, ArrowUp, Eraser, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { EduNote } from "../components/EduNote";
import { Plot, usePalette } from "../components/Plot";
import { ReportButton, decimate } from "../components/ReportButton";
import { Ladder, elementsToLadder } from "../components/Schematic";
import { SmithChart, type SmithTrace } from "../components/SmithChart";
import { Steps } from "../components/Steps";
import { Btn, Field, Grid, Input, KV, Note, OriginBadge, PageHeader, Panel, Select, Stat, useCall } from "../components/ui";
import { post } from "../lib/api";
import { cx, fmt, hz, num, pairs, si } from "../lib/format";
import { useForm } from "../lib/store";
import { useTheme } from "../lib/theme";

type Part = "L" | "C" | "R" | "line" | "stub_open" | "stub_short";
type El = { id: string; kind: "series" | "shunt" | "line"; part: Part; base?: string; k?: number; z0?: string; length?: number; unit?: "lambda" | "deg"; vf?: number };

const uid = () => Math.random().toString(36).slice(2, 9);
const UNIT: Record<string, string> = { L: "H", C: "F", R: "Ω" };
const ADD: { label: string; el: Omit<El, "id"> }[] = [
  { label: "L serie", el: { kind: "series", part: "L", base: "10n", k: 0 } },
  { label: "C serie", el: { kind: "series", part: "C", base: "5p", k: 0 } },
  { label: "R serie", el: { kind: "series", part: "R", base: "10", k: 0 } },
  { label: "L paralelo", el: { kind: "shunt", part: "L", base: "20n", k: 0 } },
  { label: "C paralelo", el: { kind: "shunt", part: "C", base: "3p", k: 0 } },
  { label: "R paralelo", el: { kind: "shunt", part: "R", base: "200", k: 0 } },
  { label: "Línea", el: { kind: "line", part: "line", z0: "50", length: 0.125, unit: "lambda", vf: 1 } },
  { label: "Stub abierto ‖", el: { kind: "shunt", part: "stub_open", z0: "50", length: 0.1, unit: "lambda", vf: 1 } },
  { label: "Stub en corto ‖", el: { kind: "shunt", part: "stub_short", z0: "50", length: 0.1, unit: "lambda", vf: 1 } },
];
const PRESETS: { label: string; zl: string; f0: string; z0: number; els: Omit<El, "id">[] }[] = [
  { label: "Red L (Pozar 5.1)", zl: "200-j100", f0: "500MHz", z0: 100, els: [{ kind: "shunt", part: "C", base: "0.9194p", k: 0 }, { kind: "series", part: "L", base: "38.82n", k: 0 }] },
  { label: "Transformador λ/4", zl: "100", f0: "1GHz", z0: 50, els: [{ kind: "line", part: "line", z0: "70.71", length: 0.25, unit: "lambda", vf: 1 }] },
  { label: "Stub simple (Pozar 5.2)", zl: "60-j80", f0: "2GHz", z0: 50, els: [{ kind: "line", part: "line", z0: "50", length: 0.1104, unit: "lambda", vf: 1 }, { kind: "shunt", part: "stub_short", z0: "50", length: 0.0948, unit: "lambda", vf: 1 }] },
  { label: "Vacío", zl: "25-j40", f0: "433MHz", z0: 50, els: [] },
];

/** Valor efectivo de un L/C/R: base × 10^k (k = posición del deslizador, ±1 década). */
function effValue(e: El): string {
  if (!e.base) return "";
  if (!e.k) return e.base;
  const m = /^\s*([0-9.eE+-]+)\s*([fpnuµmkMG]?)/.exec(e.base);
  if (!m) return e.base;
  return `${Number((Number(m[1]) * 10 ** e.k).toPrecision(5))}${m[2]}`;
}

const DEF = { zl: "25-j40", z0: 50, f0: "433MHz", span: 0.5, load_model: "series_equiv", els: [] as El[], sel: "" as string, ins: -1 };

export function CircuitModule() {
  const [s, set] = useForm("circuit", DEF);
  const T = useTheme();
  const PAL = usePalette();
  const n = s.els.length;
  const ins = s.ins < 0 || s.ins > n ? n : s.ins;           // punto de inserción (0 = junto a la carga, n = junto a Zin)
  const selIdx = s.els.findIndex((e) => e.id === s.sel);
  const colorOf = (i: number) => PAL[(i + 1) % PAL.length];

  const payload = s.els.map((e) => (e.part === "line" || e.part.startsWith("stub")
    ? { kind: e.kind, part: e.part, z0: e.z0, length: e.length, unit: e.unit, vf: e.vf }
    : { kind: e.kind, part: e.part, value: effValue(e) }));
  const call = useCall(() => post("/circuit/builder", { zl: s.zl, z0: s.z0, f0: s.f0, span: s.span, load_model: s.load_model, elements: payload }),
    [s.zl, s.z0, s.f0, s.span, s.load_model, JSON.stringify(payload)], 90);
  const r = call.data as any;

  const upd = (id: string, p: Partial<El>) => set({ els: s.els.map((e) => (e.id === id ? { ...e, ...p } : e)) });
  const add = (el: Omit<El, "id">) => {
    const id = uid();
    const els = [...s.els.slice(0, ins), { ...el, id }, ...s.els.slice(ins)];
    set({ els, sel: id, ins: ins + 1 });
  };
  const remove = (id: string) => {
    const i = s.els.findIndex((e) => e.id === id);
    set({ els: s.els.filter((e) => e.id !== id), sel: "", ins: i >= 0 && i < ins ? ins - 1 : ins });
  };
  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= n) return;
    const a = [...s.els];
    [a[i], a[j]] = [a[j], a[i]];
    set({ els: a });
  };

  // Tecla Supr: borra el elemento seleccionado (si no se está escribiendo en un campo)
  useEffect(() => {
    const h = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement)?.tagName;
      if (ev.key === "Delete" && s.sel && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") remove(s.sel);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const smith = useMemo(() => {
    if (!r) return null;
    const traces: SmithTrace[] = [
      { pts: pairs(r.sweep.gamma), color: T.faint, width: 1, dash: true, name: "Zin(f)" },
      ...r.segments.map((sg: any, i: number) => ({ pts: pairs(sg.gamma), color: colorOf(i), width: i === selIdx ? 4.2 : 2.2, arrow: true, name: sg.label })),
    ];
    const ng = pairs(r.nodes_gamma);
    const pts = ng.map((g, i) => ({ g, label: i === 0 ? "ZL" : i === ng.length - 1 ? "Zin" : String(i), color: i === 0 ? T.warn : i === ng.length - 1 ? T.acc : colorOf(i - 1), hollow: i > 0 && i < ng.length - 1, size: i === ng.length - 1 ? 0.028 : 0.02 }));
    return { traces, pts };
  }, [r, T, PAL, selIdx]);

  const f = (r?.sweep?.f ?? []).map((v: any) => num(v));
  const refl = r?.reflection;
  const lam = num(r?.lambda_m);
  // el motor devuelve los elementos fuente→carga; el esquema se dibuja carga→Zin (mismo orden que la lista)
  const ladder = r ? elementsToLadder([...r.elements].reverse(), Number.isFinite(lam) ? lam : undefined) : [];

  const buildReport = () => r && ({
    title: `Circuito construido — ZL = ${s.zl} Ω, ${n} elementos`, module: "Circuit Builder", origin: "calculated" as const,
    inputs: [["ZL", `${s.zl} Ω`], ["Z0", `${s.z0} Ω`], ["f0", s.f0], ...s.els.map((e, i) => [`Elemento ${i + 1} (desde la carga)`, labelOf(e)] as [string, string])] as [string, string][],
    results: [...r.nodes.map((z: any, i: number) => [i === 0 ? "Z carga" : `Z tras elemento ${i}`, cx(z)] as [string, string]),
      ...(refl ? [["Γ en la entrada", cx(refl.gamma, "")], ["VSWR / RL", `${fmt(refl.vswr, 4)} / ${fmt(refl.return_loss_db, 4)} dB`]] as [string, string][] : [])],
    steps: r.trace,
    smith: { z0: s.z0, points: smith!.pts.map((p) => ({ re: p.g[0], im: p.g[1], label: p.label })), traces: smith!.traces.slice(1).map((t) => ({ name: t.name, re: t.pts.map((q) => q[0]), im: t.pts.map((q) => q[1]) })) },
    plots: [{ title: "|Γ| en la entrada", ylabel: "dB", x: decimate(f), series: [{ name: "|Γ| dB", y: decimate((r.sweep.s11_db as any[]).map((v) => num(v))) }] }],
  });

  const InsertBar = ({ at }: { at: number }) => (
    <button onClick={() => set({ ins: at })} title="Los elementos nuevos se insertarán aquí"
      className={`flex w-full items-center gap-2 px-3 py-0.5 text-2xs transition-colors ${ins === at ? "bg-acc/10 font-semibold text-acc" : "text-faint hover:text-acc"}`}>
      <span className={`h-px flex-1 ${ins === at ? "bg-acc" : "bg-line2"}`} />
      <Plus className="h-3 w-3" />{ins === at ? "Los nuevos elementos irán aquí" : "Insertar aquí"}
      <span className={`h-px flex-1 ${ins === at ? "bg-acc" : "bg-line2"}`} />
    </button>
  );

  return (
    <div>
      <PageHeader index={3} title="Circuit Builder" desc="Construya su red elemento a elemento y vea en tiempo real cómo se desplaza la impedancia sobre la carta de Smith. Todo se lee en el mismo orden: ZL → 1 → 2 → … → Zin." right={<><OriginBadge origin="calculated" /><ReportButton build={buildReport} disabled={!r} /></>} />
      <EduNote>
        El circuito se construye <b>desde la carga (ZL) hacia la entrada (Zin)</b>, igual que se recorre la carta de Smith: el elemento 1 es el que está junto a la carga.
        Cada elemento mueve el punto por una curva característica: <b>serie</b> → círculo de resistencia constante (L sube, C baja);
        <b> paralelo</b> → círculo de conductancia constante; <b>línea sin pérdidas</b> → giro alrededor del centro, en sentido horario hacia el generador.
        La curva discontinua muestra cómo cambia Zin con la frecuencia.
      </EduNote>
      <Panel title="Esquema" sub="Izquierda: carga ZL · derecha: entrada Zin · pulse un elemento para seleccionarlo y un «+» para elegir dónde insertar"
        actions={<Btn small variant="danger" icon={<Eraser className="h-3.5 w-3.5" />} disabled={!n} onClick={() => { if (confirm("¿Vaciar el circuito?")) set({ els: [], sel: "", ins: 0 }); }}>Vaciar</Btn>} pad={false} className="mb-3">
        <div className="overflow-x-auto bg-panel2 px-2 py-1">
          <div className="mx-auto" style={{ minWidth: Math.max(360, 140 + Math.max(n, 1) * 78), maxWidth: 220 + Math.max(n, 1) * 120 }}>
            <Ladder items={ladder} left={{ kind: "load", label: "ZL" }} right={{ kind: "port", label: "Zin" }} height={182}
              selected={selIdx >= 0 ? selIdx : undefined} onSelect={(i) => set({ sel: s.els[i]?.id ?? "" })}
              slot={ins} onSlot={(k) => set({ ins: k })} numbered colorsOf={colorOf} />
          </div>
        </div>
      </Panel>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[400px_minmax(0,1fr)]">
        <div className="space-y-3">
          <Panel title="Carga y referencia" actions={<Select value="" onChange={(v) => { const p = PRESETS.find((x) => x.label === v); if (p) set({ zl: p.zl, f0: p.f0, z0: p.z0, els: p.els.map((e) => ({ ...e, id: uid() })), sel: "", ins: -1 }); }} options={[{ value: "", label: "Ejemplos…" }, ...PRESETS.map((p) => ({ value: p.label, label: p.label }))]} />}>
            <div className="grid grid-cols-2 gap-2.5">
              <Field label="Carga ZL"><Input value={s.zl} suffix="Ω" onChange={(e) => set({ zl: e.target.value })} /></Field>
              <Field label="Z0 (carta)"><Input type="number" value={s.z0} suffix="Ω" onChange={(e) => set({ z0: Number(e.target.value) || 50 })} /></Field>
              <Field label="Frecuencia f0"><Input value={s.f0} onChange={(e) => set({ f0: e.target.value })} /></Field>
              <Field label="Barrido ± fracción"><Input type="number" step="0.05" min={0.05} max={0.95} value={s.span} onChange={(e) => set({ span: Number(e.target.value) })} /></Field>
            </div>
            <div className="mt-2"><Field label="ZL fuera de f0"><Select value={s.load_model} onChange={(v) => set({ load_model: v })} options={[{ value: "series_equiv", label: "R + L/C serie equivalente" }, { value: "constant", label: "Constante" }]} /></Field></div>
          </Panel>
          <Panel title="Añadir elemento" sub={n === 0 ? "Se colocará junto a la carga" : ins === 0 ? "Se insertará junto a la carga (posición 1)" : ins === n ? `Se insertará junto a Zin (posición ${n + 1})` : `Se insertará entre el ${ins} y el ${ins + 1}`}>
            <div className="grid grid-cols-3 gap-1.5">
              {ADD.map((a) => <Btn key={a.label} small icon={<Plus className="h-3 w-3" />} onClick={() => add(a.el)}>{a.label}</Btn>)}
            </div>
          </Panel>
          <Panel title={`Circuito (${n})`} sub="Orden: ZL (carga) → Zin (entrada)" pad={false}>
            <div className="border-b border-line px-3 py-1.5 text-2xs font-medium text-warn">ZL = {s.zl} Ω (carga)</div>
            <InsertBar at={0} />
            {s.els.map((e, i) => {
              const isLine = e.part === "line" || e.part.startsWith("stub");
              const selected = e.id === s.sel;
              return (
                <div key={e.id}>
                  <div onClick={() => set({ sel: e.id })} className={`cursor-pointer border-y px-3 py-2 ${selected ? "border-acc/50 bg-acc/[0.07]" : "border-transparent hover:bg-panel2"}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2 text-[12.5px] font-medium text-ink">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full font-mono text-[10px] font-bold text-panel" style={{ background: colorOf(i) }}>{i + 1}</span>
                        {kindLabel(e)}
                      </span>
                      <span className="flex items-center gap-1" onClick={(ev) => ev.stopPropagation()}>
                        <button className="rounded p-1 text-dim hover:bg-panel2 hover:text-ink disabled:opacity-30" disabled={i === 0} onClick={() => move(i, -1)} title="Mover hacia la carga"><ArrowUp className="h-3.5 w-3.5" /></button>
                        <button className="rounded p-1 text-dim hover:bg-panel2 hover:text-ink disabled:opacity-30" disabled={i === n - 1} onClick={() => move(i, 1)} title="Mover hacia Zin"><ArrowDown className="h-3.5 w-3.5" /></button>
                        <button className="inline-flex items-center gap-1 rounded border border-err/40 px-1.5 py-0.5 text-2xs text-err hover:bg-err/10" onClick={() => remove(e.id)} title="Eliminar (tecla Supr)"><Trash2 className="h-3 w-3" />Eliminar</button>
                      </span>
                    </div>
                    {isLine ? (
                      <div className="mt-1.5 grid grid-cols-[1fr_70px_60px] items-end gap-1.5" onClick={(ev) => ev.stopPropagation()}>
                        <div>
                          <div className="flex justify-between text-2xs text-dim"><span>Longitud</span><span className="font-mono text-ink">{(e.length ?? 0).toFixed(4)} λ · {fmt((e.length ?? 0) * 360, 4)}°</span></div>
                          <input type="range" min={0} max={0.5} step={0.0005} value={e.length ?? 0} onChange={(ev) => upd(e.id, { length: Number(ev.target.value) })} className="w-full accent-acc" />
                        </div>
                        <Field label="Zc (Ω)"><Input value={e.z0 ?? "50"} onChange={(ev) => upd(e.id, { z0: ev.target.value })} className="py-1" /></Field>
                        <Field label="vf"><Input type="number" step="0.01" value={e.vf ?? 1} onChange={(ev) => upd(e.id, { vf: Number(ev.target.value) })} className="py-1" /></Field>
                      </div>
                    ) : (
                      <div className="mt-1.5 grid grid-cols-[124px_1fr] items-center gap-2" onClick={(ev) => ev.stopPropagation()}>
                        <Input value={e.base ?? ""} suffix={UNIT[e.part]} onChange={(ev) => upd(e.id, { base: ev.target.value, k: 0 })} className="py-1" />
                        <div>
                          <input type="range" min={-1} max={1} step={0.005} value={e.k ?? 0} onChange={(ev) => upd(e.id, { k: Number(ev.target.value) })} className="w-full accent-acc" />
                          <div className="flex justify-between font-mono text-2xs text-faint"><span>÷10</span><span className="text-ink">{effValue(e)}{UNIT[e.part]}</span><span>×10</span></div>
                        </div>
                      </div>
                    )}
                  </div>
                  <InsertBar at={i + 1} />
                </div>
              );
            })}
            <div className="border-t border-line px-3 py-1.5 text-2xs font-medium text-acc">Zin (entrada){r?.zin && !r.zin.inf ? ` = ${cx(r.zin, "Ω", 4)}` : ""}</div>
          </Panel>
          {call.error && <Note kind="err">{call.error}</Note>}
        </div>
        <div className="space-y-3">
          {r && (
            <Grid cols="grid-cols-2 lg:grid-cols-4">
              <Stat label="Zin a f0" value={r.zin?.inf ? "∞" : `${fmt(r.zin.re, 4)}${r.zin.im < 0 ? "−" : "+"}j${fmt(Math.abs(r.zin.im), 4)}`} unit="Ω" tone="acc" />
              <Stat label="|Γ| entrada" value={refl ? fmt(refl.gamma_mag, 4) : "1"} sub={refl ? `∠ ${fmt(refl.gamma_deg, 4)}°` : undefined} />
              <Stat label="VSWR" value={refl ? fmt(refl.vswr, 4) : "∞"} tone="warn" />
              <Stat label="Return Loss" value={refl ? fmt(refl.return_loss_db, 4) : "0"} unit="dB" />
            </Grid>
          )}
          <Grid cols="lg:grid-cols-[minmax(0,1fr)_320px]">
            <Panel title="Carta de Smith" sub="Trayectoria de cada elemento (mismo color y número) · discontinua: Zin(f)" pad={false}>
              <div className="mx-auto aspect-square max-h-[calc(100vh-230px)] w-full p-2">
                {smith && <SmithChart z0={s.z0} traces={smith.traces} points={smith.pts} vswrCircles={refl ? [num(refl.gamma_mag)] : []} exportName="circuito_smith" />}
              </div>
            </Panel>
            <Panel title="Impedancia en cada nodo">
              {r ? <KV dense rows={r.nodes.map((z: any, i: number) => [
                <span className="flex items-center gap-1.5">{i > 0 && <span className="h-2 w-2 rounded-full" style={{ background: colorOf(i - 1) }} />}{i === 0 ? "ZL (carga)" : i === r.nodes.length - 1 ? `Zin (tras ${i})` : `Tras elemento ${i}`}</span>,
                cx(z, "Ω", 4)])} /> : <p className="text-[12px] text-dim">—</p>}
            </Panel>
          </Grid>
          {r && (
            <Panel title="Respuesta en frecuencia" sub={`Γ referido a Z0 = ${s.z0} Ω · f0 = ${hz(r.f0)}`} pad={false}>
              <Plot height={240} data={[{ x: f, y: (r.sweep.s11_db as any[]).map((v) => Math.max(num(v), -80)), name: "|Γ| (dB)" }, { x: f, y: (r.sweep.vswr as any[]).map((v) => Math.min(num(v), 20)), name: "VSWR", yaxis: "y2", line: { color: T.warn, width: 1.2 } }]}
                layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "|Γ| (dB)" } }, yaxis2: { title: { text: "VSWR" }, range: [1, 10] },
                  shapes: [{ type: "line", x0: num(r.f0), x1: num(r.f0), yref: "paper", y0: 0, y1: 1, line: { color: T.acc, dash: "dot", width: 1 } }] }} />
            </Panel>
          )}
          <Steps steps={r?.trace} title="Desarrollo elemento a elemento" />
          {r && <p className="text-2xs text-faint">λ a f0 = {si(lam, "m", 4)}</p>}
        </div>
      </div>
    </div>
  );
}

function kindLabel(e: El) {
  if (e.part === "line") return "Línea de transmisión";
  if (e.part === "stub_open") return "Stub abierto en paralelo";
  if (e.part === "stub_short") return "Stub en cortocircuito en paralelo";
  return `${e.part} en ${e.kind === "series" ? "serie" : "paralelo"}`;
}

function labelOf(e: El) {
  if (e.part === "line" || e.part.startsWith("stub")) return `${kindLabel(e)}: ${(e.length ?? 0).toFixed(4)} λ, Zc = ${e.z0} Ω`;
  return `${kindLabel(e)} = ${effValue(e)}${UNIT[e.part]}`;
}
