export type ParsedTrip = {
  origin: string | null;
  destinations: string[];
  destination_names: string[];
  start_date: string | null;
  end_date: string | null;
  travelers: number;
  budget: number | null;
  currency: string;
  interests: string[];
  pace: string | null;
  constraints: string[];
  intent: "full_trip" | "flights_only" | "stays_only" | "activities_only";
  needs_clarification: boolean;
  clarify_question: string | null;
};

export type FlightOffer = {
  offer_id: string;
  carrier: string | null;
  price: number;
  currency: string;
  stops: number;
  duration: string;
  origin: string | null;
  destination: string | null;
  segments: {
    carrier: string | null;
    flight_number: string | null;
    from: string | null;
    to: string | null;
    departure_at: string | null;
    arrival_at: string | null;
  }[];
};

export type Stay = {
  hotel_id: string;
  name: string;
  lat: number | null;
  lon: number | null;
  checkin: string;
  checkout: string;
  price: number | null;
  currency: string | null;
};

export type Activity = {
  osm_id?: string;
  name: string;
  type: string | null;
  lat?: number | null;
  lon?: number | null;
  snippet?: string;
  url?: string;
  selectable?: boolean;
};

export type ActivitySlot =
  | "sight"
  | "viewpoint"
  | "museum"
  | "park"
  | "cafe"
  | "food"
  | "bar"
  | "activity"
  | "market"
  | "historic";

export type ItineraryActivity = {
  name: string;
  slot: ActivitySlot;
  note: string;
};

export type ItineraryDay = {
  day_number: number;
  date: string;
  theme: string;
  area: string;
  activities: ItineraryActivity[];
  suggested_hotel: string | null;
  weather_note: string | null;
};

export type NarrativeSummary = {
  overview: string;
  flights_section: string;
  stays_section: string;
  itinerary_section: string;
  budget_section: string;
  closing_summary: string;
};

export type BudgetBreakdown = {
  flights: number;
  stays_estimate: number;
  activities_estimate: number;
  total: number;
  currency: string;
  note: string;
};

export type CriticVerdict = {
  passed: boolean;
  groundedness_ok: boolean;
  budget_ok: boolean;
  day_balance_ok: boolean;
  variety_ok: boolean;
  issues: string[];
};

export type FinalResult = {
  parsed: ParsedTrip;
  flights: FlightOffer[];
  stays: Stay[];
  activities: Activity[];
  weather: { date: string; temp_max_c: number | null; temp_min_c: number | null }[];
  itinerary: ItineraryDay[];
  budget_breakdown: BudgetBreakdown;
  critic_verdict: CriticVerdict;
  narrative_summary: NarrativeSummary | null;
  revision_count: number;
  llm_calls: number;
};

export type Trip = {
  id: string;
  user_id: string;
  title: string | null;
  raw_query: string;
  parsed: ParsedTrip | null;
  status: "pending" | "needs_clarification" | "done" | "error";
  share_id: string;
  created_at: string;
};

export type TripDetail = Trip & {
  results: {
    trip_id: string;
    flights: FlightOffer[];
    stays: Stay[];
    activities: Activity[];
    itinerary: ItineraryDay[];
    budget: BudgetBreakdown;
    narrative_summary: NarrativeSummary | null;
    llm_calls: number;
  } | null;
};

export const PIPELINE_NODES = [
  "parser",
  "supervisor",
  "flight_agent",
  "stay_agent",
  "activities_agent",
  "planner",
  "critic",
  "finalizer",
] as const;

export type PipelineNode = (typeof PIPELINE_NODES)[number];
export type NodeStatus = "pending" | "running" | "done" | "error";
