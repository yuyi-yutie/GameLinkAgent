import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { JobConsole } from "../components/JobConsole";
import { OptionsForm } from "../components/OptionsForm";
import { ReportView } from "../components/ReportView";
import { useJob } from "../hooks/useJob";
import { message } from "../lib/format";
import type { DesignerOptions } from "../types";

export interface AnalyzeOutcome {
  report: string | null;
  specs: string[];
  out: string | null;
}

interface Props {
  projectPath: string;
  choices: Record<string, string[]>;
  options: DesignerOptions | null;
  onOptions: (next: DesignerOptions) => void;
  onOutcome: (outcome: AnalyzeOutcome) => void;
  onNext: () => void;
}

export function AnalyzeStep({
  projectPath,
  choices,
  options,
  onOptions,
  onOutcome,
  onNext,
}: Props) {
  const job = useJob();
  const [report, setReport] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const outcome = job.outcome;
    if (!outcome) return;

    const reportPath = typeof outcome.report === "string" ? outcome.report : null;
    const specs = Array.isArray(outcome.specs) ? (outcome.specs as string[]) : [];
    const out = typeof outcome.out === "string" ? outcome.out : null;

    onOutcome({ report: reportPath, specs, out });
    if (!reportPath) return;
    api
      .artifact(reportPath)
      .then((artifact) => setReport(artifact.text))
      .catch((cause) => setLoadError(message(cause)));
  }, [job.outcome, onOutcome]);

  const start = useCallback(() => {
    if (!options) return;
    setReport(null);
    setLoadError(null);
    void job.start("analyze", {
      project: projectPath,
      options: { ...options },
      emit_specs: true,
    });
  }, [job, options, projectPath]);

  return (
    <div className="step-body">
      <section className="panel">
        <h3>生成选项</h3>
        <p className="muted small">
          这些选项直接决定规格与服务端代码，分析开始前设好即可。
        </p>
        {options ? (
          <OptionsForm
            choices={choices}
            value={options}
            disabled={job.running}
            onChange={onOptions}
          />
        ) : (
          <p className="muted">加载选项…</p>
        )}
        <div className="step-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={job.running || !options}
            onClick={start}
          >
            {job.running ? "分析中…" : "开始分析"}
          </button>
          {job.job?.status === "succeeded" && (
            <button type="button" className="btn" onClick={onNext}>
              下一步：审阅规格
            </button>
          )}
        </div>
      </section>

      <JobConsole
        job={job.job}
        events={job.events}
        stream={job.stream}
        running={job.running}
        error={job.error}
        onCancel={job.cancel}
      />

      {loadError && <p className="alert alert-bad">{loadError}</p>}
      {report && <ReportView source={report} title="分析报告" />}
    </div>
  );
}
