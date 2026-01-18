"""
Geographer Agent - Translates territorial descriptions to province updates via AREAS.

The Geographer interprets the Dreamer's STRUCTURED territorial changes
and converts them into specific province-level OWNER updates.

HIERARCHY:
- REGIONS: Large geographical areas (e.g., "France", "Egypt", "Anatolia")
- AREAS: Medium-sized subdivisions of regions (e.g., "Brittany", "Lower Egypt", "Bithynia")
- PROVINCES: Individual territories within areas (rarely needed for most operations)

The Geographer should ALMOST ALWAYS work at the AREA level:
- Areas are descriptive enough for most territorial changes
- Switching an entire area is cleaner than listing individual provinces
- Only drill down to provinces for very specific edge cases

The Dreamer provides structured changes with:
- location: Natural language description of WHERE
- change_type: CONQUEST | LOSS | TRANSFER
- from_nation: Nation losing territory (if applicable)
- to_nation: Nation gaining territory (if applicable)

The Geographer's job is to:
1. Query regions to see what areas exist
2. Identify which AREAS match the location description
3. Return area names (which will be expanded to provinces automatically)
4. Only query individual provinces in rare special cases
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from util.province_memory import (
    get_all_region_names,
    get_areas_for_region,
    get_all_area_names,
    get_provinces_for_area,
    load_areas,
)
from util.scenario import get_scenario_tags

load_dotenv()


# Module-level caches for tool access
_available_tags: Dict[str, Dict[str, Any]] = {}
_current_provinces_cache: Dict[int, Dict[str, Any]] = {}  # province_id -> province data


class ProvinceUpdate(BaseModel):
    """A single province update."""
    id: int = Field(description="The province ID")
    name: str = Field(description="The province name")
    owner: str = Field(description="The new owner tag (e.g., 'BYZ', 'ARB'), or empty string '' if lost to an untracked state")


class GeographerOutput(BaseModel):
    """Structured output from the Geographer agent."""
    province_updates: List[ProvinceUpdate] = Field(
        default_factory=list,
        description="List of province updates with id, name, owner, and control fields"
    )


@tool
def get_available_regions() -> str:
    """
    Get the list of all available REGION names.
    Regions are large geographical areas that contain multiple AREAS.
    
    Call this first to see what regions exist, then query specific regions
    to see their areas.
    
    Examples of regions: France, Egypt, Anatolia, Balkans, Italy, etc.
    
    Returns:
        List of region names
    """
    region_names = get_all_region_names()
    
    if not region_names:
        return "No regions available."
    
    return f"Available regions ({len(region_names)} total):\n" + "\n".join(
        f"  - {name}" for name in sorted(region_names)
    )


@tool
def query_region_areas(region_name: str) -> str:
    """
    Query the AREAS within a specific REGION.
    
    Areas are the preferred unit for territorial changes - they are descriptive
    enough for most operations and cleaner than listing individual provinces.
    
    Args:
        region_name: The region name (e.g., 'France', 'Egypt', 'Anatolia')
        
    Returns:
        List of area names within that region, with summary of current ownership
    """
    areas = get_areas_for_region(region_name)
    
    if not areas:
        return f"Region '{region_name}' not found. Use get_available_regions() to see valid region names."
    
    lines = [f"Areas in {region_name} ({len(areas)} areas):"]
    
    for area_name in areas:
        # Get provinces to determine current ownership summary
        provinces = get_provinces_for_area(area_name)
        if provinces:
            # Summarize ownership
            owners = {}
            for p in provinces:
                prov_id = p['id']
                current = _current_provinces_cache.get(prov_id)
                if current:
                    owner = current.get('owner', '?')
                    owners[owner] = owners.get(owner, 0) + 1
                else:
                    owners['untracked'] = owners.get('untracked', 0) + 1
            
            # Format ownership summary
            if len(owners) == 1:
                owner = list(owners.keys())[0]
                lines.append(f"  - {area_name} ({len(provinces)} provinces, all {owner})")
            else:
                owner_str = ", ".join(f"{o}: {c}" for o, c in owners.items())
                lines.append(f"  - {area_name} ({len(provinces)} provinces, mixed: {owner_str})")
        else:
            lines.append(f"  - {area_name} (no provinces mapped)")
    
    return "\n".join(lines)


@tool
def query_area_provinces(area_name: str) -> str:
    """
    Query the individual PROVINCES within a specific AREA.
    
    ⚠️ USE SPARINGLY! You should almost always work at the AREA level.
    Only use this tool when you need to:
    - Split an area (e.g., "only the coastal provinces of Brittany")
    - Handle a very specific location that doesn't align with area boundaries
    
    For most territorial changes, just return the area name instead!
    
    Args:
        area_name: The area name (e.g., 'Brittany', 'Lower Egypt')
        
    Returns:
        List of provinces with their IDs, names, and current ownership
    """
    provinces = get_provinces_for_area(area_name)
    
    if not provinces:
        return f"Area '{area_name}' not found. Use query_region_areas() to see valid area names."
    
    lines = [f"Provinces in {area_name}:"]
    for p in provinces:
        prov_id = p['id']
        name = p['name']
        
        # Look up current state from cache
        current = _current_provinces_cache.get(prov_id)
        if current:
            owner = current.get('owner', '?')
            lines.append(f"  - ID {prov_id}: {name} [owner: {owner}]")
        else:
            lines.append(f"  - ID {prov_id}: {name} [not tracked]")
    
    return "\n".join(lines)


@tool
def query_tag_territories(tag: str) -> str:
    """
    Query ALL territories owned by a specific nation TAG.
    
    🎯 USE THIS TOOL when handling commands like:
    - "All remaining X territory goes to Y"
    - "All of X goes to Y except for Z"
    - "The rest of X's holdings..."
    - "X loses everything except..."
    
    This tool returns:
    1. AREAS that the tag FULLY owns (all provinces in the area belong to the tag)
    2. Individual PROVINCES from areas where the tag only PARTIALLY owns
    
    This is more efficient than querying regions one by one when you need to
    know everything a tag owns.
    
    Args:
        tag: The nation tag (e.g., 'USA', 'BYZ', 'FRA')
        
    Returns:
        Structured list of fully-owned areas and partially-owned provinces
    """
    if not _current_provinces_cache:
        return f"No province data loaded. Cannot query territories for tag '{tag}'."
    
    # Get all provinces owned by this tag
    owned_province_ids = set()
    for prov_id, prov_data in _current_provinces_cache.items():
        if prov_data.get('owner') == tag:
            owned_province_ids.add(prov_id)
    
    if not owned_province_ids:
        return f"Tag '{tag}' does not own any tracked provinces."
    
    # Load all areas and categorize
    all_areas = load_areas()
    
    fully_owned_areas = []
    partial_provinces = []  # provinces from areas not fully owned
    
    for area_name, area_provinces in all_areas.items():
        area_province_ids = {p['id'] for p in area_provinces}
        
        # How many provinces in this area does the tag own?
        owned_in_area = area_province_ids & owned_province_ids
        
        if not owned_in_area:
            # Tag owns nothing in this area
            continue
        elif owned_in_area == area_province_ids:
            # Tag fully owns this area
            fully_owned_areas.append({
                'name': area_name,
                'province_count': len(area_provinces)
            })
        else:
            # Tag partially owns this area - list individual provinces
            for p in area_provinces:
                if p['id'] in owned_in_area:
                    partial_provinces.append({
                        'id': p['id'],
                        'name': p['name'],
                        'area': area_name
                    })
    
    # Build response
    lines = [f"Territories owned by {tag}:"]
    lines.append("")
    
    if fully_owned_areas:
        lines.append(f"FULLY OWNED AREAS ({len(fully_owned_areas)} areas):")
        for area in sorted(fully_owned_areas, key=lambda x: x['name']):
            lines.append(f"  - {area['name']} ({area['province_count']} provinces)")
    else:
        lines.append("FULLY OWNED AREAS: None")
    
    lines.append("")
    
    if partial_provinces:
        # Group by area for readability
        by_area = {}
        for p in partial_provinces:
            area = p['area']
            if area not in by_area:
                by_area[area] = []
            by_area[area].append(p)
        
        lines.append(f"PARTIAL OWNERSHIP ({len(partial_provinces)} provinces in {len(by_area)} areas):")
        for area_name in sorted(by_area.keys()):
            area_provs = by_area[area_name]
            lines.append(f"  {area_name}:")
            for p in area_provs:
                lines.append(f"    - ID {p['id']}: {p['name']}")
    else:
        lines.append("PARTIAL OWNERSHIP: None (all owned areas are fully owned)")
    
    lines.append("")
    lines.append(f"TOTAL: {len(owned_province_ids)} provinces ({len(fully_owned_areas)} full areas + {len(partial_provinces)} individual provinces)")
    
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a geographer assistant for an alternate history simulation.
Your job is to resolve natural language location descriptions to specific AREAS (and occasionally provinces).

GEOGRAPHICAL HIERARCHY:
- REGIONS: Large areas (France, Egypt, Anatolia) - use get_available_regions()
- AREAS: Medium subdivisions (Brittany, Lower Egypt, Bithynia) - use query_region_areas()
- PROVINCES: Individual territories - use query_area_provinces() ONLY when necessary

⚠️ IMPORTANT: ALWAYS PREFER AREAS OVER PROVINCES!
- Areas are descriptive and map well to historical territorial changes
- Most conquests, losses, and transfers happen at the area level
- Only drill down to provinces for very specific edge cases (e.g., "just the city of Alexandria")

🎯 QUERY BY TAG - USE query_tag_territories() WHEN:
Commands reference a nation's EXISTING holdings rather than geographical locations:
- "All remaining USA territory goes to Canada"
- "All of BYZ goes to ARB except for Constantinople"  
- "The rest of France's holdings in Italy..."
- "X loses everything except for Y"
- "Remaining territories of X are transferred to Y"

The query_tag_territories() tool returns:
1. FULLY OWNED AREAS - areas where the tag owns ALL provinces (use these as area names)
2. PARTIAL PROVINCES - individual provinces from areas where the tag only owns some

This is MUCH more efficient than scanning regions one-by-one when you need to know
what a nation currently owns.

WORKFLOW:
1. Determine if the change references GEOGRAPHY (use regions/areas) or a TAG's HOLDINGS (use query_tag_territories)
2. For geography-based: Call get_available_regions() → query_region_areas() → return area names
3. For tag-based: Call query_tag_territories(tag) → use the fully owned areas + partial provinces
4. ONLY use query_area_provinces() if you need to split an area or handle edge cases

OUTPUT FORMAT (return as final response):
{
  "resolutions": [
    {
      "change_index": 0,
      "areas": ["Lower Egypt", "Nile Delta"],
      "provinces": []
    },
    {
      "change_index": 1,
      "areas": ["Brittany"],
      "provinces": []
    },
    {
      "change_index": 2,
      "areas": [],
      "provinces": [{"id": 358, "name": "Alexandria"}]
    }
  ]
}

NOTES:
- "areas" should contain area names that match the location
- "provinces" should almost always be empty - only use for specific edge cases
- If both areas and provinces are needed, list them separately
- The change_index corresponds to the index of the territorial change in the input list

EXAMPLES OF GOOD RESOLUTIONS:
- "Egypt" → areas: ["Lower Egypt", "Upper Egypt", "Nile Delta", ...]
- "Gaul" → areas: ["Brittany", "Normandy", "Aquitaine", ...]
- "Constantinople" → provinces: [{"id": 151, "name": "Thrace"}] (specific city)
- "The Levant coast" → areas: ["Syria", "Palestine", "Phoenicia"]
- "Northern Italy" → areas: ["Lombardy", "Venetia", "Piedmont"]
- "All remaining USA territory" → query_tag_territories("USA") → use returned areas + provinces"""


# Initialize LLM with timeout
llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=120,  # 2 minute timeout
    max_retries=2
)

# Tools for the geographer
tools = [get_available_regions, query_region_areas, query_area_provinces, query_tag_territories]

# Two versions: one that forces tool use, one that allows finishing
llm_with_tools_required = llm.bind_tools(tools, tool_choice="any")
llm_with_tools_auto = llm.bind_tools(tools, tool_choice="auto")


def apply_change_type(
    change_type: str,
    from_nation: Optional[str],
    to_nation: Optional[str],
    province_id: int,
    province_name: str,
    current_owner: str
) -> Optional[Dict[str, Any]]:
    """
    Apply a structured change type to determine the new owner value.
    
    Returns a province update dict, or None if no change is needed.
    
    Change types:
    - CONQUEST: Tracked nation gains from untracked → owner = to_nation
    - LOSS: Tracked nation loses to untracked → owner = "" (UNTRACK the province)
    - TRANSFER: Between tracked nations → owner = to_nation
    """
    new_owner = current_owner
    
    if change_type == "CONQUEST":
        if to_nation:
            new_owner = to_nation
        else:
            return None
            
    elif change_type == "LOSS":
        new_owner = ""  # Untrack the province
        
    elif change_type == "TRANSFER":
        if to_nation:
            new_owner = to_nation
        else:
            return None
            
    else:
        print(f"⚠️ Unknown change_type: {change_type}")
        return None
    
    if new_owner != current_owner:
        return {
            "id": province_id,
            "name": province_name,
            "owner": new_owner
        }
    return None


def expand_areas_to_provinces(area_names: List[str]) -> List[Dict[str, Any]]:
    """
    Expand a list of area names to their constituent provinces.
    
    Args:
        area_names: List of area names (e.g., ["Brittany", "Normandy"])
        
    Returns:
        List of province dicts with 'id' and 'name' keys
    """
    provinces = []
    seen_ids = set()
    
    for area_name in area_names:
        area_provinces = get_provinces_for_area(area_name)
        for p in area_provinces:
            if p['id'] not in seen_ids:
                provinces.append({"id": p['id'], "name": p['name']})
                seen_ids.add(p['id'])
    
    return provinces


def resolve_locations_with_llm(
    territorial_changes: List[Dict[str, Any]],
    scenario_id: str = "rome"
) -> Dict[int, Dict[str, Any]]:
    """
    Use LLM to resolve natural language locations to area names (and optionally province IDs).
    
    Args:
        territorial_changes: List of structured territorial changes from Dreamer
        scenario_id: The scenario ID
        
    Returns:
        Dict mapping change_index -> {"areas": [...], "provinces": [...]}
    """
    # Format the changes for the prompt
    changes_text = []
    for i, change in enumerate(territorial_changes):
        location = change.get("location", "Unknown")
        change_type = change.get("change_type", "Unknown")
        from_nation = change.get("from_nation", "N/A")
        to_nation = change.get("to_nation", "N/A")
        changes_text.append(
            f"  [{i}] Location: \"{location}\" (change_type: {change_type}, from: {from_nation}, to: {to_nation})"
        )
    
    user_prompt = f"""Resolve these territorial change locations to AREAS (preferred) or provinces (only if necessary):

{chr(10).join(changes_text)}

Remember: 
- ALWAYS prefer areas over provinces
- Query regions first, then their areas
- Only drill down to provinces for very specific locations that don't align with area boundaries

Return your final JSON answer with areas and/or provinces for each change."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    # Use tool-calling approach for proper querying
    max_iterations = 15
    iteration = 0
    
    print(f"🗺️  Geographer: Resolving {len(territorial_changes)} location(s) to areas...")
    response = llm_with_tools_required.invoke(messages)
    
    while response.tool_calls and iteration < max_iterations:
        iteration += 1
        print(f"🗺️  Geographer: Iteration {iteration}, executing {len(response.tool_calls)} tool calls")
        
        messages.append(response)
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            
            if tool_name == "get_available_regions":
                result = get_available_regions.invoke({})
            elif tool_name == "query_region_areas":
                result = query_region_areas.invoke(tool_args)
            elif tool_name == "query_area_provinces":
                result = query_area_provinces.invoke(tool_args)
            elif tool_name == "query_tag_territories":
                result = query_tag_territories.invoke(tool_args)
            else:
                result = f"Unknown tool: {tool_name}"
            
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call["id"]
            })
        
        response = llm_with_tools_auto.invoke(messages)
    
    # Extract the final response
    content = response.content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                text_parts.append(block.get("text", ""))
            else:
                text_parts.append(str(block))
        content = "\n".join(text_parts)
    content = content.strip() if content else ""
    
    # Parse the JSON response
    try:
        # Clean up markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        
        # Find JSON object
        if not content.startswith("{"):
            brace_start = content.find("{")
            if brace_start != -1:
                depth = 0
                for i, char in enumerate(content[brace_start:], brace_start):
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            content = content[brace_start:i+1]
                            break
        
        result = json.loads(content)
        
        # Convert to our expected format: change_index -> {areas, provinces}
        resolutions = {}
        for resolution in result.get("resolutions", []):
            change_index = resolution.get("change_index", 0)
            areas = resolution.get("areas", [])
            provinces = resolution.get("provinces", [])
            
            resolutions[change_index] = {
                "areas": areas,
                "provinces": provinces
            }
        
        return resolutions
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse geographer response: {e}")
        print(f"Raw response: {content[:500] if content else 'Empty'}")
        return {}


def interpret_territorial_changes(
    territorial_changes: List[Dict[str, Any]],
    scenario_id: str = "rome",
    current_provinces: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Interpret STRUCTURED territorial changes into province updates.
    
    This uses AREAS as the primary unit of territorial change, expanding
    them to provinces only at the final step.
    
    Args:
        territorial_changes: List of structured territorial change dicts from Dreamer
        scenario_id: The scenario ID for looking up nation tags
        current_provinces: Optional list of current province states (for context)
        
    Returns:
        Dict with province_updates list
    """
    global _available_tags, _current_provinces_cache
    
    # Load available nation tags
    _available_tags = get_scenario_tags(scenario_id)
    
    # Build province lookup cache from current provinces
    _current_provinces_cache = {}
    if current_provinces:
        for p in current_provinces:
            prov_id = p.get("id")
            if prov_id is not None:
                _current_provinces_cache[prov_id] = p
    
    # If no territorial changes, return empty
    if not territorial_changes:
        return {"province_updates": []}
    
    # Filter out any changes that are just informational (no actual change)
    valid_changes = [
        c for c in territorial_changes 
        if c.get("change_type") and c.get("location")
    ]
    
    if not valid_changes:
        return {"province_updates": []}
    
    print(f"🗺️  Geographer: Processing {len(valid_changes)} territorial change(s)")
    for i, change in enumerate(valid_changes):
        print(f"    [{i}] {change.get('change_type')}: {change.get('location')} "
              f"(from: {change.get('from_nation')}, to: {change.get('to_nation')})")
    
    # Use LLM to resolve locations to areas (and occasionally provinces)
    resolutions = resolve_locations_with_llm(valid_changes, scenario_id)
    
    # Apply changes based on change_type
    province_updates = []
    
    for i, change in enumerate(valid_changes):
        change_type = change.get("change_type", "")
        from_nation = change.get("from_nation")
        to_nation = change.get("to_nation")
        
        # Get resolved areas and provinces for this change
        resolution = resolutions.get(i, {"areas": [], "provinces": []})
        resolved_areas = resolution.get("areas", [])
        resolved_provinces = resolution.get("provinces", [])
        
        # Expand areas to provinces
        area_provinces = expand_areas_to_provinces(resolved_areas)
        
        # Combine with any directly specified provinces
        all_provinces = area_provinces + resolved_provinces
        
        # Remove duplicates
        seen_ids = set()
        unique_provinces = []
        for p in all_provinces:
            if p['id'] not in seen_ids:
                unique_provinces.append(p)
                seen_ids.add(p['id'])
        
        if not unique_provinces:
            print(f"⚠️ No provinces resolved for change [{i}]: {change.get('location')}")
            continue
        
        area_info = f" (from {len(resolved_areas)} areas)" if resolved_areas else ""
        print(f"🗺️  Applying {change_type} to {len(unique_provinces)} province(s){area_info}")
        
        for prov in unique_provinces:
            prov_id = prov["id"]
            prov_name = prov["name"]
            
            # Get current state
            current = _current_provinces_cache.get(prov_id, {})
            current_owner = current.get("owner", "")
            
            # Apply the change type
            update = apply_change_type(
                change_type=change_type,
                from_nation=from_nation,
                to_nation=to_nation,
                province_id=prov_id,
                province_name=prov_name,
                current_owner=current_owner
            )
            
            if update:
                province_updates.append(update)
    
    print(f"✓ Geographer: {len(province_updates)} province update(s) generated")
    
    return {"province_updates": province_updates}


# Keep backward compatibility with old prose-based interface
def interpret_territorial_changes_legacy(
    territorial_description: str,
    scenario_id: str = "rome",
    current_provinces: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    LEGACY: Interpret territorial changes from prose description.
    
    This is the old interface kept for backward compatibility.
    New code should use interpret_territorial_changes with structured changes.
    """
    global _available_tags, _current_provinces_cache
    
    # Load available nation tags
    _available_tags = get_scenario_tags(scenario_id)
    
    _current_provinces_cache = {}
    if current_provinces:
        for p in current_provinces:
            prov_id = p.get("id")
            if prov_id is not None:
                _current_provinces_cache[prov_id] = p
    
    if not territorial_description or territorial_description.strip() == "":
        return {"province_updates": []}
    
    no_change_phrases = [
        "no territorial changes",
        "no significant territorial",
        "borders remained",
        "no changes occurred",
        "territory unchanged"
    ]
    if any(phrase in territorial_description.lower() for phrase in no_change_phrases):
        return {"province_updates": []}
    
    print(f"⚠️ Using legacy prose-based territorial interpretation")
    print(f"   Consider updating to use structured territorial_changes")
    
    # Use the old prose-based system prompt
    legacy_prompt = """You are a geographer assistant. Translate prose territorial descriptions into province updates.
Query regions with get_available_regions and query_region_areas, then return JSON with province_updates.
PREFER working at the AREA level - expand to provinces only at the end."""
    
    tags_text = "Available nation tags:\n"
    if _available_tags:
        for tag, info in _available_tags.items():
            tags_text += f"  - {tag}: {info.get('name', 'Unknown')}\n"
    
    user_prompt = f"""=== TERRITORIAL CHANGES ===
{territorial_description}

=== {tags_text}

Query relevant regions and areas, then return JSON: {{"province_updates": [{{"id": 123, "name": "...", "owner": "TAG"}}]}}"""

    messages = [
        {"role": "system", "content": legacy_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    max_iterations = 15
    iteration = 0
    
    response = llm_with_tools_required.invoke(messages)
    
    while response.tool_calls and iteration < max_iterations:
        iteration += 1
        messages.append(response)
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            
            if tool_name == "get_available_regions":
                result = get_available_regions.invoke({})
            elif tool_name == "query_region_areas":
                result = query_region_areas.invoke(tool_args)
            elif tool_name == "query_area_provinces":
                result = query_area_provinces.invoke(tool_args)
            elif tool_name == "query_tag_territories":
                result = query_tag_territories.invoke(tool_args)
            else:
                result = f"Unknown tool: {tool_name}"
            
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call["id"]
            })
        
        response = llm_with_tools_auto.invoke(messages)
    
    content = response.content
    if isinstance(content, list):
        content = "\n".join(str(b) for b in content)
    content = content.strip() if content else ""
    
    try:
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        
        if not content.startswith("{"):
            brace_start = content.find("{")
            if brace_start != -1:
                depth = 0
                for i, char in enumerate(content[brace_start:], brace_start):
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            content = content[brace_start:i+1]
                            break
        
        result = json.loads(content)
        if "province_updates" not in result:
            result["province_updates"] = []
        return result
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse legacy geographer response: {e}")
        return {"province_updates": []}
