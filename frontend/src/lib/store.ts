import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Origin, Step } from "./api";

export type ModuleKey =
  | "dashboard" | "smith" | "circuit" | "impedance" | "matching" | "tline" | "sparams" | "antenna" | "library" | "touchstone" | "vna" | "reports";

export interface ReportItem {
  id: string;
  title: string;
  module: string;
  origin: Origin;
  created: string;
  source_detail?: string;
  inputs?: [string, string][];
  results?: [string, string][];
  steps?: Step[];
  smith?: { z0: number; points: { re: number; im: number; label?: string }[]; traces: { name?: string; re: number[]; im: number[] }[] };
  plots?: { title: string; xlabel?: string; ylabel?: string; x: number[]; series: { name: string; y: (number | null)[] }[]; x_is_freq?: boolean }[];
  tables?: { title: string; header: string[]; rows: string[][] }[];
  notes?: string[];
}

interface Toast { id: number; kind: "ok" | "err" | "info"; text: string }

interface State {
  module: ModuleKey;
  education: boolean;
  forms: Record<string, any>;
  report: ReportItem[];
  project: { id?: number; name: string };
  toasts: Toast[];
  theme: { mode: "dark" | "light" | "system"; accent: "emerald" | "cyan" | "blue" | "violet" | "amber" };
  setTheme: (p: Partial<State["theme"]>) => void;
  setModule: (m: ModuleKey) => void;
  setEducation: (v: boolean) => void;
  setForm: (key: string, patch: any) => void;
  addReport: (it: Omit<ReportItem, "id" | "created">) => void;
  removeReport: (id: string) => void;
  moveReport: (id: string, dir: -1 | 1) => void;
  clearReport: () => void;
  loadProject: (p: { id?: number; name: string; data: any }) => void;
  setProject: (p: { id?: number; name: string }) => void;
  toast: (kind: Toast["kind"], text: string) => void;
  dropToast: (id: number) => void;
}

let tid = 0;

export const useStore = create<State>()(
  persist(
    (set) => ({
      module: "dashboard",
      education: true,
      forms: {},
      report: [],
      project: { name: "Proyecto sin título" },
      toasts: [],
      theme: { mode: "dark", accent: "emerald" },
      setTheme: (p) => set((s) => ({ theme: { ...s.theme, ...p } })),
      setModule: (module) => set({ module }),
      setEducation: (education) => set({ education }),
      setForm: (key, patch) => set((s) => ({ forms: { ...s.forms, [key]: { ...(s.forms[key] ?? {}), ...patch } } })),
      addReport: (it) =>
        set((s) => ({
          report: [...s.report, { ...it, id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, created: new Date().toLocaleString("es-ES") }],
        })),
      removeReport: (id) => set((s) => ({ report: s.report.filter((r) => r.id !== id) })),
      moveReport: (id, dir) =>
        set((s) => {
          const i = s.report.findIndex((r) => r.id === id);
          const j = i + dir;
          if (i < 0 || j < 0 || j >= s.report.length) return s;
          const r = [...s.report];
          [r[i], r[j]] = [r[j], r[i]];
          return { report: r };
        }),
      clearReport: () => set({ report: [] }),
      loadProject: (p) => set({ project: { id: p.id, name: p.name }, forms: p.data?.forms ?? {}, report: p.data?.report ?? [] }),
      setProject: (project) => set({ project }),
      toast: (kind, text) => {
        const id = ++tid;
        set((s) => ({ toasts: [...s.toasts, { id, kind, text }] }));
        setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), kind === "err" ? 7000 : 3500);
      },
      dropToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
    }),
    { name: "rfwb-state", partialize: (s) => ({ forms: s.forms, report: s.report, project: s.project, education: s.education, module: s.module, theme: s.theme }) },
  ),
);

/** Estado de formulario de un módulo, persistido en el proyecto. */
export function useForm<T extends object>(key: string, defaults: T): [T, (patch: Partial<T>) => void] {
  const saved = useStore((s) => s.forms[key]);
  const setForm = useStore((s) => s.setForm);
  const value = { ...defaults, ...(saved ?? {}) } as T;
  return [value, (patch) => setForm(key, patch)];
}
