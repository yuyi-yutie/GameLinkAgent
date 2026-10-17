export function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

export function clockTime(seconds: number | null): string {
  if (!seconds) return "—";
  return new Date(seconds * 1000).toLocaleTimeString();
}

export function duration(job: { started_at: number | null; finished_at: number | null }): string {
  if (!job.started_at) return "—";
  const end = job.finished_at ?? Date.now() / 1000;
  return `${(end - job.started_at).toFixed(1)}s`;
}

const STATUS_TEXT: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
  interrupted: "已中断",
};

export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status;
}

const ISSUE_TEXT: Record<string, string> = {
  error: "错误",
  warning: "疑似幻觉",
  info: "遗漏",
};

export function issueText(severity: string): string {
  return ISSUE_TEXT[severity] ?? severity;
}
