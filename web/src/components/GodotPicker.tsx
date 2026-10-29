import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api";
import { message } from "../lib/format";
import type { FileListing } from "../types";

interface Props {
  value: string;
  onPick: (path: string) => void;
}

function directoryOf(value: string): string | undefined {
  const clean = value.trim().replace(/[/\\]+$/, "");
  if (!clean) return undefined;
  if (/\.exe$/i.test(clean)) {
    const cut = Math.max(clean.lastIndexOf("\\"), clean.lastIndexOf("/"));
    return cut > 0 ? clean.slice(0, cut) : undefined;
  }
  return clean;
}

function samePath(a: string, b: string): boolean {
  return a.replace(/\//g, "\\").toLowerCase() === b.replace(/\//g, "\\").toLowerCase();
}

export function GodotPicker({ value, onPick }: Props) {
  const [listing, setListing] = useState<FileListing | null>(null);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const initialDir = useRef(directoryOf(value));

  const browse = useCallback((path?: string) => {
    setError(null);
    api
      .entries(path)
      .then((next) => {
        setListing(next);
        setTyped(next.path);
      })
      .catch((cause) => setError(message(cause)));
  }, []);

  useEffect(() => {
    browse(initialDir.current);
  }, [browse]);

  return (
    <section className="godot-picker">
      <div className="browser-bar">
        <button
          type="button"
          className="btn"
          disabled={!listing?.parent}
          onClick={() => listing?.parent && browse(listing.parent)}
        >
          上级
        </button>
        <input
          className="browser-path"
          value={typed}
          spellCheck={false}
          aria-label="目录路径"
          onChange={(event) => setTyped(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") browse(typed);
          }}
        />
        <button type="button" className="btn btn-secondary" onClick={() => browse(typed)}>
          跳转
        </button>
      </div>

      {listing && listing.roots.length > 1 && (
        <div className="browser-roots">
          {listing.roots.map((root) => (
            <button key={root} type="button" className="btn btn-ghost" onClick={() => browse(root)}>
              {root}
            </button>
          ))}
        </div>
      )}

      {error && <p className="alert alert-bad">{error}</p>}

      <ul className="browser-list">
        {listing?.dirs.map((dir) => (
          <li key={dir.path}>
            <button type="button" onClick={() => browse(dir.path)}>
              <span className="dir-icon">▸</span>
              {dir.name}
            </button>
          </li>
        ))}
        {listing?.files.map((file) => {
          const selected = value ? samePath(value, file.path) : false;
          return (
            <li key={file.path}>
              <button
                type="button"
                className={`file-entry${selected ? " file-entry-selected" : ""}`}
                title={file.path}
                onClick={() => onPick(file.path)}
              >
                <span className="file-icon">◆</span>
                <span className="file-name">{file.name}</span>
                {selected && <span className="file-check">已选择</span>}
              </button>
            </li>
          );
        })}
        {listing && listing.dirs.length === 0 && listing.files.length === 0 && (
          <li className="browser-empty muted">这个目录里没有子目录或 .exe 文件</li>
        )}
      </ul>

      <p className="muted small">只显示 .exe；点击可执行文件即可选中。</p>
    </section>
  );
}
