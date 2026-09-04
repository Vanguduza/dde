import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    // The workbench is hosted inside VS Code and Electron, both of which
    // serve it from a local origin, so a relative base keeps the bundle
    // portable between them.
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
  },
  base: "./",
});
