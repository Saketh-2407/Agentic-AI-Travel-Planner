"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { ArrowRight, Luggage } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { listTrips } from "@/lib/api";
import type { Trip } from "@/lib/types";
import { CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerItem, StaggerList } from "@/components/Stagger";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";

const STATUS_VARIANT: Record<Trip["status"], "default" | "secondary" | "destructive" | "outline"> = {
  done: "default",
  pending: "secondary",
  needs_clarification: "outline",
  error: "destructive",
};

export default function TripsPage() {
  const { session, loading } = useAuth();
  const router = useRouter();
  const reduceMotion = useReducedMotionSafe();
  const [trips, setTrips] = useState<Trip[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !session) {
      router.push("/login");
    }
  }, [loading, session, router]);

  useEffect(() => {
    if (!session) return;
    listTrips(session.access_token)
      .then(setTrips)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load trips"));
  }, [session]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="font-heading text-2xl font-medium sm:text-3xl">My trips</h1>
      <p className="text-muted-foreground mt-1 mb-8 text-sm">Everything you&apos;ve asked the agents to plan.</p>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {!trips && !error && (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      )}

      {trips && trips.length === 0 && (
        <div className="glass flex flex-col items-center gap-2 rounded-2xl p-10 text-center">
          <Luggage className="text-muted-foreground size-6" />
          <p className="text-muted-foreground text-sm">No trips yet.</p>
          <Link href="/plan" className="text-sm text-[--aurora-to] hover:underline">
            Plan your first one
          </Link>
        </div>
      )}

      <StaggerList className="flex flex-col gap-3">
        {trips?.map((trip) => (
          <StaggerItem key={trip.id}>
            <Link href={`/trip/${trip.id}`} className="group block">
              <motion.div
                layoutId={`trip-surface-${trip.id}`}
                layout
                transition={{ type: "spring", stiffness: 260, damping: 28 }}
                whileHover={reduceMotion ? undefined : { y: -2 }}
                className="group/card flex flex-col gap-(--card-spacing) overflow-hidden rounded-xl bg-card py-(--card-spacing) text-sm text-card-foreground ring-1 ring-foreground/10 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.35)] [--card-spacing:--spacing(4)] transition-colors duration-200 group-hover:ring-[--aurora-to]/40 group-hover:bg-white/[0.06]"
              >
                <CardContent className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <motion.p layoutId={`trip-title-${trip.id}`} className="truncate text-sm font-medium">
                      {trip.title || trip.raw_query}
                    </motion.p>
                    <p className="text-muted-foreground mt-1 text-xs">
                      {new Date(trip.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={STATUS_VARIANT[trip.status]}>{trip.status}</Badge>
                    <ArrowRight className="text-muted-foreground size-4 shrink-0 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-[--aurora-to]" />
                  </div>
                </CardContent>
              </motion.div>
            </Link>
          </StaggerItem>
        ))}
      </StaggerList>
    </div>
  );
}
