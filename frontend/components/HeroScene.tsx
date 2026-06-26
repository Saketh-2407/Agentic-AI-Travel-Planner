"use client";

import { motion, useMotionValue, useScroll, useSpring, useTransform } from "motion/react";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";

// The flight path starts lower-left (where the eye begins reading the badge
// and headline) and lands center-bottom, near where the CTA sits — the plane
// is flying toward the call to action, not just decorating the background.
// Cities sit in the corners so their connecting arcs frame the text column
// instead of cutting across it. Fixed coordinates (no randomness) so this
// renders identically on server and client.
const FLIGHT_PATH = "M 40 540 C 260 260, 520 560, 600 360";
const LANDING_POINT: [number, number] = [600, 360];
const CITIES: [number, number][] = [
  [110, 90],
  [1100, 110],
  [1100, 500],
];
const CLOUDS = [
  { cx: 180, cy: 110, rx: 90, ry: 26, delay: "0s", duration: "46s" },
  { cx: 820, cy: 70, rx: 120, ry: 30, delay: "-12s", duration: "58s" },
  { cx: 480, cy: 520, rx: 100, ry: 24, delay: "-30s", duration: "52s" },
];

export function HeroScene() {
  const reduceMotion = useReducedMotionSafe();

  // Cursor parallax: spring-smoothed pointer position drives a subtle
  // counter-translation on the scene, deepest layer (the plane) further out.
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springX = useSpring(mouseX, { stiffness: 50, damping: 18 });
  const springY = useSpring(mouseY, { stiffness: 50, damping: 18 });
  const parallaxX = useTransform(springX, [-0.5, 0.5], [-16, 16]);
  const parallaxY = useTransform(springY, [-0.5, 0.5], [-16, 16]);

  // Scroll-linked reveal: the scene drifts down and fades as the page scrolls
  // past the hero, reinforcing depth instead of just disappearing under the fold.
  const { scrollY } = useScroll();
  const scrollY1 = useTransform(scrollY, [0, 600], [0, 80]);
  const scrollOpacity = useTransform(scrollY, [0, 500], [1, 0.2]);

  function handlePointerMove(e: React.MouseEvent<HTMLDivElement>) {
    if (reduceMotion) return;
    const rect = e.currentTarget.getBoundingClientRect();
    mouseX.set((e.clientX - rect.left) / rect.width - 0.5);
    mouseY.set((e.clientY - rect.top) / rect.height - 0.5);
  }

  return (
    <motion.div
      onMouseMove={handlePointerMove}
      style={reduceMotion ? undefined : { y: scrollY1, opacity: scrollOpacity }}
      className="absolute inset-0 overflow-hidden"
      aria-hidden="true"
    >
      <motion.svg
        viewBox="0 0 1200 600"
        preserveAspectRatio="xMidYMid slice"
        className="h-full w-full"
        style={reduceMotion ? undefined : { x: parallaxX, y: parallaxY }}
      >
        <defs>
          <linearGradient id="aurora-stroke" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--aurora-from)" />
            <stop offset="100%" stopColor="var(--aurora-to)" />
          </linearGradient>
          <filter id="soft-blur">
            <feGaussianBlur stdDeviation="18" />
          </filter>
        </defs>

        {/* Drifting clouds */}
        {CLOUDS.map((cloud, i) => (
          <ellipse
            key={i}
            cx={cloud.cx}
            cy={cloud.cy}
            rx={cloud.rx}
            ry={cloud.ry}
            fill="white"
            opacity={0.05}
            filter="url(#soft-blur)"
            style={
              reduceMotion
                ? undefined
                : { animation: `hero-cloud-drift ${cloud.duration} linear infinite`, animationDelay: cloud.delay }
            }
          />
        ))}

        {/* Pulsing arcs between cities */}
        {CITIES.map((from, i) => {
          const to = CITIES[(i + 1) % CITIES.length];
          if (i === CITIES.length - 1) return null;
          const midX = (from[0] + to[0]) / 2;
          const midY = Math.min(from[1], to[1]) - 60;
          const d = `M ${from[0]} ${from[1]} Q ${midX} ${midY}, ${to[0]} ${to[1]}`;
          return (
            <path
              key={i}
              d={d}
              fill="none"
              stroke="url(#aurora-stroke)"
              strokeWidth={1.5}
              strokeDasharray="2 7"
              opacity={0.45}
              style={reduceMotion ? undefined : { animation: `hero-arc-pulse 3.4s ease-in-out infinite`, animationDelay: `${i * 0.8}s` }}
            />
          );
        })}
        {CITIES.map((city, i) => (
          <circle key={i} cx={city[0]} cy={city[1]} r={3} fill="var(--aurora-to)" opacity={0.7} />
        ))}

        {/* Contrail: the same path, dashed, with a flowing dash animation */}
        <path
          d={FLIGHT_PATH}
          fill="none"
          stroke="url(#aurora-stroke)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeDasharray="10 14"
          opacity={0.55}
          style={reduceMotion ? undefined : { animation: "hero-contrail-flow 3.2s linear infinite" }}
        />

        {/* Landing point glow: marks where the path arrives, near the CTA */}
        <circle
          cx={LANDING_POINT[0]}
          cy={LANDING_POINT[1]}
          r={5}
          fill="none"
          stroke="var(--aurora-to)"
          opacity={0.5}
          style={reduceMotion ? undefined : { animation: "hero-arc-pulse 3.4s ease-in-out infinite" }}
        />

        {/* The plane itself, gliding along the path and rotating to match it */}
        {!reduceMotion && (
          <g>
            <path d="M -7 0 L 7 0 L 2 -3.5 L 2 -7 L 0 -8 L -2 -7 L -2 -3.5 Z" fill="white">
              <animateMotion dur="9s" repeatCount="indefinite" path={FLIGHT_PATH} rotate="auto" />
            </path>
          </g>
        )}
        {reduceMotion && <circle cx={LANDING_POINT[0]} cy={LANDING_POINT[1]} r={4} fill="white" opacity={0.8} />}
      </motion.svg>
    </motion.div>
  );
}
