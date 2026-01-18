"""
Geographer Agent - Translates territorial descriptions to province updates.

The Geographer interprets the Dreamer's STRUCTURED territorial changes
and converts them into specific province-level OWNER updates.

The Dreamer provides structured changes with:
- location: Natural language description of WHERE
- change_type: CONQUEST | LOSS | TRANSFER
- from_nation: Nation losing territory (if applicable)
- to_nation: Nation gaining territory (if applicable)

These changes describe the NET TERRITORIAL STATE at the END of the period,
compared to the beginning. Intermediate changes during the period are not tracked.

The Geographer's job is to:
1. Resolve the natural language "location" to specific province IDs
2. Apply the change based on change_type (no interpretation of intent needed)
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any, Optional, Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from util.province_memory import (
    load_region_provinces,
    get_all_region_names,
    get_provinces_for_region
)
from util.scenario import get_scenario_tags

load_dotenv()


# Module-level caches for tool access
_region_names_cache: Optional[List[str]] = None
_available_tags: Dict[str, Dict[str, Any]] = {}
_current_provinces_cache: Dict[int, Dict[str, Any]] = {}  # province_id -> province data


class ProvinceUpdate(BaseModel):
    """A single province update."""
    id: int = Field(description="The province ID")
    name: str = Field(description="The province name")
    owner: str = Field(description="The new owner tag (e.g., 'BYZ', 'ARB'), or empty string '' if lost to an untracked state")


class LocationResolution(BaseModel):
    """Resolution of a location description to province IDs."""
    province_ids: List[int] = Field(
        description="List of province IDs that match the location description"
    )


class GeographerOutput(BaseModel):
    """Structured output from the Geographer agent."""
    province_updates: List[ProvinceUpdate] = Field(
        default_factory=list,
        description="List of province updates with id, name, owner, and control fields"
    )


@tool
def get_available_regions() -> str:
    """
    Get the list of all available region names that can be queried.
    Call this first to see what regions exist before querying specific ones.
    Returns a list of region names
    """
    global _region_names_cache
    
    if _region_names_cache is None:
        _region_names_cache = get_all_region_names()
    
    if not _region_names_cache:
        return "No regions available."
    
    # Group regions by general area for better readability
    return f"Available regions ({len(_region_names_cache)} total):\n" + "\n".join(
        f"  - {name}" for name in sorted(_region_names_cache)
    )


@tool
def query_region_provinces(region_name: str) -> str:
    """
    Query the provinces within a specific region.
    Returns province IDs, names, and their CURRENT owner/controller status.
    Use this to find province IDs for regions mentioned in territorial changes.
    
    Args:
        region_name: The exact region name (e.g., 'egypt_region', 'syria_region')
        
    Returns:
        List of provinces with their IDs, names, and current ownership status
    """
    provinces = get_provinces_for_region(region_name)
    
    if not provinces:
        # Try adding _region suffix if not present
        if not region_name.endswith("_region"):
            provinces = get_provinces_for_region(f"{region_name}_region")
        
        if not provinces:
            return f"Region '{region_name}' not found. Use get_available_regions() to see valid region names."
    
    lines = [f"Provinces in {region_name}:"]
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


SYSTEM_PROMPT = """You are a geographer assistant for an alternate history simulation.
Your job is to resolve natural language location descriptions to specific province IDs.

You will receive STRUCTURED territorial changes with:
- location: Natural language description (e.g., "Egypt", "Syria up to the Euphrates", "Thrace and Greece")
- change_type: The type of change (CONQUEST, LOSS, TRANSFER)
- from_nation / to_nation: The nations involved

YOUR ONLY JOB is to find which province IDs match each location description.
You do NOT need to interpret intent - the change_type already tells us what to do.

IMPORTANT - CAREFUL CONSIDERATION:
- Think carefully about each territorial change before resolving it.
- Consider the historical and geographical context of the location.
- Many province names may be obscure, archaic, or use historical names that differ from modern ones.
- If a province name seems unfamiliar, try to deduce its likely location based on:
  * The region it's in (e.g., a province in "egypt_region" is likely in Egypt)
  * Historical context (ancient city names, Latin/Greek names, etc.)
  * Neighboring provinces you do recognize
- When in doubt, include provinces that could plausibly match rather than excluding them.
- For broad locations like "Egypt" or "Gaul", include ALL provinces in the relevant region(s).
- For specific locations like "Alexandria" or "along the Danube", be more selective.

WORKFLOW:
1. First, call get_available_regions to see all region names
2. For each territorial change, identify which regions match the location description
3. Call query_region_provinces for each relevant region to get province IDs
4. Carefully review the province names - even if unfamiliar, consider if they fit the location
5. Return the list of province IDs for each change

OUTPUT FORMAT (return as final response):
{
  "resolutions": [
    {
      "change_index": 0,
      "province_ids": [101, 102, 103],
      "province_names": ["Alexandria", "Memphis", "Thebes"]
    },
    ...
  ]
}

The change_index corresponds to the index of the territorial change in the input list."""


# Initialize LLM with timeout
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=120,  # 2 minute timeout
    max_retries=2
)

# Tools for the geographer
tools = [get_available_regions, query_region_provinces]

# Two versions: one that forces tool use, one that allows finishing
llm_with_tools_required = llm.bind_tools(tools, tool_choice="any")
llm_with_tools_auto = llm.bind_tools(tools, tool_choice="auto")

# Structured output version
llm_structured = llm.with_structured_output(GeographerOutput)


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
    
    IMPORTANT: These describe the NET change from period start to end.
    When a province is LOST to an untracked state (barbarians, Persians, etc.),
    we set owner = "" (empty string). This effectively UNTRACKS the province - we only
    track provinces owned by nations defined in the scenario metadata.
    """
    new_owner = current_owner
    
    if change_type == "CONQUEST":
        # Tracked nation gains territory from untracked state
        # to_nation is required, from_nation is null/untracked
        if to_nation:
            new_owner = to_nation
        else:
            return None  # Invalid: CONQUEST needs to_nation
            
    elif change_type == "LOSS":
        # Tracked nation loses territory to untracked state
        # Province becomes UNTRACKED (owner = empty string)
        # This is used when territory is lost to barbarians, Persians (if not tracked), etc.
        # from_nation should be the current owner, to_nation is null
        new_owner = ""  # Untrack the province - no tracked nation owns it
        
    elif change_type == "TRANSFER":
        # Territory moves between two tracked nations
        # Both from_nation and to_nation required
        if to_nation:
            new_owner = to_nation
        else:
            return None  # Invalid: TRANSFER needs to_nation
            
    else:
        print(f"⚠️ Unknown change_type: {change_type}")
        return None
    
    # Only return an update if something changed
    if new_owner != current_owner:
        return {
            "id": province_id,
            "name": province_name,
            "owner": new_owner
        }
    return None


def resolve_locations_with_llm(
    territorial_changes: List[Dict[str, Any]],
    scenario_id: str = "rome"
) -> Dict[int, List[Dict[str, Any]]]:
    """
    Use LLM to resolve natural language locations to province IDs.
    
    Args:
        territorial_changes: List of structured territorial changes from Dreamer
        scenario_id: The scenario ID
        
    Returns:
        Dict mapping change_index -> list of {province_id, province_name}
    """
    global _region_names_cache
    
    # Pre-load region names
    _region_names_cache = get_all_region_names()
    
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
    
    user_prompt = f"""Resolve these territorial change locations to province IDs:

{chr(10).join(changes_text)}

Query the relevant regions to find province IDs for each location, then return your final JSON answer."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    # Use tool-calling approach for proper querying
    max_iterations = 10
    iteration = 0
    
    print(f"🗺️  Geographer: Resolving {len(territorial_changes)} location(s)...")
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
            elif tool_name == "query_region_provinces":
                result = query_region_provinces.invoke(tool_args)
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
        
        # Convert to our expected format: change_index -> list of provinces
        resolutions = {}
        for resolution in result.get("resolutions", []):
            change_index = resolution.get("change_index", 0)
            province_ids = resolution.get("province_ids", [])
            province_names = resolution.get("province_names", [])
            
            provinces = []
            for j, pid in enumerate(province_ids):
                name = province_names[j] if j < len(province_names) else f"Province {pid}"
                provinces.append({"id": pid, "name": name})
            
            resolutions[change_index] = provinces
        
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
    
    This is the new format where the Dreamer provides structured changes with:
    - location: Natural language description of WHERE
    - change_type: CONQUEST | LOSS | TRANSFER | OCCUPATION | LIBERATION
    - from_nation: Nation losing territory (if applicable)
    - to_nation: Nation gaining territory (if applicable)
    
    The Geographer resolves locations to province IDs and applies the change_type
    deterministically - no interpretation of intent needed.
    
    IMPORTANT: When change_type is LOSS, the province becomes UNTRACKED (owner = "").
    This happens when territory is lost to a nation not defined in the scenario metadata
    (e.g., barbarians, Persians if not tracked). We only track provinces owned by
    nations in the scenario metadata.
    
    Args:
        territorial_changes: List of structured territorial change dicts from Dreamer
        scenario_id: The scenario ID for looking up nation tags
        current_provinces: Optional list of current province states (for context)
        
    Returns:
        Dict with province_updates list
    """
    global _available_tags, _region_names_cache, _current_provinces_cache
    
    # Load available nation tags
    _available_tags = get_scenario_tags(scenario_id)
    
    # Pre-load region names
    _region_names_cache = get_all_region_names()
    
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
    
    # Use LLM to resolve locations to province IDs
    resolutions = resolve_locations_with_llm(valid_changes, scenario_id)
    
    # Apply changes based on change_type (deterministic, no LLM needed)
    province_updates = []
    
    for i, change in enumerate(valid_changes):
        change_type = change.get("change_type", "")
        from_nation = change.get("from_nation")
        to_nation = change.get("to_nation")
        
        # Get resolved provinces for this change
        resolved_provinces = resolutions.get(i, [])
        
        if not resolved_provinces:
            print(f"⚠️ No provinces resolved for change [{i}]: {change.get('location')}")
            continue
        
        print(f"🗺️  Applying {change_type} to {len(resolved_provinces)} province(s)")
        
        for prov in resolved_provinces:
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
    global _available_tags, _region_names_cache, _current_provinces_cache
    
    # Load available nation tags
    _available_tags = get_scenario_tags(scenario_id)
    _region_names_cache = get_all_region_names()
    
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
Query regions with get_available_regions and query_region_provinces, then return JSON with province_updates."""
    
    tags_text = "Available nation tags:\n"
    if _available_tags:
        for tag, info in _available_tags.items():
            tags_text += f"  - {tag}: {info.get('name', 'Unknown')}\n"
    
    user_prompt = f"""=== TERRITORIAL CHANGES ===
{territorial_description}

=== {tags_text}

Query relevant regions, then return JSON: {{"province_updates": [{{"id": 123, "name": "...", "owner": "TAG"}}]}}"""

    messages = [
        {"role": "system", "content": legacy_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    max_iterations = 10
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
            elif tool_name == "query_region_provinces":
                result = query_region_provinces.invoke(tool_args)
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
