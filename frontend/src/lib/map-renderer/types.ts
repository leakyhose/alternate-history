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