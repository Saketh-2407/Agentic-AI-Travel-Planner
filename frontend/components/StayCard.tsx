import { BedDouble } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StaggerItem } from "@/components/Stagger";
import type { Stay } from "@/lib/types";

export function StayCard({ stay }: { stay: Stay }) {
  return (
    <StaggerItem>
      <Card className="gap-3">
        <CardContent className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="bg-aurora flex size-9 items-center justify-center rounded-full text-white">
              <BedDouble className="size-4" strokeWidth={1.75} />
            </div>
            <p className="text-sm font-medium">{stay.name}</p>
          </div>
          <Badge variant="secondary" className="text-[10px] whitespace-nowrap">
            Estimated cost
          </Badge>
        </CardContent>
      </Card>
    </StaggerItem>
  );
}
