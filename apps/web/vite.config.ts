/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(() => {
  const runtimeEnvironment = (
    globalThis as typeof globalThis & {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process?.env;
  const apiOrigin =
    runtimeEnvironment?.WSC_API_ORIGIN ?? "http://127.0.0.1:8000";
  const webPort = Number(runtimeEnvironment?.WSC_WEB_PORT ?? "5173");
  const websocketOrigin = apiOrigin.replace(/^http/, "ws");
  return {
    plugins: [react()],
    server: {
      port: webPort,
      proxy: {
        "/healthz": apiOrigin,
        "/api": apiOrigin,
        "/ws": { target: websocketOrigin, ws: true },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test-setup.ts"],
      exclude: ["e2e/**", "node_modules/**", "dist/**"],
    },
  };
});
