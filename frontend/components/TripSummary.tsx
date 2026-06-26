import { BedDouble, BookOpen, PiggyBank, Plane, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { NarrativeSummary } from "@/lib/types";

function Row({ icon: Icon, label, children }: { icon: typeof Plane; label: string; children: string }) {
  return (
    <div className="flex gap-3">
      <Icon className="mt-0.5 size-4 shrink-0 text-[--aurora-to]" />
      <div>
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
        <p className="mt-0.5 text-sm leading-relaxed">{children}</p>
      </div>
    </div>
  );
}

export function TripSummary({ summary }: { summary: NarrativeSummary }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-5">
        <p className="font-heading text-lg leading-snug">{summary.overview}</p>

        <div className="flex flex-col gap-4">
          <Row icon={Plane} label="Flight">
            {summary.flights_section}
          </Row>
          <Row icon={BedDouble} label="Stay">
            {summary.stays_section}
          </Row>
          <Row icon={BookOpen} label="The trip">
            {summary.itinerary_section}
          </Row>
          <Row icon={PiggyBank} label="Budget">
            {summary.budget_section}
          </Row>
        </div>

        <div className="flex gap-3 rounded-xl border-l-2 border-[--accent-gold] bg-[--accent-gold]/[0.07] p-4">
          <Sparkles className="mt-0.5 size-4 shrink-0 text-[--accent-gold]" />
          <p className="text-sm leading-relaxed italic text-foreground/90">{summary.closing_summary}</p>
        </div>
      </CardContent>
    </Card>
  );
}
