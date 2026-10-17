import { useCallback, useMemo } from "react";

import { JobConsole } from "../components/JobConsole";
import { SpecEditor } from "../components/SpecEditor";
import { VerifyList, type VerifyIssue } from "../components/VerifyList";
import { useJob } from "../hooks/useJob";

interface Props {
  projectPath: string;
  specsDir: string | null;
  specs: string[];
  onNext: () => void;
}

export function SpecsStep({ projectPath, specsDir, specs, onNext }: Props) {
  const job = useJob();

  const issues = useMemo<VerifyIssue[]>(
    () =>
      job.events
        .filter((event) => event.type === "issue")
        .map((event) => ({
          severity: String(event.data.severity ?? "info"),
          message: String(event.data.message ?? ""),
        })),
    [job.events],
  );

  const runVerify = useCallback(() => {
    if (!specsDir) return;
    void job.start("verify", { project: projectPath, specs: specsDir });
  }, [job, projectPath, specsDir]);

  if (!specsDir || specs.length === 0) {
    return (
      <div className="step-body">
        <p className="muted">还没有规格。先回到「分析」步骤跑一次（分析会同时导出两份规格）。</p>
      </div>
    );
  }

  return (
    <div className="step-body">
      <p className="muted small">
        规格是唯一契约：代码由规格派生。改完记得保存——保存时服务端会按 JSON Schema 校验。
      </p>

      {specs.map((path) => {
        const name = path.split(/[\\/]/).pop() ?? path;
        const title = name.startsWith("protocol") ? "协议规格" : "服务端架构规格";
        return <SpecEditor key={path} artifactPath={path} title={title} />;
      })}

      <section className="panel">
        <h3>一致性校验</h3>
        <p className="muted small">
          用 headless Godot 内省工程里真实存在的 @rpc 与 autoload，与规格逐条比对，
          抓 LLM 的幻觉与遗漏。
        </p>
        <div className="step-actions">
          <button
            type="button"
            className="btn"
            disabled={job.running}
            onClick={runVerify}
          >
            {job.running ? "校验中…" : "用 Godot 内省校验"}
          </button>
          <button type="button" className="btn btn-primary" onClick={onNext}>
            下一步：生成
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
        showIssues={false}
      />

      {(issues.length > 0 || job.job?.status === "succeeded") && <VerifyList issues={issues} />}
    </div>
  );
}
