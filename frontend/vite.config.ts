import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react],
  build: {
    rollupOptions: {
      input: {
        landing: "index.html",
        signin: "signin.html",
        dashboard: "dashboard.html",
      },
    },
  },
  server: {
    proxy: {
      "/api": process.env.PARAKH_API || "http://127.0.0.1:8000",
    },
  },
});
