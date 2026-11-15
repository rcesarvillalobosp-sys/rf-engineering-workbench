import { motion } from "motion/react";
import { Activity, Antenna, ArrowRight, CircleDot, Cpu, FileInput, FileText, GitBranch, Library, Radio, RefreshCw, ShieldCheck, Waves } from "lucide-react";
import { useEffect, useState } from "react";
import { Btn, Collapse, Note, OriginBadge, PageHeader, Panel, Table } from "../components/ui";
import { CONCEPTS } from "../content/concepts";
import { get } from "../lib/api";
import { hz } from "../lib/format";
import { type ModuleKey, useStore } from "../lib/store";

const CARDS: { key: ModuleKey; title: string; icon: any; desc: string }[] = [
  { key: "smith", title: "Smith Chart", icon: CircleDot, desc: "Impedancias, admitancias, Γ, VSWR y transformación por líneas sobre una carta exacta e interactiva." },
  { key: "impedance", title: "Impedance Analyzer", icon: Activity, desc: "Circuitos R, L, C serie/paralelo y redes arbitrarias, potencias y barridos con desarrollo paso a paso." },
  { key: "matching", title: "Matching Designer", icon: GitBranch, desc: "Redes L, Pi, T, λ/4 y stubs simples/dobles con ancho de banda, Bode–Fano y Monte Carlo." },
  { key: "tline", title: "Transmission Lines", icon: Waves, desc: "Propagación, Zin, Γ(d), VSWR, onda estacionaria y balance de potencias en líneas con pérdidas." },
  { key: "sparams", title: "S-Parameters", icon: Radio, desc: "Magnitud, fase, Smith, marcadores, bandas, retardo de grupo, estabilidad K/μ, círculos de ganancia y TDR." },
  { key: "antenna", title: "Antenna Analyzer", icon: Antenna, desc: "Resonancia, ancho de banda y Q de antenas a partir de S11/Z importados, tabulados o modelados." },
  { key: "library", title: "Component Library", icon: Library, desc: "Componentes ideales y reales (Q, ESR, SRF) para usar en los diseños de adaptación." },
  { key: "touchstone", title: "Touchstone Importer", icon: FileInput, desc: "Lectura validada de .s1p–.s4p (v1/v2, RI/MA/DB) contrastada con scikit-rf, y exportación." },
  { key: "vna", title: "VNA Integration", icon: Cpu, desc: "Drivers NanoVNA, LibreVNA y SCPI/VISA, captura y calibración SOL. Sin conexiones simuladas." },
  { key: "reports", title: "Reports", icon: FileText, desc: "Informes PDF y CSV con procedencia explícita de cada dato, gráficas y procedimientos." },
];

export function Dashboard() {
  const setModule = useStore((s) => s.setModule);
  const report = useStore((s) => s.report);
  const [health, setHealth] = useState<any>(null);
  const [datasets, setDatasets] = useState<any[]>([]);
  const [self, setSelf] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    get("/health").then(setHealth).catch((e) => setErr(e.message));
    get("/datasets").then(setDatasets).catch(() => {});
  }, []);
  const [upd, setUpd] = useState<any>(null);
  const [checking, setChecking] = useState(false);
  useEffect(() => { window.rfwb?.updates.state().then(setUpd).catch(() => {}); }, []);
  const checkUpd = async () => {
    setChecking(true);
    try { const s = await window.rfwb!.updates.check(); setUpd({ ...(upd ?? {}), ...s }); } finally { setChecking(false); }
  };
  const runSelf = async () => {
    setRunning(true);
    try { setSelf(await get("/selftest")); } catch (e: any) { setErr(e.message); } finally { setRunning(false); }
  };
  return (
    <div>
      <PageHeader index={1} title="Dashboard" desc="Plataforma de análisis, simulación y diseño de sistemas RF. Funciona sin instrumento: todos los resultados proceden del motor matemático, de modelos o de archivos importados, y cada dato indica su origen." />
      {err && <Note kind="err" className="mb-3">No se puede contactar con el motor RF: {err}</Note>}
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_380px]">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {CARDS.map((c, i) => {
            const Icon = c.icon;
            return (
              <motion.button key={c.key} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }} onClick={() => setModule(c.key)}
                className="group rounded-md border border-line bg-panel p-4 text-left transition-colors hover:border-acc/40 hover:bg-[#0c1517]">
                <div className="flex items-center justify-between">
                  <Icon className="h-5 w-5 text-acc" />
                  <ArrowRight className="h-4 w-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-acc" />
                </div>
                <div className="mt-3 text-[14px] font-semibold text-ink">{c.title}</div>
                <p className="mt-1 text-[12px] leading-snug text-dim">{c.desc}</p>
              </motion.button>
            );
          })}
        </div>
        <div className="space-y-3">
          <Panel title="Estado del sistema">
            <div className="space-y-1.5 font-mono text-[12px]">
              <div className="flex justify-between"><span className="text-dim">Motor RF</span><span className={health ? "text-acc" : "text-err"}>{health ? `v${health.version} en línea` : "sin conexión"}</span></div>
              {health && <div className="flex justify-between"><span className="text-dim">NumPy / SciPy / skrf</span><span>{health.numpy} / {health.scipy} / {health.skrf}</span></div>}
              <div className="flex justify-between"><span className="text-dim">Conjuntos de datos</span><span>{datasets.length}</span></div>
              <div className="flex justify-between"><span className="text-dim">Elementos en el informe</span><span>{report.length}</span></div>
              {upd && <div className="flex justify-between"><span className="text-dim">Aplicación</span><span>v{upd.current}</span></div>}
            </div>
            {window.rfwb && (
              <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-line pt-2.5">
                <span className="text-2xs text-faint">{upd?.message || "Actualizaciones desde GitHub Releases"}</span>
                <Btn small loading={checking} icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={checkUpd}>Buscar actualizaciones</Btn>
              </div>
            )}
          </Panel>
          <Panel title="Validación del motor" sub="Casos analíticos, Pozar y contraste con scikit-rf" actions={<Btn small variant="primary" loading={running} icon={<ShieldCheck className="h-3.5 w-3.5" />} onClick={runSelf}>Ejecutar</Btn>}>
            {!self ? <p className="text-[12px] text-dim">Ejecuta una batería de comprobaciones del motor matemático contra resultados de referencia. La batería completa (139 pruebas) está en <span className="font-mono">backend/tests</span>.</p> : (
              <div>
                <Note kind={self.passed === self.total ? "ok" : "err"} className="mb-2">{self.passed} / {self.total} comprobaciones superadas</Note>
                <div className="max-h-72 space-y-1 overflow-auto">
                  {self.cases.map((c: any, i: number) => (
                    <div key={i} className="rounded border border-line px-2 py-1 text-[11.5px]">
                      <div className="flex justify-between gap-2"><span className="text-ink">{c.name}</span><span className={c.ok ? "text-acc" : "text-err"}>{c.ok ? "OK" : "FALLO"}</span></div>
                      <div className="font-mono text-2xs text-faint">esperado {c.expected} · obtenido {c.got} · {c.reference}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Panel>
          <Panel title="Datos recientes">
            {datasets.length === 0 ? <p className="text-[12px] text-dim">Sin datos. Importe un archivo Touchstone o genere datos simulados desde S-Parameters.</p> : (
              <Table head={["Nombre", "Origen", "Rango"]} rows={datasets.slice(0, 6).map((d) => [<span className="font-sans">{d.name}</span>, <OriginBadge origin={d.origin} />, `${hz(d.f_start, 4)} – ${hz(d.f_stop, 4)}`])} />
            )}
          </Panel>
        </div>
      </div>
      <div className="mt-3">
        <Panel title="Conceptos fundamentales" sub="Modo educativo">
          <div className="grid grid-cols-1 gap-2 lg:grid-cols-3">
            {CONCEPTS.map((c) => (
              <Collapse key={c.term} title={<span>{c.term} <span className="ml-1 font-mono text-2xs text-acc/80">{c.formula}</span></span>}>
                <p className="text-[12.5px] leading-relaxed text-dim">{c.text}</p>
              </Collapse>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
