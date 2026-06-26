"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { PipelineViz } from "@/components/PipelineViz";
import { TripResults } from "@/components/TripResults";
import { Magnetic } from "@/components/Magnetic";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { answerTrip, createTrip, streamTrip, type SSEEvent } from "@/lib/api";
import { PIPELINE_NODES, type FinalResult, type NodeStatus, type PipelineNode } from "@/lib/types";
import { SAMPLE_PROMPTS } from "@/lib/samplePrompts";

type RunStatus = "idle" | "running" | "needs_clarification" | "done" | "error";

const initialStatuses: Record<PipelineNode, NodeStatus> = Object.fromEntries(
  PIPELINE_NODES.map((n) => [n, "pending"])
) as Record<PipelineNode, NodeStatus>;

const EXAMPLE_QUERY =
  "Plan a 4 day trip from JFK to Paris starting next month, budget $3000 for 2 travelers. We like museums and good food.";

export default function PlanPage() {
  const { session, loading } = useAuth();
  const router = useRouter();

  const [query, setQuery] = useState("");
  const [tripId, setTripId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [statuses, setStatuses] = useState(initialStatuses);
  const [notes, setNotes] = useState<Partial<Record<PipelineNode, string>>>({});
  const [clarifyQuestion, setClarifyQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [finalResult, setFinalResult] = useState<FinalResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !session) {
      router.push("/login");
    }
  }, [loading, session, router]);

  function setNodeStatus(node: PipelineNode, status: NodeStatus, note?: string) {
    setStatuses((prev) => ({ ...prev, [node]: status }));
    if (note) setNotes((prev) => ({ ...prev, [node]: note }));
  }

  function markRunningNodeAsError() {
    setStatuses((prev) => {
      const next = { ...prev };
      for (const node of PIPELINE_NODES) {
        if (next[node] === "running") next[node] = "error";
      }
      return next;
    });
  }

  async function consume(gen: AsyncGenerator<SSEEvent>) {
    for await (const evt of gen) {
      const data = evt.data as Record<string, unknown>;
      switch (evt.event) {
        case "clarify":
          setNodeStatus("parser", "done");
          setClarifyQuestion(data.question as string);
          setRunStatus("needs_clarification");
          break;
        case "parsed":
          setNodeStatus("parser", "done");
          setNodeStatus("supervisor", "done");
          break;
        case "agent_start":
          setNodeStatus(data.agent as PipelineNode, "running");
          break;
        case "agent_done":
          setNodeStatus(data.agent as PipelineNode, "done", data.summary as string);
          break;
        case "itinerary_partial":
          setNodeStatus("planner", "done");
          break;
        case "critic": {
          const verdict = data.verdict as { passed: boolean; issues: string[] };
          setNodeStatus(
            "critic",
            "done",
            verdict.passed ? "passed" : `revision ${data.revision} — ${verdict.issues.length} issue(s)`
          );
          if (!verdict.passed) {
            setNodeStatus("planner", "running");
          }
          break;
        }
        case "final":
          setNodeStatus("finalizer", "done");
          setFinalResult(data as unknown as FinalResult);
          setRunStatus("done");
          break;
        case "error":
          markRunningNodeAsError();
          setErrorMessage(data.message as string);
          setRunStatus("error");
          break;
      }
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    setRunStatus("running");
    setStatuses(initialStatuses);
    setNotes({});
    setFinalResult(null);
    setErrorMessage(null);
    setClarifyQuestion(null);
    setNodeStatus("parser", "running");

    try {
      const { trip_id } = await createTrip(session.access_token, query);
      setTripId(trip_id);
      const gen = await streamTrip(session.access_token, trip_id);
      await consume(gen);
    } catch (err) {
      markRunningNodeAsError();
      setErrorMessage(err instanceof Error ? err.message : "Something went wrong");
      setRunStatus("error");
    }
  }

  async function handleAnswer(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !tripId) return;
    setRunStatus("running");
    setClarifyQuestion(null);
    setNodeStatus("parser", "running");

    try {
      const gen = await answerTrip(session.access_token, tripId, answer);
      await consume(gen);
    } catch (err) {
      markRunningNodeAsError();
      setErrorMessage(err instanceof Error ? err.message : "Something went wrong");
      setRunStatus("error");
    }
  }

  const showForm = runStatus === "idle" || runStatus === "error";
  const showPipeline = runStatus !== "idle";
  const isInitial = runStatus === "idle";

  if (isInitial) {
    return (
      <div className="mx-auto flex min-h-[calc(100dvh-8rem)] max-w-2xl items-center px-4 py-10">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full"
        >
          <Card>
            <CardContent className="flex flex-col gap-6 py-2">
              <div className="text-center">
                <h1 className="font-heading text-2xl font-medium sm:text-3xl">Plan a trip</h1>
                <p className="text-muted-foreground mx-auto mt-2 max-w-md text-sm">
                  Describe where, when, who, and what you care about — the agents fill in the rest.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                <Textarea
                  required
                  rows={6}
                  placeholder={EXAMPLE_QUERY}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="text-base"
                />
                <Magnetic className="self-center">
                  <Button type="submit" size="lg" className="cta-glow bg-aurora text-white hover:opacity-90">
                    Plan my trip <ArrowRight className="size-4" />
                  </Button>
                </Magnetic>
              </form>

              <div className="flex flex-col items-center gap-3 border-t border-white/10 pt-5">
                <p className="text-muted-foreground text-xs tracking-wide uppercase">Try something like</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {SAMPLE_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => setQuery(prompt)}
                      className="glass min-h-11 cursor-pointer rounded-full px-4 py-1.5 text-xs text-foreground/80 transition-colors duration-200 hover:bg-white/[0.08] hover:text-foreground"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-heading text-2xl font-medium sm:text-3xl">Plan a trip</h1>
      <p className="text-muted-foreground mt-1 mb-8 text-sm">
        Describe where, when, who, and what you care about — the agents fill in the rest.
      </p>

      <div className="grid gap-8 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col gap-6 lg:sticky lg:top-20 lg:self-start">
          {showForm && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <Card>
                <CardContent>
                  <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                    <Textarea
                      required
                      rows={5}
                      placeholder={EXAMPLE_QUERY}
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                    <Magnetic strength={10} className="self-start">
                      <Button type="submit" className="cta-glow bg-aurora text-white hover:opacity-90">
                        Plan my trip <ArrowRight className="size-4" />
                      </Button>
                    </Magnetic>
                  </form>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {errorMessage && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass flex items-start gap-2 rounded-xl p-4 text-sm">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-400" />
              <p>
                Busy or out of free quota right now — please try again shortly.
                <span className="text-muted-foreground mt-1 block text-xs">{errorMessage}</span>
              </p>
            </motion.div>
          )}

          {showPipeline && <PipelineViz statuses={statuses} notes={notes} />}

          {runStatus === "needs_clarification" && clarifyQuestion && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <Card>
                <CardContent>
                  <form onSubmit={handleAnswer} className="flex flex-col gap-3">
                    <p className="text-sm font-medium">{clarifyQuestion}</p>
                    <Input
                      required
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                      placeholder="Your answer"
                    />
                    <Button type="submit" className="bg-aurora self-start text-white hover:opacity-90">
                      Continue
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </div>

        <div className="min-w-0">
          {finalResult ? (
            <TripResults
              flights={finalResult.flights}
              stays={finalResult.stays}
              activities={finalResult.activities}
              itinerary={finalResult.itinerary}
              budget={finalResult.budget_breakdown}
              narrativeSummary={finalResult.narrative_summary}
              origin={finalResult.parsed.origin}
              destination={finalResult.parsed.destinations[0]}
              criticVerdict={finalResult.critic_verdict}
              revisionCount={finalResult.revision_count}
              footer={
                <Magnetic className="self-start">
                  <Button onClick={() => router.push("/trips")} className="cta-glow bg-aurora text-white hover:opacity-90">
                    View in trip history <ArrowRight className="size-4" />
                  </Button>
                </Magnetic>
              }
            />
          ) : (
            !showForm && (
              <div className="text-muted-foreground flex h-40 items-center text-sm">
                Watching the agents work — results will appear here as they stream in.
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
