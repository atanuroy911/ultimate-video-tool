// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/hooks/usePersistedState.ts @ 9242a95. See src/occ/NOTICE.md.
import { useEffect, useState } from 'react';

// useState backed by localStorage: reads the saved value on init, writes on
// change. Errors (private mode / quota / bad JSON) fall back to `initial`.
export function usePersistedState<T>(key: string, initial: T): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw != null ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* ignore storage errors */
    }
  }, [key, value]);

  return [value, setValue];
}
