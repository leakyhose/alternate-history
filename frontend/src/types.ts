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

export interface Quote {
  tag: string;
  ruler_name: string;
  ruler_title: string;
  quote: string;
}

export interface LogEntry {
  year_range: string;
  narrative: string;
  divergences: string[];
  territorial_changes_summary: string;
  quotes?: Quote[];
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
  snapshots?: ProvinceSnapshot[];  // Province snapshots per log entry
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
  snapshots?: ProvinceSnapshot[];  // Province snapshots per log entry
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
  snapshots?: ProvinceSnapshot[];  // Province snapshots per log entry
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
  provinces: GameProvince[];
  rulers: Record<string, RulerInfo>;
  divergences: string[];
}

// Streaming types for SSE partial updates

export type StreamingPhase = 'idle' | 'filtering' | 'dreaming' | 'quoting' | 'mapping' | 'complete';

export interface StreamingState {
  phase: StreamingPhase;
  year?: number;           // From filter
  narrative?: string;      // From dreamer
  rulers?: Record<string, RulerInfo>;
  divergences?: string[];
  provinces?: GameProvince[];
  yearRange?: string;      // From dreamer (e.g., "117-137")
  territorialChangesSummary?: string;
}

// SSE Event types from backend
export interface FilterCompleteEvent {
  event: 'filter_complete';
  year: number;
  game_id: string;
  nation_tags: Record<string, { name: string; color: string }>;
}

export interface DreamerCompleteEvent {
  event: 'dreamer_complete';
  log_entry: LogEntry;
  rulers: Record<string, RulerInfo>;
  divergences: string[];
  year_range: string;
}

export interface GeographerCompleteEvent {
  event: 'geographer_complete';
  provinces: GameProvince[];
}

export interface QuotegiverCompleteEvent {
  event: 'quotegiver_complete';
  quotes: Quote[];
}

export interface CompleteEvent {
  event: 'complete';
  game_id: string;
  current_year: number;
  merged: boolean;
  logs: LogEntry[];
  rulers: Record<string, RulerInfo>;
  divergences: string[];
  snapshots: ProvinceSnapshot[];
}

export interface ErrorEvent {
  event: 'error';
  message: string;
}

export interface RejectedEvent {
  event: 'rejected';
  reason: string;
  alternative?: string;
}

export type StreamEvent =
  | FilterCompleteEvent
  | DreamerCompleteEvent
  | QuotegiverCompleteEvent
  | GeographerCompleteEvent
  | CompleteEvent
  | ErrorEvent
  | RejectedEvent;