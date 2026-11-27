// Temas de la interfaz: ÚNICA fuente de colores. Se aplican como variables CSS (clases Tailwind)
// y se leen desde JS (carta de Smith, Plotly, esquemas) con useTheme().
import { useEffect, useMemo, useState } from "react";
import { useStore } from "./store";

export type ThemeMode = "dark" | "light" | "system";
export type Accent = "magenta" | "yellow" | "cyan" | "green" | "white";

/** Colores de traza de un analizador: el acento es la traza activa. */
export const ACCENTS: { key: Accent; label: string; dark: string; light: string }[] = [
  { key: "magenta", label: "Traza magenta", dark: "#ff4fa8", light: "#c2185b" },
  { key: "yellow", label: "Traza amarilla", dark: "#f2d600", light: "#8a6f00" },
  { key: "cyan", label: "Traza cian", dark: "#3fd5e0", light: "#00838f" },
  { key: "green", label: "Traza verde", dark: "#8be04e", light: "#3c8c1c" },
  { key: "white", label: "Traza blanca", dark: "#e6e6e6", light: "#2b2b2b" },
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
    // Pantalla de instrumento: negro neutro, sin tinte azul
    const base = {
      bg: "#0b0b0c", panel: "#141516", panel2: "#1b1c1e", line: "#27292c", line2: "#36393d",
      ink: "#e7e8e9", dim: "#9b9fa4", faint: "#64686d",
      warn: "#f2c230", err: "#ff5c5c", info: "#7aa7ff", violet: "#b69cff", cyan: "#3fd5e0", orange: "#ff9a3c",
    };
    return {
      mode, ...base, acc, acc2: mix(acc, "#ffffff", 0.25), onacc: "#0b0b0c", accSoft: rgba(acc, 0.1),
      plotBg: "#08090a", grid: "#1e2022", zero: "#36393d",
      smithBg0: "#121314", smithBg1: "#08090a", smithGrid: "#2b2d30", smithGridUnit: mix("#2b2d30", acc, 0.45),
      smithAdm: "#3f4a3a", smithRim: "#5b5f64", smithRing: "#3a3d41", smithLabel: "#7a7e83",
      series: dedupe([acc, "#f2d600", "#3fd5e0", "#8be04e", "#ff9a3c", "#b69cff", "#ff5c5c", "#e6e6e6"]),
    };
  }
  const acc = ac.light;
  const base = {
    bg: "#e2e3e4", panel: "#f7f7f7", panel2: "#eeeff0", line: "#d2d4d6", line2: "#b9bcbf",
    ink: "#141516", dim: "#4d5155", faint: "#83878b",
    warn: "#9a6a00", err: "#c62828", info: "#1f5fbf", violet: "#6a3fc0", cyan: "#00838f", orange: "#c25400",
  };
  return {
    mode, ...base, acc, acc2: mix(acc, "#000000", 0.15), onacc: "#ffffff", accSoft: rgba(acc, 0.08),
    plotBg: "#ffffff", grid: "#e3e5e7", zero: "#b9bcbf",
    smithBg0: "#ffffff", smithBg1: "#f4f4f5", smithGrid: "#d3d5d8", smithGridUnit: mix("#d3d5d8", acc, 0.5),
    smithAdm: "#a9c79a", smithRim: "#5f6368", smithRing: "#a6a9ad", smithLabel: "#5f6368",
    series: dedupe([acc, "#8a6f00", "#00838f", "#3c8c1c", "#c25400", "#6a3fc0", "#c62828", "#2b2b2b"]),
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
