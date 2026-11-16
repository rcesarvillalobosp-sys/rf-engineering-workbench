// Temas de la interfaz: ÚNICA fuente de colores. Se aplican como variables CSS (clases Tailwind)
// y se leen desde JS (carta de Smith, Plotly, esquemas) con useTheme().
import { useEffect, useMemo, useState } from "react";
import { useStore } from "./store";

export type ThemeMode = "dark" | "light" | "system";
export type Accent = "emerald" | "cyan" | "blue" | "violet" | "amber";

export const ACCENTS: { key: Accent; label: string; dark: string; light: string }[] = [
  { key: "emerald", label: "Esmeralda", dark: "#34d399", light: "#059669" },
  { key: "cyan", label: "Cian", dark: "#22d3ee", light: "#0891b2" },
  { key: "blue", label: "Azul", dark: "#60a5fa", light: "#2563eb" },
  { key: "violet", label: "Violeta", dark: "#a78bfa", light: "#7c3aed" },
  { key: "amber", label: "Ámbar", dark: "#fbbf24", light: "#d97706" },
];

export interface Palette {
  mode: "dark" | "light";
  bg: string; panel: string; panel2: string; line: string; line2: string;
  ink: string; dim: string; faint: string;
  acc: string; acc2: string; onacc: string; accSoft: string;
  warn: string; err: string; info: string; violet: string; cyan: string; orange: string;
  plotBg: string; grid: string; zero: string;
  smithBg0: string; smithBg1: string; smithGrid: string; smithGridUnit: string; smithAdm: string;
  smithRim: string; smithRing: string; smithLabel: string;
  series: string[];
}

const hexToRgb = (h: string) => {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const mix = (a: string, b: string, t: number) => {
  const A = hexToRgb(a), B = hexToRgb(b);
  return "#" + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, "0")).join("");
};
const rgba = (h: string, a: number) => `rgba(${hexToRgb(h).join(",")},${a})`;

export function buildPalette(mode: "dark" | "light", accent: Accent): Palette {
  const ac = ACCENTS.find((a) => a.key === accent) ?? ACCENTS[0];
  if (mode === "dark") {
    const acc = ac.dark;
    const base = {
      bg: "#0a0e13", panel: "#10161d", panel2: "#151d26", line: "#1f2a35", line2: "#2b3946",
      ink: "#e2e8f0", dim: "#8b9aab", faint: "#5a6878",
      warn: "#fbbf24", err: "#f87171", info: "#60a5fa", violet: "#a78bfa", cyan: "#22d3ee", orange: "#fb923c",
    };
    return {
      mode, ...base, acc, acc2: mix(acc, "#ffffff", 0.25), onacc: "#06120d", accSoft: rgba(acc, 0.08),
      plotBg: "#0c1218", grid: "#1c2733", zero: "#2b3946",
      smithBg0: "#111a23", smithBg1: "#0b1118", smithGrid: "#253444", smithGridUnit: mix("#253444", acc, 0.45),
      smithAdm: "#2d4a6b", smithRim: "#465b70", smithRing: "#33424f", smithLabel: "#6a7b8d",
      series: dedupe([acc, "#60a5fa", "#fbbf24", "#f87171", "#a78bfa", "#22d3ee", "#e879f9", "#fb923c", "#34d399"]),
    };
  }
  const acc = ac.light;
  const base = {
    bg: "#f3f5f8", panel: "#ffffff", panel2: "#f3f6f9", line: "#dde3ea", line2: "#c7d0da",
    ink: "#0f172a", dim: "#475569", faint: "#8a97a8",
    warn: "#b45309", err: "#dc2626", info: "#2563eb", violet: "#7c3aed", cyan: "#0891b2", orange: "#ea580c",
  };
  return {
    mode, ...base, acc, acc2: mix(acc, "#000000", 0.15), onacc: "#ffffff", accSoft: rgba(acc, 0.08),
    plotBg: "#ffffff", grid: "#e5eaf0", zero: "#c7d0da",
    smithBg0: "#ffffff", smithBg1: "#f6f8fb", smithGrid: "#cdd6e0", smithGridUnit: mix("#cdd6e0", acc, 0.5),
    smithAdm: "#9cc3f5", smithRim: "#64748b", smithRing: "#a3b0bf", smithLabel: "#64748b",
    series: dedupe([acc, "#2563eb", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#c026d3", "#ea580c", "#059669"]),
  };
}

function dedupe(a: string[]) {
  return a.filter((c, i) => a.indexOf(c) === i);
}

const VARS: (keyof Palette)[] = ["bg", "panel", "panel2", "line", "line2", "ink", "dim", "faint", "acc", "acc2", "onacc",
  "warn", "err", "info", "violet", "cyan", "orange"];

function useSystemDark() {
  const q = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const [dark, setDark] = useState(q ? q.matches : true);
  useEffect(() => {
    if (!q) return;
    const f = (e: MediaQueryListEvent) => setDark(e.matches);
    q.addEventListener("change", f);
    return () => q.removeEventListener("change", f);
  }, []);
  return dark;
}

/** Paleta activa (resuelve «sistema»). */
export function useTheme(): Palette {
  const mode = useStore((s) => s.theme.mode);
  const accent = useStore((s) => s.theme.accent);
  const sysDark = useSystemDark();
  const resolved = mode === "system" ? (sysDark ? "dark" : "light") : mode;
  return useMemo(() => buildPalette(resolved, accent), [resolved, accent]);
}

/** Aplica la paleta como variables CSS «r g b» en <html>. */
export function useApplyTheme() {
  const T = useTheme();
  useEffect(() => {
    const root = document.documentElement;
    for (const k of VARS) root.style.setProperty(`--${k}`, hexToRgb(T[k] as string).join(" "));
    root.style.colorScheme = T.mode;
    root.dataset.theme = T.mode;
  }, [T]);
  return T;
}
