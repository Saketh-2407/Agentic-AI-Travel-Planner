"use client";

import { useEffect, useRef, useState } from "react";
import { animate } from "motion/react";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { BudgetBreakdown as BudgetBreakdownType } from "@/lib/types";

function CountUp({ value, prefix = "" }: { value: number; prefix?: string }) {
  const [display, setDisplay] = useState(0);
  const reduceMotion = useReducedMotionSafe();

  useEffect(() => {
    if (reduceMotion) {
      setDisplay(value);
      return;
    }
    const controls = animate(0, value, {
      duration: 1.1,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(v),
    });
    return () => controls.stop();
  }, [value, reduceMotion]);

  return (
    <span>
      {prefix}
      {display.toLocaleString(undefined, { maximumFractionDigits: 0 })}
    </span>
  );
}

export function BudgetBreakdown({ budget }: { budget: BudgetBreakdownType }) {
  const rows = [
    { label: "Flights", value: budget.flights, real: true },
    { label: "Stays (estimate)", value: budget.stays_estimate, real: false },
    { label: "Activities (estimate)", value: budget.activities_estimate, real: false },
  ];

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          {rows.map((row) => (
            <div key={row.label} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{row.label}</span>
              <span>
                <CountUp value={row.value} /> {budget.currency}
              </span>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between border-t border-white/10 pt-3">
          <span className="font-heading text-base">Total</span>
          <span className="font-heading text-2xl font-semibold text-[--accent-gold]">
            <CountUp value={budget.total} /> {budget.currency}
          </span>
        </div>
        <div className="flex items-start gap-2">
          <Badge variant="secondary" className="text-[10px] whitespace-nowrap">
            Estimate
          </Badge>
          <p className="text-muted-foreground text-xs">{budget.note}</p>
        </div>
      </CardContent>
    </Card>
  );
}
