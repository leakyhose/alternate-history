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
  name: string;
  dynasty: string;
  title: string;
}


export interface RulerHistory {
  tags: string[];
  [year: string]: RulerHistoryEntry[] | string[];
}

export interface RulerFile {
  tag: string;
  country: string;
  title: string;
  rulers: Record<string, RulerHistoryEntry | null>;
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