"use client";

import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";

const ARC_PATH = "M 16 46 Q 150 -6, 284 46";

export function FlightArcHeader({ origin, destination }: { origin: string; destination: string }) {
  const reduceMotion = useReducedMotionSafe();

  return (
    <div className="glass flex items-center gap-4 rounded-xl px-5 py-3">
      <span className="font-heading text-sm font-medium">{origin}</span>
      <svg viewBox="0 0 300 56" className="h-9 flex-1" aria-hidden="true">
        <defs>
          <linearGradient id="flight-arc-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--aurora-from)" />
            <stop offset="100%" stopColor="var(--aurora-to)" />
          </linearGradient>
        </defs>
        <path
          d={ARC_PATH}
          fill="none"
          stroke="url(#flight-arc-grad)"
          strokeWidth={1.5}
          strokeDasharray="2 6"
          opacity={0.55}
        />
        <circle cx={16} cy={46} r={3} fill="var(--aurora-from)" />
        <circle cx={284} cy={46} r={3} fill="var(--aurora-to)" />
        {!reduceMotion && (
          <path d="M0 -4 L4 0 L0 4 L-1.2 0 Z" fill="white">
            <animateMotion dur="3.6s" repeatCount="indefinite" path={ARC_PATH} rotate="auto" />
          </path>
        )}
      </svg>
      <span className="font-heading text-sm font-medium">{destination}</span>
    </div>
  );
}
