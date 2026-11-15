// Formato de presentación (no realiza cálculos de ingeniería).
import type { Arr, Cx, CxArr, Num } from "./api";

export const num = (v: Num | undefined): number => (v === "inf" ? Infinity : v === "-inf" ? -Infinity : v == null ? NaN : v);

export function fmt(v: Num | undefined, digits = 4): string {
  const x = num(v);
  if (x === Infinity) return "∞";
  if (x === -Infinity) return "−∞";
  if (!Number.isFinite(x)) return "—";
  if (x === 0) return "0";
  const a = Math.abs(x);
  if (a >= 1e6 || a < 1e-4) return x.toExponential(Math.max(0, digits - 1)).replace("-", "−");
  return Number(x.toPrecision(digits)).toString().replace("-", "−");
}

const PREFIX: [number, string][] = [
  [1e12, "T"], [1e9, "G"], [1e6, "M"], [1e3, "k"], [1, ""], [1e-3, "m"], [1e-6, "µ"], [1e-9, "n"], [1e-12, "p"], [1e-15, "f"],
];

export function si(v: Num | undefined, unit = "", digits = 4): string {
  const x = num(v);
  if (x === Infinity) return `∞ ${unit}`.trim();
  if (!Number.isFinite(x)) return "—";
  if (x === 0) return `0 ${unit}`.trim();
  const a = Math.abs(x);
  for (const [m, p] of PREFIX) {
    if (a >= m * 0.9999999) return `${Number((x / m).toPrecision(digits))} ${p}${unit}`.replace("-", "−").trim();
  }
  return `${x.toExponential(digits - 1)} ${unit}`;
}

export const hz = (v: Num | undefined, d = 6) => si(v, "Hz", d);

export function cx(c: Cx | undefined | null, unit = "Ω", digits = 5): string {
  if (!c) return "—";
  if (c.inf) return "∞ (abierto)";
  const re = c.re ?? NaN;
  const im = c.im ?? NaN;
  const sign = im < 0 ? "−" : "+";
  return `${fmt(re, digits)} ${sign} j${fmt(Math.abs(im), digits)} ${unit}`.trim();
}

export function polar(c: Cx | undefined | null, digits = 4): string {
  if (!c || c.re == null || c.im == null) return "—";
  const m = Math.hypot(c.re, c.im);
  const a = (Math.atan2(c.im, c.re) * 180) / Math.PI;
  return `${fmt(m, digits)} ∠ ${fmt(a, digits)}°`;
}

export const pairs = (a: CxArr): [number, number][] =>
  a.re.map((r, i) => [r ?? NaN, a.im[i] ?? NaN] as [number, number]).filter(([r, i]) => Number.isFinite(r) && Number.isFinite(i));

export const arr = (a: Arr | undefined): number[] => (a ?? []).map((v) => (v == null ? NaN : v));

export function freqScale(fmax: number): [number, string] {
  if (fmax >= 1e9) return [1e9, "GHz"];
  if (fmax >= 1e6) return [1e6, "MHz"];
  if (fmax >= 1e3) return [1e3, "kHz"];
  return [1, "Hz"];
}

export const toPct = (v: Num, d = 2) => `${fmt(num(v) * 100, d + 2)} %`;
