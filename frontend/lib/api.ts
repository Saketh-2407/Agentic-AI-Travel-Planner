import type { NarrativeSummary, Trip, TripDetail } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function authedFetch(path: string, token: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init?.headers || {}), Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || `Request failed: ${res.status}`);
  }
  return res;
}

export async function createTrip(token: string, query: string): Promise<{ trip_id: string; thread_id: string }> {
  const res = await authedFetch("/trips", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  return res.json();
}

export async function listTrips(token: string): Promise<Trip[]> {
  const res = await authedFetch("/trips", token);
  return res.json();
}

export async function getTrip(token: string, tripId: string): Promise<TripDetail> {
  const res = await authedFetch(`/trips/${tripId}`, token);
  return res.json();
}

export async function getSharedTrip(shareId: string): Promise<TripDetail> {
  const res = await fetch(`${API_BASE}/share/${shareId}`);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function regenerateSummary(token: string, tripId: string): Promise<{ narrative_summary: NarrativeSummary }> {
  const res = await authedFetch(`/trips/${tripId}/regenerate-summary`, token, { method: "POST" });
  return res.json();
}

export type SSEEvent = { event: string; data: unknown };

/** Reads a `text/event-stream` response body and yields parsed {event, data} pairs. */
async function* parseSSEStream(res: Response): AsyncGenerator<SSEEvent> {
  if (!res.body) return;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex: number;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);

      let eventName = "message";
      let dataLine = "";
      for (const line of rawEvent.split("\n")) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
      }
      if (dataLine) {
        yield { event: eventName, data: JSON.parse(dataLine) };
      }
    }
  }
}

export async function streamTrip(token: string, tripId: string): Promise<AsyncGenerator<SSEEvent>> {
  const res = await authedFetch(`/trips/${tripId}/stream`, token);
  return parseSSEStream(res);
}

export async function answerTrip(token: string, tripId: string, answer: string): Promise<AsyncGenerator<SSEEvent>> {
  const res = await authedFetch(`/trips/${tripId}/answer`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
  return parseSSEStream(res);
}
