"use client";

import { AnimatePresence, motion } from "motion/react";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";
import {
  BedDouble,
  CalendarRange,
  CheckCircle2,
  MapPinned,
  Plane,
  ScanText,
  ShieldCheck,
  Sparkles,
  Workflow,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PIPELINE_NODES, type NodeStatus, type PipelineNode } from "@/lib/types";

const ICONS: Record<PipelineNode, LucideIcon> = {
  parser: ScanText,
  supervisor: Workflow,
  flight_agent: Plane,
  stay_agent: BedDouble,
  activities_agent: MapPinned,
  planner: CalendarRange,
  critic: ShieldCheck,
  finalizer: Sparkles,
};

const LABELS: Record<PipelineNode, string> = {
  parser: "Parser",
  supervisor: "Supervisor",
  flight_agent: "Flight agent",
  stay_agent: "Stay agent",
  activities_agent: "Activities agent",
  planner: "Planner",
  critic: "Critic",
  finalizer: "Finalizer",
};

function NodeOrb({
  status,
  Icon,
  reduceMotion,
}: {
  status: NodeStatus;
  Icon: LucideIcon;
  reduceMotion: boolean;
}) {
  return (
    <div className="relative flex size-11 shrink-0 items-center justify-center">
      {status === "running" && !reduceMotion && (
        <motion.span
          className="bg-aurora absolute inset-0 rounded-full"
          initial={{ opacity: 0.55, scale: 0.85 }}
          animate={{ opacity: 0, scale: 1.7 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <div
        className={cn(
          "relative flex size-11 items-center justify-center rounded-full border transition-colors duration-500",
          status === "pending" && "border-white/10 bg-white/[0.03] text-white/30",
          status === "running" &&
            "bg-aurora border-transparent text-white shadow-[0_0_22px_rgba(139,92,246,0.65)]",
          status === "done" &&
            "bg-aurora border-transparent text-white shadow-[0_0_12px_rgba(45,212,191,0.35)]",
          status === "error" && "border-red-400/50 bg-red-500/15 text-red-300"
        )}
      >
        {status === "done" ? (
          <CheckCircle2 className="size-5" />
        ) : status === "error" ? (
          <XCircle className="size-5" />
        ) : (
          <Icon className="size-5" strokeWidth={1.75} />
        )}
      </div>
    </div>
  );
}

function Connector({
  lit,
  flowing,
  reduceMotion,
}: {
  lit: boolean;
  flowing: boolean;
  reduceMotion: boolean;
}) {
  return (
    <svg className="my-1 h-9 w-0.5 flex-1 overflow-visible" viewBox="0 0 2 36" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="beam-grad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="var(--aurora-from)" />
          <stop offset="100%" stopColor="var(--aurora-to)" />
        </linearGradient>
      </defs>
      <path d="M1 0 L1 36" stroke="rgba(255,255,255,0.1)" strokeWidth={2} />
      <motion.path
        d="M1 0 L1 36"
        stroke="url(#beam-grad)"
        strokeWidth={2}
        strokeLinecap="round"
        initial={false}
        animate={{ pathLength: lit ? 1 : 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      />
      {flowing && !reduceMotion && (
        <motion.circle
          cx={1}
          r={2.5}
          fill="white"
          filter="blur(1px)"
          initial={{ cy: -4 }}
          animate={{ cy: 40 }}
          transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
        />
      )}
    </svg>
  );
}

export function PipelineViz({
  statuses,
  notes,
}: {
  statuses: Record<PipelineNode, NodeStatus>;
  notes?: Partial<Record<PipelineNode, string>>;
}) {
  const reduceMotion = useReducedMotionSafe();

  return (
    <div className="glass rounded-2xl p-5 sm:p-6" aria-label="Agent pipeline status">
      {PIPELINE_NODES.map((node, i) => {
        const status = statuses[node];
        const next = PIPELINE_NODES[i + 1];
        const lit = status === "done" || status === "running" || status === "error";
        const flowing = status === "done" && !!next && statuses[next] === "running";
        const isLast = i === PIPELINE_NODES.length - 1;

        return (
          <div key={node} className="flex gap-4">
            <div className="flex flex-col items-center">
              <NodeOrb status={status} Icon={ICONS[node]} reduceMotion={reduceMotion} />
              {!isLast && <Connector lit={lit} flowing={flowing} reduceMotion={reduceMotion} />}
            </div>
            <div className={cn("pt-1.5 transition-opacity duration-300", isLast ? "pb-1" : "pb-7", status === "pending" && "opacity-45")}>
              <p className="text-sm font-medium">{LABELS[node]}</p>
              <AnimatePresence mode="wait">
                {notes?.[node] ? (
                  <motion.p
                    key={notes[node]}
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-muted-foreground mt-0.5 text-xs"
                  >
                    {notes[node]}
                  </motion.p>
                ) : status === "running" ? (
                  <motion.p
                    key="working"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="mt-0.5 text-xs text-[--aurora-to]"
                  >
                    working…
                  </motion.p>
                ) : null}
              </AnimatePresence>
            </div>
          </div>
        );
      })}
    </div>
  );
}
