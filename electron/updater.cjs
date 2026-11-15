// Actualizaciones automáticas desde las Releases públicas de GitHub (rf-engineering-workbench-releases).
// Sólo en la app instalada (app.isPackaged). Nunca descarga ni instala sin preguntar.
const { app, dialog, ipcMain } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

let updater = null;
let state = { status: "idle", message: "", version: null };
let getWindow = () => null;
let manual = false;

function log(msg) {
  try {
    fs.appendFileSync(path.join(app.getPath("userData"), "updater.log"), `${new Date().toISOString()} ${msg}\n`);
  } catch { /* sin log */ }
}

function set(status, message, version = null) {
  state = { status, message, version };
  log(`${status}: ${message}`);
}

function setup(winGetter) {
  getWindow = winGetter;
  ipcMain.handle("updates:check", async () => { await check(true); return state; });
  ipcMain.handle("updates:state", () => ({ ...state, current: app.getVersion(), packaged: app.isPackaged }));
  if (!app.isPackaged && !process.env.RFWB_FORCE_UPDATER) {
    set("disabled", "Actualizaciones desactivadas al ejecutar desde el código fuente.");
    return;
  }
  ({ autoUpdater: updater } = require("electron-updater"));
  updater.autoDownload = false;
  updater.autoInstallOnAppQuit = false;
  updater.logger = { info: log, warn: log, error: log, debug: () => {} };

  updater.on("checking-for-update", () => set("checking", "Buscando actualizaciones…"));
  updater.on("update-not-available", (i) => {
    set("latest", `Ya tiene la última versión (${app.getVersion()}).`, i?.version);
    if (manual) dialog.showMessageBox(getWindow(), { type: "info", title: "Actualizaciones", message: state.message });
  });
  updater.on("error", (e) => {
    set("error", `No se pudo comprobar: ${e?.message ?? e}`);
    if (manual) dialog.showMessageBox(getWindow(), { type: "warning", title: "Actualizaciones", message: "No se pudo comprobar si hay actualizaciones.", detail: String(e?.message ?? e) });
  });
  updater.on("update-available", async (info) => {
    set("available", `Versión ${info.version} disponible.`, info.version);
    const r = await dialog.showMessageBox(getWindow(), {
      type: "info", title: "Actualización disponible", buttons: ["Descargar", "Más tarde"], defaultId: 0, cancelId: 1,
      message: `Hay una nueva versión de RF Engineering Workbench: ${info.version} (instalada: ${app.getVersion()}).`,
      detail: "Se descargará en segundo plano. Al terminar se le preguntará antes de instalar.",
    });
    if (r.response === 0) { set("downloading", `Descargando ${info.version}…`, info.version); updater.downloadUpdate().catch((e) => set("error", String(e))); }
  });
  updater.on("download-progress", (p) => { state.message = `Descargando… ${Math.round(p.percent)} %`; getWindow()?.setProgressBar(p.percent / 100); });
  updater.on("update-downloaded", async (info) => {
    getWindow()?.setProgressBar(-1);
    set("ready", `Versión ${info.version} lista para instalar.`, info.version);
    const r = await dialog.showMessageBox(getWindow(), {
      type: "question", title: "Instalar actualización", buttons: ["Reiniciar e instalar", "Al cerrar la aplicación"], defaultId: 0, cancelId: 1,
      message: `La versión ${info.version} se ha descargado.`, detail: "Sus datos (proyectos, biblioteca, mediciones) se conservan.",
    });
    if (r.response === 0) { app.isQuitting = true; updater.quitAndInstall(false, true); }
    else updater.autoInstallOnAppQuit = true;
  });
  setTimeout(() => check(false), 4000);
}

async function check(isManual) {
  manual = isManual;
  if (!updater) {
    if (isManual) dialog.showMessageBox(getWindow(), { type: "info", title: "Actualizaciones", message: state.message || "Actualizaciones no disponibles." });
    return;
  }
  try { await updater.checkForUpdates(); } catch (e) { set("error", String(e?.message ?? e)); }
}

module.exports = { setup };
