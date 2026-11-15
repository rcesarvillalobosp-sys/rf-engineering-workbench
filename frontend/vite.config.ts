import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = process.env.RFWB_API ?? "http://127.0.0.1:47615";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy: { "/api": API } },
  build: { outDir: "dist", chunkSizeWarningLimit: 6000 },
});
