// Ported from OpenChatCut (AGPL-3.0-or-later, github.com/0xsline/OpenChatCut) src/shortcuts/useActionBindings.ts @ 9242a95. See src/occ/NOTICE.md.
import { useEffect, useRef } from 'react';
import {
  bindAction,
  type ActionHandler,
} from './actionRegistry';

export type ActionBindings = Partial<Record<string, ActionHandler>>;

export function useActionBindings(bindings: ActionBindings): void {
  const bindingsRef = useRef(bindings);
  bindingsRef.current = bindings;
  const signature = Object.keys(bindings).sort().join('\n');

  useEffect(() => {
    const cleanups = Object.keys(bindingsRef.current).map((id) =>
      bindAction(id, (context, trigger) => {
        bindingsRef.current[id]?.(context, trigger);
      }),
    );
    return () => cleanups.forEach((cleanup) => cleanup());
  }, [signature]);
}
