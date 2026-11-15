// RF Engineering Workbench — proceso principal de Electron.
// Arranca el motor RF (Python/FastAPI) como subproceso, espera a que responda y carga la interfaz.
const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn, execFile } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const http = require("node:http");
const net = require("node:net");

const ROOT = path.resolve(__dirname, "..");
const BACKEND = path.join(ROOT, "backend");
const DEV_URL = process.env.RFWB_DEV_URL || "";
let backend = null;
let backendLog = "";
let win = null;

// Instalado (app.isPackaged): motor PyInstaller e interfaz en resources/. Desde el código: venv + frontend/dist.
const UI_DIST = app.isPackaged ? path.join(process.resourcesPath, "ui") : path.join(ROOT, "frontend", "dist");

function engineCommand(port) {
  if (app.isPackaged) {
    const dir = path.join(process.resourcesPath, "engine");
    const exe = path.join(dir, process.platform === "win32" ? "rfwb-engine.exe" : "rfwb-engine");
    return { cmd: exe, args: ["--host", "127.0.0.1", "--port", String(port)], cwd: dir };
  }
  return { cmd: pythonPath(), args: ["-m", "uvicorn", "rfwb.main:app", "--host", "127.0.0.1", "--port", String(port), "--log-level", "warning"], cwd: BACKEND };
}

function pythonPath() {
  if (process.env.RFWB_PYTHON) return process.env.RFWB_PYTHON;
  const venv = process.platform === "win32" ? path.join(BACKEND, ".venv", "Scripts", "python.exe") : path.join(BACKEND, ".venv", "bin", "python");
  return fs.existsSync(venv) ? venv : process.platform === "win32" ? "python" : "python3";
}

const DEV_PORT = 47615; // debe coincidir con frontend/vite.config.ts

/** Puerto efímero libre asignado por el sistema operativo (evita choques con otras aplicaciones). */
function ephemeralPort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once("error", reject);
    srv.listen(0, "127.0.0.1", () => { const p = srv.address().port; srv.close(() => resolve(p)); });
  });
}

/** true sólo si en ese puerto responde ESTE motor (no cualquier servidor HTTP). */
function health(port) {
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port, path: "/api/health", timeout: 1500 }, (res) => {
      let body = "";
      res.on("data", (d) => { body += d; });
      res.on("end", () => {
        try { const j = JSON.parse(body); resolve(res.statusCode === 200 && j.status === "ok" && "skrf" in j); } catch { resolve(false); }
      });
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

async function startBackend() {
  // En desarrollo Vite redirige /api a DEV_PORT; en producción, puerto efímero (o RFWB_PORT si se define).
  const port = DEV_URL ? DEV_PORT : Number(process.env.RFWB_PORT) || (await ephemeralPort());
  if (DEV_URL && (await health(port))) return port; // motor ya en marcha (p. ej. arrancado a mano)
  const dataDir = path.join(app.getPath("userData"), "data");
  fs.mkdirSync(dataDir, { recursive: true });
  const eng = engineCommand(port);
  backend = spawn(eng.cmd, eng.args, {
    cwd: eng.cwd,
    env: { ...process.env, RFWB_DATA_DIR: dataDir, RFWB_UI_DIST: UI_DIST, PYTHONUNBUFFERED: "1" },
    windowsHide: true,
  });
  const keep = (d) => { backendLog = (backendLog + d.toString()).slice(-6000); };
  backend.stdout.on("data", keep);
  backend.stderr.on("data", keep);
  backend.on("exit", (code) => {
    backend = null;
    if (code && win && !app.isQuitting) dialog.showErrorBox("Motor RF detenido", `El motor de cálculo terminó (código ${code}).\n\n${backendLog.slice(-2000)}`);
  });
  for (let i = 0; i < 240; i++) { // hasta 60 s (primer arranque con antivirus puede ser lento)
    if (await health(port)) return port;
    if (!backend) break;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`No se pudo iniciar el motor RF.\nEjecutable: ${eng.cmd}\n\n${backendLog.slice(-2500)}`);
}

function stopBackend() {
  if (!backend) return;
  if (process.platform === "win32") execFile("taskkill", ["/pid", String(backend.pid), "/T", "/F"], () => {});
  else backend.kill("SIGTERM");
  backend = null;
}

const SPLASH = `data:text/html;charset=utf-8,${encodeURIComponent(`<html><body style="margin:0;background:#05080a;color:#7f9089;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh">
<div style="text-align:center"><div style="color:#2fe39a;letter-spacing:.3em;font-size:12px">RF ENGINEERING WORKBENCH</div><div style="margin-top:10px;font-size:12px">Iniciando motor de cálculo…</div></div></body></html>`)}`;

async function createWindow() {
  win = new BrowserWindow({
    width: 1600, height: 1000, minWidth: 1100, minHeight: 700, backgroundColor: "#05080a", title: "RF Engineering Workbench",
    autoHideMenuBar: true, show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.once("ready-to-show", () => win.show());
  win.webContents.setWindowOpenHandler(({ url }) => { if (/^https?:/.test(url)) shell.openExternal(url); return { action: "deny" }; });
  await win.loadURL(SPLASH);
  try {
    const port = await startBackend();
    if (!DEV_URL && !fs.existsSync(path.join(UI_DIST, "index.html"))) {
      throw new Error("No se encuentra la interfaz compilada (frontend/dist). Ejecute: npm run build:ui");
    }
    await win.loadURL(DEV_URL || `http://127.0.0.1:${port}/`);
  } catch (e) {
    dialog.showErrorBox("RF Engineering Workbench", String(e.message || e));
    app.quit();
  }
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
  app.whenReady().then(createWindow);
  app.on("before-quit", () => { app.isQuitting = true; stopBackend(); });
  app.on("window-all-closed", () => app.quit());
  process.on("exit", stopBackend);
}
