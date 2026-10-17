import { issueText } from "../lib/format";

export interface VerifyIssue {
  severity: string;
  message: string;
}

interface Props {
  issues: VerifyIssue[];
}

const GROUPS: { severity: string; blurb: string }[] = [
  { severity: "error", blurb: "规格与引擎事实冲突，必须修正。" },
  { severity: "warning", blurb: "规格里有、工程里没有 —— 疑似 LLM 幻觉。" },
  { severity: "info", blurb: "工程里有、规格里没有 —— 可能是遗漏。" },
];

export function VerifyList({ issues }: Props) {
  if (issues.length === 0) {
    return <p className="muted">还没有校验结果。</p>;
  }
  return (
    <div className="verify">
      {GROUPS.map((group) => {
        const items = issues.filter((issue) => issue.severity === group.severity);
        if (items.length === 0) return null;
        return (
          <section key={group.severity} className={`verify-group verify-${group.severity}`}>
            <header>
              <span className="issue-tag">{issueText(group.severity)}</span>
              <span className="muted small">{group.blurb}</span>
            </header>
            <ul>
              {items.map((issue) => (
                <li key={issue.message}>{issue.message}</li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
