import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the OilShield frontend.
// The dev server proxies /api to the FastAPI backend (default http://localhost:8000)
// so the browser can call the API without CORS friction during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
