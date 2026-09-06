import tailwindcss from "@tailwindcss/vite";
import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

function spaBypass(req: { headers: { accept?: string } }) {
  if (req.headers.accept?.includes("text/html")) {
    return "/index.html";
  }
  return undefined;
}

function toApi(path: string): [string, ProxyOptions] {
  return [path, { target: "http://127.0.0.1:8000", bypass: spaBypass }];
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      [
        "/ingest",
        "/reconcile",
        "/transactions",
        "/decisions",
        "/review",
        "/metrics",
        "/webhook",
        "/health",
      ].map(toApi),
    ),
  },
});
