import type { PipelineEvent } from "../types";

const EVENT_TYPES = [
  "stage_started",
  "progress",
  "chunk",
  "artifact",
  "log",
  "issue",
  "todo",
  "stage_finished",
  "job_failed",
  "job_finished",
  "job_cancelled",
];

const TERMINAL = new Set(["job_failed", "job_finished", "job_cancelled"]);

export interface Subscription {
  close: () => void;
}

/**
 * Follow one job's event stream.
 *
 * The server ends the stream with a terminal event, and it takes `from_seq` from
 * the query string rather than `Last-Event-ID` — so we always close the
 * connection ourselves instead of letting EventSource reconnect and replay.
 */
export function subscribeJobEvents(
  jobId: string,
  fromSeq: number,
  onEvent: (event: PipelineEvent) => void,
): Subscription {
  const source = new EventSource(`/api/jobs/${jobId}/events?from_seq=${fromSeq}`);
  let closed = false;

  const close = () => {
    if (closed) return;
    closed = true;
    source.close();
  };

  const handle = (raw: Event) => {
    let event: PipelineEvent;
    try {
      event = JSON.parse((raw as MessageEvent<string>).data) as PipelineEvent;
    } catch {
      return;
    }
    onEvent(event);
    if (TERMINAL.has(event.type)) close();
  };

  for (const type of EVENT_TYPES) {
    source.addEventListener(type, handle);
  }
  source.addEventListener("error", close);

  return { close };
}
