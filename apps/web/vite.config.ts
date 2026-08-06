import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

const proxyTarget = process.env.VITE_PROXY_TARGET || process.env.VITE_API_URL || "http://localhost:8100";

export default defineConfig({
  plugins: [tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": proxyTarget,
    },
  },
});
