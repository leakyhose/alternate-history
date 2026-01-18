#!/usr/bin/env python3
"""
Generate two JSON files:
1. areas.json - Maps areas to provinces (with province names)
2. regions.json - Maps regions to areas
"""

import json
import re
import os

# Transliteration map for special characters
TRANSLIT_MAP = {
    'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A', 'Å': 'A', 'Æ': 'AE',
    'Ç': 'C', 'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E',
    'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I',
    'Ð': 'D', 'Ñ': 'N',
    'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O', 'Ø': 'O',
    'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U',
    'Ý': 'Y', 'Þ': 'TH', 'ß': 'ss',
    'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a', 'æ': 'ae',
    'ç': 'c', 'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
    'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
    'ð': 'd', 'ñ': 'n',
    'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o', 'ø': 'o',
    'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
    'ý': 'y', 'þ': 'th', 'ÿ': 'y',
    'Œ': 'OE', 'œ': 'oe', 'Š': 'S', 'š': 's', 'Ž': 'Z', 'ž': 'z',
    'ƒ': 'f', 'Ÿ': 'Y'
}


def transliterate(text):
    """Convert special characters to ASCII equivalents."""
    return ''.join(TRANSLIT_MAP.get(c, c) for c in text)


def load_province_names(csv_path):
    """Load province names from definition.csv, handling Latin-1 encoding."""
    names = {}
    
    # Read file as binary and decode as Latin-1
    with open(csv_path, 'rb') as f:
        content = f.read().decode('latin-1')
    
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if i == 0:  # Skip header
            continue
        parts = line.split(';')
        if len(parts) >= 5 and parts[0]:
            try:
                province_id = int(parts[0])
                name = parts[4]
                if name and name != 'x':
                    # Transliterate to ASCII
                    name = transliterate(name.strip())
                    names[province_id] = name
            except ValueError:
                continue
    
    return names


def parse_areas(areas_path):
    """Parse areas.txt and return a dict mapping area names to province IDs."""
    areas = {}
    
    with open(areas_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove comments (lines starting with # or inline # comments)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip full-line comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        # Remove inline comments
        if '#' in line:
            line = line[:line.index('#')]
        cleaned_lines.append(line)
    content = '\n'.join(cleaned_lines)
    
    # Parse area definitions
    # They look like: area_name = { ... } with possible nested braces for color
    current_area = None
    brace_depth = 0
    current_content = []
    in_color_block = False
    color_brace_depth = 0
    
    i = 0
    while i < len(content):
        # Check for area name pattern
        if brace_depth == 0:
            # Look for pattern like "name = {"
            match = re.match(r'(\w+_area)\s*=\s*\{', content[i:])
            if match:
                current_area = match.group(1)
                current_content = []
                brace_depth = 1
                in_color_block = False
                i += match.end()
                continue
        
        if brace_depth > 0:
            char = content[i]
            
            # Check for color = { pattern
            if not in_color_block:
                color_match = re.match(r'color\s*=\s*\{', content[i:])
                if color_match:
                    in_color_block = True
                    color_brace_depth = 1
                    i += color_match.end()
                    continue
            
            if in_color_block:
                if char == '{':
                    color_brace_depth += 1
                elif char == '}':
                    color_brace_depth -= 1
                    if color_brace_depth == 0:
                        in_color_block = False
                i += 1
                continue
            
            if char == '{':
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    # End of this area - extract province IDs
                    area_text = ''.join(current_content)
                    
                    # Extract all numbers
                    province_ids = []
                    for token in area_text.split():
                        try:
                            province_id = int(token)
                            province_ids.append(province_id)
                        except ValueError:
                            continue
                    
                    if current_area and province_ids:
                        areas[current_area] = province_ids
                    
                    current_area = None
                    current_content = []
            else:
                current_content.append(char)
        
        i += 1
    
    return areas


def parse_regions(regions_path):
    """Parse region.txt and return a dict mapping region names to area names."""
    regions = {}
    
    with open(regions_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match region definitions
    # region_name = { areas = { area1 area2 ... } }
    region_pattern = r'(\w+_region)\s*=\s*\{([^}]*areas\s*=\s*\{([^}]*)\}[^}]*)\}'
    
    for match in re.finditer(region_pattern, content, re.DOTALL):
        region_name = match.group(1)
        areas_content = match.group(3)
        
        # Extract area names
        area_names = []
        for token in areas_content.split():
            token = token.strip()
            if token and not token.startswith('#'):
                area_names.append(token)
        
        if area_names:
            regions[region_name] = area_names
    
    return regions


def format_area_name(area_name):
    """Convert area_name to a more readable format."""
    # Remove _area suffix if present
    name = area_name
    if name.endswith('_area'):
        name = name[:-5]
    # Replace underscores with spaces and title case
    name = name.replace('_', ' ').title()
    return transliterate(name)


def format_region_name(region_name):
    """Convert region_name to a more readable format."""
    # Remove _region suffix if present
    name = region_name
    if name.endswith('_region'):
        name = name[:-7]
    # Replace underscores with spaces and title case
    name = name.replace('_', ' ').title()
    return transliterate(name)


def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(script_dir, '..', 'static')
    
    csv_path = os.path.join(static_dir, 'definition.csv')
    areas_path = os.path.join(static_dir, 'areas.txt')
    regions_path = os.path.join(static_dir, 'region.txt')
    
    # Output paths
    areas_output = os.path.join(static_dir, 'areas.json')
    regions_output = os.path.join(static_dir, 'regions.json')
    
    print("Loading province names from definition.csv...")
    province_names = load_province_names(csv_path)
    print(f"  Loaded {len(province_names)} province names")
    
    print("Parsing areas.txt...")
    raw_areas = parse_areas(areas_path)
    print(f"  Found {len(raw_areas)} areas")
    
    print("Parsing region.txt...")
    raw_regions = parse_regions(regions_path)
    print(f"  Found {len(raw_regions)} regions")
    
    # Build areas.json - maps area names to provinces with their names
    # Format: { "Area Name": [{"id": 123, "name": "Province Name"}, ...], ... }
    areas_json = {}
    missing_provinces = set()
    
    for area_name, province_ids in raw_areas.items():
        formatted_area = format_area_name(area_name)
        provinces = []
        for pid in province_ids:
            if pid in province_names:
                provinces.append({
                    "id": pid,
                    "name": province_names[pid]
                })
            else:
                missing_provinces.add(pid)
                provinces.append({
                    "id": pid,
                    "name": f"Unknown ({pid})"
                })
        areas_json[formatted_area] = provinces
    
    if missing_provinces:
        print(f"  Warning: {len(missing_provinces)} provinces not found in definition.csv")
    
    # Build regions.json - maps region names to area names
    # Format: { "Region Name": ["Area Name 1", "Area Name 2", ...], ... }
    regions_json = {}
    missing_areas = set()
    
    for region_name, area_names in raw_regions.items():
        formatted_region = format_region_name(region_name)
        areas = []
        for area_name in area_names:
            formatted_area = format_area_name(area_name)
            # Verify the area exists
            if formatted_area in areas_json:
                areas.append(formatted_area)
            else:
                missing_areas.add(area_name)
                areas.append(formatted_area)  # Include anyway but note it
        regions_json[formatted_region] = areas
    
    if missing_areas:
        print(f"  Warning: {len(missing_areas)} areas in regions not found in areas.txt")
        print(f"    Missing: {list(missing_areas)[:10]}...")  # Show first 10
    
    # Write output files
    print(f"\nWriting {areas_output}...")
    with open(areas_output, 'w', encoding='utf-8') as f:
        json.dump(areas_json, f, indent=2, ensure_ascii=False)
    print(f"  Created with {len(areas_json)} areas")
    
    print(f"Writing {regions_output}...")
    with open(regions_output, 'w', encoding='utf-8') as f:
        json.dump(regions_json, f, indent=2, ensure_ascii=False)
    print(f"  Created with {len(regions_json)} regions")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
