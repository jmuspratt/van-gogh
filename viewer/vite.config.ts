import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

// The pipeline writes everything the viewer loads to ../build/data (run pipeline/build.py and
// pipeline/texture.py first); serving ../build as the public dir makes it available at /data/...
export default defineConfig({
  publicDir: fileURLToPath(new URL("../build", import.meta.url)),
  server: { port: 5173 },
});
