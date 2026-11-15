// Esquemas eléctricos en escalera (SVG). Orden de los elementos: desde la fuente/puerto hacia la carga.
import { si } from "../lib/format";

export type LadderItem = {
  type: "series" | "shunt" | "line" | "stub";
  part?: "R" | "L" | "C" | "Z" | "open" | "short";
  label?: string;
  sub?: string;
};

const W = 78;
const TOP = 34;
const BOT = 112;
const C = { wire: "#7f9089", sym: "#2fe39a", txt: "#d6e2dd", dim: "#7f9089", line: "#58b4ff" };

function Sym({ part, x, y, vertical }: { part: string; x: number; y: number; vertical?: boolean }) {
  const t = vertical ? `translate(${x} ${y}) rotate(90)` : `translate(${x} ${y})`;
  let body: JSX.Element;
  if (part === "R" || part === "Z") {
    body = part === "Z" ? <rect x={-14} y={-6} width={28} height={12} fill="#0a1013" stroke={C.sym} strokeWidth={1.6} /> :
      <path d="M-16 0 L-12 -6 L-6 6 L0 -6 L6 6 L12 -6 L16 0" fill="none" stroke={C.sym} strokeWidth={1.6} strokeLinejoin="round" />;
  } else if (part === "L") {
    body = <path d="M-16 0 a4 4 0 0 1 8 0 a4 4 0 0 1 8 0 a4 4 0 0 1 8 0 a4 4 0 0 1 8 0" fill="none" stroke={C.sym} strokeWidth={1.6} />;
  } else {
    body = (
      <g>
        <line x1={-4} y1={-10} x2={-4} y2={10} stroke={C.sym} strokeWidth={2} />
        <line x1={4} y1={-10} x2={4} y2={10} stroke={C.sym} strokeWidth={2} />
      </g>
    );
  }
  const gap = part === "C" ? 4 : 16;
  return (
    <g transform={t}>
      <line x1={-22} y1={0} x2={-gap} y2={0} stroke={C.wire} strokeWidth={1.4} />
      <line x1={gap} y1={0} x2={22} y2={0} stroke={C.wire} strokeWidth={1.4} />
      {body}
    </g>
  );
}

export function Ladder({ items, left = { kind: "source", label: "Zs" }, right = { kind: "load", label: "ZL" }, height = 150 }: {
  items: LadderItem[];
  left?: { kind: "source" | "port"; label: string };
  right?: { kind: "load" | "short" | "open"; label?: string };
  height?: number;
}) {
  const n = Math.max(items.length, 1);
  const x0 = 64;
  const width = x0 + n * W + 76;
  const xEnd = x0 + n * W;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxHeight: height }}>
      {/* raíles */}
      <line x1={left.kind === "source" ? 40 : 30} y1={TOP} x2={xEnd} y2={TOP} stroke={C.wire} strokeWidth={1.4} />
      <line x1={left.kind === "source" ? 40 : 30} y1={BOT} x2={xEnd} y2={BOT} stroke={C.wire} strokeWidth={1.4} />
      {/* lado izquierdo */}
      {left.kind === "source" ? (
        <g>
          <circle cx={26} cy={(TOP + BOT) / 2 + 12} r={12} fill="none" stroke={C.dim} strokeWidth={1.4} />
          <path d={`M18 ${(TOP + BOT) / 2 + 12} q4 -7 8 0 t8 0`} fill="none" stroke={C.dim} strokeWidth={1.2} />
          <line x1={26} y1={TOP} x2={26} y2={(TOP + BOT) / 2 - 18} stroke={C.wire} strokeWidth={1.4} />
          <rect x={20} y={TOP + 6} width={12} height={18} fill="#0a1013" stroke={C.dim} strokeWidth={1.2} />
          <line x1={26} y1={(TOP + BOT) / 2 + 24} x2={26} y2={BOT} stroke={C.wire} strokeWidth={1.4} />
          <line x1={26} y1={TOP} x2={40} y2={TOP} stroke={C.wire} strokeWidth={1.4} />
          <line x1={26} y1={BOT} x2={40} y2={BOT} stroke={C.wire} strokeWidth={1.4} />
          <text x={6} y={TOP + 18} fontSize={10} fill={C.txt} fontFamily="JetBrains Mono">{left.label}</text>
        </g>
      ) : (
        <g>
          <circle cx={30} cy={TOP} r={3} fill="#05080a" stroke={C.txt} strokeWidth={1.4} />
          <circle cx={30} cy={BOT} r={3} fill="#05080a" stroke={C.txt} strokeWidth={1.4} />
          <text x={6} y={(TOP + BOT) / 2 + 4} fontSize={10.5} fill={C.txt} fontFamily="JetBrains Mono">{left.label}</text>
        </g>
      )}
      {items.map((it, i) => {
        const cx = x0 + i * W + W / 2;
        const label = (
          <>
            {it.label && <text x={cx} y={it.type === "shunt" || it.type === "stub" ? BOT + 16 : TOP - 14} textAnchor="middle" fontSize={10} fill={C.txt} fontFamily="JetBrains Mono">{it.label}</text>}
            {it.sub && <text x={cx} y={it.type === "shunt" || it.type === "stub" ? BOT + 28 : TOP + 22} textAnchor="middle" fontSize={9} fill={C.dim} fontFamily="JetBrains Mono">{it.sub}</text>}
          </>
        );
        if (it.type === "series") {
          return (
            <g key={i}>
              <rect x={cx - 24} y={TOP - 3} width={48} height={6} fill="#05080a" />
              <Sym part={it.part ?? "Z"} x={cx} y={TOP} />
              {label}
            </g>
          );
        }
        if (it.type === "shunt") {
          return (
            <g key={i}>
              <circle cx={cx} cy={TOP} r={2.4} fill={C.wire} />
              <line x1={cx} y1={TOP} x2={cx} y2={(TOP + BOT) / 2 - 22} stroke={C.wire} strokeWidth={1.4} />
              <Sym part={it.part ?? "Z"} x={cx} y={(TOP + BOT) / 2} vertical />
              <line x1={cx} y1={(TOP + BOT) / 2 + 22} x2={cx} y2={BOT} stroke={C.wire} strokeWidth={1.4} />
              <circle cx={cx} cy={BOT} r={2.4} fill={C.wire} />
              {label}
            </g>
          );
        }
        if (it.type === "line") {
          return (
            <g key={i}>
              <rect x={cx - 30} y={TOP - 7} width={60} height={14} rx={2} fill="#0a1013" stroke={C.line} strokeWidth={1.4} />
              <line x1={cx - 30} y1={TOP} x2={cx + 30} y2={TOP} stroke={C.line} strokeWidth={0.8} strokeDasharray="2 2" />
              <rect x={cx - 30} y={BOT - 4} width={60} height={8} fill="#0a1013" stroke={C.line} strokeWidth={0.8} strokeOpacity={0.5} />
              {it.label && <text x={cx} y={TOP - 13} textAnchor="middle" fontSize={10} fill={C.line} fontFamily="JetBrains Mono">{it.label}</text>}
              {it.sub && <text x={cx} y={TOP + 22} textAnchor="middle" fontSize={9} fill={C.dim} fontFamily="JetBrains Mono">{it.sub}</text>}
            </g>
          );
        }
        // stub en paralelo
        const yTop = TOP + 10, yBot = BOT - 18;
        return (
          <g key={i}>
            <circle cx={cx} cy={TOP} r={2.4} fill={C.wire} />
            <line x1={cx} y1={TOP} x2={cx} y2={yTop} stroke={C.wire} strokeWidth={1.4} />
            <rect x={cx - 7} y={yTop} width={14} height={yBot - yTop} rx={2} fill="#0a1013" stroke={C.line} strokeWidth={1.4} />
            {it.part === "short" ? (
              <g>
                <line x1={cx} y1={yBot} x2={cx} y2={BOT} stroke={C.wire} strokeWidth={1.4} />
                <circle cx={cx} cy={BOT} r={2.4} fill={C.wire} />
              </g>
            ) : (
              <text x={cx} y={yBot + 12} textAnchor="middle" fontSize={8.5} fill={C.dim} fontFamily="JetBrains Mono">abierto</text>
            )}
            {it.label && <text x={cx + 12} y={(yTop + yBot) / 2} fontSize={9.5} fill={C.line} fontFamily="JetBrains Mono">{it.label}</text>}
            {it.sub && <text x={cx + 12} y={(yTop + yBot) / 2 + 12} fontSize={9} fill={C.dim} fontFamily="JetBrains Mono">{it.sub}</text>}
          </g>
        );
      })}
      {/* lado derecho */}
      {right.kind === "load" && (
        <g>
          <line x1={xEnd} y1={TOP} x2={xEnd + 30} y2={TOP} stroke={C.wire} strokeWidth={1.4} />
          <line x1={xEnd} y1={BOT} x2={xEnd + 30} y2={BOT} stroke={C.wire} strokeWidth={1.4} />
          <line x1={xEnd + 30} y1={TOP} x2={xEnd + 30} y2={(TOP + BOT) / 2 - 16} stroke={C.wire} strokeWidth={1.4} />
          <rect x={xEnd + 22} y={(TOP + BOT) / 2 - 16} width={16} height={32} fill="#0a1013" stroke="#f0b44c" strokeWidth={1.5} />
          <line x1={xEnd + 30} y1={(TOP + BOT) / 2 + 16} x2={xEnd + 30} y2={BOT} stroke={C.wire} strokeWidth={1.4} />
          <text x={xEnd + 44} y={(TOP + BOT) / 2 + 4} fontSize={10} fill="#f0b44c" fontFamily="JetBrains Mono">{right.label ?? "ZL"}</text>
        </g>
      )}
      {right.kind === "short" && <line x1={xEnd} y1={TOP} x2={xEnd} y2={BOT} stroke={C.wire} strokeWidth={1.4} />}
    </svg>
  );
}

// Utilidades para traducir elementos del motor a items de esquema
export function elementsToLadder(elements: any[], lambda?: number): LadderItem[] {
  return elements.map((e) => {
    if (e.kind === "line") return { type: "line", label: `Z0=${Number(e.z0).toPrecision(4)}Ω`, sub: lambda ? `${(e.length_m / lambda).toFixed(4)}λ` : si(e.length_m, "m") };
    if (e.part === "stub_open" || e.part === "stub_short")
      return { type: "stub", part: e.part === "stub_open" ? "open" : "short", label: lambda ? `${(e.length_m / lambda).toFixed(4)}λ` : si(e.length_m, "m"), sub: si(e.length_m, "m", 4) };
    const unit = e.part === "L" ? "H" : e.part === "C" ? "F" : "Ω";
    return { type: e.kind === "series" ? "series" : "shunt", part: e.part, label: si(e.value, unit, 4), sub: e.q ? `Q=${e.q}` : undefined };
  });
}

