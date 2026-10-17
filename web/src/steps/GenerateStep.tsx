import { useCallback, useEffect } from "react";

import { JobConsole } from "../components/JobConsole";
import { useJob } from "../hooks/useJob";

export interface GenerateOutcome {
  out: string;
  files: number;
  todos: number;
}

interface Props {
  projectPath: string;
  specsDir: string | null;
  onOutcome: (outcome: GenerateOutcome) => void;
  onNext: () => void;
}

export function GenerateStep({ projectPath, specsDir, onOutcome, onNext }: Props) {
  const job = useJob();

  useEffect(() => {
    const outcome = job.outcome;
    if (!outcome || typeof outcome.out !== "string") return;
    onOutcome({
      out: outcome.out,
      files: Number(outcome.files ?? 0),
      todos: Number(outcome.todos ?? 0),
    });
  }, [job.outcome, onOutcome]);

  const start = useCallback(() => {
    if (!specsDir) return;
    void job.start("generate", { project: projectPath, specs: specsDir });
  }, [job, projectPath, specsDir]);

  return (
    <div className="step-body">
      <section className="panel">
        <h3>按规格生成服务端工程</h3>
        <p className="muted small">
          复制输入工程（保留资源与场景），写入网络层、补 autoload，并写出导出预设与部署清单。
          refactors 会以 TODO 列出，交给人工或后续补全。
        </p>
        <div className="step-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={job.running || !specsDir}
            onClick={start}
          >
            {job.running ? "生成中…" : "开始生成"}
          </button>
          {job.job?.status === "succeeded" && (
            <button type="button" className="btn" onClick={onNext}>
              下一步：导出
            </button>
          )}
        </div>
        {!specsDir && <p className="alert alert-warn">缺少规格目录，请先完成「分析」步骤。</p>}
      </section>

      <JobConsole
        job={job.job}
        events={job.events}
        stream={job.stream}
        running={job.running}
        error={job.error}
        onCancel={job.cancel}
      />
    </div>
  );
}
