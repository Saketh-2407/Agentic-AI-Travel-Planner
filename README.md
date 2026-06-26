# Wayfare

**An agentic AI travel planner — describe a trip in plain language, watch a multi-agent system plan it live.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-frontend--flame--one--50.vercel.app-2dd4bf?style=for-the-badge)](https://frontend-flame-one-50.vercel.app) [![GitHub](https://img.shields.io/badge/GitHub-Saketh--2407%2FAgentic--AI--Travel--Planner-181717?style=for-the-badge&logo=github)](https://github.com/Saketh-2407/Agentic-AI-Travel-Planner)
[![Tech Stack](https://img.shields.io/badge/Stack-Next.js%20·%20FastAPI%20·%20LangGraph-8b5cf6?style=for-the-badge)](#tech-stack)

## What it is

Wayfare is a publicly accessible travel planner where you describe a trip — destination, dates,
budget, who's going, what you care about — and a graph of cooperating AI agents plans it: real
flight search, real places to stay and visit, a day-by-day itinerary, and a budget breakdown. The
whole pipeline streams live into an animated UI, node by node, so you watch the plan get built
instead of waiting on a spinner.

## Why it's genuinely agentic

This isn't a single prompt wrapped in a chat UI — it's a graph of specialized agents that make
real decisions and call real tools:

- **Dynamic routing**: a supervisor node reads the parsed intent and routes to only the agents a
  request actually needs (a "flights only" query never invokes the stay or activities agents).
- **Real tool-calling, not invented data**: flight search hits Duffel by actual route and date;
  places come from OpenStreetMap across 10 categories (sights, museums, parks, cafés, food, bars,
  markets, viewpoints, historic sites, and more); weather comes from Open-Meteo, with an automatic
  fallback to the same calendar dates one year prior for trips beyond the live forecast window;
  Tavily fills in qualitative "best things to do" context.
- **A self-correcting critic loop**: a deterministic critic re-checks every plan against the data
  actually retrieved. In a real run during development, the critic caught the planner LLM citing
  place names that didn't exist in the retrieved data — invented, not retrieved — and forced a
  revision rather than letting it through. That isn't a hypothetical; it's logged, real model
  output.
- **Human-in-the-loop clarification**: when a request is missing a destination or has dates too
  vague to resolve, the graph pauses (a LangGraph `interrupt()`) and asks — it doesn't guess and
  hallucinate a plan around a guess.
- **Long-term memory**: returning users' preferences (budget style, pace, interests) are recalled
  via pgvector similarity search and folded into future parsing, without overriding anything the
  current request states explicitly.

## Tech stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js (App Router), Tailwind CSS, Motion (Framer Motion), shadcn/ui, Leaflet |
| **Backend** | FastAPI, LangGraph, Python |
| **LLMs** | Gemini 2.5 Flash (primary) → Groq Llama 3.3 70B (fallback) → OpenRouter free models (tertiary) |
| **Data** | Duffel (flights, test mode), OpenStreetMap (places/stays), Open-Meteo (weather), Tavily (web enrichment) |
| **Infrastructure** | Supabase (Postgres + pgvector + Auth, RLS-scoped), Render (backend), Vercel (frontend), UptimeRobot (keep-warm) |

## Architecture

```
                              ┌───────────────┐
   raw query ───────────────▶ │    Parser     │  extracts trip details;
                              └──────┬────────┘  may interrupt() to ask for
                                     │            a missing destination/dates
                              ┌──────▼────────┐
                              │  Supervisor   │  routes by parsed intent
                              └──────┬────────┘
                  ┌──────────────────┼──────────────────┐
                  ▼                  ▼                  ▼
          ┌───────────────┐ ┌───────────────┐ ┌─────────────────────┐
          │ Flight Agent  │ │  Stay Agent   │ │  Activities Agent   │
          │   (Duffel)    │ │     (OSM)     │ │ (OSM + Open-Meteo   │
          │               │ │               │ │     + Tavily)       │
          └───────┬───────┘ └───────┬───────┘ └──────────┬──────────┘
                  └──────────────────┼────────────────────┘
                                     ▼
                              ┌───────────────┐
                              │    Planner    │  composes the day-by-day
                              └──────┬────────┘  itinerary from real data
                                     ▼
                     revise   ┌───────────────┐
                  ┌────────── │    Critic     │  deterministic: groundedness,
                  │  (≤ 2x)   └──────┬────────┘  budget, variety checks
                  │                  │ passed
                  └──────────────────┤
                                     ▼
                              ┌───────────────┐
                              │   Finalizer   │  narrates the validated plan
                              └───────────────┘
```

## Eval results

A 15-case eval harness (`backend/app/eval/`) runs the graph against real LLM calls — never a dev
cache or hand-seeded data — covering full trips, flights/stays/activities-only requests, vague
queries, missing/bad dates, a deliberately impossible over-budget stress case, and a known
zero-offer route.

| Metric | Result | Target |
|---|---|---|
| Groundedness (every named flight/hotel/place is real) | **100%** (hard requirement) | 100% |
| Clarification accuracy | **100%** | 100% |
| Budget adherence | **83%** (5/6) | 80% |
| Quality (LLM-as-judge, 1–5) | **2.5 avg** | — |

The one budget "failure" is the deliberately impossible stress case ($200 for 5 days in Paris with
fine dining and 5-star hotels — real cost came to $1,626); the critic correctly flags it rather
than pretending it fits. The quality score's spread is the meaningful part, not the average: 4/5 on
a clean, well-specified request, down to 1/5 on the cases designed to be hard to satisfy — a judge
that gave every case the same score would be the actual red flag.

## Running locally

**Backend:**

```bash
cd backend
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env   # fill in the keys below
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`backend/.env` needs:

```
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
DUFFEL_API_KEY=
TAVILY_API_KEY=
OSM_CONTACT_EMAIL=you@example.com
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=
SUPABASE_DB_URL=
ALLOWED_ORIGINS=http://localhost:3000
```

Visit `http://localhost:8000/health` — should return `{"status":"ok"}`.

**Frontend:**

```bash
cd frontend
npm install
copy .env.local.example .env.local   # fill in the keys below
npm run dev
```

`frontend/.env.local` needs:

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Visit `http://localhost:3000`.

**Eval harness:**

```bash
cd backend
.venv\Scripts\python.exe -m app.eval.run_eval --report-only
```

## Honest limits

- **Not a booking product.** Flights come from Duffel's *test* environment — real route-and-date
  offers under a sandbox airline, not live bookable inventory. The UI shows a "Demo data" badge on
  every flight result so this is never misread as a real fare.
- **Stay/activity costs are estimates**, not quotes — derived from OSM data, not a pricing API.
- **Free-tier LLM quota is real and finite.** Gemini's free tier caps at 20 requests/day per model;
  the Groq → OpenRouter fallback chain exists specifically to absorb that, not as a theoretical
  safety net — every fallback in this project has actually fired in production use.
- **Render's free tier cold-starts** after periods of inactivity; an UptimeRobot monitor pings
  `/health` every 10 minutes to keep the backend warm.

---

**Live demo**: [https://frontend-flame-one-50.vercel.app](https://frontend-flame-one-50.vercel.app)
