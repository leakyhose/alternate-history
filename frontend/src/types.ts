export interface Province {
    id: number // Must be a valid tag
    name: string
    owner: string
}

export interface Tags {
    [id: string]: {
        name: string
        color: string
    }
}

export interface SaveData {
  provinces: Record<string, string | null>;
}