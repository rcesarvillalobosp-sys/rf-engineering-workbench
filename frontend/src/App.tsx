import { AnimatePresence, motion } from "motion/react";
import {
  Activity, Antenna, BookOpen, CircleDot, Cpu, FileInput, FileText, FolderOpen, GitBranch, GraduationCap, LayoutDashboard,
  Library, Radio, Save, Waves, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Btn, Input, Toggle } from "./components/ui";
import { get, post, put, del } from "./lib/api";
import { type ModuleKey, useStore } from "./lib/store";
import { AntennaModule } from "./modules/Antenna";
import { Dashboard } from "./modules/Dashboard";
import { ImpedanceModule } from "./modules/Impedance";
import { LibraryModule } from "./modules/Library";
import { MatchingModule } from "./modules/Matching";
import { ReportsModule } from "./modules/Reports";
import { SmithModule } from "./modules/SmithModule";
import { SParamsModule } from "./modules/SParams";
import { TLineModule } from "./modules/TLine";
import { TouchstoneModule } from "./modules/Touchstone";
import { VNAModule } from "./modules/VNA";

export const MODULES: { key: ModuleKey; label: string; icon: any; Comp: () => JSX.Element }[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard, Comp: Dashboard },
  { key: "smith", label: "Smith Chart", icon: CircleDot, Comp: SmithModule },
  { key: "impedance", label: "Impedance Analyzer", icon: Activity, Comp: ImpedanceModule },
  { key: "matching", label: "Matching Designer", icon: GitBranch, Comp: MatchingModule },
  { key: "tline", label: "Transmission Lines", icon: Waves, Comp: TLineModule },
  { key: "sparams", label: "S-Parameters", icon: Radio, Comp: SParamsModule },
  { key: "antenna", label: "Antenna Analyzer", icon: Antenna, Comp: AntennaModule },
  { key: "library", label: "Component Library", icon: Library, Comp: LibraryModule },
  { key: "touchstone", label: "Touchstone Importer", icon: FileInput, Comp: TouchstoneModule },
  { key: "vna", label: "VNA Integration", icon: Cpu, Comp: VNAModule },
  { key: "reports", label: "Reports", icon: FileText, Comp: ReportsModule },
];

function VnaBadge() {
  const [st, setSt] = useState<any>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    let alive = true;
    const tick = () => get("/vna/status").then((s) => { if (alive) { setSt(s); setErr(false); } }).catch(() => alive && setErr(true));
    tick();
    const t = setInterval(tick, 4000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  if (err) return <span className="rounded border border-err/40 px-2 py-0.5 text-2xs text-err">Motor RF no disponible</span>;
  if (!st) return null;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-2xs ${st.connected ? "border-[#ff8a5c]/50 bg-[#ff8a5c]/10 text-[#ffab8a]" : "border-line2 text-dim"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${st.connected ? "animate-pulse bg-[#ff8a5c]" : "bg-faint"}`} />
      {st.label}
    </span>
  );
}

function ProjectMenu({ onClose }: { onClose: () => void }) {
  const { project, setProject, loadProject, toast } = useStore();
  const [list, setList] = useState<any[]>([]);
  const [name, setName] = useState(project.name);
  const refresh = () => get("/projects").then(setList).catch((e) => toast("err", e.message));
  useEffect(() => { refresh(); }, []);
  const save = async (asNew: boolean) => {
    const s = useStore.getState();
    const data = { forms: s.forms, report: s.report, version: 1 };
    try {
      if (project.id && !asNew) {
        await put(`/projects/${project.id}`, { name, data });
        setProject({ id: project.id, name });
      } else {
        const r = await post("/projects", { name, data });
        setProject({ id: r.id, name });
      }
      toast("ok", `Proyecto guardado: ${name}`);
      refresh();
    } catch (e: any) {
      toast("err", e.message);
    }
  };
  return (
    <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="absolute right-0 top-9 z-50 w-[360px] rounded-md border border-line2 bg-panel p-3 shadow-2xl">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[12px] font-semibold uppercase tracking-wider text-dim">Proyecto</span>
        <button onClick={onClose} className="text-dim hover:text-ink"><X className="h-4 w-4" /></button>
      </div>
      <Input mono={false} value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre del proyecto" />
      <div className="mt-2 flex gap-2">
        <Btn variant="primary" small icon={<Save className="h-3.5 w-3.5" />} onClick={() => save(false)}>{project.id ? "Guardar" : "Guardar nuevo"}</Btn>
        {project.id && <Btn small onClick={() => save(true)}>Guardar como nuevo</Btn>}
        <Btn small variant="subtle" onClick={() => { loadProject({ name: "Proyecto sin título", data: {} }); setName("Proyecto sin título"); }}>Nuevo vacío</Btn>
      </div>
      <p className="mt-2 text-2xs text-faint">Se guardan las entradas de todos los módulos y los elementos del informe en la base SQLite local.</p>
      <div className="mt-3 max-h-64 space-y-1 overflow-auto">
        {list.length === 0 && <div className="text-2xs text-faint">No hay proyectos guardados.</div>}
        {list.map((p) => (
          <div key={p.id} className={`flex items-center justify-between rounded px-2 py-1.5 text-[12px] hover:bg-white/[0.03] ${p.id === project.id ? "bg-acc/10" : ""}`}>
            <button className="min-w-0 flex-1 truncate text-left text-ink" onClick={async () => {
              const full = await get(`/projects/${p.id}`);
              loadProject(full);
              setName(full.name);
              toast("ok", `Proyecto abierto: ${full.name}`);
              onClose();
            }}>{p.name}<span className="ml-2 font-mono text-2xs text-faint">{new Date(p.updated * 1000).toLocaleString("es-ES")}</span></button>
            <button title="Eliminar" className="ml-2 text-faint hover:text-err" onClick={async () => { if (confirm(`¿Eliminar el proyecto «${p.name}»?`)) { await del(`/projects/${p.id}`); refresh(); } }}><X className="h-3.5 w-3.5" /></button>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

export default function App() {
  const { module, setModule, education, setEducation, toasts, dropToast, report, project } = useStore();
  const [projOpen, setProjOpen] = useState(false);
  const current = MODULES.find((m) => m.key === module) ?? MODULES[0];
  const Comp = current.Comp;
  return (
    <div className="flex h-full">
      <aside className="flex w-[218px] shrink-0 flex-col border-r border-line bg-[#060a0c]">
        <div className="border-b border-line px-4 py-3.5">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 32 32" className="h-7 w-7">
              <circle cx="16" cy="16" r="13" fill="none" stroke="#2fe39a" strokeWidth="1.6" />
              <circle cx="20.3" cy="16" r="8.7" fill="none" stroke="#2fe39a" strokeWidth="1" opacity="0.6" />
              <circle cx="24.6" cy="16" r="4.3" fill="none" stroke="#2fe39a" strokeWidth="1" opacity="0.4" />
              <line x1="3" y1="16" x2="29" y2="16" stroke="#2fe39a" strokeWidth="1" opacity="0.5" />
            </svg>
            <div className="leading-tight">
              <div className="text-[12.5px] font-semibold tracking-wide text-ink">RF ENGINEERING</div>
              <div className="font-mono text-[10px] tracking-[0.25em] text-acc">WORKBENCH</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 overflow-auto py-2">
          {MODULES.map((m, i) => {
            const Icon = m.icon;
            const on = m.key === module;
            return (
              <button key={m.key} onClick={() => setModule(m.key)} className={`group relative flex w-full items-center gap-2.5 px-4 py-[7px] text-left text-[12.5px] transition-colors ${on ? "text-acc" : "text-dim hover:text-ink"}`}>
                {on && <motion.span layoutId="nav-active" className="absolute inset-y-0.5 left-1.5 right-1.5 rounded bg-acc/[0.08] ring-1 ring-acc/20" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
                <span className="relative w-5 font-mono text-[10px] text-faint group-hover:text-dim">{String(i + 1).padStart(2, "0")}</span>
                <Icon className="relative h-4 w-4" />
                <span className="relative">{m.label}</span>
                {m.key === "reports" && report.length > 0 && <span className="relative ml-auto rounded bg-acc/15 px-1.5 font-mono text-[10px] text-acc">{report.length}</span>}
              </button>
            );
          })}
        </nav>
        <div className="border-t border-line px-4 py-3 text-2xs leading-relaxed text-faint">
          Motor: Python · NumPy · SciPy · scikit-rf
          <br />
          Convención e<sup>+jωt</sup> · Z0 real
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line bg-[#070b0d] px-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="truncate text-[12.5px] text-dim">
              <BookOpen className="mr-1.5 inline h-3.5 w-3.5 text-faint" />
              {project.name}
            </span>
            <VnaBadge />
          </div>
          <div className="relative flex items-center gap-3">
            <Toggle checked={education} onChange={setEducation} label={<span className="flex items-center gap-1"><GraduationCap className="h-3.5 w-3.5" />Modo educativo</span>} />
            <Btn small icon={<FolderOpen className="h-3.5 w-3.5" />} onClick={() => setProjOpen((v) => !v)}>Proyecto</Btn>
            <AnimatePresence>{projOpen && <ProjectMenu onClose={() => setProjOpen(false)} />}</AnimatePresence>
          </div>
        </header>
        <main className="bg-grid min-h-0 flex-1 overflow-auto">
          {/* Sin animación de salida: el cambio de módulo nunca espera a que termine una animación. */}
          <motion.div key={module} initial={{ opacity: 0.4, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.14 }} className="mx-auto max-w-[1680px] p-5">
            <Comp />
          </motion.div>
        </main>
      </div>
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[380px] flex-col gap-2">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div key={t.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} onClick={() => dropToast(t.id)}
              className={`pointer-events-auto cursor-pointer rounded border px-3 py-2 text-[12.5px] shadow-xl backdrop-blur ${t.kind === "err" ? "border-err/50 bg-[#2a0f12]/95 text-[#ffc2c2]" : t.kind === "ok" ? "border-acc/40 bg-[#07211a]/95 text-[#b6f5d8]" : "border-line2 bg-panel/95 text-ink"}`}>
              {t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
