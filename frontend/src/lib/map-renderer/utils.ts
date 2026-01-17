import type { SaveData, TagDefinitions } from './types';

// packs four 8 bit color channels into one 32 bit integer
export function packColor(r: number, g: number, b: number, a: number): number {
  return (r << 24) | (g << 16) | (b << 8) | a;
}

// Hex to rgb conversion
export function hexToRgb(hex: string): [number, number, number] {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result 
    ? [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)]
    : [0, 0, 0];
}

// Build color array for all provinces based on save data and tag definitions
export function buildColorArray(
  saveData: SaveData,
  tagDefs: TagDefinitions,
  provinceCount: number
): Uint32Array {
  const colors = new Uint32Array(provinceCount);
  
  // Default color (unassigned provinces)
  const defaultColor = packColor(94, 94, 94, 255);
  colors.fill(defaultColor);
  
  // Fill in tagged provinces
  for (const [provinceId, tag] of Object.entries(saveData.provinces)) {
    if (tag && tagDefs[tag]) {
      const [r, g, b] = hexToRgb(tagDefs[tag].color);
      colors[parseInt(provinceId)] = packColor(r, g, b, 255);
    }
  }
  
  return colors;
}