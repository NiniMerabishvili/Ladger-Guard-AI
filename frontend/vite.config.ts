import tailwindcss from "@tailwindcss/vite";
import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

function spaBypass(req: { method?: string; url?: string; headers: { accept?: string } }) {
  if (req.headers.accept?.includes("text/html")) {
    return "/index.html";
  }
  // Page route `/review` collides with API prefix `/review/{id}` — never proxy bare GET /review.
  const path = (req.url ?? "").split("?")[0];
  if (req.method === "GET" && path === "/review") {
    return "/index.html";
  }
  return undefined;
}

function toApi(path: string): [string, ProxyOptions] {
  return [path, { target: "http://127.0.0.1:8000", bypass: spaBypass }];
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    // Vercel injects this at build time so the UI can show which commit was deployed.
    __APP_COMMIT__: JSON.stringify(
      (process.env.VERCEL_GIT_COMMIT_SHA || process.env.npm_package_version || "local").slice(0, 7),
    ),
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      [
        "/ingest",
        "/reconcile",
        "/projects",
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
