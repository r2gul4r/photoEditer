import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const port = Number(process.env.TONEPILOT_DESKTOP_PORT ?? process.env.VITE_PORT ?? 5173);
const strictPort = Boolean(process.env.TONEPILOT_DESKTOP_PORT ?? process.env.VITE_STRICT_PORT);

export default defineConfig({
  plugins: [react()],
  server: {
    port,
    host: "127.0.0.1",
    strictPort,
  },
});
