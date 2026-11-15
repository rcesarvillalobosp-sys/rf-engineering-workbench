import { FilePlus2 } from "lucide-react";
import { type ReportItem, useStore } from "../lib/store";
import { Btn } from "./ui";

export function ReportButton({ build, disabled }: { build: () => Omit<ReportItem, "id" | "created"> | null; disabled?: boolean }) {
  const add = useStore((s) => s.addReport);
  const toast = useStore((s) => s.toast);
  return (
    <Btn
      small
      disabled={disabled}
      icon={<FilePlus2 className="h-3.5 w-3.5" />}
      onClick={() => {
        const it = build();
        if (!it) return;
        add(it);
        toast("ok", `Añadido al informe: ${it.title}`);
      }}
    >
      Añadir al informe
    </Btn>
  );
}

/** Reduce arrays largos para el informe (máx. n puntos). */
export function decimate<T>(a: T[], n = 400): T[] {
  if (a.length <= n) return a;
  const step = a.length / n;
  return Array.from({ length: n }, (_, i) => a[Math.floor(i * step)]);
}
