import { ArrowDown, ArrowUp, FileDown, FileSpreadsheet, Trash2 } from "lucide-react";
import { useState } from "react";
import { Btn, Empty, Field, Input, KV, Note, OriginBadge, PageHeader, Panel } from "../components/ui";
import { ORIGIN_LABEL, download } from "../lib/api";
import { useForm, useStore } from "../lib/store";

export function ReportsModule() {
  const { report, removeReport, moveReport, clearReport, toast, project } = useStore();
  const [s, set] = useForm("reports", { title: "Informe técnico RF", author: "" });
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const item = report.find((r) => r.id === sel) ?? report[0];
  const origins = Array.from(new Set(report.map((r) => r.origin)));
  const payload = () => ({ title: s.title, author: s.author, project: project.name, created: new Date().toLocaleString("es-ES"), items: report });
  const exp = async (kind: "pdf" | "csv") => {
    setBusy(kind);
    try { await download(`/reports/${kind}`, payload(), `${s.title.replace(/[^\w\-áéíóúñÁÉÍÓÚÑ ]/g, "_")}.${kind}`); toast("ok", `Informe ${kind.toUpperCase()} generado`); }
    catch (e: any) { toast("err", e.message); } finally { setBusy(null); }
  };
  return (
    <div>
      <PageHeader index={11} title="Reports" desc="Informe técnico con datos de entrada, resultados, carta de Smith, gráficas y procedimientos. Cada elemento declara si procede de cálculo, simulación, archivo importado o medición real."
        right={<><Btn small loading={busy === "csv"} disabled={!report.length} icon={<FileSpreadsheet className="h-3.5 w-3.5" />} onClick={() => exp("csv")}>Exportar CSV</Btn><Btn small variant="primary" loading={busy === "pdf"} disabled={!report.length} icon={<FileDown className="h-3.5 w-3.5" />} onClick={() => exp("pdf")}>Exportar PDF</Btn></>} />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[420px_minmax(0,1fr)]">
        <div className="space-y-3">
          <Panel title="Documento">
            <div className="grid grid-cols-1 gap-2">
              <Field label="Título"><Input mono={false} value={s.title} onChange={(e) => set({ title: e.target.value })} /></Field>
              <Field label="Autor (opcional)"><Input mono={false} value={s.author} onChange={(e) => set({ author: e.target.value })} /></Field>
            </div>
            {origins.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{origins.map((o) => <OriginBadge key={o} origin={o} />)}</div>}
          </Panel>
          <Panel title={`Elementos (${report.length})`} actions={report.length > 0 && <Btn small variant="danger" onClick={() => { if (confirm("¿Vaciar el informe?")) clearReport(); }}>Vaciar</Btn>}>
            {report.length === 0 ? <p className="text-[12px] text-dim">Use «Añadir al informe» en cualquier módulo para incluir sus resultados.</p> : (
              <div className="space-y-1.5">{report.map((r, i) => (
                <div key={r.id} onClick={() => setSel(r.id)} className={`cursor-pointer rounded border px-2.5 py-2 ${item?.id === r.id ? "border-acc/50 bg-acc/[0.05]" : "border-line hover:border-line2"}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0"><div className="truncate text-[12.5px] text-ink">{i + 1}. {r.title}</div><div className="text-2xs text-faint">{r.module} · {r.created}</div></div>
                    <div className="flex shrink-0 gap-1 text-faint">
                      <button className="hover:text-ink" onClick={(e) => { e.stopPropagation(); moveReport(r.id, -1); }}><ArrowUp className="h-3.5 w-3.5" /></button>
                      <button className="hover:text-ink" onClick={(e) => { e.stopPropagation(); moveReport(r.id, 1); }}><ArrowDown className="h-3.5 w-3.5" /></button>
                      <button className="hover:text-err" onClick={(e) => { e.stopPropagation(); removeReport(r.id); }}><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  </div>
                  <div className="mt-1"><OriginBadge origin={r.origin} /></div>
                </div>
              ))}</div>
            )}
          </Panel>
        </div>
        <div>
          {item ? (
            <Panel title={item.title} sub={`${item.module} · ${ORIGIN_LABEL[item.origin]}`}>
              {item.source_detail && <Note className="mb-2">{item.source_detail}</Note>}
              {!!item.inputs?.length && <><h4 className="mb-1 text-2xs uppercase tracking-wider text-dim">Datos de entrada</h4><KV dense rows={item.inputs} /></>}
              {!!item.results?.length && <><h4 className="mb-1 mt-3 text-2xs uppercase tracking-wider text-dim">Resultados</h4><KV dense rows={item.results} /></>}
              <div className="mt-3 flex flex-wrap gap-3 text-2xs text-faint">
                {item.smith && <span>Carta de Smith: {item.smith.traces.length} trazas, {item.smith.points.length} puntos</span>}
                {!!item.plots?.length && <span>{item.plots.length} gráficas</span>}
                {!!item.steps?.length && <span>{item.steps.length} pasos de cálculo</span>}
              </div>
              {item.notes?.map((n, i) => <Note key={i} kind="warn" className="mt-2">{n}</Note>)}
            </Panel>
          ) : <Empty>El informe está vacío.</Empty>}
        </div>
      </div>
    </div>
  );
}
