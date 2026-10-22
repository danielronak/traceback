/// <reference lib="webworker" />
// The engine worker: loads Pyodide and the pymentor package, then answers
// check / run / exercise requests from the page. Learner code runs here, so a
// hung program can never freeze the page, and the page can always terminate us.

import type { PyodideAPI } from "pyodide";
import bootstrap from "./bootstrap.py?raw";
import {
  ANSWERED,
  CANCELLED,
  IDLE,
  WAITING,
  type InitMessage,
  type Request,
  type WorkerMessage,
} from "./protocol";

declare const self: DedicatedWorkerGlobalScope;

// The engine's card patterns are tested against this Python version (D15, D25).
const EXPECTED_PYTHON = "3.14";

// The engine's own source, bundled at build time: one source of truth with the
// Python package, and no separate wheel to build.
const ENGINE_FILES = import.meta.glob("../../../engine/src/pymentor/**/*.{py,toml}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

let pyodide: PyodideAPI;
let api: Record<string, (...args: unknown[]) => string>;
let control: Int32Array | undefined;
let data: Uint8Array | undefined;

function post(message: WorkerMessage) {
  self.postMessage(message);
}

async function start(init: InitMessage) {
  const indexURL = new URL(`${import.meta.env.BASE_URL}pyodide/`, self.location.origin).href;
  const { loadPyodide } = (await import(/* @vite-ignore */ `${indexURL}pyodide.mjs`)) as typeof import("pyodide");
  pyodide = await loadPyodide({ indexURL });

  const version = pyodide.runPython("import sys; '%d.%d' % sys.version_info[:2]") as string;
  if (version !== EXPECTED_PYTHON) {
    throw new Error(`Pyodide ships Python ${version}, but the engine targets ${EXPECTED_PYTHON}.`);
  }

  for (const [path, text] of Object.entries(ENGINE_FILES)) {
    const relative = path.slice(path.indexOf("pymentor/"));
    const target = `/engine/${relative}`;
    pyodide.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
    pyodide.FS.writeFile(target, text);
  }
  const module = pyodide.globals.get("dict")();
  pyodide.runPython(bootstrap, { globals: module });
  api = Object.fromEntries(
    ["check", "run", "load_curriculum", "run_exercise"].map((name) => [name, module.get(name)]),
  );

  if (init.control && init.data && init.interrupt) {
    control = new Int32Array(init.control);
    data = new Uint8Array(init.data);
    pyodide.setInterruptBuffer(new Uint8Array(init.interrupt));
  }
  const curriculum = api.load_curriculum(JSON.stringify(init.curriculum));
  post({ type: "ready", pythonVersion: version, curriculum, crossOriginIsolated: control !== undefined });
}

// Called from Python's input(): block this worker until the page answers.
function ask(prompt: string): string | undefined {
  if (!control || !data) {
    post({ type: "input-unavailable" });
    return undefined;
  }
  flush(); // the prompt must be on screen before we wait
  Atomics.store(control, 0, WAITING);
  post({ type: "input-request", prompt });
  Atomics.wait(control, 0, WAITING);
  const state = Atomics.load(control, 0);
  const answer =
    state === ANSWERED ? new TextDecoder().decode(data.slice(0, Atomics.load(control, 1))) : undefined;
  Atomics.store(control, 0, IDLE);
  return state === CANCELLED ? undefined : answer;
}

// Output is batched: a loop printing thousands of lines would otherwise send
// thousands of messages and swamp the page. (Timers can't fire while Python
// runs, so we flush by elapsed time on each write, and once at the end.)
let pending = "";
let lastFlush = 0;
const FLUSH_MS = 50;
const FLUSH_BYTES = 4096;

function emit(text: string) {
  pending += text;
  const now = performance.now();
  if (pending.length >= FLUSH_BYTES || now - lastFlush >= FLUSH_MS) flush(now);
}

function flush(now = performance.now()) {
  lastFlush = now;
  if (!pending) return;
  post({ type: "output", text: pending });
  pending = "";
}

function handle(request: Request): string {
  switch (request.type) {
    case "check":
      return api.check(request.source);
    case "run":
      return api.run(request.source, ask, emit);
    case "exercise":
      return api.run_exercise(request.exerciseId, request.source);
  }
}

let started: Promise<void> | undefined;

self.onmessage = async (event: MessageEvent<InitMessage | Request>) => {
  const message = event.data;
  if (message.type === "init") {
    started = start(message).catch((error: unknown) => {
      post({ type: "failed", message: String(error instanceof Error ? error.message : error) });
    });
    return;
  }
  await started;
  try {
    const json = handle(message);
    flush();
    post({ type: "result", id: message.id, json });
  } catch (error) {
    flush();
    post({ type: "error", id: message.id, message: String(error) });
  }
};
