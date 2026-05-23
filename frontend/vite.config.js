import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/api": {
        // Allow overriding the proxy target for local development by
        // setting the API_PROXY_TARGET environment variable. In Docker
        // Compose this will typically be http://backend:8000, but for
        // local runs use http://localhost:8000
        target: process.env.API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
