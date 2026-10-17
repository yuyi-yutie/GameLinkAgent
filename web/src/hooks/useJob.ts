import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api";
import { subscribeJobEvents } from "../lib/sse";
import type { Job, PipelineEvent } from "../types";

export interface JobStream {
  reasoning: string;
  content: string;
}

export interface UseJob {
  job: Job | null;
  events: PipelineEvent[];
  /** Streamed model text, accumulated outside React state to avoid a render per token. */
  stream: JobStream;
  /** Payload of the most recent `stage_finished` — paths, counts, and so on. */
  outcome: Record<string, unknown> | null;
  running: boolean;
  error: string | null;
  start: (kind: string, params: Record<string, unknown>) => Promise<void>;
  cancel: () => Promise<void>;
  reset: () => void;
}

export function useJob(): UseJob {
  const [job, setJob] = useState<Job | null>(null);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [outcome, setOutcome] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, setTick] = useState(0);

  const streamRef = useRef<JobStream>({ reasoning: "", content: "" });
  const seqRef = useRef(0);
  const subscriptionRef = useRef<{ close: () => void } | null>(null);

  const running = job?.status === "queued" || job?.status === "running";

  useEffect(() => () => subscriptionRef.current?.close(), []);

  // Coalesce streamed tokens: ~4 re-renders a second instead of one per delta.
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 250);
    return () => window.clearInterval(timer);
  }, [running]);

  const start = useCallback(async (kind: string, params: Record<string, unknown>) => {
    subscriptionRef.current?.close();
    streamRef.current = { reasoning: "", content: "" };
    seqRef.current = 0;
    setEvents([]);
    setOutcome(null);
    setError(null);
    setJob(null);

    let created: Job;
    try {
      created = await api.submitJob(kind, params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      return;
    }

    setJob(created);
    subscriptionRef.current = subscribeJobEvents(created.id, 0, (event) => {
      if (event.seq <= seqRef.current) return;
      seqRef.current = event.seq;

      if (event.type === "chunk") {
        const kind = String(event.data.kind ?? "");
        const text = String(event.data.text ?? "");
        if (kind === "reasoning") streamRef.current.reasoning += text;
        else streamRef.current.content += text;
        return;
      }

      setEvents((previous) => [...previous, event]);
      if (event.type === "stage_finished") setOutcome(event.data);
      if (event.type === "job_failed") setError(String(event.data.error ?? "任务失败"));
      if (event.type.startsWith("job_")) {
        void api
          .job(created.id)
          .then(setJob)
          .catch(() => undefined);
      }
    });
  }, []);

  const cancel = useCallback(async () => {
    if (!job) return;
    await api.cancelJob(job.id).catch(() => undefined);
  }, [job]);

  const reset = useCallback(() => {
    subscriptionRef.current?.close();
    streamRef.current = { reasoning: "", content: "" };
    setJob(null);
    setEvents([]);
    setOutcome(null);
    setError(null);
  }, []);

  return { job, events, stream: streamRef.current, outcome, running, error, start, cancel, reset };
}
