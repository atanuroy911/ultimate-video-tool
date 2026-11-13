// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/hooks/useFocusReturn.ts @ 9242a95. See src/occ/NOTICE.md.
import { useCallback, useRef } from 'react';

interface FocusReturn {
  remember: (restore: () => void) => void;
  restore: () => void;
}

export function useFocusReturn(): FocusReturn {
  const restoreRef = useRef<(() => void) | null>(null);
  const remember = useCallback((restore: () => void) => {
    restoreRef.current = restore;
  }, []);
  const restore = useCallback(() => {
    const callback = restoreRef.current;
    restoreRef.current = null;
    if (callback) requestAnimationFrame(callback);
  }, []);
  return { remember, restore };
}
