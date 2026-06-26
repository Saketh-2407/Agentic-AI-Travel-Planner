"use client";

import { useEffect, useMemo, useRef } from "react";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";
import { useReducedMotionSafe } from "@/lib/useReducedMotionSafe";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Activity, ItineraryDay, Stay } from "@/lib/types";

const DARK_TILES = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const ATTRIBUTION =
  '&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const PLANE_GLIDE_DURATION_MS = 7000;
const DRAW_IN_DELAY_MS = 1300;

// Day 1 reads teal, the last day reads violet — lets the eye group pins by
// day at a glance without needing a line drawn between every single stop.
function dayColor(dayIndex: number, totalDays: number): string {
  const t = totalDays > 1 ? dayIndex / (totalDays - 1) : 0;
  const from = [45, 212, 191]; // aurora-from #2dd4bf
  const to = [139, 92, 246]; // aurora-to #8b5cf6
  const mix = from.map((c, i) => Math.round(c + (to[i] - c) * t));
  return `rgb(${mix.join(",")})`;
}

function activityIcon(delayMs: number, color: string) {
  return L.divIcon({
    className: "",
    html: `<div class="map-marker map-marker-activity" style="animation-delay:${delayMs}ms;background:${color};box-shadow:0 0 8px ${color}99,0 0 2px rgba(255,255,255,0.6)"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

function hotelIcon(delayMs: number) {
  return L.divIcon({
    className: "",
    html: `<div class="map-marker map-marker-hotel" style="animation-delay:${delayMs}ms"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 13);
    } else {
      map.fitBounds(L.latLngBounds(points), { padding: [32, 32] });
    }
  }, [map, points]);
  return null;
}

/** Same polyline, but its SVG path "draws in" (stroke-dashoffset 0) on mount
 * instead of just appearing — grabs the underlying Leaflet path DOM node via
 * ref, which react-leaflet forwards through for path layers. */
function DrawnPolyline({
  positions,
  pathOptions,
  reduceMotion,
  durationMs = 1300,
}: {
  positions: [number, number][];
  pathOptions: L.PathOptions;
  reduceMotion: boolean;
  durationMs?: number;
}) {
  const ref = useRef<L.Polyline | null>(null);

  useEffect(() => {
    const layer = ref.current;
    const el = layer?.getElement() as SVGPathElement | null | undefined;
    if (!el) return;
    if (reduceMotion) return;

    const length = el.getTotalLength();
    el.style.transition = "none";
    el.style.strokeDasharray = `${length}`;
    el.style.strokeDashoffset = `${length}`;
    // force a reflow so the transition below actually animates from this state
    el.getBoundingClientRect();
    el.style.transition = `stroke-dashoffset ${durationMs}ms ease-out`;
    requestAnimationFrame(() => {
      el.style.strokeDashoffset = "0";
    });
  }, [reduceMotion, durationMs]);

  return <Polyline ref={ref} positions={positions} pathOptions={pathOptions} />;
}

function bearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const toDeg = (r: number) => (r * 180) / Math.PI;
  const dLon = toRad(lon2 - lon1);
  const y = Math.sin(dLon) * Math.cos(toRad(lat2));
  const x =
    Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) - Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLon);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

/** The hero moving object: a plane marker that glides along the route at
 * constant speed, rotated each frame to face its heading. Driven by raw
 * Leaflet (not react-leaflet's <Marker>) so position/rotation can update
 * every animation frame without a React re-render. */
function RoutePlane({ route, reduceMotion }: { route: [number, number][]; reduceMotion: boolean }) {
  const map = useMap();

  useEffect(() => {
    if (reduceMotion || route.length < 2) return;

    const icon = L.divIcon({
      className: "",
      html: '<div class="map-plane"><svg viewBox="0 0 20 20" width="20" height="20"><path d="M10 1 L15.5 17 L10 13.5 L4.5 17 Z" fill="white" stroke="#0a0e1a" stroke-width="0.6"/></svg></div>',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });
    const marker = L.marker(route[0], { icon, zIndexOffset: 1000 }).addTo(map);

    const segmentDistances: number[] = [];
    let total = 0;
    for (let i = 0; i < route.length - 1; i++) {
      const d = map.distance(route[i], route[i + 1]);
      segmentDistances.push(d);
      total += d;
    }

    let rafId = 0;
    let startTime: number | null = null;

    function frame(now: number) {
      if (startTime === null) startTime = now;
      const elapsed = (now - startTime) % PLANE_GLIDE_DURATION_MS;
      const t = elapsed / PLANE_GLIDE_DURATION_MS;
      const targetDist = t * total;

      let acc = 0;
      let segIndex = 0;
      while (segIndex < segmentDistances.length - 1 && acc + segmentDistances[segIndex] < targetDist) {
        acc += segmentDistances[segIndex];
        segIndex++;
      }
      const segStart = route[segIndex];
      const segEnd = route[segIndex + 1] ?? route[segIndex];
      const segLen = segmentDistances[segIndex] || 1;
      const segT = Math.min(Math.max((targetDist - acc) / segLen, 0), 1);

      const lat = segStart[0] + (segEnd[0] - segStart[0]) * segT;
      const lon = segStart[1] + (segEnd[1] - segStart[1]) * segT;
      marker.setLatLng([lat, lon]);

      const heading = bearing(segStart[0], segStart[1], segEnd[0], segEnd[1]);
      const el = marker.getElement()?.querySelector(".map-plane") as HTMLElement | null;
      if (el) el.style.transform = `rotate(${heading}deg)`;

      rafId = requestAnimationFrame(frame);
    }

    const timeout = setTimeout(() => {
      rafId = requestAnimationFrame(frame);
    }, DRAW_IN_DELAY_MS);

    return () => {
      clearTimeout(timeout);
      cancelAnimationFrame(rafId);
      marker.remove();
    };
  }, [map, route, reduceMotion]);

  return null;
}

export function TripMap({
  stays,
  activities,
  itinerary,
}: {
  stays: Stay[];
  activities: Activity[];
  itinerary: ItineraryDay[];
}) {
  const reduceMotion = useReducedMotionSafe();

  const activityCoords = useMemo(() => {
    const byName = new Map<string, [number, number]>();
    for (const a of activities) {
      if (typeof a.lat === "number" && typeof a.lon === "number") {
        byName.set(a.name, [a.lat, a.lon]);
      }
    }
    return byName;
  }, [activities]);

  // Pins for every stop, color-coded by day — but the connecting line only
  // runs between each day's center point. Connecting every single stop in
  // plan order zigzags across the whole city; a day-to-day line reads as a
  // calm "journey across the week" instead of a tangle.
  const dayPins = useMemo(() => {
    const days: { pos: [number, number]; dayIndex: number }[][] = [];
    itinerary.forEach((day, dayIndex) => {
      const pins: { pos: [number, number]; dayIndex: number }[] = [];
      for (const act of day.activities) {
        const coords = activityCoords.get(act.name);
        if (coords) pins.push({ pos: coords, dayIndex });
      }
      if (pins.length > 0) days.push(pins);
    });
    return days;
  }, [itinerary, activityCoords]);

  const allPins = useMemo(() => dayPins.flat(), [dayPins]);
  const totalDays = dayPins.length;

  const dayAnchors = useMemo<[number, number][]>(
    () =>
      dayPins.map((pins) => {
        const lat = pins.reduce((sum, p) => sum + p.pos[0], 0) / pins.length;
        const lon = pins.reduce((sum, p) => sum + p.pos[1], 0) / pins.length;
        return [lat, lon];
      }),
    [dayPins]
  );

  const hotel = stays.find((s) => typeof s.lat === "number" && typeof s.lon === "number");

  const allPoints = useMemo(() => {
    const pts = allPins.map((p) => p.pos);
    if (hotel && hotel.lat && hotel.lon) pts.push([hotel.lat, hotel.lon]);
    return pts;
  }, [allPins, hotel]);

  if (allPoints.length === 0) {
    return (
      <div className="glass flex h-64 items-center justify-center rounded-2xl text-sm text-muted-foreground">
        No mappable locations for this trip yet.
      </div>
    );
  }

  return (
    <div className="glass overflow-hidden rounded-2xl">
      <MapContainer
        center={allPoints[0]}
        zoom={13}
        scrollWheelZoom={false}
        style={{ height: "320px", width: "100%", background: "#0a0e1a" }}
      >
        <TileLayer url={DARK_TILES} attribution={ATTRIBUTION} />
        <FitBounds points={allPoints} />

        {dayAnchors.length > 1 && (
          <>
            <DrawnPolyline
              positions={dayAnchors}
              pathOptions={{ color: "#a5b4d6", weight: 1.5, opacity: 0.4, dashArray: "1 8" }}
              reduceMotion={reduceMotion}
            />
            <RoutePlane route={dayAnchors} reduceMotion={reduceMotion} />
          </>
        )}

        {allPins.map((pin, i) => (
          <Marker
            key={`act-${i}`}
            position={pin.pos}
            icon={activityIcon(i * 60, dayColor(pin.dayIndex, totalDays))}
          />
        ))}
        {hotel && hotel.lat && hotel.lon && (
          <Marker position={[hotel.lat, hotel.lon]} icon={hotelIcon(allPins.length * 60)} />
        )}
      </MapContainer>
    </div>
  );
}
