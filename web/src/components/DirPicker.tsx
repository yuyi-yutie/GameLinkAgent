import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { message } from "../lib/format";
import type { DirListing } from "../types";

interface Props {
  onPick: (path: string) => void;
}

export function DirPicker({ onPick }: Props) {
  const [listing, setListing] = useState<DirListing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");

  const browse = useCallback((path?: string) => {
    setError(null);
    api
      .dirs(path)
      .then((next) => {
        setListing(next);
        setTyped(next.path);
      })
      .catch((cause) => setError(message(cause)));
  }, []);

  useEffect(() => browse(), [browse]);

  return (
    <div className="browser">
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
          onChange={(event) => setTyped(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") browse(typed);
          }}
        />
        <button type="button" className="btn" onClick={() => browse(typed)}>
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
        {listing && listing.dirs.length === 0 && (
          <li className="browser-empty muted">没有子目录</li>
        )}
      </ul>

      <div className="browser-actions">
        {listing?.is_project ? (
          <>
            <span className="pill pill-succeeded">找到 project.godot</span>
            <button type="button" className="btn btn-primary" onClick={() => onPick(listing.path)}>
              使用这个工程
            </button>
          </>
        ) : (
          <span className="muted small">这个目录里没有 project.godot，继续往里找。</span>
        )}
      </div>
    </div>
  );
}
