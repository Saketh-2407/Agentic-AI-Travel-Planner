"use client";

import { useEffect, useState } from "react";

/**
 * Framer Motion's own `useReducedMotion()` returns `undefined` during SSR
 * (no `window.matchMedia` on the server) and only resolves after mount —
 * for any component whose render output actually branches on it, that's a
 * server/client mismatch every time. This always starts at `false` (matching
 * what the server rendered) and corrects itself in an effect right after
 * mount, before the user has a chance to notice.
 */
export function useReducedMotionSafe(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
