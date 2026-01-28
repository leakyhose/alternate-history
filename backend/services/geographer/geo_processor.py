"""Geography processing using LLM with tool-based output."""
import os
import json
import logging
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

from .config import GEMINI_API_KEY, GEMINI_MODEL, LLM_TIMEOUT_SECONDS, MAX_TOOL_ITERATIONS

logger = logging.getLogger(__name__)

# Get backend directory for static files
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Module-level state
_province_updates: List[Dict[str, Any]] = []
_current_provinces: Dict[int, Dict[str, Any]] = {}
_available_tags: Dict[str, Dict[str, Any]] = {}
_areas_cache: Optional[Dict[str, List[dict]]] = None
_regions_cache: Optional[Dict[str, List[str]]] = None


def _load_areas() -> Dict[str, List[dict]]:
    """Load areas.json mapping."""
    global _areas_cache
    if _areas_cache is None:
        path = os.path.join(_BACKEND_DIR, "static", "areas.json")
        try:
            with open(path, "r") as f:
                _areas_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _areas_cache = {}
    return _areas_cache


def _load_regions() -> Dict[str, List[str]]:
    """Load regions.json mapping."""
    global _regions_cache
    if _regions_cache is None:
        path = os.path.join(_BACKEND_DIR, "static", "regions.json")
        try:
            with open(path, "r") as f:
                _regions_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _regions_cache = {}
    return _regions_cache


# =============================================================================
# QUERY TOOLS
# =============================================================================

@tool
def get_regions() -> str:
    """List all available region names. Call first to see what regions exist."""
    regions = _load_regions()
    if not regions:
        return "No regions available."
    return f"Available regions ({len(regions)}):\n" + "\n".join(f"  - {r}" for r in sorted(regions.keys()))


@tool
def query_region(region_name: str) -> str:
    """Get areas within a region with ownership summary. Use to find area names."""
    regions = _load_regions()
    areas = regions.get(region_name)
    if not areas:
        return f"Region '{region_name}' not found. Use get_regions() to see valid names."

    all_areas = _load_areas()
    lines = [f"Areas in {region_name} ({len(areas)} areas):"]

    for area_name in areas:
        provs = all_areas.get(area_name, [])
        if provs:
            owners = {}
            for p in provs:
                current = _current_provinces.get(p["id"])
                owner = current.get("owner", "?") if current else "untracked"
                owners[owner] = owners.get(owner, 0) + 1

            if len(owners) == 1:
                lines.append(f"  - {area_name} ({len(provs)} provs, all {list(owners.keys())[0]})")
            else:
                owner_str = ", ".join(f"{o}:{c}" for o, c in owners.items())
                lines.append(f"  - {area_name} ({len(provs)} provs, mixed: {owner_str})")
        else:
            lines.append(f"  - {area_name} (no provinces)")

    return "\n".join(lines)


@tool
def query_area_provinces(area_name: str) -> str:
    """
    *** USE SPARINGLY - PREFER AREA-LEVEL OPERATIONS ***

    Get individual provinces within an area. Only use when you MUST split an area
    (e.g., "only coastal provinces" or "northern half of the area").

    For most changes, use transfer_areas() instead - it's faster and more reliable.
    """
    all_areas = _load_areas()
    provs = all_areas.get(area_name)
    if not provs:
        return f"Area '{area_name}' not found. Use query_region() to see valid area names."

    lines = [f"Provinces in {area_name} (PREFER transfer_areas for whole-area changes):"]
    for p in provs:
        current = _current_provinces.get(p["id"])
        owner = current.get("owner", "?") if current else "untracked"
        lines.append(f"  - ID {p['id']}: {p['name']} [{owner}]")

    return "\n".join(lines)


@tool
def query_nation_territories(tag: str) -> str:
    """Get all territories owned by a nation. Use for 'all of X goes to Y' commands."""
    if not _current_provinces:
        return f"No province data available."

    owned_ids = {pid for pid, p in _current_provinces.items() if p.get("owner") == tag}
    if not owned_ids:
        return f"'{tag}' owns no tracked provinces."

    all_areas = _load_areas()
    fully_owned = []
    partial = []

    for area_name, area_provs in all_areas.items():
        area_ids = {p["id"] for p in area_provs}
        owned_in_area = area_ids & owned_ids
        if not owned_in_area:
            continue
        elif owned_in_area == area_ids:
            fully_owned.append(area_name)
        else:
            partial.append(f"{area_name} ({len(owned_in_area)}/{len(area_ids)})")

    lines = [f"Territories owned by {tag}:"]
    if fully_owned:
        lines.append(f"  Full areas: {', '.join(sorted(fully_owned)[:10])}")
        if len(fully_owned) > 10:
            lines.append(f"    ... and {len(fully_owned) - 10} more")
    if partial:
        lines.append(f"  Partial: {', '.join(partial[:5])}")

    lines.append(f"  Total: {len(owned_ids)} provinces")
    return "\n".join(lines)


# =============================================================================
# ACTION TOOLS
# =============================================================================

@tool
def transfer_areas(area_names: List[str], to_nation: str) -> str:
    """
    Transfer entire areas to a new owner. THIS IS THE PREFERRED METHOD.

    Always use this when possible - it's more reliable than province-level transfers.
    Example: transfer_areas(["Brittany", "Normandy"], "ENG")
    """
    global _province_updates

    if not area_names:
        return "Error: No area names provided."
    if not to_nation:
        return "Error: No destination tag provided."

    all_areas = _load_areas()
    transferred = 0
    processed = []
    not_found = []

    for area_name in area_names:
        provs = all_areas.get(area_name)
        if not provs:
            not_found.append(area_name)
            continue

        processed.append(area_name)
        for p in provs:
            current = _current_provinces.get(p["id"], {})
            if current.get("owner") != to_nation:
                _province_updates.append({"id": p["id"], "name": p["name"], "owner": to_nation})
                if p["id"] in _current_provinces:
                    _current_provinces[p["id"]]["owner"] = to_nation
                transferred += 1

    result = []
    if processed:
        result.append(f"Transferred {len(processed)} area(s) to {to_nation}: {', '.join(processed)}")
        result.append(f"  ({transferred} provinces changed)")
    if not_found:
        result.append(f"Not found: {', '.join(not_found)}")

    return "\n".join(result) if result else "No areas processed."


@tool
def transfer_provinces(province_ids: List[int], to_nation: str) -> str:
    """
    *** USE SPARINGLY - PREFER transfer_areas() ***

    Transfer specific provinces by ID. Only use when you MUST transfer a subset
    of an area (e.g., specific coastal provinces, a border strip).

    For whole-area transfers, ALWAYS use transfer_areas() instead.
    """
    global _province_updates

    if not province_ids:
        return "Error: No province IDs provided."
    if not to_nation:
        return "Error: No destination tag provided."

    all_areas = _load_areas()
    id_to_name = {p["id"]: p["name"] for provs in all_areas.values() for p in provs}

    transferred = []
    for pid in province_ids:
        name = id_to_name.get(pid, f"Province {pid}")
        current = _current_provinces.get(pid, {})
        if current.get("owner") != to_nation:
            _province_updates.append({"id": pid, "name": name, "owner": to_nation})
            if pid in _current_provinces:
                _current_provinces[pid]["owner"] = to_nation
            transferred.append(f"{name} ({pid})")

    if transferred:
        return f"Transferred {len(transferred)} province(s) to {to_nation}: {', '.join(transferred[:5])}"
    return "No provinces transferred."


@tool
def annex_nation(from_nation: str, to_nation: str) -> str:
    """
    Transfer ALL territory from one nation to another. Use for complete annexation.
    Example: annex_nation("BYZ", "ARB") - all Byzantine territory goes to Arabs.
    """
    global _province_updates

    if not from_nation or not to_nation:
        return "Error: Both from_nation and to_nation required."
    if from_nation == to_nation:
        return "Error: Source and destination cannot be the same."

    to_transfer = [
        {"id": pid, "name": p.get("name", f"Province {pid}")}
        for pid, p in _current_provinces.items()
        if p.get("owner") == from_nation
    ]

    if not to_transfer:
        return f"{from_nation} owns no provinces."

    for prov in to_transfer:
        _province_updates.append({"id": prov["id"], "name": prov["name"], "owner": to_nation})
        if prov["id"] in _current_provinces:
            _current_provinces[prov["id"]]["owner"] = to_nation

    return f"ANNEXED: {len(to_transfer)} provinces from {from_nation} to {to_nation}."


@tool
def untrack_areas(area_names: List[str]) -> str:
    """
    Mark areas as lost to untracked nations (barbarians, rebels, etc.).
    The preferred method for LOSS changes.
    """
    global _province_updates

    if not area_names:
        return "Error: No area names provided."

    all_areas = _load_areas()
    untracked = 0
    processed = []
    not_found = []

    for area_name in area_names:
        provs = all_areas.get(area_name)
        if not provs:
            not_found.append(area_name)
            continue

        processed.append(area_name)
        for p in provs:
            current = _current_provinces.get(p["id"], {})
            if current.get("owner"):
                _province_updates.append({"id": p["id"], "name": p["name"], "owner": ""})
                if p["id"] in _current_provinces:
                    _current_provinces[p["id"]]["owner"] = ""
                untracked += 1

    result = []
    if processed:
        result.append(f"Untracked {len(processed)} area(s): {', '.join(processed)}")
        result.append(f"  ({untracked} provinces)")
    if not_found:
        result.append(f"Not found: {', '.join(not_found)}")

    return "\n".join(result) if result else "No areas untracked."


@tool
def untrack_provinces(province_ids: List[int]) -> str:
    """
    *** USE SPARINGLY - PREFER untrack_areas() ***

    Mark specific provinces as lost. Only use for partial area losses.
    """
    global _province_updates

    if not province_ids:
        return "Error: No province IDs provided."

    all_areas = _load_areas()
    id_to_name = {p["id"]: p["name"] for provs in all_areas.values() for p in provs}

    untracked = []
    for pid in province_ids:
        name = id_to_name.get(pid, f"Province {pid}")
        current = _current_provinces.get(pid, {})
        if current.get("owner"):
            _province_updates.append({"id": pid, "name": name, "owner": ""})
            if pid in _current_provinces:
                _current_provinces[pid]["owner"] = ""
            untracked.append(name)

    if untracked:
        return f"Untracked {len(untracked)} province(s): {', '.join(untracked[:5])}"
    return "No provinces untracked."


@tool
def mark_complete() -> str:
    """Call this when all territorial changes have been processed."""
    return f"COMPLETE: {len(_province_updates)} province update(s) queued."


# =============================================================================
# LLM SETUP
# =============================================================================

QUERY_TOOLS = [get_regions, query_region, query_nation_territories]
ACTION_TOOLS = [transfer_areas, annex_nation, untrack_areas, mark_complete]
PROVINCE_TOOLS = [query_area_provinces, transfer_provinces, untrack_provinces]
ALL_TOOLS = QUERY_TOOLS + ACTION_TOOLS + PROVINCE_TOOLS

SYSTEM_PROMPT = """You are a geographer for an alternate history simulation.
Translate territorial changes into province updates using action tools.

=== WORK AT THE AREA LEVEL ===
Areas are your PRIMARY unit of operation. Always prefer area-level tools.

GEOGRAPHICAL HIERARCHY:
- REGIONS: Large areas (France, Egypt, Anatolia) - use get_regions(), query_region()
- AREAS: Subdivisions of regions (Brittany, Lower Egypt) - YOUR WORKING UNIT

=== PREFERRED TOOLS (USE THESE) ===
Query:
- get_regions(): List all regions
- query_region(name): List areas in a region with ownership

Action:
- transfer_areas(areas, to_nation): Transfer entire areas (PREFERRED)
- annex_nation(from, to): Transfer all territory between nations
- untrack_areas(areas): Mark areas as lost to untracked nations
- mark_complete(): Call when done

=== PROVINCE-LEVEL TOOLS (USE SPARINGLY) ===
Only use these when you MUST split an area (e.g., "coastal provinces only"):
- query_area_provinces(area): See individual provinces
- transfer_provinces(ids, to): Transfer specific provinces
- untrack_provinces(ids): Mark specific provinces as lost

*** STRONG PREFERENCE: If the change affects a whole area, use transfer_areas(). ***
*** Province-level operations are slower and more error-prone. ***

=== WORKFLOW ===
1. Read the territorial change
2. Query the relevant region to find area names
3. Use transfer_areas() or untrack_areas() for the whole areas
4. Only drill down to provinces if absolutely necessary
5. Call mark_complete() when done

=== EXAMPLES ===
- "Rome conquers Gaul" -> query_region("Gaul") -> transfer_areas([...], "ROM")
- "All BYZ goes to ARB" -> annex_nation("BYZ", "ARB")
- "Gaul lost to barbarians" -> query_region("Gaul") -> untrack_areas([...])
- "Coastal Brittany to ENG" -> query_area_provinces("Brittany") -> transfer_provinces([coastal ids], "ENG")"""


def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GEMINI_API_KEY,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=2,
    )


llm_with_tools = get_llm().bind_tools(ALL_TOOLS)


def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute a tool by name."""
    tool_map = {t.name: t for t in ALL_TOOLS}
    tool_func = tool_map.get(tool_name)
    return tool_func.invoke(tool_args) if tool_func else f"Unknown tool: {tool_name}"


# =============================================================================
# MAIN PROCESSING FUNCTION
# =============================================================================

def process_territorial_changes(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process territorial changes from a timeline event.

    Args:
        event: Timeline event with dreamer_decision.territorial_changes and current_provinces

    Returns:
        List of province update dicts
    """
    global _province_updates, _current_provinces, _available_tags

    # Reset state
    _province_updates = []
    _current_provinces = {}

    # Extract data from event
    decision = event.get("dreamer_decision", {})
    territorial_changes = decision.get("territorial_changes", [])
    current_provinces = event.get("current_provinces", [])
    year_range = event.get("year_range", "Unknown")

    # Build province cache
    for p in current_provinces:
        pid = p.get("id")
        if pid is not None:
            _current_provinces[pid] = p

    if not territorial_changes:
        logger.info(f"[Geographer] No territorial changes for {year_range}")
        return []

    valid_changes = [c for c in territorial_changes if c.get("change_type") and c.get("location")]
    if not valid_changes:
        logger.info(f"[Geographer] No valid changes for {year_range}")
        return []

    logger.info(f"[Geographer] Processing {len(valid_changes)} change(s) for {year_range}")

    # Format changes for prompt
    changes_text = []
    for i, change in enumerate(valid_changes):
        loc = change.get("location", "Unknown")
        ctype = change.get("change_type", "Unknown")
        from_n = change.get("from_nation", "")
        to_n = change.get("to_nation", "")
        ctx = change.get("context", "")

        line = f"[{i+1}] {ctype}: \"{loc}\""
        if from_n:
            line += f" (from: {from_n})"
        if to_n:
            line += f" (to: {to_n})"
        if ctx:
            line += f" - {ctx}"
        changes_text.append(line)
        logger.info(f"    {line}")

    user_prompt = f"""Process these territorial changes for {year_range} AD.

=== TERRITORIAL CHANGES ===
{chr(10).join(changes_text)}

Process each change using the appropriate action tools.
Prefer transfer_areas() over transfer_provinces() whenever possible.
Call mark_complete() when done."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Tool-calling loop
    iteration = 0
    completed = False

    try:
        response = llm_with_tools.invoke(messages)

        while iteration < MAX_TOOL_ITERATIONS and not completed:
            iteration += 1

            if not response.tool_calls:
                logger.info(f"[Geographer] Iteration {iteration}: No tool calls")
                break

            logger.info(f"[Geographer] Iteration {iteration}: {len(response.tool_calls)} call(s)")
            messages.append(response)

            for tc in response.tool_calls:
                name = tc["name"]
                args = tc.get("args", {})

                if name == "mark_complete":
                    logger.info(f"    -> COMPLETE")
                    completed = True
                else:
                    # Log tool call (abbreviated for long lists)
                    if name in ("transfer_areas", "untrack_areas") and args.get("area_names"):
                        areas = args["area_names"]
                        if len(areas) > 3:
                            logger.info(f"    -> {name}([{areas[0]}, ...{len(areas)} areas])")
                        else:
                            logger.info(f"    -> {name}({args})")
                    else:
                        logger.info(f"    -> {name}({args})")

                result = execute_tool(name, args)
                messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

            if not completed:
                response = llm_with_tools.invoke(messages)

        updates = _province_updates.copy()
        logger.info(f"[Geographer] Done: {len(updates)} province update(s)")
        return updates

    except Exception as e:
        logger.error(f"[Geographer] Error: {e}")
        raise
