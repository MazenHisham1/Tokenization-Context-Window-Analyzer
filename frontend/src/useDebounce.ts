import { useEffect, useState } from "react";

/** Returns `value`, but only after it has stopped changing for `delayMs`.
 *  Typing "hello" then sends one request, not five. */
export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id); // a new keystroke cancels the previous timer
  }, [value, delayMs]);
  return debounced;
}
