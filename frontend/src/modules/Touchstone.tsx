import { EduNote } from "../components/EduNote";
import { Download, ExternalLink, Save, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Plot, usePalette } from "../components/Plot";
import { SmithChart } from "../components/SmithChart";
import { Btn, Empty, KV, Note, OriginBadge, PageHeader, Panel, Select, Table } from "../components/ui";
import { del, download, get, post } from "../lib/api";
import { arr, fmt, hz, pairs } from "../lib/format";
import { useStore } from "../lib/store";

type Parsed = { filename: string; text: string; res?: any; error?: string };

export function TouchstoneModule() {
  const PALETTE = usePalette();
  const { toast, setModule, setForm } = useStore();
  const [files, setFiles] = useState<Parsed[]>([]);
  const [cur, setCur] = useState(0);
  const [list, setList] = useState<any[]>([]);
  const [fmtOut, setFmtOut] = useState("RI");
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const refresh = () => get("/datasets").then(setList).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const ingest = async (fl: FileList | File[]) => {
    const arrF = Array.from(fl).slice(0, 12);
    const out: Parsed[] = [];
    for (const f of arrF) {
      if (f.size > 50e6) { out.push({ filename: f.name, text: "", error: "Archivo demasiado grande (> 50 MB)." }); continue; }
      const text = await f.text();
      try { out.push({ filename: f.name, text, res: await post("/touchstone/parse", { filename: f.name, text }) }); }
      catch (e: any) { out.push({ filename: f.name, text, error: e.message }); }
    }
    setFiles(out);
    setCur(0);
  };

  const saveOne = async (p: Parsed) => {
    try {
      const r = await post("/touchstone/parse", { filename: p.filename, text: p.text, save: true, name: p.filename });
      toast("ok", `Guardado: ${p.filename}`);
      refresh();
      return r.dataset_id as number;
    } catch (e: any) { toast("err", e.message); return null; }
  };

  const p = files[cur];
  const r = p?.res;
  const sm = r?.summary;
  const f = arr(r?.f);
  const params = r ? Object.keys(r.params) : [];
  const magData = params.map((n, i) => ({ x: f, y: arr(r.db[n]), name: n, line: { width: 1.5, color: PALETTE[i % PALETTE.length] } }));

  return (
    <div>
      <PageHeader index={10} title="Touchstone Importer" desc="Importación de archivos .s1p, .s2p, .s3p, .s4p (Touchstone v1.x y v2.0): formatos RI/MA/DB, parámetros S/Y/Z y H/G (2 puertos), unidades Hz–GHz. Cada archivo se valida y se contrasta con scikit-rf." right={<OriginBadge origin="imported" />} />
      <EduNote>Touchstone es el formato estándar de intercambio de parámetros de red. La línea de opciones «# GHz S MA R 50» indica la unidad de frecuencia, el tipo de parámetro, el formato numérico (RI real/imaginario, MA magnitud/ángulo, DB dB/ángulo) y la impedancia de referencia. En 2 puertos (v1) el orden es S11 S21 S12 S22.</EduNote>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-3">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); ingest(e.dataTransfer.files); }}
            onClick={() => input.current?.click()} className={`flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? "border-acc bg-acc/5" : "border-line2 hover:border-acc/50"}`}>
            <Upload className="mb-2 h-7 w-7 text-acc" />
            <div className="text-[13.5px] text-ink">Arrastre archivos Touchstone o haga clic para seleccionar</div>
            <div className="mt-1 text-2xs text-faint">.s1p · .s2p · .s3p · .s4p · .sNp — hasta 12 archivos</div>
            <input ref={input} type="file" multiple accept=".s1p,.s2p,.s3p,.s4p,.S1P,.S2P,.S3P,.S4P,.ts" className="hidden" onChange={(e) => e.target.files && ingest(e.target.files)} />
          </div>
          {files.length > 0 && (
            <Panel title="Archivos analizados" actions={<Btn small variant="primary" icon={<Save className="h-3.5 w-3.5" />} onClick={async () => { for (const x of files) if (x.res) await saveOne(x); }}>Guardar válidos</Btn>}>
              <div className="space-y-1">{files.map((x, i) => (
                <button key={i} onClick={() => setCur(i)} className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[12px] ${i === cur ? "bg-acc/10" : "hover:bg-white/[0.03]"}`}>
                  <span className="truncate font-mono text-ink">{x.filename}</span>
                  <span className={x.error ? "text-err" : "text-acc"}>{x.error ? "Error" : `${x.res.summary.nports} puertos · ${x.res.summary.points} pts`}</span>
                </button>
              ))}</div>
            </Panel>
          )}
          {p?.error && <Note kind="err"><b>{p.filename}</b>: {p.error}</Note>}
          {r && (
            <Panel title={sm.filename} sub="Metadatos interpretados" actions={<Btn small variant="primary" icon={<Save className="h-3.5 w-3.5" />} onClick={() => saveOne(p)}>Guardar</Btn>}>
              <KV dense rows={[["Versión", sm.version], ["Puertos", sm.nports], ["Puntos de frecuencia", sm.points], ["Rango", `${hz(sm.f_start, 7)} – ${hz(sm.f_stop, 7)}`], ["Parámetro / formato", `${sm.param} / ${sm.format}`], ["Unidad del archivo", sm.freq_unit], ["Z0 de referencia", `${sm.z0.join(", ")} Ω`], ["Datos de ruido", sm.has_noise ? "Presentes (no se usan)" : "No"]]} />
              {r.skrf_check?.skipped && <Note className="mt-2">{r.skrf_check.note}</Note>}
              {r.skrf_check?.available && !r.skrf_check.skipped && (
                <Note kind={r.skrf_check.ok ? "ok" : "warn"} className="mt-2">
                  {r.skrf_check.ok ? `Contraste con scikit-rf ${r.skrf_check.skrf_version}: coincidencia (máx. |ΔS| = ${fmt(r.skrf_check.max_abs_diff_s, 3)}).` : `Contraste con scikit-rf: ${r.skrf_check.error ?? `diferencia máx. |ΔS| = ${fmt(r.skrf_check.max_abs_diff_s, 3)}`}`}
                </Note>
              )}
              {sm.warnings.map((w: string, i: number) => <Note key={i} kind="warn" className="mt-1.5">{w}</Note>)}
              {sm.comments.length > 0 && <details className="mt-2 text-2xs text-dim"><summary className="cursor-pointer">Comentarios del archivo ({sm.comments.length})</summary><pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap font-mono">{sm.comments.join("\n")}</pre></details>}
            </Panel>
          )}
        </div>
        <div className="space-y-3">
          {r ? (
            <>
              <Panel title="Magnitud de todos los parámetros" pad={false}><Plot height={280} data={magData} layout={{ xaxis: { title: { text: "Frecuencia (Hz)" } }, yaxis: { title: { text: "|S| (dB)" } } }} /></Panel>
              <Panel title="Reflexión en la carta de Smith" pad={false}>
                <div className="mx-auto aspect-square max-w-[420px] p-1.5"><SmithChart z0={sm.z0[0]} traces={params.filter((n) => n[1] === n[2]).map((n, i) => ({ pts: pairs(r.params[n]), color: PALETTE[i % PALETTE.length], width: 1.5 }))} /></div>
              </Panel>
            </>
          ) : <Empty>Vista previa del archivo seleccionado.</Empty>}
        </div>
      </div>
      <div className="mt-3">
        <Panel title={`Datos almacenados (${list.length})`} sub="Importados, simulados, medidos y derivados — cada uno con su origen" actions={<div className="w-40"><Select value={fmtOut} onChange={setFmtOut} options={[{ value: "RI", label: "Exportar RI" }, { value: "MA", label: "Exportar MA" }, { value: "DB", label: "Exportar DB" }]} /></div>}>
          {list.length === 0 ? <p className="text-[12px] text-dim">No hay datos almacenados.</p> : (
            <Table head={["Nombre", "Origen", "Puertos", "Puntos", "Rango", "Creado", "Acciones"]} rows={list.map((d) => [
              <span className="font-sans">{d.name}</span>, <OriginBadge origin={d.origin} />, d.nports, d.points, `${hz(d.f_start, 4)} – ${hz(d.f_stop, 4)}`, new Date(d.created * 1000).toLocaleString("es-ES"),
              <span className="flex gap-2">
                <button title="Abrir en S-Parameters" className="text-dim hover:text-acc" onClick={() => { setForm("sparams", { ds: d.id }); setModule("sparams"); }}><ExternalLink className="h-3.5 w-3.5" /></button>
                <button title={`Exportar Touchstone (${fmtOut})`} className="text-dim hover:text-acc" onClick={() => download(`/datasets/${d.id}/export?kind=touchstone&fmt=${fmtOut}`, null, `${d.name.replace(/\.s\d+p$/i, "")}.s${d.nports}p`).catch((e) => toast("err", e.message))}><Download className="h-3.5 w-3.5" /></button>
                <button title="Exportar CSV" className="font-mono text-2xs text-dim hover:text-acc" onClick={() => download(`/datasets/${d.id}/export?kind=csv`, null, `${d.name}.csv`).catch((e) => toast("err", e.message))}>CSV</button>
                <button title="Eliminar" className="text-dim hover:text-err" onClick={async () => { if (confirm(`¿Eliminar «${d.name}»?`)) { await del(`/datasets/${d.id}`); refresh(); } }}><Trash2 className="h-3.5 w-3.5" /></button>
              </span>,
            ])} />
          )}
        </Panel>
      </div>
    </div>
  );
}
