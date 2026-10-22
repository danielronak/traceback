// The page's handle on the engine worker.

import {
  ANSWERED,
  CANCELLED,
  INPUT_BYTES,
  type InitMessage,
  type Request,
  type WorkerMessage,
} from "./protocol";
import type { Exercise, ExerciseReport, Report } from "./types";

export interface ReadyInfo {
  pythonVersion: string;
  exercises: Exercise[];
  inputAvailable: boolean;
}

export interface RunHandlers {
  onOutput(text: string): void;
  onInputRequest(prompt: string): void;
  onInputUnavailable(): void;
}

// The engine stops runaway code itself (step budget and a 5 s limit, D8). This
// is the backstop for code that defeats it: after this much running time (not
// counting time waiting for input), the worker is terminated and restarted.
const HARD_LIMIT_MS = 15_000;

type Pending = { resolve: (json: string) => void; reject: (error: Error) => void };
type RequestBody = Request extends infer R ? (R extends Request ? Omit<R, "id"> : never) : never;

export class EngineClient {
  ready!: Promise<ReadyInfo>;
  private worker!: Worker;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private handlers: RunHandlers | undefined;
  private control?: Int32Array;
  private data?: Uint8Array;
  private interrupt?: Uint8Array;
  private watchdog?: { timer: number; remaining: number; startedAt: number };
  private waitingForInput = false;

  constructor(private exerciseFiles: [string, string][]) {
    this.start();
  }

  private start() {
    this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    const init: InitMessage = { type: "init", exercises: this.exerciseFiles };
    if (self.crossOriginIsolated) {
      init.control = new SharedArrayBuffer(8);
      init.data = new SharedArrayBuffer(INPUT_BYTES);
      init.interrupt = new SharedArrayBuffer(1);
      this.control = new Int32Array(init.control);
      this.data = new Uint8Array(init.data);
      this.interrupt = new Uint8Array(init.interrupt);
    }
    this.ready = new Promise((resolve, reject) => {
      this.worker.onmessage = (event: MessageEvent<WorkerMessage>) => {
        const message = event.data;
        switch (message.type) {
          case "ready":
            resolve({
              pythonVersion: message.pythonVersion,
              exercises: JSON.parse(message.exercises),
              inputAvailable: message.crossOriginIsolated,
            });
            break;
          case "failed":
            reject(new Error(message.message));
            break;
          default:
            this.receive(message);
        }
      };
      this.worker.onerror = (event) => reject(new Error(event.message || "The engine failed to start."));
    });
    this.worker.postMessage(init);
  }

  check(source: string): Promise<Report> {
    return this.request<Report>({ type: "check", source });
  }

  run(source: string, handlers: RunHandlers): Promise<Report> {
    this.handlers = handlers;
    if (this.interrupt) this.interrupt[0] = 0;
    this.armWatchdog();
    return this.request<Report>({ type: "run", source }).finally(() => {
      this.handlers = undefined;
      this.waitingForInput = false;
      this.disarmWatchdog();
    });
  }

  runExercise(exerciseId: string, source: string): Promise<ExerciseReport> {
    if (this.interrupt) this.interrupt[0] = 0;
    this.armWatchdog();
    return this.request<ExerciseReport>({ type: "exercise", exerciseId, source }).finally(() =>
      this.disarmWatchdog(),
    );
  }

  /** Answer the program's pending input(). */
  answer(text: string) {
    if (!this.control || !this.data) return;
    const bytes = new TextEncoder().encode(text).slice(0, INPUT_BYTES);
    this.data.set(bytes);
    Atomics.store(this.control, 1, bytes.length);
    this.waitingForInput = false;
    Atomics.store(this.control, 0, ANSWERED);
    Atomics.notify(this.control, 0);
    this.resumeWatchdog();
  }

  /** Ask the running program to stop, as Ctrl+C would. */
  stop() {
    if (!this.control || !this.interrupt) {
      this.restart("stopped"); // no shared memory: only a restart can stop it
    } else if (this.waitingForInput) {
      // Cancelling the wait is enough; input() then raises KeyboardInterrupt.
      this.waitingForInput = false;
      Atomics.store(this.control, 0, CANCELLED);
      Atomics.notify(this.control, 0);
    } else {
      this.interrupt[0] = 2; // SIGINT: Pyodide raises KeyboardInterrupt in the program
    }
  }

  private request<T>(body: RequestBody): Promise<T> {
    const id = this.nextId++;
    return new Promise<string>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ ...body, id } as Request);
    }).then((json) => JSON.parse(json) as T);
  }

  private receive(message: WorkerMessage) {
    switch (message.type) {
      case "result":
        this.pending.get(message.id)?.resolve(message.json);
        this.pending.delete(message.id);
        break;
      case "error":
        this.pending.get(message.id)?.reject(new Error(message.message));
        this.pending.delete(message.id);
        break;
      case "output":
        this.handlers?.onOutput(message.text);
        break;
      case "input-request":
        this.waitingForInput = true;
        this.pauseWatchdog();
        this.handlers?.onInputRequest(message.prompt);
        break;
      case "input-unavailable":
        this.handlers?.onInputUnavailable();
        break;
    }
  }

  // --- the hard-kill backstop --------------------------------------------------

  private armWatchdog() {
    this.watchdog = { timer: 0, remaining: HARD_LIMIT_MS, startedAt: 0 };
    this.resumeWatchdog();
  }

  private resumeWatchdog() {
    const dog = this.watchdog;
    if (!dog) return;
    dog.startedAt = performance.now();
    dog.timer = self.setTimeout(() => this.restart("killed"), dog.remaining);
  }

  private pauseWatchdog() {
    const dog = this.watchdog;
    if (!dog) return;
    self.clearTimeout(dog.timer);
    dog.remaining -= performance.now() - dog.startedAt;
  }

  private disarmWatchdog() {
    if (this.watchdog) self.clearTimeout(this.watchdog.timer);
    this.watchdog = undefined;
  }

  /** Terminate the worker and start a fresh one. Pending requests fail. */
  private restart(reason: "killed" | "stopped") {
    this.disarmWatchdog();
    this.worker.terminate();
    for (const { reject } of this.pending.values()) reject(new EngineRestarted(reason));
    this.pending.clear();
    this.start();
  }
}

export class EngineRestarted extends Error {
  constructor(public reason: "killed" | "stopped") {
    super(reason === "killed" ? "The program was stopped because it ran too long." : "Stopped.");
  }
}
