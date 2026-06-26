import {
  BedDouble,
  Building2,
  Camera,
  Castle,
  Coffee,
  Landmark,
  type LucideIcon,
  ShoppingBag,
  Sparkles,
  Sun,
  Trees,
  UtensilsCrossed,
  Wine,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StaggerItem, StaggerList } from "@/components/Stagger";
import type { ActivitySlot, ItineraryDay } from "@/lib/types";

const SLOT_ICONS: Record<ActivitySlot, LucideIcon> = {
  sight: Landmark,
  viewpoint: Camera,
  museum: Building2,
  park: Trees,
  cafe: Coffee,
  food: UtensilsCrossed,
  bar: Wine,
  activity: Sparkles,
  market: ShoppingBag,
  historic: Castle,
};

const SLOT_LABELS: Record<ActivitySlot, string> = {
  sight: "Sight",
  viewpoint: "Viewpoint",
  museum: "Museum",
  park: "Park",
  cafe: "Cafe",
  food: "Local food",
  bar: "Bar",
  activity: "Activity",
  market: "Market",
  historic: "Historic",
};

export function DayTimeline({ days }: { days: ItineraryDay[] }) {
  return (
    <StaggerList className="flex flex-col gap-3">
      {days.map((day) => (
        <StaggerItem key={day.day_number}>
          <Card>
            <CardContent className="flex gap-4">
              <div className="flex flex-col items-center pt-1">
                <div className="bg-aurora flex size-8 items-center justify-center rounded-full text-xs font-semibold text-white">
                  {day.day_number}
                </div>
              </div>
              <div className="flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <p className="text-sm font-medium">{day.theme}</p>
                  <p className="text-muted-foreground text-xs">{day.date}</p>
                </div>
                <p className="text-muted-foreground mt-0.5 text-xs">{day.area}</p>

                {day.weather_note && (
                  <p className="mt-1.5 flex items-center gap-1.5 text-xs text-[--accent-gold]">
                    <Sun className="size-3.5" /> {day.weather_note}
                  </p>
                )}

                <ul className="mt-3 flex flex-col gap-1.5">
                  {day.activities.map((a, i) => {
                    const Icon = SLOT_ICONS[a.slot] ?? Sparkles;
                    return (
                      <li key={i} className="flex items-center gap-2 text-sm">
                        <Icon className="size-3.5 shrink-0 text-[--aurora-to]" />
                        <span>{a.name}</span>
                        <Badge variant="outline" className="text-[10px] text-muted-foreground">
                          {SLOT_LABELS[a.slot]}
                        </Badge>
                      </li>
                    );
                  })}
                </ul>

                {day.suggested_hotel && (
                  <p className="mt-3 flex items-center gap-1.5 border-t border-white/10 pt-2 text-xs text-muted-foreground">
                    <BedDouble className="size-3.5 text-[--aurora-from]" />
                    Stay near: {day.suggested_hotel}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </StaggerItem>
      ))}
    </StaggerList>
  );
}
