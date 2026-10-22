import { createHash } from "node:crypto";
import { createReadStream, readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import preact from "@preact/preset-vite";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..");
const pyodideDir = join(here, "node_modules", "pyodide");

// The Pyodide runtime files the app loads, served from our own origin so the
// app makes no third-party requests and works offline (principle 3).
const PYODIDE_FILES = [
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
];
const MIME: Record<string, string> = {
  ".mjs": "text/javascript",
  ".wasm": "application/wasm",
  ".zip": "application/zip",
  ".json": "application/json",
};

// input() needs SharedArrayBuffer, which needs cross-origin isolation (D9).
const ISOLATION_HEADERS = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "require-corp",
};

function pyodideAssets(): Plugin {
  return {
    name: "pymentor:pyodide-assets",
    configureServer(server) {
      server.middlewares.use("/pyodide/", (req, res, next) => {
        const name = (req.url ?? "").split("?")[0].replace(/^\//, "");
        if (!PYODIDE_FILES.includes(name)) return next();
        res.setHeader("Content-Type", MIME[name.slice(name.lastIndexOf("."))] ?? "application/octet-stream");
        res.setHeader("Cross-Origin-Resource-Policy", "same-origin");
        createReadStream(join(pyodideDir, name)).pipe(res);
      });
    },
    generateBundle() {
      for (const name of PYODIDE_FILES) {
        this.emitFile({ type: "asset", fileName: `pyodide/${name}`, source: readFileSync(join(pyodideDir, name)) });
      }
    },
  };
}

// A service worker generated at build time (no PWA dependency): it precaches
// every built file plus Pyodide so the app works offline after one visit, and
// adds the isolation headers itself for hosts that can't set them (D9, D26).
function serviceWorker(): Plugin {
  return {
    name: "pymentor:service-worker",
    apply: "build",
    enforce: "post",
    generateBundle(_options, bundle) {
      const publicFiles = readdirSync(join(here, "public")).filter((name) => !name.startsWith("_"));
      const files = [...Object.keys(bundle), ...publicFiles].filter((name) => name !== "sw.js").sort();
      const pyodideVersion = JSON.parse(readFileSync(join(pyodideDir, "package.json"), "utf8")).version;
      const version = createHash("sha256")
        .update(files.join("\n") + pyodideVersion)
        .digest("hex")
        .slice(0, 12);
      const urls = ["./", ...files.filter((name) => name !== "index.html")];
      const source = readFileSync(join(here, "src", "sw.template.js"), "utf8")
        .replace("__VERSION__", JSON.stringify(version))
        .replace("__PRECACHE__", JSON.stringify(urls));
      this.emitFile({ type: "asset", fileName: "sw.js", source });
    },
  };
}

export default defineConfig({
  plugins: [preact(), pyodideAssets(), serviceWorker()],
  server: { headers: ISOLATION_HEADERS, fs: { allow: [repoRoot] } },
  preview: { headers: ISOLATION_HEADERS },
  worker: { format: "es" },
  build: { target: "es2022" },
  test: { include: ["tests/unit/**/*.test.ts"] },
});
