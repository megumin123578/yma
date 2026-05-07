import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import mkcert from "vite-plugin-mkcert";

const parsePort = (value, fallback) => {
  const port = Number(value);
  return Number.isInteger(port) && port > 0 ? port : fallback;
};

const truthy = (value) => /^(1|true|yes|on)$/i.test(String(value || "").trim());

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const host = env.VITE_HOST || env.HOST || "0.0.0.0";
  const port = parsePort(env.VITE_PORT || env.PORT, 3001);
  const proxyTarget = env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";
  const useHttps = truthy(env.VITE_HTTPS);

  return {
    plugins: [react(), useHttps && mkcert()].filter(Boolean),
    build: {
      outDir: "build",
    },
    server: {
      host,
      port,
      allowedHosts: ["app.tuanfmcaa.site"],
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
        "/uploads": {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    preview: {
      host,
      port: parsePort(env.VITE_PREVIEW_PORT, 4173),
    },
  };
});
