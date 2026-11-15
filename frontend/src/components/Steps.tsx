import { motion } from "motion/react";
import { GraduationCap } from "lucide-react";
import type { Step } from "../lib/api";
import { useStore } from "../lib/store";
import { Collapse } from "./ui";

/** Modo educativo: fórmula → sustitución → resultado → interpretación. */
export function Steps({ steps, title = "Procedimiento matemático", open }: { steps?: Step[] | null; title?: string; open?: boolean }) {
  const education = useStore((s) => s.education);
  if (!steps?.length) return null;
  return (
    <Collapse
      open={open ?? education}
      title={
        <span className="flex items-center gap-2">
          <GraduationCap className="h-3.5 w-3.5 text-acc" />
          {title}
          <span className="font-mono text-2xs text-faint">{steps.length} pasos</span>
        </span>
      }
    >
      <ol className="space-y-2.5">
        {steps.map((s, i) => (
          <motion.li key={i} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.025 }} className="grid grid-cols-[22px_1fr] gap-2">
            <span className="mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border border-acc/40 font-mono text-[10px] text-acc">{i + 1}</span>
            <div className="min-w-0">
              <div className="text-[12.5px] font-medium text-ink">{s.title}</div>
              <div className="mt-0.5 overflow-x-auto whitespace-nowrap rounded bg-[#060a0c] px-2 py-1 font-mono text-[12px] text-[#9fe9c8]">{s.formula}</div>
              {s.substitution && <div className="mt-0.5 overflow-x-auto whitespace-nowrap font-mono text-[11.5px] text-dim">{s.substitution}</div>}
              {s.result && (
                <div className="mt-0.5 font-mono text-[12px] text-ink">
                  = <span className="text-acc">{s.result}</span> {s.unit && <span className="text-dim">{s.unit}</span>}
                </div>
              )}
              {s.note && <div className="mt-0.5 text-[11.5px] italic leading-snug text-faint">{s.note}</div>}
            </div>
          </motion.li>
        ))}
      </ol>
    </Collapse>
  );
}
