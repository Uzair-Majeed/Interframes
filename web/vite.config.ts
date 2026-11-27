import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const webDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(webDirectory, "..");
// Docker builds contain only the web folder, while local development uses root .env.
const envDirectory = existsSync(path.join(repositoryRoot, ".env")) ? repositoryRoot : webDirectory;

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, envDirectory, "");
  const apiProxy = process.env.VITE_API_PROXY ?? fileEnv.VITE_API_PROXY ?? "http://localhost:8000";

  return {
    plugins: [react()],
    envDir: envDirectory,
    server: {
      proxy: {
        "/api/v1": apiProxy,
        "/health": apiProxy,
      },
    },
  };
});
