export type Stage = "inspect" | "analyze" | "generate" | "verify" | "deploy";

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "interrupted";

export interface DesignerOptions {
  authority_model: string;
  sync_mechanism: string;
  transport: string;
  room_mode: string;
  max_players: number;
  tick_rate: number;
  persistence: string;
  deploy_target: string;
}

export interface Health {
  version: string;
  workspace: string;
  python: string;
  llm: { model: string; base_url: string; configured: boolean };
  godot: { bin: string | null; configured: boolean; exists: boolean };
  deploy: { host: string | null; game_port: number };
  user_config: string;
  ui_built: boolean;
}

export interface OptionsResponse {
  choices: Record<string, string[]>;
  defaults: DesignerOptions;
}

export interface Artifact {
  path: string;
  kind: string;
  label: string;
  stage: string;
}

export interface Job {
  id: string;
  kind: Stage;
  params: Record<string, unknown>;
  status: JobStatus;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  error: string | null;
  error_kind: string | null;
  artifacts: Artifact[];
  todos: string[];
  progress: string;
  seq: number;
}

export interface PipelineEvent {
  type: string;
  seq: number;
  ts: number;
  stage: string | null;
  data: Record<string, unknown>;
}

export interface DirEntry {
  name: string;
  path: string;
}

export interface DirListing {
  path: string;
  name: string;
  parent: string | null;
  is_project: boolean;
  dirs: DirEntry[];
  roots: string[];
}

export interface FileListing extends DirListing {
  files: DirEntry[];
}

export interface ProjectInfo {
  root: string;
  name: string;
  features: string[];
  main_scene: string | null;
  autoloads: Record<string, string>;
  scripts: string[];
  scenes: string[];
  resources: string[];
  file_tree: string[];
  counts: { scripts: number; scenes: number; resources: number };
}

export interface AppConfig {
  base_url: string;
  model: string;
  has_key: boolean;
  godot_bin: string | null;
  deploy_host: string | null;
  user_config: string;
}

export interface ArtifactText {
  path: string;
  name: string;
  text: string;
}
