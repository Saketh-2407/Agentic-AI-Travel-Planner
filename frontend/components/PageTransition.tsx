"use client";

import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { usePathname } from "next/navigation";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";

// `mode="wait"` fully unmounts the exiting page before the entering page
// mounts — no two pages are ever interactive at once. The /trips -> /trip/[id]
// shared-element transition still works across that gap: LayoutGroup keeps
// the last known rect for a given layoutId and animates the next element
// with the same id from there, even after a full unmount/remount.
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const reduceMotion = useReducedMotionSafe();

  return (
    <LayoutGroup>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={pathname}
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduceMotion ? undefined : { opacity: 0, y: -8 }}
          transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </LayoutGroup>
  );
}
