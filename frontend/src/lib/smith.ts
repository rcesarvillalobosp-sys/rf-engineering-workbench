// Geometría de la carta de Smith — ÚNICO lugar del frontend con la transformación Γ ↔ z.
// Se usa exclusivamente para DIBUJAR la carta y para la lectura instantánea del cursor;
// todos los resultados que se muestran en paneles provienen del motor (backend).
//   z = (1 + Γ) / (1 − Γ)      Γ = (z − 1) / (z + 1)      (z normalizada a Z0)

export type P = [number, number];

export function gammaToZn([gr, gi]: P): P {
  const dr = 1 - gr;
  const den = dr * dr + gi * gi;
  if (den < 1e-18) return [Infinity, 0];
  return [(1 - gr * gr - gi * gi) / den, (2 * gi) / den];
}

export function znToGamma([r, x]: P): P {
  if (!Number.isFinite(r)) return [1, 0];
  const den = (r + 1) * (r + 1) + x * x;
  return [(r * r + x * x - 1) / den, (2 * x) / den];
}

/** Círculo de resistencia normalizada r constante. */
export const rCircle = (r: number) => ({ cx: r / (1 + r), cy: 0, rad: 1 / (1 + r) });
/** Círculo de reactancia normalizada x constante (centro (1, 1/x)). */
export const xCircle = (x: number) => ({ cx: 1, cy: 1 / x, rad: 1 / Math.abs(x) });

/** Escala "longitudes de onda hacia el generador" para un ángulo de Γ en grados. */
export const wtg = (angDeg: number) => (((180 - angDeg) / 720) % 0.5 + 0.5) % 0.5;

/** Sólo para la lectura del cursor (presentación). */
export const vswrOf = (mag: number) => (mag >= 1 ? Infinity : (1 + mag) / (1 - mag));
