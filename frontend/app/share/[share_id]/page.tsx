"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Compass } from "lucide-react";
import { getSharedTrip } from "@/lib/api";
import type { TripDetail } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Magnetic } from "@/components/Magnetic";
import { TripResults } from "@/components/TripResults";

export default function SharedTripPage({ params }: { params: Promise<{ share_id: string }> }) {
  const { share_id } = use(params);
  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSharedTrip(share_id)
      .then(setTrip)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load this trip"));
  }, [share_id]);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-10 text-center">
        <p className="text-destructive text-sm">{error}</p>
        <p className="text-muted-foreground mt-2 text-sm">This share link may be invalid or the trip was removed.</p>
      </div>
    );
  }

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
      <div className="glass mb-8 rounded-xl px-5 py-4">
        <Badge variant="secondary" className="mb-2 gap-1.5 text-[11px]">
          <Compass className="size-3" /> Shared trip — viewing read-only
        </Badge>
        <h1 className="font-heading text-2xl font-medium sm:text-3xl">{trip.title || trip.raw_query}</h1>
        <p className="text-muted-foreground mt-2 text-sm">{new Date(trip.created_at).toLocaleDateString()}</p>
      </div>

      {!results && <p className="text-muted-foreground text-sm">This trip has no saved results yet.</p>}

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
          footer={
            <div className="flex justify-center">
              <Magnetic>
                <Button asChild size="lg" className="cta-glow bg-aurora text-white hover:opacity-90">
                  <Link href="/">
                    Plan your own trip <ArrowRight className="size-4" />
                  </Link>
                </Button>
              </Magnetic>
            </div>
          }
        />
      )}
    </div>
  );
}
