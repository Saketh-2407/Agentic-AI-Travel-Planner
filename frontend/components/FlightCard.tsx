import { ArrowRight, Plane } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StaggerItem } from "@/components/Stagger";
import type { FlightOffer } from "@/lib/types";

function formatDuration(iso: string) {
  const match = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?/);
  if (!match) return iso;
  const [, h, m] = match;
  return [h && `${h}h`, m && `${m}m`].filter(Boolean).join(" ");
}

export function FlightCard({ flight }: { flight: FlightOffer }) {
  const first = flight.segments[0];
  const origin = flight.origin ?? first?.from;
  const destination = flight.destination ?? first?.to;

  return (
    <StaggerItem>
      <Card className="gap-3">
        <CardContent className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="bg-aurora flex size-9 items-center justify-center rounded-full text-white">
              <Plane className="size-4" strokeWidth={1.75} />
            </div>
            <div>
              <p className="text-sm font-medium">
                {origin} <ArrowRight className="inline size-3.5 -translate-y-px text-muted-foreground" />{" "}
                {destination}
              </p>
              <p className="text-muted-foreground text-xs">
                {flight.carrier} · {formatDuration(flight.duration)} ·{" "}
                {flight.stops === 0 ? "nonstop" : `${flight.stops} stop${flight.stops > 1 ? "s" : ""}`}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="font-heading text-lg leading-tight">
              {flight.price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              <span className="text-muted-foreground ml-1 text-xs">{flight.currency}</span>
            </p>
            <Badge variant="secondary" className="mt-1 text-[10px]">
              Demo data
            </Badge>
          </div>
        </CardContent>
      </Card>
    </StaggerItem>
  );
}
