import type { Stage } from "../types";

export type StepKey = "import" | "analyze" | "specs" | "generate" | "deploy";

export interface StepDoc {
  key: StepKey;
  label: string;
  hint: string;
}

export const STEPS: StepDoc[] = [
  { key: "import", label: "导入", hint: "选择 Godot 工程并查看摘要" },
  { key: "analyze", label: "分析", hint: "LLM 产出报告与两份规格" },
  { key: "specs", label: "规格审阅", hint: "检查、修改并校验规格" },
  { key: "generate", label: "生成", hint: "按规格生成服务端工程" },
  { key: "deploy", label: "导出", hint: "导出 headless 服务端" },
];

export const STAGE_LABEL: Record<Stage, string> = {
  inspect: "解析工程",
  analyze: "LLM 分析",
  generate: "代码生成",
  verify: "一致性校验",
  deploy: "导出服务端",
};

interface Props {
  current: StepKey;
  done: StepKey[];
  onSelect: (key: StepKey) => void;
}

export function Stepper({ current, done, onSelect }: Props) {
  return (
    <ol className="stepper">
      {STEPS.map((step, index) => {
        const isDone = done.includes(step.key);
        const state = step.key === current ? "current" : isDone ? "done" : "todo";
        return (
          <li key={step.key} className={`step step-${state}`}>
            <button type="button" onClick={() => onSelect(step.key)}>
              <span className="step-index">{isDone ? "✓" : index + 1}</span>
              <span className="step-text">
                <span className="step-label">{step.label}</span>
                <span className="step-hint">{step.hint}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
