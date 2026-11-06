import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const story = fileURLToPath(new URL("../../server/renderer/story/src", import.meta.url));     // Cartoon 2: the same engine source the renderer bundles

const target = process.env.VT_SERVER_URL || "http://127.0.0.1:8790";
// Browser tests only: VT_SERVER_KEY is a server's own key, sent with every proxied request so a test browser needs no pairing. Unset in normal use, so nothing changes.
const headers = process.env.VT_SERVER_KEY ? { Authorization: `Bearer ${process.env.VT_SERVER_KEY}` } : undefined;
// The server refuses a request that carries another site's Origin (a web page working through someone's browser). This proxy is the person's own tool, as the desktop app's proxy is, so it sends none.
const noOrigin = (proxy: any) => { proxy.on("proxyReq", (req: any) => req.removeHeader("origin")); proxy.on("proxyReqWs", (req: any) => req.removeHeader("origin")); };
const same = { target, changeOrigin: true, headers, configure: noOrigin };
export default defineConfig({
  plugins: [react(), {name:'client-server-identity',configureServer(server){server.middlewares.use('/__client/connection',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({server:target,role:'client'}));});}}],
  resolve: { alias: { "@story": story }, dedupe: ["react", "react-dom"] },
  server: {
    port: 5173,
    fs: { allow: ["..", story] },
    proxy: {
      "/api": same,
      "/media": same,
      "/bundled": same,
      "/.well-known": same,
      "/ws": { target: target.replace(/^http/, 'ws'), ws: true, headers, configure: noOrigin },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
