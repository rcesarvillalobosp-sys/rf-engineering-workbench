import { Download, Maximize2, ZoomIn, ZoomOut } from "lucide-react";
import React, { useCallback, useMemo, useRef, useState } from "react";
import { fmt } from "../lib/format";
import { type P, gammaToZn, rCircle, vswrOf, wtg, xCircle, znToGamma } from "../lib/smith";
import { useTheme } from "../lib/theme";

export interface SmithPoint { g: P; label?: string; color?: string; size?: number; hollow?: boolean }
export interface SmithTrace { pts: P[]; name?: string; color?: string; dash?: boolean; width?: number; arrow?: boolean }
export interface SmithCircle { c: P; r: number; color?: string; label?: string; dash?: boolean; fill?: string }

interface Props {
  z0: number;
  points?: SmithPoint[];
  traces?: SmithTrace[];
  circles?: SmithCircle[];
  vswrCircles?: number[]; // radios |Γ|
  admittance?: boolean;
  impedance?: boolean;
  fine?: boolean;
  dragIndex?: number;
  onPick?: (g: P) => void;
  onDrag?: (g: P) => void;
  height?: number | string;
  className?: string;
  /** Nombre base del archivo exportado. */
  exportName?: string;
}

const R_MAIN = [0.2, 0.5, 1, 2, 5];
const R_FINE = [0.1, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9, 1.5, 3, 4, 10, 20];
const X_MAIN = [0.2, 0.5, 1, 2, 5];
const X_FINE = [0.1, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9, 1.5, 3, 4, 10, 20];
const FULL = { x: -1.24, y: -1.24, w: 2.48 };

export function SmithChart(props: Props) {
  const { z0, points = [], traces = [], circles = [], vswrCircles = [], admittance = false, impedance = true, fine = false, dragIndex, onPick, onDrag, height = "100%", className = "", exportName = "carta_smith" } = props;
  const [expOpen, setExpOpen] = useState(false);
  const T = useTheme();
  const svg = useRef<SVGSVGElement>(null);
  const [vb, setVb] = useState(FULL);
  const [cursor, setCursor] = useState<P | null>(null);
  const drag = useRef<{ mode: "pan" | "point" | "none"; sx: number; sy: number; vb: typeof FULL; moved: boolean } | null>(null);
  const k = vb.w / FULL.w; // factor de escala para texto/marcadores

  const toGamma = useCallback((cx: number, cy: number): P => {
    const s = svg.current!;
    const pt = s.createSVGPoint();
    pt.x = cx;
    pt.y = cy;
    const m = s.getScreenCTM();
    if (!m) return [0, 0];
    const p = pt.matrixTransform(m.inverse());
    return [p.x, -p.y];
  }, []);

  const onWheel = (e: React.WheelEvent) => {
    const g = toGamma(e.clientX, e.clientY);
    const f = e.deltaY > 0 ? 1.15 : 1 / 1.15;
    setVb((v) => {
      const w = Math.min(FULL.w, Math.max(0.04, v.w * f));
      const r = w / v.w;
      const px = g[0], py = -g[1];
      const nv = { x: px - (px - v.x) * r, y: py - (py - v.y) * r, w };
      return w >= FULL.w ? FULL : nv;
    });
  };

  const onDown = (e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const g = toGamma(e.clientX, e.clientY);
    let mode: "pan" | "point" = "pan";
    if (dragIndex != null && points[dragIndex]) {
      const p = points[dragIndex].g;
      if (Math.hypot(p[0] - g[0], p[1] - g[1]) < 0.05 * k) mode = "point";
    }
    drag.current = { mode, sx: e.clientX, sy: e.clientY, vb, moved: false };
  };

  const onMove = (e: React.PointerEvent) => {
    const g = toGamma(e.clientX, e.clientY);
    setCursor(g);
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.sx, dy = e.clientY - d.sy;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    if (!d.moved) return;
    if (d.mode === "point") {
      const m = Math.hypot(g[0], g[1]);
      const gg: P = m > 0.9999 ? [(g[0] / m) * 0.9999, (g[1] / m) * 0.9999] : g;
      onDrag?.(gg);
    } else if (d.vb.w < FULL.w) {
      const s = svg.current!.getBoundingClientRect();
      const scale = d.vb.w / Math.min(s.width, s.height);
      setVb({ ...d.vb, x: d.vb.x - dx * scale, y: d.vb.y - dy * scale });
    }
  };

  const onUp = (e: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    const g = toGamma(e.clientX, e.clientY);
    if (!d.moved && onPick && Math.hypot(g[0], g[1]) <= 1.0001) onPick(g);
    if (d.moved && d.mode === "point" && onPick) {
      const m = Math.hypot(g[0], g[1]);
      onPick(m > 0.9999 ? [(g[0] / m) * 0.9999, (g[1] / m) * 0.9999] : g);
    }
  };

  const zoom = (f: number) => setVb((v) => {
    const w = Math.min(FULL.w, Math.max(0.04, v.w * f));
    if (w >= FULL.w) return FULL;
    const cx = v.x + v.w / 2, cy = v.y + v.w / 2;
    return { x: cx - w / 2, y: cy - w / 2, w };
  });

  const grid = useMemo(() => {
    const rs = fine ? [...R_MAIN, ...R_FINE] : R_MAIN;
    const xs = fine ? [...X_MAIN, ...X_FINE] : X_MAIN;
    return { rs, xs };
  }, [fine]);

  const cur = cursor && Math.hypot(cursor[0], cursor[1]) <= 1.0 ? cursor : null;
  const curZ = cur ? gammaToZn(cur) : null;

  const stroke = { vectorEffect: "non-scaling-stroke" as const };

  return (
    <div className={`relative h-full w-full select-none ${className}`} style={{ height }}>
      <svg
        ref={svg}
        viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.w}`}
        className="h-full w-full cursor-crosshair touch-none"
        onWheel={onWheel}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={() => setCursor(null)}
        onDoubleClick={() => setVb(FULL)}
      >
        <defs>
          <clipPath id="smith-clip"><circle cx={0} cy={0} r={1} /></clipPath>
          <radialGradient id="smith-bg" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={T.smithBg0} />
            <stop offset="100%" stopColor={T.smithBg1} />
          </radialGradient>
          <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="context-stroke" />
          </marker>
        </defs>
        <circle cx={0} cy={0} r={1} fill="url(#smith-bg)" />
        {/* Escala de longitudes de onda hacia el generador */}
        <g>
          {Array.from({ length: 50 }, (_, i) => {
            const d = i / 100;
            const th = ((180 - 720 * d) * Math.PI) / 180;
            const big = i % 5 === 0;
            const r1 = 1.0, r2 = big ? 1.035 : 1.02;
            return <line key={i} x1={r1 * Math.cos(th)} y1={-r1 * Math.sin(th)} x2={r2 * Math.cos(th)} y2={-r2 * Math.sin(th)} stroke={T.smithRing} strokeWidth={1} style={stroke} />;
          })}
          {Array.from({ length: 10 }, (_, i) => {
            const d = i * 0.05;
            const th = ((180 - 720 * d) * Math.PI) / 180;
            return (
              <text key={i} x={1.085 * Math.cos(th)} y={-1.085 * Math.sin(th) + 0.012 * k} fontSize={0.034 * Math.max(k, 0.35)} textAnchor="middle" fill={T.smithLabel} fontFamily="JetBrains Mono">
                {d.toFixed(2)}
              </text>
            );
          })}
          <text x={0} y={-1.165} fontSize={0.032} textAnchor="middle" fill={T.smithLabel} fontFamily="IBM Plex Sans">λ hacia el generador →</text>
        </g>
        <g clipPath="url(#smith-clip)">
          {admittance && (
            <g opacity={0.9}>
              {grid.rs.map((g) => { const c = rCircle(g); return <circle key={`g${g}`} cx={-c.cx} cy={0} r={c.rad} fill="none" stroke={T.smithAdm} strokeWidth={R_MAIN.includes(g) ? 0.9 : 0.5} strokeDasharray="4 3" style={stroke} />; })}
              {grid.xs.flatMap((b) => [b, -b]).map((b) => { const c = xCircle(b); return <circle key={`b${b}`} cx={-c.cx} cy={c.cy} r={c.rad} fill="none" stroke={T.smithAdm} strokeWidth={X_MAIN.includes(Math.abs(b)) ? 0.9 : 0.5} strokeDasharray="4 3" style={stroke} />; })}
            </g>
          )}
          {impedance && (
            <g>
              {grid.rs.map((r) => { const c = rCircle(r); return <circle key={`r${r}`} cx={c.cx} cy={0} r={c.rad} fill="none" stroke={r === 1 ? T.smithGridUnit : T.smithGrid} strokeWidth={R_MAIN.includes(r) ? 1 : 0.55} style={stroke} />; })}
              {grid.xs.flatMap((x) => [x, -x]).map((x) => { const c = xCircle(x); return <circle key={`x${x}`} cx={c.cx} cy={-c.cy} r={c.rad} fill="none" stroke={Math.abs(x) === 1 ? T.smithGridUnit : T.smithGrid} strokeWidth={X_MAIN.includes(Math.abs(x)) ? 1 : 0.55} style={stroke} />; })}
            </g>
          )}
          <line x1={-1} y1={0} x2={1} y2={0} stroke={T.smithRing} strokeWidth={1} style={stroke} />
          {/* Círculos r/x por el cursor */}
          {cur && curZ && Number.isFinite(curZ[0]) && (
            <g opacity={0.65}>
              {(() => { const c = rCircle(Math.max(curZ[0], 0)); return <circle cx={c.cx} cy={0} r={c.rad} fill="none" stroke={T.acc} strokeWidth={0.7} strokeDasharray="2 3" style={stroke} />; })()}
              {Math.abs(curZ[1]) > 1e-6 && (() => { const c = xCircle(curZ[1]); return <circle cx={c.cx} cy={-c.cy} r={c.rad} fill="none" stroke={T.info} strokeWidth={0.7} strokeDasharray="2 3" style={stroke} />; })()}
              <circle cx={0} cy={0} r={Math.hypot(cur[0], cur[1])} fill="none" stroke={T.warn} strokeWidth={0.6} strokeDasharray="1 3" style={stroke} />
            </g>
          )}
          {vswrCircles.map((m, i) => <circle key={`v${i}`} cx={0} cy={0} r={m} fill="none" stroke={T.warn} strokeWidth={0.9} strokeDasharray="5 4" opacity={0.7} style={stroke} />)}
        </g>
        <circle cx={0} cy={0} r={1} fill="none" stroke={T.smithRim} strokeWidth={1.4} style={stroke} />
        {/* Etiquetas de rejilla */}
        {impedance && (
          <g fontFamily="JetBrains Mono" fill={T.smithLabel} fontSize={0.032 * k}>
            {[0, ...grid.rs.filter((r) => R_MAIN.includes(r))].map((r) => {
              const x = (r - 1) / (r + 1);
              return <text key={`lr${r}`} x={x + 0.008 * k} y={-0.012 * k} transform={`rotate(-90 ${x + 0.008 * k} ${-0.012 * k})`}>{r}</text>;
            })}
            {X_MAIN.flatMap((x) => [x, -x]).map((x) => {
              const g = znToGamma([0, x]);
              return <text key={`lx${x}`} x={g[0] * 0.955} y={-g[1] * 0.955 + 0.01 * k} textAnchor="middle">{x > 0 ? `+j${x}` : `−j${-x}`}</text>;
            })}
          </g>
        )}
        {/* Círculos de usuario (estabilidad, ganancia…) */}
        {circles.map((c, i) => (
          <g key={`c${i}`}>
            <circle cx={c.c[0]} cy={-c.c[1]} r={c.r} fill={c.fill ?? "none"} stroke={c.color ?? T.err} strokeWidth={1.3} strokeDasharray={c.dash ? "5 4" : undefined} style={stroke} />
            {c.label && <text x={c.c[0] + c.r * 0.72} y={-c.c[1] - c.r * 0.72} fontSize={0.034 * k} fill={c.color ?? T.err} fontFamily="JetBrains Mono">{c.label}</text>}
          </g>
        ))}
        {traces.map((t, i) => (
          <polyline
            key={`t${i}`}
            points={t.pts.map(([x, y]) => `${x},${-y}`).join(" ")}
            fill="none"
            stroke={t.color ?? T.acc}
            strokeWidth={t.width ?? 1.8}
            strokeDasharray={t.dash ? "5 4" : undefined}
            strokeLinejoin="round"
            markerEnd={t.arrow ? "url(#arr)" : undefined}
            style={stroke}
          />
        ))}
        {points.map((p, i) => (
          <g key={`p${i}`} style={{ cursor: i === dragIndex ? "grab" : undefined }}>
            <circle cx={p.g[0]} cy={-p.g[1]} r={(p.size ?? 0.022) * k} fill={p.hollow ? T.smithBg1 : p.color ?? T.acc} stroke={p.color ?? T.acc} strokeWidth={1.6} style={stroke} />
            {i === dragIndex && <circle cx={p.g[0]} cy={-p.g[1]} r={0.045 * k} fill="none" stroke={p.color ?? T.acc} strokeOpacity={0.35} strokeWidth={1} style={stroke} />}
            {p.label && (
              <text x={p.g[0] + 0.035 * k} y={-p.g[1] - 0.03 * k} fontSize={0.04 * k} fill={p.color ?? T.acc} fontFamily="JetBrains Mono" fontWeight={600} paintOrder="stroke" stroke={T.smithBg1} strokeWidth={0.012 * k}>
                {p.label}
              </text>
            )}
          </g>
        ))}
      </svg>
      {/* Lectura del cursor */}
      <div className="pointer-events-none absolute left-2 top-2 min-w-[178px] rounded border border-line bg-bg/85 px-2.5 py-1.5 font-mono text-[11px] leading-[1.55] text-dim backdrop-blur">
        {cur && curZ ? (
          <>
            <div><span className="text-faint">Γ </span><span className="text-ink">{fmt(Math.hypot(cur[0], cur[1]), 4)} ∠ {fmt((Math.atan2(cur[1], cur[0]) * 180) / Math.PI, 4)}°</span></div>
            <div><span className="text-faint">z </span><span className="text-acc">{fmt(curZ[0], 4)} {curZ[1] < 0 ? "−" : "+"} j{fmt(Math.abs(curZ[1]), 4)}</span></div>
            <div><span className="text-faint">Z </span><span className="text-ink">{fmt(curZ[0] * z0, 4)} {curZ[1] < 0 ? "−" : "+"} j{fmt(Math.abs(curZ[1] * z0), 4)} Ω</span></div>
            <div><span className="text-faint">VSWR </span><span className="text-warn">{fmt(vswrOf(Math.hypot(cur[0], cur[1])), 4)}</span><span className="text-faint"> · λ </span>{fmt(wtg((Math.atan2(cur[1], cur[0]) * 180) / Math.PI), 3)}</div>
          </>
        ) : (
          <div className="text-faint">Cursor sobre la carta · Z0 = {z0} Ω</div>
        )}
      </div>
      <div className="absolute right-2 top-2 flex flex-col gap-1">
        {[
          { i: <ZoomIn className="h-3.5 w-3.5" />, f: () => zoom(1 / 1.5), t: "Acercar" },
          { i: <ZoomOut className="h-3.5 w-3.5" />, f: () => zoom(1.5), t: "Alejar" },
          { i: <Maximize2 className="h-3.5 w-3.5" />, f: () => setVb(FULL), t: "Vista completa (doble clic)" },
          { i: <Download className="h-3.5 w-3.5" />, f: () => setExpOpen((v) => !v), t: "Exportar la carta en alta calidad" },
        ].map((b, i) => (
          <button key={i} title={b.t} onClick={b.f} className="rounded border border-line bg-bg/80 p-1.5 text-dim hover:border-acc/50 hover:text-acc">{b.i}</button>
        ))}
      </div>
      {expOpen && (
        <div className="absolute right-11 top-2 z-10 w-[210px] rounded border border-line2 bg-panel p-2 text-[12px] shadow-xl">
          <div className="mb-1 text-2xs uppercase tracking-wider text-dim">Exportar vista actual</div>
          {([["svg", "SVG vectorial (escalable)"], ["png", "PNG 4000 × 4000 px"], ["png-white", "PNG 4000 px · fondo blanco"]] as const).map(([k, l]) => (
            <button key={k} className="block w-full rounded px-2 py-1.5 text-left text-ink hover:bg-acc/10 hover:text-acc"
              onClick={() => { setExpOpen(false); exportSmith(svg.current!, vb, k, exportName, z0); }}>{l}</button>
          ))}
          <p className="mt-1 px-2 text-2xs text-faint">Respeta el zoom actual. Para imprimir, el tema claro da mejor contraste.</p>
        </div>
      )}
      {k < 0.999 && <div className="pointer-events-none absolute bottom-2 right-2 rounded bg-bg/80 px-1.5 py-0.5 font-mono text-2xs text-dim">×{fmt(1 / k, 3)}</div>}
    </div>
  );
}

/** Exporta el SVG de la carta: vectorial o PNG de 4000 px. Las líneas «non-scaling-stroke» se reescalan
 *  para conservar el grosor relativo que se ve en pantalla. */
async function exportSmith(src: SVGSVGElement, vb: { x: number; y: number; w: number }, kind: "svg" | "png" | "png-white", name: string, z0: number) {
  const NS = "http://www.w3.org/2000/svg";
  const size = 4000;
  const clone = src.cloneNode(true) as SVGSVGElement;
  const scale = size / Math.max(1, src.clientWidth);
  clone.setAttribute("xmlns", NS);
  clone.setAttribute("width", String(kind === "svg" ? 1200 : size));
  clone.setAttribute("height", String(kind === "svg" ? 1200 : size));
  clone.querySelectorAll<SVGElement>("*").forEach((el) => {
    if (el.style.vectorEffect === "non-scaling-stroke") {
      const sw = parseFloat(el.getAttribute("stroke-width") || "1");
      el.setAttribute("stroke-width", String(sw * (kind === "svg" ? 1200 / Math.max(1, src.clientWidth) : scale)));
    }
  });
  const css = getComputedStyle(document.documentElement);
  const panel = `rgb(${css.getPropertyValue("--panel").trim().split(" ").join(",")})`;
  const ink = `rgb(${css.getPropertyValue("--ink").trim().split(" ").join(",")})`;
  const bg = document.createElementNS(NS, "rect");
  bg.setAttribute("x", String(vb.x)); bg.setAttribute("y", String(vb.y));
  bg.setAttribute("width", String(vb.w)); bg.setAttribute("height", String(vb.w));
  bg.setAttribute("fill", kind === "png-white" ? "#ffffff" : panel);
  clone.insertBefore(bg, clone.firstChild);
  const title = document.createElementNS(NS, "text");
  title.setAttribute("x", String(vb.x + vb.w * 0.02)); title.setAttribute("y", String(vb.y + vb.w * 0.035));
  title.setAttribute("font-size", String(vb.w * 0.022)); title.setAttribute("font-family", "IBM Plex Sans, Arial, sans-serif");
  title.setAttribute("fill", kind === "png-white" ? "#111827" : ink);
  title.textContent = `Carta de Smith · Z0 = ${z0} Ω · RF Engineering Workbench`;
  clone.appendChild(title);
  const xml = new XMLSerializer().serializeToString(clone);
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  if (kind === "svg") return save(new Blob([xml], { type: "image/svg+xml" }), `${name}_${stamp}.svg`);
  const img = new Image();
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
  await img.decode();
  const cv = document.createElement("canvas");
  cv.width = size; cv.height = size;
  cv.getContext("2d")!.drawImage(img, 0, 0, size, size);
  const blob: Blob = await new Promise((res) => cv.toBlob((b) => res(b!), "image/png"));
  save(blob, `${name}_${stamp}.png`);
}

function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
