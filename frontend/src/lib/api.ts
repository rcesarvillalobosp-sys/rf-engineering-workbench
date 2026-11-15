// Cliente de la API del motor RF. Todas las magnitudes de ingeniería se calculan en el backend.
export type Num = number | "inf" | "-inf" | null;
export type Cx = { re: number | null; im: number | null; inf?: boolean };
export type Arr = (number | null)[];
export type CxArr = { re: Arr; im: Arr };
export type Step = { title: string; formula: string; substitution: string; result: string; unit: string; note: string };
export type Origin = "calculated" | "simulated" | "imported" | "measured" | "derived";

export class ApiError extends Error {}

async function handle(res: Response) {
  if (res.ok) return res;
  let msg = `Error ${res.status}`;
  try {
    const j = await res.json();
    if (typeof j.detail === "string") msg = j.detail;
    else if (Array.isArray(j.detail)) msg = j.detail.map((d: any) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join(" · ");
  } catch {
    /* sin cuerpo JSON */
  }
  throw new ApiError(msg);
}

export async function post<T = any>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return (await handle(res)).json();
}

export async function put<T = any>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return (await handle(res)).json();
}

export async function get<T = any>(path: string): Promise<T> {
  return (await handle(await fetch(`/api${path}`))).json();
}

export async function del<T = any>(path: string): Promise<T> {
  return (await handle(await fetch(`/api${path}`, { method: "DELETE" }))).json();
}

export async function download(path: string, body: unknown | null, filename: string) {
  const res = await handle(
    await fetch(`/api${path}`, body === null ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  );
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const ORIGIN_LABEL: Record<Origin, string> = {
  calculated: "Calculado — motor matemático",
  simulated: "Simulado — modelo",
  imported: "Datos importados desde Touchstone",
  measured: "Medición real — VNA conectado",
  derived: "Derivado — procesado (calibración)",
};
