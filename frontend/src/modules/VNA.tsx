import { EduNote } from "../components/EduNote";
import { Cable, Play, Plug, PlugZap, Radar, Ruler, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Plot } from "../components/Plot";
import { Btn, Field, Input, KV, Note, OriginBadge, PageHeader, Panel, Select, Table, Toggle } from "../components/ui";
import { get, post } from "../lib/api";
import { arr, hz } from "../lib/format";
import { useForm, useStore } from "../lib/store";

const DEF = { driver: "nanovna", address: "", profile: "keysight_ena", start: "1MHz", stop: "900MHz", points: 201, params: "S11,S21", capName: "", raw: 0, open: 0, short: 0, load: 0,
  s2raw: 0, s2short: 0, s2open: 0, s2load: 0, s2thru: 0, useKit: false, kit: {} as KitForm };
type KitForm = Record<string, string>;
const KIT_FIELDS: { std: "open" | "short" | "load" | "thru"; title: string; fields: [string, string, string][] }[] = [
  { std: "open", title: "Open", fields: [["C0", "C0", "fF"], ["C1", "C1", "1e-27 F/Hz"], ["C2", "C2", "1e-36 F/Hz²"], ["C3", "C3", "1e-45 F/Hz³"], ["offset_delay", "Retardo offset", "ps"], ["offset_loss", "Pérdida offset", "GΩ/s"], ["offset_z0", "Z0 offset", "Ω"]] },
  { std: "short", title: "Short", fields: [["L0", "L0", "pH"], ["L1", "L1", "1e-24 H/Hz"], ["L2", "L2", "1e-33 H/Hz²"], ["L3", "L3", "1e-42 H/Hz³"], ["offset_delay", "Retardo offset", "ps"], ["offset_loss", "Pérdida offset", "GΩ/s"], ["offset_z0", "Z0 offset", "Ω"]] },
  { std: "load", title: "Load", fields: [["load_r", "R", "Ω"], ["load_x", "X", "Ω"], ["offset_delay", "Retardo offset", "ps"], ["offset_loss", "Pérdida offset", "GΩ/s"]] },
  { std: "thru", title: "Thru", fields: [["offset_delay", "Retardo", "ps"], ["offset_loss", "Pérdida", "GΩ/s"], ["offset_z0", "Z0", "Ω"]] },
];

/** Convierte el formulario (ps, GΩ/s) a la definición del motor (s, Ω/s). Campos vacíos = valor ideal. */
function kitPayload(useKit: boolean, k: KitForm) {
  if (!useKit) return null;
  const out: Record<string, Record<string, number>> = {};
  for (const s of KIT_FIELDS) {
    out[s.std] = {};
    for (const [key] of s.fields) {
      const v = k[`${s.std}.${key}`];
      if (v === undefined || v === "") continue;
      const n = Number(v);
      out[s.std][key] = key === "offset_delay" ? n * 1e-12 : key === "offset_loss" ? n * 1e9 : n;
    }
  }
  return out;
}

function KitEditor({ useKit, kit, set }: { useKit: boolean; kit: KitForm; set: (p: any) => void }) {
  return (
    <Panel title="Definición del kit de calibración" sub="Se aplica a SOL (1 puerto) y SOLT (2 puertos)">
      <Toggle checked={useKit} onChange={(v) => set({ useKit: v })} label="Usar coeficientes del kit (si no, estándares ideales)" />
      {useKit && (
        <div className="mt-2 grid grid-cols-1 gap-2 lg:grid-cols-2">
          {KIT_FIELDS.map((s) => (
            <div key={s.std} className="rounded border border-line p-2">
              <div className="mb-1 text-[12px] font-medium text-ink">{s.title}</div>
              <div className="grid grid-cols-3 gap-1.5">
                {s.fields.map(([key, label, unit]) => (
                  <Field key={key} label={label} hint={unit}><Input value={kit[`${s.std}.${key}`] ?? ""} placeholder={key === "offset_z0" || key === "load_r" ? "50" : "0"}
                    onChange={(e) => set({ kit: { ...kit, [`${s.std}.${key}`]: e.target.value } })} /></Field>
                ))}
              </div>
            </div>
          ))}
          <Note className="lg:col-span-2">Copie los coeficientes de la documentación de su kit (la app no incluye datos de fabricantes). Modelo: línea de offset con pérdidas + C(f) / L(f) polinómicas + carga.</Note>
        </div>
      )}
    </Panel>
  );
}


/** Barrido continuo: encadena capturas (sin guardarlas) mientras está activo. */
function LiveSweep({ connected, params }: { connected: boolean; params: string }) {
  const toast = useStore((st) => st.toast);
  const [on, setOn] = useState(false);
  const [data, setData] = useState<any>(null);
  const [count, setCount] = useState(0);
  const [rate, setRate] = useState<number | null>(null);
  const alive = useRef(false);
  useEffect(() => () => { alive.current = false; }, []);
  useEffect(() => { if (!connected) { alive.current = false; setOn(false); } }, [connected]);
  const start = async () => {
    alive.current = true;
    setOn(true);
    while (alive.current) {
      const t0 = performance.now();
      try {
        const d = await post("/vna/live", { params: params.split(",").map((x) => x.trim().toUpperCase()) });
        if (!alive.current) break;
        setData(d);
        setCount((c) => c + 1);
        setRate(1000 / (performance.now() - t0));
      } catch (e: any) {
        toast("err", e.message);
        break;
      }
    }
    alive.current = false;
    setOn(false);
  };
  const f = arr(data?.f);
  return (
    <Panel title="Barrido continuo" sub={on ? `En curso · ${count} barridos · ${rate ? rate.toFixed(2) : "—"} barridos/s` : "Requiere instrumento conectado y barrido configurado"}
      actions={<div className="flex gap-2">
        {on ? <Btn small variant="danger" icon={<Square className="h-3.5 w-3.5" />} onClick={() => { alive.current = false; }}>Detener</Btn>
          : <Btn small variant="primary" icon={<Play className="h-3.5 w-3.5" />} disabled={!connected} onClick={start}>Iniciar</Btn>}
        <Btn small disabled={!data} onClick={() => post("/vna/save-last", { params: [], name: null }).then((r) => toast("ok", `Última captura guardada (#${r.id})`)).catch((e) => toast("err", e.message))}>Guardar última</Btn>
      </div>}>
      {data ? (
        <>
          <OriginBadge origin="measured" />
          <Plot height={260} data={Object.keys(data.db).map((k) => ({ x: f, y: arr(data.db[k]), name: k }))} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "|S| (dB)" } } }} />
        </>
      ) : <p className="text-[12px] text-dim">Las capturas del modo continuo no se guardan automáticamente: use «Guardar última» para almacenar la que interese.</p>}
    </Panel>
  );
}

const ROADMAP: [string, "ok" | "partial" | "pending", string][] = [
  ["Arquitectura de drivers por fabricante/modelo", "ok", "Interfaz común VNADriver; un driver por protocolo."],
  ["Detección de instrumentos", "ok", "Puertos serie (VID:PID NanoVNA), servidor LibreVNA-GUI y recursos VISA."],
  ["Conexión USB/serie (NanoVNA)", "ok", "Shell de texto propio a 115200 baudios. Sin verificar con hardware."],
  ["Conexión LAN/TCP (LibreVNA, SCPI)", "ok", "LibreVNA vía servidor SCPI; Keysight/R&S/Copper Mountain vía PyVISA. Sin verificar con hardware."],
  ["Configuración de barrido y número de puntos", "ok", "Validada contra el máximo de puntos del driver."],
  ["Lectura de S11 y S21 · captura", "ok", "Se guarda como «Medición real — VNA conectado»."],
  ["Exportación Touchstone y comparación", "ok", "Las capturas se exportan y comparan como cualquier conjunto de datos."],
  ["Calibración SOL de 1 puerto en la aplicación", "ok", "Modelo de 3 términos validado contra scikit-rf."],
  ["Calibración SOLT de 2 puertos en la aplicación", "ok", "12 términos (scikit-rf); rechaza sistemas singulares."],
  ["Kits de calibración no ideales (offset, C(f), L(f), carga)", "ok", "Coeficientes introducidos por el usuario desde la documentación del kit."],
  ["Visualización en tiempo real (barrido continuo)", "ok", "Barridos encadenados sin guardar; «Guardar última» la almacena como medición real."],
  ["Verificación con instrumentos físicos", "pending", "Pendiente: requiere probar cada driver con su equipo real."],
];

export function VNAModule() {
  const [s, set] = useForm("vna", DEF);
  const toast = useStore((st) => st.toast);
  const [status, setStatus] = useState<any>(null);
  const [drivers, setDrivers] = useState<any>(null);
  const [scan, setScan] = useState<any>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [list, setList] = useState<any[]>([]);
  const refresh = () => { get("/vna/status").then(setStatus); get("/datasets").then(setList); };
  useEffect(() => { refresh(); get("/vna/drivers").then(setDrivers); }, []);
  const drv = drivers?.drivers.find((d: any) => d.key === s.driver);

  const act = async (name: string, fn: () => Promise<any>) => {
    setBusy(name);
    try { await fn(); } catch (e: any) { toast("err", e.message); } finally { setBusy(null); refresh(); }
  };

  return (
    <div>
      <PageHeader index={11} title="VNA Integration" desc="Conexión con analizadores vectoriales de redes reales. La aplicación nunca simula una conexión física: sin instrumento trabaja en modo simulación con datos calculados o importados." />
      <EduNote>Un VNA mide relaciones complejas entre ondas incidentes y reflejadas, pero cables, conectores y acopladores introducen errores sistemáticos. La <b>calibración</b> los modela con términos de error (3 por puerto en SOL, 12 en SOLT) que se calculan midiendo estándares conocidos (Open, Short, Load, Thru) y después se eliminan de la medida del dispositivo.</EduNote>
      <div className={`mb-3 flex items-center gap-3 rounded-md border px-4 py-3 ${status?.connected ? "border-orange/50 bg-orange/10" : "border-line2 bg-panel"}`}>
        {status?.connected ? <PlugZap className="h-5 w-5 text-orange" /> : <Plug className="h-5 w-5 text-dim" />}
        <div className="flex-1">
          <div className={`text-[14px] font-semibold ${status?.connected ? "text-orange" : "text-ink"}`}>{status?.label ?? "…"}</div>
          {status?.connected && <div className="font-mono text-2xs text-dim">{status.driver_name} · {status.address} · {status.idn}</div>}
        </div>
        {status?.connected && <OriginBadge origin="measured" />}
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-3">
          <Panel title="Detección" actions={<Btn small icon={<Radar className="h-3.5 w-3.5" />} loading={busy === "scan"} onClick={() => act("scan", async () => setScan(await post("/vna/scan", {})))}>Buscar</Btn>}>
            {!scan ? <p className="text-[12px] text-dim">Busca puertos serie, el servidor SCPI de LibreVNA-GUI y recursos VISA.</p> : (
              <div className="space-y-1.5">
                {scan.devices.length === 0 && <p className="text-[12px] text-dim">No se detectaron instrumentos.</p>}
                {scan.devices.map((d: any, i: number) => (
                  <button key={i} onClick={() => set({ address: d.address, ...(d.suggested_driver ? { driver: d.suggested_driver } : {}) })} className="w-full rounded border border-line px-2 py-1.5 text-left text-[12px] hover:border-acc/40">
                    <div className="flex justify-between"><span className="font-mono text-ink">{d.address}</span><span className="text-2xs text-dim">{d.interface}{d.vid_pid ? ` · ${d.vid_pid}` : ""}</span></div>
                    <div className="text-2xs text-faint">{d.description}{d.suggested_driver ? ` → driver ${d.suggested_driver}` : ""}</div>
                  </button>
                ))}
                {scan.notes.map((n: string, i: number) => <p key={i} className="text-2xs text-faint">· {n}</p>)}
              </div>
            )}
          </Panel>
          <Panel title="Conexión">
            <div className="space-y-2.5">
              <Field label="Driver"><Select value={s.driver} onChange={(v) => set({ driver: v })} options={(drivers?.drivers ?? []).map((d: any) => ({ value: d.key, label: d.name }))} /></Field>
              {s.driver === "scpi" && <Field label="Perfil SCPI"><Select value={s.profile} onChange={(v) => set({ profile: v })} options={Object.entries<string>(drivers?.scpi_profiles ?? {}).map(([v, l]) => ({ value: v, label: l }))} /></Field>}
              <Field label="Dirección" hint={drv?.address_hint}><Input value={s.address} onChange={(e) => set({ address: e.target.value })} /></Field>
              <div className="flex gap-2">
                <Btn variant="primary" small disabled={status?.connected || !s.address} loading={busy === "conn"} icon={<Cable className="h-3.5 w-3.5" />} onClick={() => act("conn", async () => { await post("/vna/connect", { driver: s.driver, address: s.address, profile: s.driver === "scpi" ? s.profile : null }); toast("ok", "Instrumento conectado"); })}>Conectar</Btn>
                <Btn small disabled={!status?.connected} onClick={() => act("disc", () => post("/vna/disconnect", {}))}>Desconectar</Btn>
              </div>
            </div>
          </Panel>
          <Panel title="Barrido y captura" sub={status?.connected ? "Instrumento conectado" : "Requiere instrumento conectado"}>
            <div className="grid grid-cols-3 gap-2">
              <Field label="Inicio"><Input value={s.start} onChange={(e) => set({ start: e.target.value })} /></Field>
              <Field label="Fin"><Input value={s.stop} onChange={(e) => set({ stop: e.target.value })} /></Field>
              <Field label="Puntos"><Input type="number" value={s.points} onChange={(e) => set({ points: Number(e.target.value) })} /></Field>
              <Field label="Parámetros" className="col-span-2"><Input value={s.params} onChange={(e) => set({ params: e.target.value })} /></Field>
              <Field label="Nombre"><Input mono={false} value={s.capName} onChange={(e) => set({ capName: e.target.value })} /></Field>
            </div>
            <div className="mt-2 flex gap-2">
              <Btn small disabled={!status?.connected} loading={busy === "sweep"} onClick={() => act("sweep", () => post("/vna/sweep", { start: s.start, stop: s.stop, points: s.points }))}>Configurar barrido</Btn>
              <Btn small variant="primary" disabled={!status?.connected} loading={busy === "cap"} onClick={() => act("cap", async () => { const r = await post("/vna/capture", { params: s.params.split(",").map((x: string) => x.trim().toUpperCase()), name: s.capName || null }); toast("ok", `Medición guardada (${r.points} puntos)`); })}>Capturar</Btn>
            </div>
            {!status?.connected && <Note className="mt-2">Sin instrumento no se generan datos aquí. Para trabajar sin hardware use Touchstone Importer o «Generar datos simulados» en S-Parameters.</Note>}
          </Panel>
        </div>
        <div className="space-y-3">
          <LiveSweep connected={!!status?.connected} params={s.params} />
          <Panel title="Drivers disponibles">
            <Table head={["Driver", "Interfaces", "Protocolo", "Parámetros", "Máx. puntos", "Calibración", "Verificado"]} rows={(drivers?.drivers ?? []).map((d: any) => [
              <span className="font-sans">{d.name}</span>, <span className="font-sans text-2xs">{d.interfaces.join(" · ")}</span>, <span className="font-sans text-2xs">{d.protocol}</span>, d.params.join(" "), d.max_points ?? "Según equipo",
              <span className="font-sans text-2xs">{d.calibration.join("; ")}</span>, <span className={d.verified_with_hardware ? "text-acc" : "text-warn"}>{d.verified_with_hardware ? "Sí" : "Sin verificar con hardware"}</span>])} />
            {drv?.notes && <p className="mt-2 text-2xs text-faint">{drv.notes}</p>}
          </Panel>
          <KitEditor useKit={s.useKit} kit={s.kit} set={set} />
          <Panel title="Calibración SOL de 1 puerto" sub={`Corrección de 3 términos · ${s.useKit ? "kit definido" : "estándares ideales (Open Γ=1, Short Γ=−1, Load Γ=0)"}`}>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {(["raw", "open", "short", "load"] as const).map((k) => (
                <Field key={k} label={{ raw: "Medida a corregir", open: "Estándar Open", short: "Estándar Short", load: "Estándar Load" }[k]}>
                  <Select value={String((s as any)[k])} onChange={(v) => set({ [k]: Number(v) } as any)} options={[{ value: "0", label: "—" }, ...list.map((d) => ({ value: String(d.id), label: `${d.name} (${d.origin})` }))]} />
                </Field>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-3">
              <Btn small variant="primary" icon={<Ruler className="h-3.5 w-3.5" />} disabled={!(s.raw && s.open && s.short && s.load)} loading={busy === "cal"} onClick={() => act("cal", async () => { const r = await post("/calibration/sol", { raw_id: s.raw, open_id: s.open, short_id: s.short, load_id: s.load, kit: kitPayload(s.useKit, s.kit) }); toast("ok", `Conjunto corregido creado (#${r.id}) como «derivado»`); })}>Aplicar calibración</Btn>
              <span className="text-2xs text-faint">El resultado se guarda como «Derivado» y conserva la referencia a sus fuentes.</span>
            </div>
          </Panel>
          <Panel title="Calibración SOLT de 2 puertos" sub={`12 términos · ${s.useKit ? "kit definido" : "estándares ideales · Thru de longitud nula"}`}>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
              {(["s2raw", "s2short", "s2open", "s2load", "s2thru"] as const).map((k) => (
                <Field key={k} label={{ s2raw: "Medida (DUT)", s2short: "Short (ambos puertos)", s2open: "Open (ambos puertos)", s2load: "Load (ambos puertos)", s2thru: "Thru" }[k]}>
                  <Select value={String((s as any)[k])} onChange={(v) => set({ [k]: Number(v) } as any)} options={[{ value: "0", label: "—" }, ...list.filter((d) => d.nports === 2).map((d) => ({ value: String(d.id), label: `${d.name} (${d.origin})` }))]} />
                </Field>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-3">
              <Btn small variant="primary" icon={<Ruler className="h-3.5 w-3.5" />} disabled={!(s.s2raw && s.s2short && s.s2open && s.s2load && s.s2thru)} loading={busy === "solt"}
                onClick={() => act("solt", async () => { const r = await post("/calibration/solt", { raw_id: s.s2raw, short_id: s.s2short, open_id: s.s2open, load_id: s.s2load, thru_id: s.s2thru, kit: kitPayload(s.useKit, s.kit) }); toast("ok", `Conjunto corregido creado (#${r.id}) como «derivado»`); })}>Aplicar SOLT</Btn>
              <span className="text-2xs text-faint">Cada estándar es un archivo de 2 puertos con el estándar conectado en ambos puertos. Si los estándares no son independientes, la calibración se rechaza.</span>
            </div>
          </Panel>
          <Panel title="Estado de las funciones de instrumentación">
            <KV dense rows={ROADMAP.map(([n, st, d]) => [<span title={d}>{n}</span>, <span className={st === "ok" ? "text-acc" : st === "partial" ? "text-warn" : "text-dim"}>{st === "ok" ? "Implementado" : st === "partial" ? "Parcial" : "Pendiente"}</span>])} />
          </Panel>
          {list.filter((d) => d.origin === "measured").length > 0 && (
            <Panel title="Mediciones capturadas">
              <Table head={["Nombre", "Puntos", "Rango"]} rows={list.filter((d) => d.origin === "measured").map((d) => [d.name, d.points, `${hz(d.f_start, 4)} – ${hz(d.f_stop, 4)}`])} />
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
