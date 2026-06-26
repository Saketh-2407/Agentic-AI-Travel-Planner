"use client";

import { Compass } from "lucide-react";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";

// A tall night-flight arc, fixed coordinates (no randomness) so server and
// client render identically — same technique as HeroScene, just portrait.
const ARC = "M 70 820 C 60 540, 360 420, 380 140";
const STARS: { top: string; left: string; size: number; delay: string }[] = [
  { top: "8%", left: "70%", size: 2, delay: "0s" },
  { top: "14%", left: "30%", size: 1, delay: "0.8s" },
  { top: "20%", left: "85%", size: 1, delay: "1.6s" },
  { top: "28%", left: "12%", size: 2, delay: "0.3s" },
  { top: "36%", left: "60%", size: 1, delay: "2.1s" },
  { top: "44%", left: "20%", size: 1, delay: "1.1s" },
  { top: "52%", left: "78%", size: 2, delay: "1.8s" },
  { top: "62%", left: "40%", size: 1, delay: "0.5s" },
  { top: "72%", left: "88%", size: 1, delay: "2.6s" },
  { top: "80%", left: "55%", size: 1, delay: "1.4s" },
];

export function AuthVisual() {
  const reduceMotion = useReducedMotionSafe();

  return (
    <div className="relative hidden overflow-hidden lg:block" aria-hidden="true">
      <svg viewBox="0 0 450 900" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
        <defs>
          <linearGradient id="auth-bg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#151c33" />
            <stop offset="100%" stopColor="#0a0e1a" />
          </linearGradient>
          <linearGradient id="auth-arc" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--aurora-from)" />
            <stop offset="100%" stopColor="var(--aurora-to)" />
          </linearGradient>
          <filter id="auth-blur">
            <feGaussianBlur stdDeviation="40" />
          </filter>
        </defs>

        <rect width="450" height="900" fill="url(#auth-bg)" />
        <circle cx="380" cy="140" r="170" fill="var(--aurora-to)" opacity="0.22" filter="url(#auth-blur)" />
        <circle cx="70" cy="820" r="150" fill="var(--aurora-from)" opacity="0.16" filter="url(#auth-blur)" />

        {STARS.map((star, i) => (
          <circle
            key={i}
            cx={(parseFloat(star.left) / 100) * 450}
            cy={(parseFloat(star.top) / 100) * 900}
            r={star.size}
            fill="white"
            style={
              reduceMotion
                ? { opacity: 0.5 }
                : { animation: `ambient-twinkle ${3 + (i % 4)}s ease-in-out infinite`, animationDelay: star.delay }
            }
          />
        ))}

        <path
          d={ARC}
          fill="none"
          stroke="url(#auth-arc)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeDasharray="2 9"
          opacity={0.55}
          style={reduceMotion ? undefined : { animation: "hero-arc-pulse 3.4s ease-in-out infinite" }}
        />

        {!reduceMotion && (
          <path d="M -6 0 L 6 0 L 2 -3 L 2 -6 L 0 -7 L -2 -6 L -2 -3 Z" fill="white">
            <animateMotion dur="7s" repeatCount="indefinite" path={ARC} rotate="auto" />
          </path>
        )}
        {reduceMotion && <circle cx="220" cy="480" r="3.5" fill="white" opacity={0.85} />}
      </svg>

      <div className="relative flex h-full flex-col justify-end p-10">
        <Compass className="mb-4 size-7 text-[--aurora-to]" strokeWidth={1.5} />
        <p className="font-heading max-w-xs text-2xl leading-snug text-white">
          Your next trip, <span className="text-gradient">assembled live.</span>
        </p>
        <p className="mt-3 max-w-xs text-sm text-white/55">
          Real flights, real places, and a critic that keeps it honest — sign in to watch the
          agents work.
        </p>
      </div>
    </div>
  );
}
