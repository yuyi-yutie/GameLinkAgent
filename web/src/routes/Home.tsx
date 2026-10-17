import { useEffect, useState } from "react";

import { api } from "../api";
import { DirPicker } from "../components/DirPicker";
import { clockTime, message, statusText } from "../lib/format";
import type { Health, Job } from "../types";

interface Props {
  health: Health | null;
  onPick: (path: string) => void;
}

export function Home({ health, onPick }: Props) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .jobs()
      .then(setJobs)
      .catch((cause) => setError(message(cause)));
  }, []);

  return (
    <main className="home">
      <section className="hero">
        <h1>把 Godot 单机游戏变成联机游戏</h1>
        <p className="muted">
          导入工程 → LLM 分析 → 审阅规格 → 生成 Godot 原生 headless 权威服务端 → 导出可部署的服务端。
        </p>
        {health && !health.ui_built && (
          <p className="alert alert-warn">
            后端报告 ui_built=false（前端产物缺失），但你现在能看到这个页面，说明只是版本不一致。
          </p>
        )}
      </section>

      <section className="panel">
        <h2>选择 Godot 工程</h2>
        <p className="muted small">挑一个含 project.godot 的目录。</p>
        <DirPicker onPick={onPick} />
      </section>

      {error && <p className="alert alert-bad">{error}</p>}

      {jobs.length > 0 && (
        <section className="panel">
          <h2>最近任务</h2>
          <ul className="job-list">
            {jobs.slice(0, 8).map((job) => (
              <li key={job.id}>
                <span className={`pill pill-${job.status}`}>{statusText(job.status)}</span>
                <span className="job-kind">{job.kind}</span>
                <span className="muted">{clockTime(job.created_at)}</span>
                {job.error && <span className="muted small">{job.error}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
