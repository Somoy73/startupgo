// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

// Production server (build only): Bun, as in the Docker image. FastAPI runs next to it in the same
// container on 127.0.0.1:8000, so /api is forwarded there, as the dev proxy does. A named constant because
// the preset's option type omits routeRules, which it passes on to Nitro as they are.
const productionServer = {
  preset: "bun",
  routeRules: { "/api/**": { proxy: "http://127.0.0.1:8000/api/**" } },
};

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  nitro: productionServer,
  vite: {
    server: {
      // Devcontainer on WSL: listen on all interfaces, and poll for file changes
      // (filesystem events don't reach the container reliably).
      host: "0.0.0.0",
      watch: { usePolling: true, interval: 100 },
      // The FastAPI backend (Backend/): `uv run uvicorn app.main:app --port 8000`.
      proxy: { "/api": "http://127.0.0.1:8000" },
    },
  },
});
