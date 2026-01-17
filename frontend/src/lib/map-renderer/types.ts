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
}

export interface RulerHistory {
  [year: string]: RulerHistoryEntry[];
}

export interface SaveData {
  provinces: Record<string, string | null>; // Province ID → Tag
}

export interface TagDefinitions {
  [tagId: string]: {
    color: string;
    name: string;
  };
}