import type { Artifact } from "../types";

interface Props {
  artifacts: Artifact[];
  title?: string;
}

export function ArtifactList({ artifacts, title = "产物" }: Props) {
  if (artifacts.length === 0) return null;
  return (
    <details className="artifacts" open>
      <summary>
        {title} <span className="muted">({artifacts.length})</span>
      </summary>
      <ul>
        {artifacts.map((artifact) => (
          <li key={artifact.path}>
            <span className="artifact-label">{artifact.label}</span>
            <code className="artifact-path">{artifact.path}</code>
          </li>
        ))}
      </ul>
    </details>
  );
}
