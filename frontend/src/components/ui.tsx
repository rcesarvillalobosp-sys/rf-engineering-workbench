import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, CheckCircle2, ChevronDown, Info, Loader2, XCircle } from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ORIGIN_LABEL, type Origin } from "../lib/api";

export function Panel(props: { title?: React.ReactNode; sub?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string; pad?: boolean }) {
  const { title, sub, actions, children, className = "", pad = true } = props;
  return (
    <section className={`rounded-md border border-line bg-panel ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-3.5 py-2">
          <div className="min-w-0">
            <h3 className="truncate text-[12px] font-semibold uppercase tracking-[0.08em] text-ink">{title}</h3>
            {sub && <p className="truncate text-2xs text-dim">{sub}</p>}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">{actions}</div>
        </header>
      )}
      <div className={pad ? "p-3.5" : ""}>{children}</div>
    </section>
  );
}

export function Field(props: { label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <label className={`block ${props.className ?? ""}`}>
      <span className="mb-1 block text-2xs font-medium uppercase tracking-wider text-dim">{props.label}</span>
      {props.children}
      {props.hint && <span className="mt-0.5 block text-2xs text-faint">{props.hint}</span>}
    </label>
  );
}

const inputCls =
  "w-full rounded border border-line2 bg-panel2 px-2.5 py-1.5 text-[13px] text-ink outline-none transition-colors placeholder:text-faint focus:border-acc/70 focus:bg-[#0f1a1e]";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement> & { mono?: boolean; suffix?: string }) {
  const { mono = true, suffix, className = "", ...rest } = props;
  return (
    <div className="relative">
      <input {...rest} className={`${inputCls} ${mono ? "font-mono" : ""} ${suffix ? "pr-11" : ""} ${className}`} />
      {suffix && <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-2xs text-dim">{suffix}</span>}
    </div>
  );
}

export function Select<T extends string>(props: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; className?: string }) {
  return (
    <div className="relative">
      <select value={props.value} onChange={(e) => props.onChange(e.target.value as T)} className={`${inputCls} appearance-none pr-7 ${props.className ?? ""}`}>
        {props.options.map((o) => (
          <option key={o.value} value={o.value} className="bg-panel2">
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-dim" />
    </div>
  );
}

export function Btn(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "subtle"; loading?: boolean; icon?: React.ReactNode; small?: boolean }) {
  const { variant = "ghost", loading, icon, small, className = "", children, disabled, ...rest } = props;
  const v = {
    primary: "bg-acc text-[#03140c] hover:bg-[#5cf0b4] border-acc font-semibold",
    ghost: "border-line2 text-ink hover:border-acc/60 hover:text-acc bg-transparent",
    subtle: "border-transparent text-dim hover:text-ink hover:bg-white/5",
    danger: "border-err/40 text-err hover:bg-err/10",
  }[variant];
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded border transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${small ? "px-2 py-1 text-2xs" : "px-3 py-1.5 text-[12.5px]"} ${v} ${className}`}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function Seg<T extends string>(props: { value: T; onChange: (v: T) => void; options: { value: T; label: React.ReactNode; title?: string }[]; small?: boolean }) {
  return (
    <div className="inline-flex flex-wrap rounded border border-line2 bg-panel2 p-0.5">
      {props.options.map((o) => (
        <button
          key={o.value}
          title={o.title}
          onClick={() => props.onChange(o.value)}
          className={`relative rounded-[3px] ${props.small ? "px-2 py-0.5 text-2xs" : "px-2.5 py-1 text-[12px]"} transition-colors ${props.value === o.value ? "text-[#03140c]" : "text-dim hover:text-ink"}`}
        >
          {props.value === o.value && <motion.span layoutId={undefined} className="absolute inset-0 rounded-[3px] bg-acc" transition={{ duration: 0.15 }} />}
          <span className="relative">{o.label}</span>
        </button>
      ))}
    </div>
  );
}

export function Toggle(props: { checked: boolean; onChange: (v: boolean) => void; label: React.ReactNode }) {
  return (
    <button onClick={() => props.onChange(!props.checked)} className="inline-flex items-center gap-2 text-[12px] text-dim hover:text-ink">
      <span className={`relative h-4 w-7 rounded-full border transition-colors ${props.checked ? "border-acc bg-acc/25" : "border-line2 bg-panel2"}`}>
        <span className={`absolute top-[1px] h-3 w-3 rounded-full transition-all ${props.checked ? "left-[13px] bg-acc" : "left-[1px] bg-dim"}`} />
      </span>
      {props.label}
    </button>
  );
}

export function KV(props: { rows: [React.ReactNode, React.ReactNode, React.ReactNode?][]; dense?: boolean }) {
  return (
    <dl className="divide-y divide-line/70">
      {props.rows.map(([k, v, u], i) => (
        <div key={i} className={`grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-3 ${props.dense ? "py-1" : "py-1.5"}`}>
          <dt className="truncate text-[12px] text-dim">{k}</dt>
          <dd className="text-right font-mono text-[12.5px] text-ink">
            {v}
            {u ? <span className="ml-1 text-2xs text-dim">{u}</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function Stat(props: { label: string; value: React.ReactNode; unit?: string; tone?: "acc" | "warn" | "err" | "ink"; sub?: React.ReactNode }) {
  const tone = { acc: "text-acc", warn: "text-warn", err: "text-err", ink: "text-ink" }[props.tone ?? "ink"];
  return (
    <div className="rounded border border-line bg-panel2/60 px-3 py-2">
      <div className="text-2xs uppercase tracking-wider text-dim">{props.label}</div>
      <div className={`mt-0.5 font-mono text-[19px] leading-tight ${tone}`}>
        {props.value}
        {props.unit && <span className="ml-1 text-[11px] text-dim">{props.unit}</span>}
      </div>
      {props.sub && <div className="mt-0.5 text-2xs text-faint">{props.sub}</div>}
    </div>
  );
}

export function Note(props: { kind?: "info" | "warn" | "err" | "ok"; children: React.ReactNode; className?: string }) {
  const k = props.kind ?? "info";
  const map = {
    info: ["border-info/30 bg-info/5 text-[#a9d4ff]", <Info key="i" className="mt-0.5 h-3.5 w-3.5 shrink-0" />],
    warn: ["border-warn/30 bg-warn/5 text-[#f6d394]", <AlertTriangle key="w" className="mt-0.5 h-3.5 w-3.5 shrink-0" />],
    err: ["border-err/40 bg-err/10 text-[#ffb3b3]", <XCircle key="e" className="mt-0.5 h-3.5 w-3.5 shrink-0" />],
    ok: ["border-acc/30 bg-acc/5 text-[#a8f3cf]", <CheckCircle2 key="o" className="mt-0.5 h-3.5 w-3.5 shrink-0" />],
  } as const;
  return (
    <div className={`flex gap-2 rounded border px-2.5 py-2 text-[12px] leading-snug ${map[k][0]} ${props.className ?? ""}`}>
      {map[k][1]}
      <div className="min-w-0">{props.children}</div>
    </div>
  );
}

const ORIGIN_STYLE: Record<Origin, string> = {
  calculated: "border-acc/40 text-acc bg-acc/5",
  simulated: "border-[#4fd1e8]/40 text-[#7fe0f0] bg-[#4fd1e8]/5",
  imported: "border-warn/40 text-warn bg-warn/5",
  measured: "border-[#ff8a5c]/50 text-[#ffab8a] bg-[#ff8a5c]/10",
  derived: "border-[#b58cff]/40 text-[#cdb3ff] bg-[#b58cff]/5",
};

export function OriginBadge({ origin, detail }: { origin: Origin; detail?: string }) {
  return (
    <span title={detail} className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-2xs font-medium ${ORIGIN_STYLE[origin]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {ORIGIN_LABEL[origin]}
    </span>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="flex h-full min-h-[120px] items-center justify-center rounded border border-dashed border-line2 p-6 text-center text-[12.5px] text-faint">{children}</div>;
}

export function Collapse(props: { title: React.ReactNode; open?: boolean; children: React.ReactNode; right?: React.ReactNode }) {
  const [open, setOpen] = useState(props.open ?? false);
  return (
    <div className="rounded border border-line">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-3 py-2 text-left text-[12px] text-ink hover:bg-white/[0.02]">
        <span className="flex items-center gap-2">
          <ChevronDown className={`h-3.5 w-3.5 text-dim transition-transform ${open ? "" : "-rotate-90"}`} />
          {props.title}
        </span>
        {props.right}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.18 }} className="overflow-hidden">
            <div className="border-t border-line p-3">{props.children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Ejecuta una llamada al motor; gestiona carga y error. Opcionalmente se relanza al cambiar deps (con retardo). */
export function useCall<T>(fn: () => Promise<T>, deps: unknown[] | null, delay = 250) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const run = useCallback(async () => {
    const my = ++seq.current;
    setLoading(true);
    try {
      const r = await fnRef.current();
      if (my === seq.current) {
        setData(r);
        setError(null);
      }
      return r;
    } catch (e: any) {
      if (my === seq.current) setError(e?.message ?? String(e));
      return null;
    } finally {
      if (my === seq.current) setLoading(false);
    }
  }, []);
  // Clave estable: el número de dependencias puede variar (null ↔ lista), lo que React no admite.
  const key = deps === null ? null : JSON.stringify(deps);
  useEffect(() => {
    if (key === null) return;
    const t = setTimeout(run, delay);
    return () => clearTimeout(t);
  }, [key, run, delay]);
  return { data, error, loading, run, setData };
}

export function Grid({ children, cols = "md:grid-cols-2", className = "" }: { children: React.ReactNode; cols?: string; className?: string }) {
  return <div className={`grid grid-cols-1 gap-3 ${cols} ${className}`}>{children}</div>;
}

export function PageHeader(props: { index: number; title: string; desc: string; right?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="font-mono text-2xs text-acc/80">{String(props.index).padStart(2, "0")} /</div>
        <h1 className="text-[21px] font-semibold tracking-tight text-ink">{props.title}</h1>
        <p className="mt-0.5 max-w-3xl text-[12.5px] text-dim">{props.desc}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">{props.right}</div>
    </div>
  );
}

export function Table(props: { head: React.ReactNode[]; rows: React.ReactNode[][]; onRow?: (i: number) => void; active?: number }) {
  return (
    <div className="overflow-auto rounded border border-line">
      <table className="w-full text-left text-[12px]">
        <thead className="sticky top-0 bg-panel2 text-2xs uppercase tracking-wider text-dim">
          <tr>{props.head.map((h, i) => <th key={i} className="whitespace-nowrap px-2.5 py-1.5 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line/70 font-mono">
          {props.rows.map((r, i) => (
            <tr key={i} onClick={() => props.onRow?.(i)} className={`${props.onRow ? "cursor-pointer hover:bg-white/[0.03]" : ""} ${props.active === i ? "bg-acc/10" : ""}`}>
              {r.map((c, j) => <td key={j} className="whitespace-nowrap px-2.5 py-1.5 text-ink">{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
