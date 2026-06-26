"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { Check, Link2, Sparkles } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { getTrip, regenerateSummary } from "@/lib/api";
import type { TripDetail } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { TripResults } from "@/components/TripResults";

const STATUS_VARIANT: Record<TripDetail["status"], "default" | "secondary" | "destructive" | "outline"> = {
  done: "default",
  pending: "secondary",
  needs_clarification: "outline",
  error: "destructive",
};

export default function TripDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { session, loading } = useAuth();
  const router = useRouter();
  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !session) {
      router.push("/login");
    }
  }, [loading, session, router]);

  useEffect(() => {
    if (!session) return;
    getTrip(session.access_token, id)
      .then(setTrip)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load trip"));
  }, [session, id]);

  function handleCopyShareLink() {
    if (!trip) return;
    const url = `${window.location.origin}/share/${trip.share_id}`;
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleRegenerateSummary() {
    if (!session) return;
    setRegenerating(true);
    setRegenerateError(null);
    try {
      const { narrative_summary } = await regenerateSummary(session.access_token, id);
      setTrip((prev) => (prev && prev.results ? { ...prev, results: { ...prev.results, narrative_summary } } : prev));
    } catch (err) {
      setRegenerateError(err instanceof Error ? err.message : "Couldn't regenerate the summary — please try again.");
    } finally {
      setRegenerating(false);
    }
  }

  if (error) return <p className="text-destructive mx-auto max-w-2xl px-4 py-10">{error}</p>;

  if (!trip) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-10">
        <Skeleton className="mb-3 h-8 w-2/3" />
        <Skeleton className="mb-8 h-4 w-1/3" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  const results = trip.results;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <motion.div
        layoutId={`trip-surface-${id}`}
        transition={{ type: "spring", stiffness: 260, damping: 28 }}
        className="glass mb-8 rounded-xl px-5 py-4"
      >
        <motion.h1 layoutId={`trip-title-${id}`} className="font-heading text-2xl font-medium sm:text-3xl">
          {trip.title || trip.raw_query}
        </motion.h1>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge variant={STATUS_VARIANT[trip.status]}>{trip.status}</Badge>
            <p className="text-muted-foreground text-sm">{new Date(trip.created_at).toLocaleString()}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopyShareLink}
            className="min-h-11 sm:min-h-0"
          >
            {copied ? <Check className="size-3.5" /> : <Link2 className="size-3.5" />}
            {copied ? "Link copied" : "Copy share link"}
          </Button>
        </div>
      </motion.div>

      {!results && <p className="text-muted-foreground text-sm">This trip has no saved results yet.</p>}

      {results && !results.narrative_summary && trip.status === "done" && (
        <div className="glass mb-8 flex flex-wrap items-center justify-between gap-3 rounded-xl px-5 py-4">
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Sparkles className="size-4 text-[--accent-gold]" />
            This trip's closing summary didn't generate (quota was likely out mid-run).
          </p>
          <Button
            size="sm"
            disabled={regenerating}
            onClick={handleRegenerateSummary}
            className="cta-glow bg-aurora min-h-11 text-white hover:opacity-90 sm:min-h-0"
          >
            {regenerating ? "Regenerating…" : "Regenerate summary"}
          </Button>
        </div>
      )}
      {regenerateError && <p className="text-destructive mb-4 text-sm">{regenerateError}</p>}

      {results && (
        <TripResults
          flights={results.flights}
          stays={results.stays}
          activities={results.activities}
          itinerary={results.itinerary}
          budget={results.budget}
          narrativeSummary={results.narrative_summary}
          origin={trip.parsed?.origin}
          destination={trip.parsed?.destinations?.[0]}
        />
      )}
    </div>
  );
}
