"use client";

import { motion, type Variants } from "motion/react";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 26 } },
};

export function StaggerList({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduceMotion = useReducedMotionSafe();
  return (
    <motion.div
      initial={reduceMotion ? "show" : "hidden"}
      animate="show"
      variants={container}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div variants={item} className={className}>
      {children}
    </motion.div>
  );
}
