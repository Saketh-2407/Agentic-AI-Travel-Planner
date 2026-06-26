"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArrowRight, Sparkles } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { HeroScene } from "@/components/HeroScene";
import { Magnetic } from "@/components/Magnetic";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";
import { SAMPLE_PROMPTS } from "@/lib/samplePrompts";

export default function LandingPage() {
  const { session, loading } = useAuth();
  const reduceMotion = useReducedMotionSafe();

  return (
    <div className="relative overflow-hidden">
      <HeroScene />
      {/* Scrim behind the text so contrast holds regardless of the scene under it. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 50% 35%, rgba(10,14,26,0.72) 0%, rgba(10,14,26,0.4) 55%, transparent 80%)",
        }}
      />

      <div className="relative z-10 mx-auto max-w-3xl px-4 py-24 text-center sm:py-32">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <Badge variant="secondary" className="mb-6 gap-1.5">
            <Sparkles className="size-3" /> Genuinely agentic, not a fixed pipeline
          </Badge>
          <h1 className="font-heading text-4xl leading-tight font-medium sm:text-5xl">
            Describe a trip. <span className="text-gradient">Watch it get planned, live.</span>
          </h1>
          <svg viewBox="0 0 160 20" className="mx-auto mt-1 h-4 w-40" aria-hidden="true">
            <defs>
              <linearGradient id="headline-arc-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="var(--aurora-from)" />
                <stop offset="100%" stopColor="var(--aurora-to)" />
              </linearGradient>
            </defs>
            <motion.path
              d="M 4 13 Q 60 3, 96 9 T 156 5"
              fill="none"
              stroke="url(#headline-arc-grad)"
              strokeWidth={2}
              strokeLinecap="round"
              initial={reduceMotion ? { pathLength: 1, opacity: 0.7 } : { pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 0.7 }}
              transition={{ duration: 0.9, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
            />
          </svg>
          <p className="text-muted-foreground mx-auto mt-4 max-w-xl text-balance">
            A multi-agent travel planner: real flight search, real places, a critic that catches
            budget overruns and hallucinated facts — and a pipeline you can watch build the plan,
            node by node.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mt-8"
        >
          {!loading && (
            <Magnetic>
              <Button asChild size="lg" className="cta-glow bg-aurora text-white hover:opacity-90">
                <Link href={session ? "/plan" : "/login"}>
                  {session ? "Plan a trip" : "Sign in to start"}
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            </Magnetic>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-14 flex flex-col items-center gap-2"
        >
          <p className="text-muted-foreground text-xs tracking-wide uppercase">Try something like</p>
          <div className="flex flex-wrap justify-center gap-2">
            {SAMPLE_PROMPTS.map((prompt) => (
              <span
                key={prompt}
                className="glass rounded-full px-4 py-1.5 text-xs text-foreground/80"
              >
                {prompt}
              </span>
            ))}
          </div>
        </motion.div>

        <p className="text-muted-foreground mt-16 text-xs">
          Demo data — sandbox flights via Duffel test mode, real OpenStreetMap places. Not a
          booking product.
        </p>
      </div>
    </div>
  );
}
