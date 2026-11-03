import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const target = process.env.VT_SERVER_URL || "http://127.0.0.1:8790";
export default defineConfig({
  plugins: [react(), {name:'client-server-identity',configureServer(server){server.middlewares.use('/__client/connection',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({server:target,role:'client'}));});}}],
  server: {
    port: 5173,
    proxy: {
      "/api": target,
      "/media": target,
      "/bundled": target,
      "/.well-known": target,
      "/ws": { target: target.replace(/^http/, 'ws'), ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
