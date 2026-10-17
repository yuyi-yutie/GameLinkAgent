import { useEffect, useState } from "react";

import { api } from "../api";
import { message } from "../lib/format";
import type { AppConfig } from "../types";

interface Props {
  onClose: () => void;
}

export function ConfigPanel({ onClose }: Props) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [godotBin, setGodotBin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .config()
      .then((loaded) => {
        setConfig(loaded);
        setBaseUrl(loaded.base_url);
        setModel(loaded.model);
        setGodotBin(loaded.godot_bin ?? "");
      })
      .catch((cause) => setError(message(cause)));
  }, []);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.saveConfig({
        base_url: baseUrl || undefined,
        model: model || undefined,
        api_key: apiKey || undefined,
        godot_bin: godotBin || undefined,
      });
      onClose();
    } catch (cause) {
      setError(message(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal" role="dialog" aria-modal="true">
      <div className="modal-card">
        <h2>配置</h2>
        <p className="muted small">
          保存到用户目录，不写入仓库：<code>{config?.user_config ?? "…"}</code>
        </p>

        <label className="field">
          <span>API 端点</span>
          <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
        </label>

        <label className="field">
          <span>模型</span>
          <input value={model} onChange={(event) => setModel(event.target.value)} />
        </label>

        <label className="field">
          <span>API key</span>
          <input
            type="password"
            value={apiKey}
            placeholder={config?.has_key ? "已配置（留空则不修改）" : "尚未配置"}
            onChange={(event) => setApiKey(event.target.value)}
          />
        </label>

        <label className="field">
          <span>Godot 引擎路径</span>
          <input
            value={godotBin}
            placeholder="C:\\D\\GodotEngine\\Godot_v4.x-stable_win64_console.exe"
            onChange={(event) => setGodotBin(event.target.value)}
          />
        </label>

        {error && <p className="alert alert-bad">{error}</p>}

        <div className="modal-actions">
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="button" className="btn btn-primary" disabled={saving} onClick={save}>
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
