import { useEffect, useState } from "react";

import { api } from "../api";
import { message } from "../lib/format";

const SCHEMA_BY_FILE: Record<string, "protocol" | "architecture"> = {
  "protocol.spec.yaml": "protocol",
  "server-architecture.spec.yaml": "architecture",
};

interface Props {
  artifactPath: string;
  title: string;
  note?: string;
}

export function SpecEditor({ artifactPath, title, note }: Props) {
  const [text, setText] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [schema, setSchema] = useState<string | null>(null);

  const name = artifactPath.split(/[\\/]/).pop() ?? "";
  const schemaKey = SCHEMA_BY_FILE[name];

  useEffect(() => {
    setText(null);
    setDirty(false);
    setError(null);
    setSaved(false);
    api
      .artifact(artifactPath)
      .then((artifact) => setText(artifact.text))
      .catch((cause) => setError(message(cause)));
  }, [artifactPath]);

  useEffect(() => {
    if (!schemaKey) return;
    api
      .schema(schemaKey)
      .then((loaded) => setSchema(JSON.stringify(loaded, null, 2)))
      .catch(() => setSchema(null));
  }, [schemaKey]);

  const save = async () => {
    if (text === null) return;
    setError(null);
    try {
      await api.saveArtifact(artifactPath, text);
      setDirty(false);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2500);
    } catch (cause) {
      setError(message(cause));
    }
  };

  return (
    <section className="editor">
      <header className="editor-head">
        <div>
          <h3>{title}</h3>
          <code className="muted small">{artifactPath}</code>
          {note && <p className="muted small">{note}</p>}
        </div>
        <div className="editor-actions">
          {saved && <span className="pill pill-succeeded">已保存</span>}
          <button
            type="button"
            className="btn btn-primary"
            disabled={!dirty || text === null}
            onClick={save}
          >
            保存并校验
          </button>
        </div>
      </header>

      {error && <p className="alert alert-bad">{error}</p>}

      {text === null ? (
        <p className="muted">加载中…</p>
      ) : (
        <textarea
          className="editor-text"
          spellCheck={false}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setDirty(true);
          }}
        />
      )}

      {schema && (
        <details className="editor-schema">
          <summary>JSON Schema（保存时在服务端校验）</summary>
          <pre>{schema}</pre>
        </details>
      )}
    </section>
  );
}
