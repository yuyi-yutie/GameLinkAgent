import type { ProjectInfo } from "../types";

interface Props {
  project: ProjectInfo | null;
  error: string | null;
  onNext: () => void;
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-field">
      <span className="summary-label">{label}</span>
      <span className="summary-value">{value}</span>
    </div>
  );
}

export function ImportStep({ project, error, onNext }: Props) {
  if (error) return <p className="alert alert-bad">{error}</p>;
  if (!project) return <p className="muted">正在解析工程…</p>;

  return (
    <div className="step-body">
      <div className="summary-grid">
        <Field label="工程名" value={project.name} />
        <Field label="根目录" value={project.root} />
        <Field label="主场景" value={project.main_scene ?? "未指定"} />
        <Field label="引擎特性" value={project.features.join(", ") || "未知"} />
        <Field label="autoload" value={Object.keys(project.autoloads).join(", ") || "无"} />
        <Field
          label="文件"
          value={`${project.counts.scripts} 脚本 · ${project.counts.scenes} 场景 · ${project.counts.resources} 资源`}
        />
      </div>

      <details className="tree">
        <summary>文件树（{project.file_tree.length}）</summary>
        <ul>
          {project.file_tree.map((entry) => (
            <li key={entry}>
              <code>{entry}</code>
            </li>
          ))}
        </ul>
      </details>

      <div className="step-actions">
        <button type="button" className="btn btn-primary" onClick={onNext}>
          下一步：分析
        </button>
      </div>
    </div>
  );
}
