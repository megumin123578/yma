import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import mkcert from "vite-plugin-mkcert";
import { visualizer } from "rollup-plugin-visualizer";

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
  const enableVisualizer = truthy(env.ANALYZE) || mode === "analyze";

  return {
    plugins: [
      react(),
      useHttps && mkcert(),
      enableVisualizer &&
        visualizer({
          filename: "build/bundle-stats.html",
          template: "treemap",
          gzipSize: true,
          brotliSize: true,
          open: true,
        }),
    ].filter(Boolean),
    resolve: {
      dedupe: ["@emotion/react", "@emotion/styled", "react", "react-dom"],
    },
    optimizeDeps: {
      include: [
        "@emotion/react",
        "@emotion/styled",
        "@mui/material",
        "@mui/material/styles",
        "@mui/icons-material",
        "@mui/system",
        "@mui/x-data-grid",
        "@mui/x-date-pickers",
        "@mui/x-date-pickers/AdapterDayjs",
        "react",
        "react-dom",
        "react-router-dom",
        "react-pro-sidebar",
        "dayjs",
        "formik",
        "yup",
        "framer-motion",
      ],
    },
    build: {
      outDir: "build",
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes("node_modules")) return undefined;
            if (id.includes("/xlsx/")) return "vendor-xlsx";
            if (id.includes("/framer-motion/")) return "vendor-framer";
            if (id.includes("/recharts/")) return "vendor-recharts";
            if (id.includes("/@nivo/")) return "vendor-nivo";
            if (
              id.includes("/@mui/x-data-grid/") ||
              id.includes("/@mui/x-date-pickers/")
            ) {
              return "vendor-mui-x";
            }
            if (id.includes("/@mui/icons-material/")) return "vendor-mui-icons";
            if (
              id.includes("/@mui/material/") ||
              id.includes("/@mui/system/") ||
              id.includes("/@emotion/")
            ) {
              return "vendor-mui";
            }
            if (id.includes("/formik/") || id.includes("/yup/")) {
              return "vendor-forms";
            }
            if (
              id.includes("/react-router") ||
              id.includes("/react-dom/") ||
              id.includes("/scheduler/") ||
              /\/react\/(?!.*-)/.test(id)
            ) {
              return "vendor-react";
            }
            return undefined;
          },
        },
      },
    },
    server: {
      host,
      port,
      allowedHosts: ["app.tuanfmcaa.site", "fmc.tuanfmcaa.site"],
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
