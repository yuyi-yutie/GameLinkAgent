import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { JobConsole } from "../components/JobConsole";
import { ReportView } from "../components/ReportView";
import { useJob } from "../hooks/useJob";
import { message } from "../lib/format";

export interface DeployOutcome {
  dist: string;
  files: number;
}

interface Props {
  serverDir: string | null;
  onOutcome: (outcome: DeployOutcome) => void;
}

export function DeployStep({ serverDir, onOutcome }: Props) {
  const job = useJob();
  const [guide, setGuide] = useState<string | null>(null);
  const [guideError, setGuideError] = useState<string | null>(null);

  useEffect(() => {
    const outcome = job.outcome;
    if (!outcome || typeof outcome.dist !== "string") return;
    onOutcome({ dist: outcome.dist, files: Number(outcome.files ?? 0) });

    const guidePath = (job.job?.artifacts ?? []).find((artifact) =>
      artifact.path.endsWith("使用说明.md"),
    )?.path;
    if (!guidePath) return;
    api
      .artifact(guidePath)
      .then((artifact) => setGuide(artifact.text))
      .catch((cause) => setGuideError(message(cause)));
  }, [job.outcome, job.job, onOutcome]);

  const start = useCallback(() => {
    if (!serverDir) return;
    setGuide(null);
    setGuideError(null);
    void job.start("deploy", { server: serverDir });
  }, [job, serverDir]);

  return (
    <div className="step-body">
      <section className="panel">
        <h3>导出 headless 服务端</h3>
        <p className="muted small">
          用 Godot CLI 导出单文件 Windows 服务端，并生成部署说明与防火墙 / 服务脚本。
          首次导出较慢。整个过程不触碰任何远端服务器。
        </p>
        {serverDir ? (
          <p className="muted small">
            服务端工程：<code>{serverDir}</code>
          </p>
        ) : (
          <p className="alert alert-warn">还没有生成的服务端工程，请先完成「生成」步骤。</p>
        )}
        <div className="step-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={job.running || !serverDir}
            onClick={start}
          >
            {job.running ? "导出中…" : "导出服务端"}
          </button>
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

      {guideError && <p className="alert alert-bad">{guideError}</p>}
      {guide && <ReportView source={guide} title="部署说明（使用说明.md）" />}
    </div>
  );
}
