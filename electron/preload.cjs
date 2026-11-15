// Puente mínimo y seguro entre la interfaz y el proceso principal (contextIsolation activo).
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("rfwb", {
  updates: {
    check: () => ipcRenderer.invoke("updates:check"),
    state: () => ipcRenderer.invoke("updates:state"),
  },
});
