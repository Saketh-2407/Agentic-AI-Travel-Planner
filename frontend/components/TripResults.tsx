import dynamic from "next/dynamic";
import { CheckCircle2, MapPin, XCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StaggerItem, StaggerList } from "@/components/Stagger";
import { FlightCard } from "@/components/FlightCard";
import { StayCard } from "@/components/StayCard";
import { DayTimeline } from "@/components/DayTimeline";
import { BudgetBreakdown } from "@/components/BudgetBreakdown";
import { TripSummary } from "@/components/TripSummary";
import { FlightArcHeader } from "@/components/FlightArcHeader";
import type {
  Activity,
  BudgetBreakdown as BudgetBreakdownType,
  CriticVerdict,
  FlightOffer,
  ItineraryDay,
  NarrativeSummary,
  Stay,
} from "@/lib/types";

const TripMap = dynamic(() => import("@/components/TripMap").then((m) => m.TripMap), { ssr: false });

// Trip-overview tiles in a bento grid: flights paired with budget, a
// full-width map for legibility, then a full-width stays band — followed by
// the linear itinerary (doesn't compress into a tile). The narrative summary
// is a wrap-up, not an intro: it closes the page, paired with the critic
// verdict, with the CTA below both.
export function TripResults({
  flights,
  stays,
  activities,
  itinerary,
  budget,
  narrativeSummary,
  origin,
  destination,
  criticVerdict,
  revisionCount,
  footer,
}: {
  flights: FlightOffer[];
  stays: Stay[];
  activities: Activity[];
  itinerary: ItineraryDay[];
  budget: BudgetBreakdownType;
  narrativeSummary: NarrativeSummary | null;
  origin?: string | null;
  destination?: string | null;
  criticVerdict?: CriticVerdict;
  revisionCount?: number;
  footer?: React.ReactNode;
}) {
  return (
    <StaggerList className="flex flex-col gap-8">
      <StaggerItem>
        <Badge variant="secondary" className="text-[11px]">
          Demo data — sandbox flights (Duffel test mode). Stay/activity costs are estimates.
        </Badge>
      </StaggerItem>

      <div className="grid gap-4 lg:grid-cols-3">
        <StaggerItem className="lg:col-span-2">
          <section>
            <h2 className="font-heading mb-3 text-lg">Flights ({flights.length})</h2>
            {origin && destination && (
              <div className="mb-3">
                <FlightArcHeader origin={origin} destination={destination} />
              </div>
            )}
            {flights.length === 0 ? (
              <p className="text-muted-foreground text-sm">No flight offers found for these dates.</p>
            ) : (
              <StaggerList className="flex flex-col gap-2">
                {flights.slice(0, 5).map((f) => (
                  <FlightCard key={f.offer_id} flight={f} />
                ))}
              </StaggerList>
            )}
          </section>
        </StaggerItem>

        <StaggerItem className="lg:col-span-1">
          <section>
            <h2 className="font-heading mb-3 text-lg">Budget</h2>
            <BudgetBreakdown budget={budget} />
          </section>
        </StaggerItem>

        <StaggerItem className="lg:col-span-3">
          <section>
            <h2 className="font-heading mb-3 flex items-center gap-1.5 text-lg">
              <MapPin className="size-4 text-[--aurora-to]" /> Route
            </h2>
            <TripMap stays={stays} activities={activities} itinerary={itinerary} />
          </section>
        </StaggerItem>

        <StaggerItem className="lg:col-span-3">
          <section>
            <h2 className="font-heading mb-3 text-lg">Stays ({stays.length})</h2>
            <StaggerList className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {stays.slice(0, 6).map((s) => (
                <StayCard key={s.hotel_id} stay={s} />
              ))}
            </StaggerList>
          </section>
        </StaggerItem>
      </div>

      <StaggerItem>
        <section>
          <h2 className="font-heading mb-3 text-lg">Itinerary</h2>
          <DayTimeline days={itinerary} />
        </section>
      </StaggerItem>

      {(narrativeSummary || criticVerdict) && (
        <div className="grid gap-4 lg:grid-cols-3">
          {narrativeSummary && (
            <StaggerItem className={criticVerdict ? "lg:col-span-2" : "lg:col-span-3"}>
              <section>
                <h2 className="font-heading mb-3 text-lg">Your trip</h2>
                <TripSummary summary={narrativeSummary} />
              </section>
            </StaggerItem>
          )}

          {criticVerdict && (
            <StaggerItem className={narrativeSummary ? "lg:col-span-1" : "lg:col-span-3"}>
              <section>
                <h2 className="font-heading mb-3 text-lg">Critic verdict</h2>
                <Card>
                  <CardContent className="flex flex-col gap-2">
                    <p className="flex items-center gap-2 text-sm font-medium">
                      {criticVerdict.passed ? (
                        <CheckCircle2 className="size-4 text-[--aurora-from]" />
                      ) : (
                        <XCircle className="size-4 text-amber-400" />
                      )}
                      {criticVerdict.passed ? "Passed" : "Did not fully pass"} — revisions: {revisionCount}
                    </p>
                    {criticVerdict.issues.length > 0 && (
                      <ul className="text-muted-foreground ml-5 list-disc text-sm">
                        {criticVerdict.issues.map((issue, i) => (
                          <li key={i}>{issue}</li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              </section>
            </StaggerItem>
          )}
        </div>
      )}

      {footer && <StaggerItem>{footer}</StaggerItem>}
    </StaggerList>
  );
}
