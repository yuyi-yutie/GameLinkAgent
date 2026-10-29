import { useMemo } from "react";

import type { JobStream } from "../hooks/useJob";
import { issueText, statusText } from "../lib/format";
import type { Job, PipelineEvent } from "../types";
import { STAGE_LABEL } from "./Stepper";
import { ArtifactList } from "./ArtifactList";

interface Props {
  job: Job | null;
  events: PipelineEvent[];
  stream: JobStream;
  running: boolean;
  error: string | null;
  onCancel?: () => void;
  showIssues?: boolean;
}

interface View {
  stage: string | null;
  progress: string;
  logs: string[];
  issues: { severity: string; message: string }[];
  todos: string[];
}

export function JobConsole({
  job,
  events,
  stream,
  running,
  error,
  onCancel,
  showIssues = true,
}: Props) {
  const view = useMemo<View>(() => {
    const result: View = { stage: null, progress: "", logs: [], issues: [], todos: [] };
    for (const event of events) {
      switch (event.type) {
        case "stage_started":
          result.stage = event.stage;
          break;
        case "progress":
          result.progress = String(event.data.message ?? "");
          break;
        case "log":
          result.logs.push(String(event.data.message ?? ""));
          break;
        case "issue":
          result.issues.push({
            severity: String(event.data.severity ?? "info"),
            message: String(event.data.message ?? ""),
          });
          break;
        case "todo":
          result.todos.push(String(event.data.message ?? ""));
          break;
        default:
          break;
      }
    }
    return result;
  }, [events]);

  if (!job && !error) return null;

  const stageLabel = view.stage
    ? (STAGE_LABEL[view.stage as keyof typeof STAGE_LABEL] ?? view.stage)
    : "准备中";
  const status = error ? "failed" : (job?.status ?? "running");
  const streamed = stream.reasoning.length + stream.content.length;

  return (
    <section className={`console${running ? " console-running" : ""}`}>
      <header className="console-head">
        <span className={`pill pill-${status}`}>{statusText(status)}</span>
        <span className="console-stage">{stageLabel}</span>
        {running && onCancel && (
          <button type="button" className="btn btn-danger" onClick={onCancel}>
            取消
          </button>
        )}
      </header>

      {view.progress && <p className="console-progress">{view.progress}</p>}

      {streamed > 0 && (
        <p className="console-progress muted">
          推理 {stream.reasoning.length.toLocaleString()} 字符 · 结构化输出{" "}
          {stream.content.length.toLocaleString()} 字符
        </p>
      )}

      {stream.reasoning.length > 0 && (
        <details className="stream">
          <summary>模型推理过程</summary>
          <pre>{stream.reasoning}</pre>
        </details>
      )}

      {view.logs.length > 0 && (
        <ul className="console-lines">
          {view.logs.map((line, index) => (
            <li key={`${index}-${line}`}>{line}</li>
          ))}
        </ul>
      )}

      {showIssues && view.issues.length > 0 && (
        <ul className="issues">
          {view.issues.map((issue, index) => (
            <li key={`${index}-${issue.message}`} className={`issue issue-${issue.severity}`}>
              <span className="issue-tag">{issueText(issue.severity)}</span>
              <span>{issue.message}</span>
            </li>
          ))}
        </ul>
      )}

      {view.todos.length > 0 && (
        <div className="todos">
          <h4>需要人工补全（refactors）</h4>
          <ul>
            {view.todos.map((todo) => (
              <li key={todo}>
                <code>{todo}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="alert alert-bad">{error}</p>}

      {job && <ArtifactList artifacts={job.artifacts} />}
    </section>
  );
}
