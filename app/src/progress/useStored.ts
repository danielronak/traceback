import { useEffect, useRef, useState } from "preact/hooks";
import type { KeyValueStore } from "./store";

/**
 * A value kept in the key-value store: loaded once, saved on every change.
 * `merge` combines the saved copy with anything recorded before it arrived.
 */
export function useStored<T>(store: KeyValueStore, key: string, empty: T, merge: (saved: T, now: T) => T) {
  const [value, setValue] = useState<T>(empty);
  const current = useRef(value);

  useEffect(() => {
    store.get<T>(key).then((saved) => {
      if (saved === undefined) return;
      current.current = merge(saved, current.current);
      setValue(current.current);
    });
  }, [store, key]);

  function update(change: (value: T) => T) {
    const next = change(current.current);
    if (next === current.current) return;
    current.current = next;
    setValue(next);
    store.set(key, next);
  }

  return [value, update] as const;
}
