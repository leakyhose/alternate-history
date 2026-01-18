"""
Geographer Agent - Translates territorial descriptions to province updates via AREAS.

The Geographer interprets the Dreamer's STRUCTURED territorial changes
and converts them into specific province-level OWNER updates by calling ACTION TOOLS.

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

WORKFLOW:
The Geographer processes changes ONE AT A TIME, in order:
1. Read the change at index N
2. Use QUERY tools to find the relevant areas/provinces
3. Call the appropriate ACTION tool to apply the change
4. Move to index N+1

ACTION TOOLS (modify provinces directly):
- transfer_areas: Transfer entire areas from one nation to another
- transfer_provinces: Transfer specific provinces from one nation to another  
- annex_nation: Transfer ALL territory from one nation to another (shortcut)
- untrack_areas: Mark areas as lost to untracked nations
- untrack_provinces: Mark specific provinces as lost to untracked nations

QUERY TOOLS (information gathering only):
- get_available_regions: List all regions
- query_region_areas: List areas in a region with ownership info
- query_area_provinces: List provinces in an area (use sparingly)
- query_tag_territories: List all territory owned by a nation
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
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

# Accumulated province updates from action tools
_pending_updates: List[Dict[str, Any]] = []


class ProvinceUpdate(BaseModel):
    """A single province update."""
    id: int = Field(description="The province ID")
    name: str = Field(description="The province name")
    owner: str = Field(description="The new owner tag (e.g., 'BYZ', 'ARB'), or empty string '' if lost to an untracked state")


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
    
    ⛔⛔⛔ WARNING: YOU ALMOST NEVER NEED THIS TOOL! ⛔⛔⛔
    
    99% of the time, you should use transfer_areas() instead of drilling down to provinces.
    
    ONLY use this tool when you MUST split an area, such as:
    - "Only the coastal provinces of Brittany" (specific provinces within an area)
    - "The province containing city X" (a single specific province)
    
    If the change mentions a region, country, or area name - use AREAS, not provinces!
    
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


# =============================================================================
# ACTION TOOLS - These modify the province state directly
# =============================================================================

@tool
def transfer_areas(area_names: List[str], to_nation: str) -> str:
    """
    🎯 ACTION TOOL: Transfer entire AREAS to a new owner.
    
    Use this tool to transfer one or more areas to a nation. All provinces
    within the specified areas will have their owner changed to the new nation.
    
    This is the PREFERRED way to make territorial changes - work at the area level!
    
    Args:
        area_names: List of area names to transfer (e.g., ["Brittany", "Normandy"])
        to_nation: The nation TAG that will receive these areas (e.g., "FRA", "BYZ")
        
    Returns:
        Status message indicating how many provinces were transferred
        
    Example usage:
        - TRANSFER from FRA to ENG: transfer_areas(["Brittany", "Normandy"], "ENG")
        - CONQUEST by ARB: transfer_areas(["Lower Egypt", "Nile Delta"], "ARB")
    """
    global _pending_updates
    
    if not area_names:
        return "❌ Error: No area names provided."
    
    if not to_nation:
        return "❌ Error: No destination nation tag provided."
    
    provinces_transferred = []
    areas_processed = []
    areas_not_found = []
    
    for area_name in area_names:
        area_provinces = get_provinces_for_area(area_name)
        
        if not area_provinces:
            areas_not_found.append(area_name)
            continue
        
        areas_processed.append(area_name)
        
        for p in area_provinces:
            prov_id = p['id']
            prov_name = p['name']
            
            # Get current owner for comparison
            current = _current_provinces_cache.get(prov_id, {})
            current_owner = current.get('owner', '')
            
            # Only add update if owner is actually changing
            if current_owner != to_nation:
                update = {
                    "id": prov_id,
                    "name": prov_name,
                    "owner": to_nation
                }
                _pending_updates.append(update)
                provinces_transferred.append(f"{prov_name} (ID {prov_id})")
                
                # Also update the cache so subsequent queries reflect the change
                if prov_id in _current_provinces_cache:
                    _current_provinces_cache[prov_id]['owner'] = to_nation
    
    # Build response
    result_lines = []
    
    if areas_processed:
        result_lines.append(f"✅ Transferred {len(areas_processed)} area(s) to {to_nation}:")
        for area in areas_processed:
            result_lines.append(f"   - {area}")
        result_lines.append(f"   Total: {len(provinces_transferred)} provinces")
    
    if areas_not_found:
        result_lines.append(f"⚠️ Areas not found: {', '.join(areas_not_found)}")
    
    if not areas_processed and not areas_not_found:
        result_lines.append("❌ No areas were processed.")
    
    return "\n".join(result_lines)


@tool
def transfer_provinces(province_ids: List[int], to_nation: str) -> str:
    """
    ACTION TOOL: Transfer specific PROVINCES to a new owner.
    
    ⛔⛔⛔ WARNING: YOU ALMOST NEVER NEED THIS TOOL! ⛔⛔⛔
    
    Use transfer_areas() instead! It's faster and cleaner.
    
    ONLY use transfer_provinces() when:
    - You must transfer a subset of provinces WITHIN a single area
    - The change explicitly names individual cities/provinces
    
    If the change mentions countries, regions, or areas - use transfer_areas()!
    
    Args:
        province_ids: List of province IDs to transfer (e.g., [358, 359, 360])
        to_nation: The nation TAG that will receive these provinces (e.g., "FRA", "BYZ")
        
    Returns:
        Status message indicating which provinces were transferred
    """
    global _pending_updates
    
    if not province_ids:
        return "❌ Error: No province IDs provided."
    
    if not to_nation:
        return "❌ Error: No destination nation tag provided."
    
    provinces_transferred = []
    provinces_not_found = []
    
    # We need to look up province names from our areas data
    all_areas = load_areas()
    id_to_name = {}
    for area_provinces in all_areas.values():
        for p in area_provinces:
            id_to_name[p['id']] = p['name']
    
    for prov_id in province_ids:
        prov_name = id_to_name.get(prov_id, f"Province {prov_id}")
        
        # Get current owner
        current = _current_provinces_cache.get(prov_id, {})
        current_owner = current.get('owner', '')
        
        if current_owner != to_nation:
            update = {
                "id": prov_id,
                "name": prov_name,
                "owner": to_nation
            }
            _pending_updates.append(update)
            provinces_transferred.append(f"{prov_name} (ID {prov_id})")
            
            # Update cache
            if prov_id in _current_provinces_cache:
                _current_provinces_cache[prov_id]['owner'] = to_nation
        else:
            provinces_not_found.append(str(prov_id))
    
    # Build response
    result_lines = []
    
    if provinces_transferred:
        result_lines.append(f"✅ Transferred {len(provinces_transferred)} province(s) to {to_nation}:")
        for prov in provinces_transferred[:10]:
            result_lines.append(f"   - {prov}")
        if len(provinces_transferred) > 10:
            result_lines.append(f"   ... and {len(provinces_transferred) - 10} more")
    
    if provinces_not_found:
        result_lines.append(f"⚠️ Provinces already owned by {to_nation} or not found: {', '.join(provinces_not_found)}")
    
    return "\n".join(result_lines) if result_lines else "No provinces were transferred."


@tool
def annex_nation(from_nation: str, to_nation: str) -> str:
    """
    🎯 ACTION TOOL: Transfer ALL territory from one nation to another.
    
    This is a SHORTCUT tool for when one nation completely annexes another.
    It transfers every province owned by from_nation to to_nation.
    
    Use this when:
    - "All of X goes to Y"
    - "X is completely annexed by Y"
    - "Y conquers all remaining X territory"
    
    Args:
        from_nation: The nation TAG losing all territory (e.g., "BYZ")
        to_nation: The nation TAG gaining all territory (e.g., "ARB")
        
    Returns:
        Status message indicating how many provinces were transferred
        
    Example usage:
        - Complete annexation: annex_nation("BYZ", "ARB")
    """
    global _pending_updates
    
    if not from_nation:
        return "❌ Error: No source nation tag provided."
    
    if not to_nation:
        return "❌ Error: No destination nation tag provided."
    
    if from_nation == to_nation:
        return "❌ Error: Source and destination nations cannot be the same."
    
    # Find all provinces owned by from_nation
    provinces_to_transfer = []
    
    for prov_id, prov_data in _current_provinces_cache.items():
        if prov_data.get('owner') == from_nation:
            provinces_to_transfer.append({
                'id': prov_id,
                'name': prov_data.get('name', f"Province {prov_id}")
            })
    
    if not provinces_to_transfer:
        return f"⚠️ {from_nation} does not own any tracked provinces. Nothing to transfer."
    
    # Transfer all provinces
    for prov in provinces_to_transfer:
        update = {
            "id": prov['id'],
            "name": prov['name'],
            "owner": to_nation
        }
        _pending_updates.append(update)
        
        # Update cache
        if prov['id'] in _current_provinces_cache:
            _current_provinces_cache[prov['id']]['owner'] = to_nation
    
    return f"✅ ANNEXED: All {len(provinces_to_transfer)} provinces transferred from {from_nation} to {to_nation}."


@tool
def untrack_areas(area_names: List[str]) -> str:
    """
    🎯 ACTION TOOL: Mark areas as LOST to untracked nations.
    
    Use this when a tracked nation loses territory to a nation we don't track.
    The provinces will have their owner set to "" (empty), meaning they're
    no longer part of any tracked nation.
    
    This is for LOSS change types where territory goes to non-scenario nations.
    
    Args:
        area_names: List of area names to untrack (e.g., ["Brittany", "Normandy"])
        
    Returns:
        Status message indicating how many provinces were untracked
        
    Example usage:
        - Loss to barbarians: untrack_areas(["Pannonia", "Dacia"])
        - Loss to untracked nation: untrack_areas(["Northern Britain"])
    """
    global _pending_updates
    
    if not area_names:
        return "❌ Error: No area names provided."
    
    provinces_untracked = []
    areas_processed = []
    areas_not_found = []
    
    for area_name in area_names:
        area_provinces = get_provinces_for_area(area_name)
        
        if not area_provinces:
            areas_not_found.append(area_name)
            continue
        
        areas_processed.append(area_name)
        
        for p in area_provinces:
            prov_id = p['id']
            prov_name = p['name']
            
            # Only untrack if currently tracked
            current = _current_provinces_cache.get(prov_id, {})
            current_owner = current.get('owner', '')
            
            if current_owner:  # Has an owner, so untrack it
                update = {
                    "id": prov_id,
                    "name": prov_name,
                    "owner": ""  # Empty string = untracked
                }
                _pending_updates.append(update)
                provinces_untracked.append(f"{prov_name} (ID {prov_id})")
                
                # Update cache
                if prov_id in _current_provinces_cache:
                    _current_provinces_cache[prov_id]['owner'] = ""
    
    # Build response
    result_lines = []
    
    if areas_processed:
        result_lines.append(f"✅ Untracked {len(areas_processed)} area(s) (lost to non-scenario nations):")
        for area in areas_processed:
            result_lines.append(f"   - {area}")
        result_lines.append(f"   Total: {len(provinces_untracked)} provinces")
    
    if areas_not_found:
        result_lines.append(f"⚠️ Areas not found: {', '.join(areas_not_found)}")
    
    return "\n".join(result_lines) if result_lines else "No areas were untracked."


@tool
def untrack_provinces(province_ids: List[int]) -> str:
    """
    ACTION TOOL: Mark specific PROVINCES as lost to untracked nations.
    
    ⛔⛔⛔ WARNING: YOU ALMOST NEVER NEED THIS TOOL! ⛔⛔⛔
    
    Use untrack_areas() instead! It's faster and cleaner.
    
    ONLY use this when you must untrack a subset of provinces within an area.
    
    Args:
        province_ids: List of province IDs to untrack (e.g., [358, 359])
        
    Returns:
        Status message indicating which provinces were untracked
    """
    global _pending_updates
    
    if not province_ids:
        return "❌ Error: No province IDs provided."
    
    provinces_untracked = []
    
    # Look up province names
    all_areas = load_areas()
    id_to_name = {}
    for area_provinces in all_areas.values():
        for p in area_provinces:
            id_to_name[p['id']] = p['name']
    
    for prov_id in province_ids:
        prov_name = id_to_name.get(prov_id, f"Province {prov_id}")
        
        current = _current_provinces_cache.get(prov_id, {})
        current_owner = current.get('owner', '')
        
        if current_owner:
            update = {
                "id": prov_id,
                "name": prov_name,
                "owner": ""
            }
            _pending_updates.append(update)
            provinces_untracked.append(f"{prov_name} (ID {prov_id})")
            
            if prov_id in _current_provinces_cache:
                _current_provinces_cache[prov_id]['owner'] = ""
    
    if provinces_untracked:
        return f"✅ Untracked {len(provinces_untracked)} province(s):\n" + "\n".join(f"   - {p}" for p in provinces_untracked[:10])
    else:
        return "⚠️ No provinces were untracked (already untracked or not found)."


@tool
def mark_complete() -> str:
    """
    🏁 FINISH TOOL: Call this when you have processed ALL territorial changes.
    
    After you have gone through each change index and called the appropriate
    action tools (transfer_areas, transfer_provinces, annex_nation, etc.),
    call this tool to signal that you are done.
    
    Returns:
        Final status summary
    """
    global _pending_updates
    
    count = len(_pending_updates)
    return f"🏁 COMPLETE: {count} province update(s) queued for application."


# =============================================================================
# SYSTEM PROMPT - Explains the workflow to the LLM
# =============================================================================

SYSTEM_PROMPT = """You are a geographer assistant for an alternate history simulation.
Your job is to process territorial changes by calling ACTION TOOLS that directly modify province ownership.

============================================================
CRITICAL RULES - READ THIS FIRST!
============================================================

1. NEVER QUERY PROVINCES! Use transfer_areas(), NOT transfer_provinces()!
   - query_area_provinces() should be called in LESS THAN 1% of cases
   - transfer_provinces() should be called in LESS THAN 1% of cases
   - If you find yourself wanting to query provinces, STOP and use areas instead!

2. WORK AT THE AREA LEVEL! Areas are the correct granularity for 99% of changes.
   - "Transfer Quebec" → transfer_areas(["Lower Canada", "Laurentian", ...], "QUE")
   - NOT: query each area's provinces and then transfer_provinces()

3. MINIMIZE QUERIES! Don't query what you don't need.
   - If change says "Egypt" → query_region_areas("Egypt") DIRECTLY
   - Do NOT call get_available_regions() first!
   - If change says "All of BYZ" → annex_nation("BYZ", "ARB") DIRECTLY, NO queries!

============================================================
GEOGRAPHICAL HIERARCHY
============================================================
- REGIONS: Large areas (France, Egypt, Canada) 
- AREAS: Medium subdivisions (Brittany, Lower Egypt, Lower Canada) ← WORK HERE!
- PROVINCES: Individual territories ← ALMOST NEVER TOUCH THESE!

============================================================
TOOLS
============================================================

QUERY TOOLS (use sparingly):
- get_available_regions(): List all regions - ONLY if you don't know the region name
- query_region_areas(region_name): List areas in a region - this is your main query tool
- query_area_provinces(area_name): ⛔ RARELY USE! Only for edge cases like splitting an area
- query_tag_territories(tag): List all territory owned by a nation

ACTION TOOLS:
- transfer_areas(area_names, to_nation): ✅ PRIMARY TOOL - transfer entire areas
- transfer_provinces(province_ids, to_nation): ⛔ RARELY USE! Only for specific province transfers
- annex_nation(from_nation, to_nation): Transfer ALL territory from one nation to another
- untrack_areas(area_names): Mark areas as lost to untracked nations
- untrack_provinces(province_ids): ⛔ RARELY USE! Only for specific province losses

FINISH:
- mark_complete(): Call when ALL changes are processed

============================================================
WORKFLOW
============================================================

Process changes ONE AT A TIME in order:

1. READ the change
2. QUERY ONLY if needed (usually just query_region_areas for the relevant region)
3. CALL ACTION - almost always transfer_areas() or untrack_areas()
4. NEXT change
5. mark_complete() when done

============================================================
EXAMPLES
============================================================

Change: "Quebec becomes independent from Canada"
WRONG: query_area_provinces("Lower Canada"), then transfer_provinces([...])
RIGHT: query_region_areas("Canada"), then transfer_areas(["Lower Canada", "Laurentian", ...], "QUE")

Change: "Egypt goes to ARB" 
→ query_region_areas("Egypt") 
→ transfer_areas(["Lower Egypt", "Upper Egypt", ...], "ARB")

Change: "All BYZ territory goes to ARB"
→ annex_nation("BYZ", "ARB")  // NO queries needed!

Change: "Gaul lost to Germanic tribes"  
→ query_region_areas("Gaul")
→ untrack_areas(["Brittany", "Normandy", "Aquitaine", ...])

After ALL changes processed:
→ mark_complete()"""


# Initialize LLM with timeout
llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=120,  # 2 minute timeout
    max_retries=2
)

# Query tools (information gathering)
query_tools = [
    get_available_regions, 
    query_region_areas, 
    query_area_provinces, 
    query_tag_territories
]

# Action tools (modify provinces)
action_tools = [
    transfer_areas,
    transfer_provinces,
    annex_nation,
    untrack_areas,
    untrack_provinces,
    mark_complete
]

# All tools combined
all_tools = query_tools + action_tools

# Bind tools to LLM - always allow tool use
llm_with_tools = llm.bind_tools(all_tools, tool_choice="auto")


# =============================================================================
# TOOL EXECUTION HELPER
# =============================================================================

def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute a tool by name and return the result."""
    tool_map = {
        # Query tools
        "get_available_regions": get_available_regions,
        "query_region_areas": query_region_areas,
        "query_area_provinces": query_area_provinces,
        "query_tag_territories": query_tag_territories,
        # Action tools
        "transfer_areas": transfer_areas,
        "transfer_provinces": transfer_provinces,
        "annex_nation": annex_nation,
        "untrack_areas": untrack_areas,
        "untrack_provinces": untrack_provinces,
        "mark_complete": mark_complete,
    }
    
    tool_func = tool_map.get(tool_name)
    if tool_func:
        return tool_func.invoke(tool_args)
    else:
        return f"Unknown tool: {tool_name}"


# =============================================================================
# MAIN FUNCTION - Process territorial changes via action tools
# =============================================================================

def interpret_territorial_changes(
    territorial_changes: List[Dict[str, Any]],
    scenario_id: str = "rome",
    current_provinces: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Interpret STRUCTURED territorial changes using action tools.
    
    Instead of returning JSON for post-processing, this function:
    1. Has the LLM call action tools directly to modify province state
    2. Collects all updates in _pending_updates
    3. Returns the province_updates list for the workflow to apply
    
    Args:
        territorial_changes: List of structured territorial change dicts from Dreamer
        scenario_id: The scenario ID for looking up nation tags
        current_provinces: Optional list of current province states (for context)
        
    Returns:
        Dict with:
        - province_updates: List of province updates to apply
        - status: Status message (for logging only, not for further processing)
    """
    global _available_tags, _current_provinces_cache, _pending_updates
    
    # Reset pending updates for this run
    _pending_updates = []
    
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
        return {
            "province_updates": [],
            "status": "No territorial changes to process."
        }
    
    # Filter out any changes that are just informational (no actual change)
    valid_changes = [
        c for c in territorial_changes 
        if c.get("change_type") and c.get("location")
    ]
    
    if not valid_changes:
        return {
            "province_updates": [],
            "status": "No valid territorial changes to process."
        }
    
    print(f"[Geographer] Processing {len(valid_changes)} territorial change(s)")
    
    # Format the changes for the prompt
    changes_text = []
    for i, change in enumerate(valid_changes):
        location = change.get("location", "Unknown")
        change_type = change.get("change_type", "Unknown")
        from_nation = change.get("from_nation", "N/A")
        to_nation = change.get("to_nation", "N/A")
        context = change.get("context", "")
        
        change_line = f"[{i}] {change_type}: \"{location}\""
        if from_nation and from_nation != "N/A":
            change_line += f" (from: {from_nation})"
        if to_nation and to_nation != "N/A":
            change_line += f" (to: {to_nation})"
        if context:
            change_line += f"\n    Context: {context}"
        changes_text.append(change_line)
        
        print(f"    {change_line}")
    
    # Build available tags info
    tags_text = "Available nation tags:\n"
    if _available_tags:
        for tag, info in _available_tags.items():
            tags_text += f"  - {tag}: {info.get('name', 'Unknown')}\n"
    
    user_prompt = f"""Process these territorial changes by calling the appropriate ACTION TOOLS.

=== TERRITORIAL CHANGES ===
{chr(10).join(changes_text)}

=== {tags_text}

INSTRUCTIONS:
1. Process each change IN ORDER, starting from [0]
2. For each change:
   a. Use QUERY tools to find the relevant areas/provinces
   b. Call the appropriate ACTION tool to apply the change
3. After processing ALL changes, call mark_complete()

Remember:
- CONQUEST/TRANSFER → transfer_areas() or annex_nation()
- LOSS → untrack_areas()
- Prefer areas over provinces
- Process changes one at a time

Begin processing change [0]."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    # Tool-calling loop
    max_iterations = 30  # Allow more iterations for multiple changes
    iteration = 0
    completed = False
    
    response = llm_with_tools.invoke(messages)
    
    while iteration < max_iterations and not completed:
        iteration += 1
        
        # Check if there are tool calls
        if not response.tool_calls:
            # No tool calls - LLM is done or confused
            print(f"[Geographer] Iteration {iteration}: No tool calls, finishing")
            break
        
        print(f"[Geographer] Iteration {iteration}: {len(response.tool_calls)} tool call(s)")
        
        messages.append(response)
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            
            # Log all tool calls with their arguments
            if tool_name == "mark_complete":
                print(f"    -> COMPLETE")
                completed = True
            elif tool_name in ["transfer_areas", "transfer_provinces", "annex_nation", "untrack_areas", "untrack_provinces"]:
                print(f"    -> {tool_name}({tool_args})")
            else:
                # Query tools - show what's being queried
                print(f"    -> {tool_name}({tool_args})")
            
            # Execute the tool
            result = execute_tool(tool_name, tool_args)
            
            # Add tool result to messages
            messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
        
        if not completed:
            response = llm_with_tools.invoke(messages)
    
    # Gather results
    province_updates = _pending_updates.copy()
    update_count = len(province_updates)
    
    status = f"[Geographer] Done: {update_count} province update(s) generated"
    print(status)
    
    return {
        "province_updates": province_updates,
        "status": status
    }
