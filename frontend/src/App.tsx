import { AnimatePresence, motion } from "motion/react";
import {
  Activity, Antenna, BookOpen, CircleDot, Cpu, FileInput, FileText, FolderOpen, GitBranch, GraduationCap, LayoutDashboard,
  Library, Monitor, Moon, Network, Palette as PaletteIcon, Radio, Save, Sun, Waves, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Btn, Input } from "./components/ui";
import { get, post, put, del } from "./lib/api";
import { type ModuleKey, useStore } from "./lib/store";
import { ACCENTS, useApplyTheme } from "./lib/theme";
import { CircuitModule } from "./modules/Circuit";
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
  { key: "circuit", label: "Circuit Builder", icon: Network, Comp: CircuitModule },
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
    <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-2xs ${st.connected ? "border-orange/50 bg-orange/10 text-orange" : "border-line2 text-dim"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${st.connected ? "animate-pulse bg-orange" : "bg-faint"}`} />
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

function ThemeMenu({ onClose }: { onClose: () => void }) {
  const theme = useStore((s) => s.theme);
  const setTheme = useStore((s) => s.setTheme);
  const T = useApplyTheme();
  return (
    <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="absolute right-0 top-9 z-50 w-[300px] rounded-md border border-line2 bg-panel p-3 shadow-2xl">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[12px] font-semibold uppercase tracking-wider text-dim">Apariencia</span>
        <button onClick={onClose} className="text-dim hover:text-ink"><X className="h-4 w-4" /></button>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {([["dark", "Oscuro", Moon], ["light", "Claro", Sun], ["system", "Sistema", Monitor]] as const).map(([k, l, I]) => (
          <button key={k} onClick={() => setTheme({ mode: k })} className={`flex flex-col items-center gap-1 rounded border px-2 py-2 text-[12px] ${theme.mode === k ? "border-acc bg-acc/10 text-acc" : "border-line2 text-dim hover:text-ink"}`}>
            <I className="h-4 w-4" />{l}
          </button>
        ))}
      </div>
      <div className="mt-3 text-2xs uppercase tracking-wider text-dim">Color de acento</div>
      <div className="mt-1.5 flex gap-2">
        {ACCENTS.map((a) => (
          <button key={a.key} title={a.label} onClick={() => setTheme({ accent: a.key })}
            className={`h-7 w-7 rounded-full border-2 ${theme.accent === a.key ? "border-ink" : "border-transparent"}`}
            style={{ background: T.mode === "dark" ? a.dark : a.light }} />
        ))}
      </div>
    </motion.div>
  );
}

export default function App() {
  const { module, setModule, education, setEducation, toasts, dropToast, report, project, theme } = useStore();
  useApplyTheme();
  const [projOpen, setProjOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const current = MODULES.find((m) => m.key === module) ?? MODULES[0];
  const Comp = current.Comp;
  return (
    <div className="flex h-full flex-col">
      <header className="shrink-0 border-b border-line bg-panel">
        <div className="flex h-12 items-center justify-between gap-3 px-4">
          <div className="flex min-w-0 items-center gap-4">
            <button onClick={() => setModule("dashboard")} className="flex shrink-0 items-center gap-2">
              <svg viewBox="0 0 32 32" className="h-7 w-7 text-acc">
                <circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" strokeWidth="1.6" />
                <circle cx="20.3" cy="16" r="8.7" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6" />
                <circle cx="24.6" cy="16" r="4.3" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.4" />
                <line x1="3" y1="16" x2="29" y2="16" stroke="currentColor" strokeWidth="1" opacity="0.5" />
              </svg>
              <div className="text-left leading-tight">
                <div className="text-[12.5px] font-semibold tracking-wide text-ink">RF ENGINEERING</div>
                <div className="font-mono text-[10px] tracking-[0.25em] text-acc">WORKBENCH</div>
              </div>
            </button>
            <span className="hidden min-w-0 truncate text-[12.5px] text-dim lg:inline">
              <BookOpen className="mr-1.5 inline h-3.5 w-3.5 text-faint" />
              {project.name}
            </span>
            <VnaBadge />
          </div>
          <div className="relative flex shrink-0 items-center gap-2.5">
            <button onClick={() => setEducation(!education)} title="Muestra u oculta fórmulas, desarrollos paso a paso y explicaciones"
              className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-[12px] transition-colors ${education ? "border-acc/60 bg-acc/10 text-acc" : "border-line2 text-dim hover:text-ink"}`}>
              <GraduationCap className="h-3.5 w-3.5" />Modo educativo: {education ? "activado" : "desactivado"}
            </button>
            <Btn small icon={theme.mode === "light" ? <Sun className="h-3.5 w-3.5" /> : <PaletteIcon className="h-3.5 w-3.5" />} onClick={() => { setThemeOpen((v) => !v); setProjOpen(false); }}>Tema</Btn>
            <Btn small icon={<FolderOpen className="h-3.5 w-3.5" />} onClick={() => { setProjOpen((v) => !v); setThemeOpen(false); }}>Proyecto</Btn>
            <AnimatePresence>{projOpen && <ProjectMenu onClose={() => setProjOpen(false)} />}</AnimatePresence>
            <AnimatePresence>{themeOpen && <ThemeMenu onClose={() => setThemeOpen(false)} />}</AnimatePresence>
          </div>
        </div>
        <nav className="no-scrollbar flex gap-0.5 overflow-x-auto px-3">
          {MODULES.map((m) => {
            const Icon = m.icon;
            const on = m.key === module;
            return (
              <button key={m.key} onClick={() => setModule(m.key)}
                className={`relative flex shrink-0 items-center gap-1.5 whitespace-nowrap px-3 pb-2 pt-1.5 text-[12.5px] transition-colors ${on ? "text-acc" : "text-dim hover:text-ink"}`}>
                <Icon className="h-4 w-4" />
                <span>{m.label}</span>
                {m.key === "reports" && report.length > 0 && <span className="rounded bg-acc/15 px-1.5 font-mono text-[10px] text-acc">{report.length}</span>}
                {on && <motion.span layoutId="nav-active" className="absolute inset-x-2 bottom-0 h-[2px] rounded-full bg-acc" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
              </button>
            );
          })}
        </nav>
      </header>
      <main className="bg-grid min-h-0 flex-1 overflow-auto">
        {/* Sin animación de salida: el cambio de módulo nunca espera a que termine una animación. */}
        <motion.div key={module} initial={{ opacity: 0.4, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.14 }} className="mx-auto max-w-[1720px] p-5">
          <Comp />
        </motion.div>
      </main>
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[380px] flex-col gap-2">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div key={t.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} onClick={() => dropToast(t.id)}
              className={`pointer-events-auto cursor-pointer rounded border bg-panel px-3 py-2 text-[12.5px] shadow-xl ${t.kind === "err" ? "border-err/50 text-err" : t.kind === "ok" ? "border-acc/50 text-acc" : "border-line2 text-ink"}`}>
              {t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
