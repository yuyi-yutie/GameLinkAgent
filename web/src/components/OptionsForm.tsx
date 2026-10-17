import type { DesignerOptions } from "../types";

const LABELS: Record<keyof DesignerOptions, string> = {
  authority_model: "权威模型",
  sync_mechanism: "同步机制",
  transport: "传输层",
  room_mode: "房间模式",
  max_players: "最大玩家数",
  tick_rate: "Tick 率 (Hz)",
  persistence: "持久化",
  deploy_target: "部署目标",
};

const NUMERIC = new Set<keyof DesignerOptions>(["max_players", "tick_rate"]);

const ORDER: (keyof DesignerOptions)[] = [
  "authority_model",
  "sync_mechanism",
  "transport",
  "room_mode",
  "max_players",
  "tick_rate",
  "persistence",
  "deploy_target",
];

interface Props {
  choices: Record<string, string[]>;
  value: DesignerOptions;
  onChange: (next: DesignerOptions) => void;
  disabled?: boolean;
}

export function OptionsForm({ choices, value, onChange, disabled }: Props) {
  return (
    <div className="options-grid">
      {ORDER.map((key) => {
        const label = LABELS[key];
        if (NUMERIC.has(key)) {
          return (
            <label className="field" key={key}>
              <span>{label}</span>
              <input
                type="number"
                min={1}
                value={value[key]}
                disabled={disabled}
                onChange={(event) =>
                  onChange({ ...value, [key]: Number(event.target.value) || 0 } as DesignerOptions)
                }
              />
            </label>
          );
        }
        const options = choices[key] ?? [];
        return (
          <label className="field" key={key}>
            <span>{label}</span>
            <select
              value={value[key]}
              disabled={disabled}
              onChange={(event) => onChange({ ...value, [key]: event.target.value } as DesignerOptions)}
            >
              {options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        );
      })}
    </div>
  );
}
