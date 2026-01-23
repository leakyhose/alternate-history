"""
Geographer Agent - Translates territorial descriptions to province updates via areas.

Hierarchy:
- REGIONS: Large geographical areas (e.g., "France", "Egypt", "Anatolia")
- AREAS: Medium-sized subdivisions of regions (e.g., "Brittany", "Lower Egypt")
- PROVINCES: Individual territories within areas (rarely needed)

The geographer works primarily at the AREA level, using action tools to apply changes.
"""
from dotenv import load_dotenv
import os
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field

from util.province_memory import (
    get_all_region_names, get_areas_for_region, get_all_area_names,
    get_provinces_for_area, load_areas
)
from util.scenario import get_scenario_tags

load_dotenv()

# Module-level caches
_available_tags: Dict[str, Dict[str, Any]] = {}
_current_provinces_cache: Dict[int, Dict[str, Any]] = {}
_pending_updates: List[Dict[str, Any]] = []


class ProvinceUpdate(BaseModel):
    """A single province update."""
    id: int = Field(description="Province ID")
    name: str = Field(description="Province name")
    owner: str = Field(description="New owner tag or empty string if untracked")


# Query tools

@tool
def get_available_regions() -> str:
    """Get all available region names. Call this first to see what regions exist."""
    region_names = get_all_region_names()
    if not region_names:
        return "No regions available."
    return f"Available regions ({len(region_names)} total):\n" + "\n".join(
        f"  - {name}" for name in sorted(region_names)
    )


@tool
def query_region_areas(region_name: str) -> str:
    """Get areas within a region with ownership summary."""
    areas = get_areas_for_region(region_name)
    if not areas:
        return f"Region '{region_name}' not found. Use get_available_regions() to see valid names."

    lines = [f"Areas in {region_name} ({len(areas)} areas):"]
    for area_name in areas:
        provinces = get_provinces_for_area(area_name)
        if provinces:
            owners = {}
            for p in provinces:
                current = _current_provinces_cache.get(p['id'])
                owner = current.get('owner', '?') if current else 'untracked'
                owners[owner] = owners.get(owner, 0) + 1

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
    Get individual provinces within an area. Use sparingly - prefer transfer_areas().
    Only use when you must split an area (e.g., "coastal provinces only").
    """
    provinces = get_provinces_for_area(area_name)
    if not provinces:
        return f"Area '{area_name}' not found. Use query_region_areas() to see valid names."

    lines = [f"Provinces in {area_name}:"]
    for p in provinces:
        current = _current_provinces_cache.get(p['id'])
        owner = current.get('owner', '?') if current else 'not tracked'
        lines.append(f"  - ID {p['id']}: {p['name']} [owner: {owner}]")

    return "\n".join(lines)


@tool
def query_tag_territories(tag: str) -> str:
    """
    Get all territories owned by a nation tag. Use for commands like:
    - "All remaining X territory goes to Y"
    - "All of X goes to Y except for Z"
    """
    if not _current_provinces_cache:
        return f"No province data loaded. Cannot query territories for '{tag}'."

    owned_ids = {pid for pid, p in _current_provinces_cache.items() if p.get('owner') == tag}
    if not owned_ids:
        return f"Tag '{tag}' does not own any tracked provinces."

    all_areas = load_areas()
    fully_owned = []
    partial_provinces = []

    for area_name, area_provs in all_areas.items():
        area_ids = {p['id'] for p in area_provs}
        owned_in_area = area_ids & owned_ids

        if not owned_in_area:
            continue
        elif owned_in_area == area_ids:
            fully_owned.append({'name': area_name, 'count': len(area_provs)})
        else:
            for p in area_provs:
                if p['id'] in owned_in_area:
                    partial_provinces.append({'id': p['id'], 'name': p['name'], 'area': area_name})

    lines = [f"Territories owned by {tag}:", ""]

    if fully_owned:
        lines.append(f"FULLY OWNED AREAS ({len(fully_owned)}):")
        for a in sorted(fully_owned, key=lambda x: x['name']):
            lines.append(f"  - {a['name']} ({a['count']} provinces)")
    else:
        lines.append("FULLY OWNED AREAS: None")

    lines.append("")

    if partial_provinces:
        by_area = {}
        for p in partial_provinces:
            by_area.setdefault(p['area'], []).append(p)
        lines.append(f"PARTIAL OWNERSHIP ({len(partial_provinces)} provinces in {len(by_area)} areas):")
        for area_name in sorted(by_area.keys()):
            lines.append(f"  {area_name}:")
            for p in by_area[area_name]:
                lines.append(f"    - ID {p['id']}: {p['name']}")
    else:
        lines.append("PARTIAL OWNERSHIP: None")

    lines.append("")
    lines.append(f"TOTAL: {len(owned_ids)} provinces")

    return "\n".join(lines)


# Action tools

@tool
def transfer_areas(area_names: List[str], to_nation: str) -> str:
    """
    Transfer entire areas to a new owner. This is the preferred way to make changes.
    Example: transfer_areas(["Brittany", "Normandy"], "ENG")
    """
    global _pending_updates

    if not area_names:
        return "Error: No area names provided."
    if not to_nation:
        return "Error: No destination nation tag provided."

    transferred = []
    processed = []
    not_found = []

    for area_name in area_names:
        area_provs = get_provinces_for_area(area_name)
        if not area_provs:
            not_found.append(area_name)
            continue

        processed.append(area_name)
        for p in area_provs:
            current = _current_provinces_cache.get(p['id'], {})
            if current.get('owner') != to_nation:
                _pending_updates.append({"id": p['id'], "name": p['name'], "owner": to_nation})
                transferred.append(f"{p['name']} (ID {p['id']})")
                if p['id'] in _current_provinces_cache:
                    _current_provinces_cache[p['id']]['owner'] = to_nation

    lines = []
    if processed:
        lines.append(f"Transferred {len(processed)} area(s) to {to_nation}:")
        for area in processed:
            lines.append(f"   - {area}")
        lines.append(f"   Total: {len(transferred)} provinces")

    if not_found:
        lines.append(f"Areas not found: {', '.join(not_found)}")

    return "\n".join(lines) if lines else "No areas were processed."


@tool
def transfer_provinces(province_ids: List[int], to_nation: str) -> str:
    """
    Transfer specific provinces. Use sparingly - prefer transfer_areas().
    Only use when you must transfer a subset within an area.
    """
    global _pending_updates

    if not province_ids:
        return "Error: No province IDs provided."
    if not to_nation:
        return "Error: No destination nation tag provided."

    all_areas = load_areas()
    id_to_name = {p['id']: p['name'] for provs in all_areas.values() for p in provs}

    transferred = []
    skipped = []

    for pid in province_ids:
        name = id_to_name.get(pid, f"Province {pid}")
        current = _current_provinces_cache.get(pid, {})
        if current.get('owner') != to_nation:
            _pending_updates.append({"id": pid, "name": name, "owner": to_nation})
            transferred.append(f"{name} (ID {pid})")
            if pid in _current_provinces_cache:
                _current_provinces_cache[pid]['owner'] = to_nation
        else:
            skipped.append(str(pid))

    lines = []
    if transferred:
        lines.append(f"Transferred {len(transferred)} province(s) to {to_nation}:")
        for p in transferred[:10]:
            lines.append(f"   - {p}")
        if len(transferred) > 10:
            lines.append(f"   ... and {len(transferred) - 10} more")

    if skipped:
        lines.append(f"Skipped (already owned by {to_nation}): {', '.join(skipped)}")

    return "\n".join(lines) if lines else "No provinces were transferred."


@tool
def annex_nation(from_nation: str, to_nation: str) -> str:
    """
    Transfer ALL territory from one nation to another.
    Use for complete annexation: annex_nation("BYZ", "ARB")
    """
    global _pending_updates

    if not from_nation:
        return "Error: No source nation tag provided."
    if not to_nation:
        return "Error: No destination nation tag provided."
    if from_nation == to_nation:
        return "Error: Source and destination cannot be the same."

    to_transfer = [
        {'id': pid, 'name': p.get('name', f"Province {pid}")}
        for pid, p in _current_provinces_cache.items()
        if p.get('owner') == from_nation
    ]

    if not to_transfer:
        return f"{from_nation} does not own any tracked provinces."

    for prov in to_transfer:
        _pending_updates.append({"id": prov['id'], "name": prov['name'], "owner": to_nation})
        if prov['id'] in _current_provinces_cache:
            _current_provinces_cache[prov['id']]['owner'] = to_nation

    return f"ANNEXED: All {len(to_transfer)} provinces transferred from {from_nation} to {to_nation}."


@tool
def untrack_areas(area_names: List[str]) -> str:
    """
    Mark areas as lost to untracked nations. Use for LOSS changes where
    territory goes to non-scenario nations (barbarians, etc.).
    """
    global _pending_updates

    if not area_names:
        return "Error: No area names provided."

    untracked = []
    processed = []
    not_found = []

    for area_name in area_names:
        area_provs = get_provinces_for_area(area_name)
        if not area_provs:
            not_found.append(area_name)
            continue

        processed.append(area_name)
        for p in area_provs:
            current = _current_provinces_cache.get(p['id'], {})
            if current.get('owner'):
                _pending_updates.append({"id": p['id'], "name": p['name'], "owner": ""})
                untracked.append(f"{p['name']} (ID {p['id']})")
                if p['id'] in _current_provinces_cache:
                    _current_provinces_cache[p['id']]['owner'] = ""

    lines = []
    if processed:
        lines.append(f"Untracked {len(processed)} area(s):")
        for area in processed:
            lines.append(f"   - {area}")
        lines.append(f"   Total: {len(untracked)} provinces")

    if not_found:
        lines.append(f"Areas not found: {', '.join(not_found)}")

    return "\n".join(lines) if lines else "No areas were untracked."


@tool
def untrack_provinces(province_ids: List[int]) -> str:
    """Mark specific provinces as lost. Use sparingly - prefer untrack_areas()."""
    global _pending_updates

    if not province_ids:
        return "Error: No province IDs provided."

    all_areas = load_areas()
    id_to_name = {p['id']: p['name'] for provs in all_areas.values() for p in provs}

    untracked = []
    for pid in province_ids:
        name = id_to_name.get(pid, f"Province {pid}")
        current = _current_provinces_cache.get(pid, {})
        if current.get('owner'):
            _pending_updates.append({"id": pid, "name": name, "owner": ""})
            untracked.append(f"{name} (ID {pid})")
            if pid in _current_provinces_cache:
                _current_provinces_cache[pid]['owner'] = ""

    if untracked:
        return f"Untracked {len(untracked)} province(s):\n" + "\n".join(f"   - {p}" for p in untracked[:10])
    return "No provinces were untracked."


@tool
def mark_complete() -> str:
    """Call this when all territorial changes have been processed."""
    return f"COMPLETE: {len(_pending_updates)} province update(s) queued."


# System prompt

SYSTEM_PROMPT = """You are a geographer assistant for an alternate history simulation.
Process territorial changes by calling action tools that modify province ownership.

WORK AT THE AREA LEVEL - areas are your primary unit of operation.

GEOGRAPHICAL HIERARCHY:
- REGIONS: Large areas (France, Egypt, Canada) - query to discover area names
- AREAS: Medium subdivisions (Brittany, Lower Egypt) - your working unit

TOOLS:

Query tools:
- get_available_regions(): List all regions
- query_region_areas(region_name): List areas in a region with ownership
- query_tag_territories(tag): List all territory owned by a nation

Action tools:
- transfer_areas(area_names, to_nation): Transfer entire areas (PRIMARY)
- annex_nation(from_nation, to_nation): Transfer all territory between nations
- untrack_areas(area_names): Mark areas as lost to untracked nations

Finish:
- mark_complete(): Call when all changes are processed

WORKFLOW:
1. Read the change
2. Query relevant region(s) if needed
3. Call transfer_areas() or untrack_areas()
4. Repeat for each change
5. mark_complete() when done

EXAMPLES:
- "Quebec becomes independent" -> query_region_areas("Canada") -> transfer_areas([...], "QUE")
- "All BYZ territory goes to ARB" -> annex_nation("BYZ", "ARB")
- "Gaul lost to Germanic tribes" -> query_region_areas("Gaul") -> untrack_areas([...])"""


# LLM setup

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=120,
    max_retries=2
)

query_tools = [get_available_regions, query_region_areas, query_tag_territories]
action_tools = [transfer_areas, annex_nation, untrack_areas, mark_complete]
all_tools = query_tools + action_tools

llm_with_tools = llm.bind_tools(all_tools, tool_choice="auto")


def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute a tool by name."""
    tool_map = {
        "get_available_regions": get_available_regions,
        "query_region_areas": query_region_areas,
        "query_area_provinces": query_area_provinces,
        "query_tag_territories": query_tag_territories,
        "transfer_areas": transfer_areas,
        "transfer_provinces": transfer_provinces,
        "annex_nation": annex_nation,
        "untrack_areas": untrack_areas,
        "untrack_provinces": untrack_provinces,
        "mark_complete": mark_complete,
    }
    tool_func = tool_map.get(tool_name)
    return tool_func.invoke(tool_args) if tool_func else f"Unknown tool: {tool_name}"


def interpret_territorial_changes(
    territorial_changes: List[Dict[str, Any]],
    scenario_id: str = "rome",
    current_provinces: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Interpret structured territorial changes using action tools.

    Args:
        territorial_changes: List of territorial change dicts from Dreamer
        scenario_id: Scenario ID for looking up nation tags
        current_provinces: Optional list of current province states

    Returns:
        Dict with province_updates list and status message
    """
    global _available_tags, _current_provinces_cache, _pending_updates

    _pending_updates = []
    _available_tags = get_scenario_tags(scenario_id)

    _current_provinces_cache = {}
    if current_provinces:
        for p in current_provinces:
            pid = p.get("id")
            if pid is not None:
                _current_provinces_cache[pid] = p

    if not territorial_changes:
        return {"province_updates": [], "status": "No territorial changes to process."}

    valid_changes = [c for c in territorial_changes if c.get("change_type") and c.get("location")]
    if not valid_changes:
        return {"province_updates": [], "status": "No valid territorial changes."}

    print(f"[Geographer] Processing {len(valid_changes)} territorial change(s)")

    # Format changes for prompt
    changes_text = []
    for i, change in enumerate(valid_changes):
        loc = change.get("location", "Unknown")
        ctype = change.get("change_type", "Unknown")
        from_n = change.get("from_nation", "N/A")
        to_n = change.get("to_nation", "N/A")
        ctx = change.get("context", "")

        line = f"[{i}] {ctype}: \"{loc}\""
        if from_n and from_n != "N/A":
            line += f" (from: {from_n})"
        if to_n and to_n != "N/A":
            line += f" (to: {to_n})"
        if ctx:
            line += f"\n    Context: {ctx}"
        changes_text.append(line)
        print(f"    {line}")

    tags_text = "Available nation tags:\n"
    for tag, info in _available_tags.items():
        tags_text += f"  - {tag}: {info.get('name', 'Unknown')}\n"

    user_prompt = f"""Process these territorial changes by calling the appropriate action tools.

=== TERRITORIAL CHANGES ===
{chr(10).join(changes_text)}

=== {tags_text}

Process each change in order, then call mark_complete()."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    # Tool-calling loop
    max_iterations = 30
    iteration = 0
    completed = False
    response = llm_with_tools.invoke(messages)

    while iteration < max_iterations and not completed:
        iteration += 1

        if not response.tool_calls:
            print(f"[Geographer] Iteration {iteration}: No tool calls, finishing")
            break

        print(f"[Geographer] Iteration {iteration}: {len(response.tool_calls)} tool call(s)")
        messages.append(response)

        for tc in response.tool_calls:
            name = tc["name"]
            args = tc.get("args", {})

            if name == "mark_complete":
                print(f"    -> COMPLETE")
                completed = True
            else:
                print(f"    -> {name}({args})")

            result = execute_tool(name, args)
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

        if not completed:
            response = llm_with_tools.invoke(messages)

    province_updates = _pending_updates.copy()
    status = f"[Geographer] Done: {len(province_updates)} province update(s)"
    print(status)

    return {"province_updates": province_updates, "status": status}
