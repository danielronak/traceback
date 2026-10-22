// Messages between the page and the engine worker.

export type Request =
  | { id: number; type: "check"; source: string }
  | { id: number; type: "run"; source: string }
  | { id: number; type: "exercise"; exerciseId: string; source: string };

export type WorkerMessage =
  | { type: "ready"; pythonVersion: string; exercises: string; crossOriginIsolated: boolean }
  | { type: "failed"; message: string }
  | { type: "result"; id: number; json: string }
  | { type: "error"; id: number; message: string }
  | { type: "output"; text: string }
  | { type: "input-request"; prompt: string }
  | { type: "input-unavailable" };

export interface InitMessage {
  type: "init";
  exercises: [origin: string, text: string][];
  // Shared memory for blocking input() and for Stop (absent without isolation).
  control?: SharedArrayBuffer; // Int32 [state, byteLength]
  data?: SharedArrayBuffer; // UTF-8 bytes of the answer
  interrupt?: SharedArrayBuffer; // Uint8 [signal], read by Pyodide
}

// control[0] states
export const IDLE = 0;
export const WAITING = 1;
export const ANSWERED = 2;
export const CANCELLED = 3;
export const INPUT_BYTES = 64 * 1024;
