import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// CORS is already open on the backend, but proxy /api → :8000 so the app can be
// served from any origin without re-touching CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
