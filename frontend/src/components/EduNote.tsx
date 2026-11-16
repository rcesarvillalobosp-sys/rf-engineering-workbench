import { motion } from "motion/react";
import { GraduationCap } from "lucide-react";
import type React from "react";
import { useStore } from "../lib/store";

/** Explicación didáctica: sólo visible con el modo educativo activado.
 *  Sin animación de salida: desaparece al instante (no depende de que termine una animación). */
export function EduNote({ children, title = "Qué está viendo" }: { children: React.ReactNode; title?: string }) {
  const education = useStore((s) => s.education);
  if (!education) return null;
  return (
    <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}
      className="mb-3 flex gap-2.5 rounded-md border border-acc/30 bg-acc/[0.06] px-3 py-2.5 text-[12.5px] leading-relaxed text-ink">
      <GraduationCap className="mt-0.5 h-4 w-4 shrink-0 text-acc" />
      <div><span className="font-semibold text-acc">{title}. </span>{children}</div>
    </motion.div>
  );
}
