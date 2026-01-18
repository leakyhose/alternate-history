export interface MapMetadata {
  width: number;
  height: number;
  westWidth: number;
  provinceCount: number;
  seaProvinces?: number[];
  countries?: Record<string, {
    color: string;
    provinces: number[];
  }>;
  tags?: Record<string, {
    name: string;
    color: string;
  }>;
}

export interface ProvinceHistoryEntry {
  ID: number;
  NAME: string;
  OWNER: string;
  CONTROL: string; // Tag that controls/occupies, empty string if none
}

export interface ProvinceHistory {
  [year: string]: ProvinceHistoryEntry[];
}

export interface RulerHistoryEntry {
  TAG: string;
  NAME: string;
  DYNASTY: string;
  TITLE: string;
  AGE: string;
}

export interface RulerHistory {
  [year: string]: RulerHistoryEntry[];
}

export interface ScenarioMetadata {
  name: string;
  description?: string;
  tags: Record<string, { name: string; color: string }>;
  period?: {
    start: number;
    end: number;
  };
}

// Game/Workflow API types

export interface LogEntry {
  year_range: string;
  narrative: string;
  divergences: string[];
  territorial_changes_summary: string;
}

export interface RulerInfo {
  name: string;
  title: string;
  age: number;
  dynasty: string;
}

export interface StartResponse {
  status: 'accepted' | 'rejected';
  game_id?: string;
  year?: number;
  reason?: string;
  alternative?: string;
  result?: {
    current_year: number;
    merged: boolean;
    rulers: Record<string, RulerInfo>;
    logs: LogEntry[];
    divergences: string[];
  };
}

export interface ContinueResponse {
  status: 'continued' | 'merged';
  current_year: number;
  merged: boolean;
  logs: LogEntry[];
  result?: {
    rulers: Record<string, RulerInfo>;
    divergences: string[];
    message?: string;
  };
}

export interface GameState {
  id: string;
  scenario_id: string;
  current_year: number;
  merged: boolean;
  rulers: Record<string, RulerInfo>;
  nation_tags: Record<string, { name: string; color: string }>;
  logs: LogEntry[];
  provinces: Array<{
    id: number;
    name: string;
    owner: string;
    control: string;
  }>;
  divergences: string[];
}

export interface GameProvince {
  id: number;
  name: string;
  owner: string;
  control: string;
}

// Timeline Branching types

export interface TimelinePoint {
  timeline: 'main' | 'alternate';
  year: number;
  logIndex?: number;  // For alternate timeline points
}

export interface ProvinceSnapshot {
  logIndex: number;
  provinces: GameProvince[];
  rulers: Record<string, RulerInfo>;
  divergences: string[];
}