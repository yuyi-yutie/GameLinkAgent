import type { Health } from "../types";

interface ChipProps {
  ok: boolean;
  label: string;
  detail: string;
  title?: string;
  action?: string;
  onClick?: () => void;
}

function Chip({ ok, label, detail, title, action, onClick }: ChipProps) {
  const className = `chip ${ok ? "chip-ok" : "chip-warn"}${onClick ? " chip-button" : ""}`;
  const content = (
    <>
      <span className="chip-dot" />
      {label}
      <span className="muted">{detail}</span>
      {action && <span className="chip-action">{action}</span>}
    </>
  );

  if (onClick) {
    return (
      <button type="button" className={className} title={title} onClick={onClick}>
        {content}
      </button>
    );
  }
  return (
    <span className={className} title={title}>
      {content}
    </span>
  );
}

function shorten(path: string): string {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts.length <= 2 ? path : `…/${parts.slice(-2).join("/")}`;
}

interface Props {
  health: Health | null;
  onOpenConfig: (section?: "godot") => void;
}

export function StatusBar({ health, onOpenConfig }: Props) {
  return (
    <header className="status-bar">
      <div className="brand">
        <strong>GameLink Agent</strong>
        {health && <span className="muted">v{health.version}</span>}
      </div>

      <div className="chips">
        {health ? (
          <>
            <Chip
              ok={health.llm.configured}
              label="LLM"
              detail={health.llm.model}
              title={health.llm.base_url}
            />
            <Chip
              ok={health.godot.exists}
              label="Godot"
              detail={health.godot.exists ? "就绪" : "未配置"}
              title="点击配置 Godot 引擎路径"
              action="设置"
              onClick={() => onOpenConfig("godot")}
            />
            <Chip ok={Boolean(health.deploy.host)} label="部署" detail={health.deploy.host ?? "未配置"} />
            <span className="chip chip-plain" title={health.workspace}>
              工作区 {shorten(health.workspace)}
            </span>
          </>
        ) : (
          <span className="chip chip-bad">未连接到后端</span>
        )}
      </div>

      <button type="button" className="btn btn-accent" onClick={() => onOpenConfig()}>
        配置
      </button>
    </header>
  );
}
