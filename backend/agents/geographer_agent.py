"""
Geographer Agent - Translates territorial descriptions to province updates.

The Geographer interprets the Dreamer's prose descriptions of territorial changes
and converts them into specific province-level OWNER and CONTROL updates.
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any, Optional

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
    control: str = Field(default="", description="The controller tag if different from owner (for contested/occupied)")


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
            control = current.get('control', '')
            if control and control != owner:
                lines.append(f"  - ID {prov_id}: {name} [owner: {owner}, controlled by: {control}]")
            else:
                lines.append(f"  - ID {prov_id}: {name} [owner: {owner}]")
        else:
            lines.append(f"  - ID {prov_id}: {name} [not tracked]")
    
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a geographer assistant for an alternate history simulation.
Your job is to translate prose descriptions of territorial changes into specific province-level updates.

WORKFLOW:
1. First, call get_available_regions to see all region names
2. Identify which regions match the areas mentioned in the territorial description  
3. Call query_region_provinces for each relevant region to get province IDs
4. After gathering the province data, STOP calling tools and return your final JSON answer

WHEN TO CREATE UPDATES:

1. CONQUEST/ANNEXATION (nation gains new territory):
   - If provinces are "[not tracked]" and a tracked nation (BYZ, ROM, etc.) conquers them → ADD them
   - Set: owner = conquering_nation, control = ""

2. LOSS TO UNTRACKED STATE (nation loses territory):
   - If provinces are owned by a tracked nation and lost to an untracked state (Bulgars, Seljuks, etc.)
   - Set: owner = "" (empty string), control = ""

3. TRANSFER BETWEEN TRACKED NATIONS:
   - If a province changes from one tracked nation to another
   - Set: owner = new_nation, control = ""

IMPORTANT: After you have queried the relevant regions, return your final answer as a JSON object. Do not keep calling tools.

OUTPUT FORMAT (return this as your final response, not a tool call):
{
  "province_updates": [
    {"id": 123, "name": "Province Name", "owner": "TAG", "control": ""},
    ...
  ]
}

If there are no changes needed, return: {"province_updates": []}"""


# Initialize LLM with timeout
llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
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


def interpret_territorial_changes(
    territorial_description: str,
    scenario_id: str = "rome",
    current_provinces: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Interpret territorial changes from prose description into province updates.
    
    Args:
        territorial_description: Prose description of territorial changes from Dreamer
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
    
    # If no territorial changes described, return empty
    if not territorial_description or territorial_description.strip() == "":
        return {"province_updates": []}
    
    # Check for explicit "no changes" statements
    no_change_phrases = [
        "no territorial changes",
        "no significant territorial",
        "borders remained",
        "no changes occurred",
        "territory unchanged"
    ]
    if any(phrase in territorial_description.lower() for phrase in no_change_phrases):
        return {"province_updates": []}
    
    # Format available tags for the prompt
    tags_text = "Available nation tags:\n"
    if _available_tags:
        for tag, info in _available_tags.items():
            tags_text += f"  - {tag}: {info.get('name', 'Unknown')}\n"
    else:
        tags_text += "  - Use standard tags: ROM, BYZ, ARB, etc.\n"
    
    user_prompt = f"""=== TERRITORIAL CHANGES ===
{territorial_description}

=== {tags_text}

Query the relevant regions to find province IDs, then return your final JSON answer with province_updates."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    # Use tool-calling approach for proper querying
    max_iterations = 10
    iteration = 0
    
    print(f"🗺️  Geographer: Sending initial request to LLM...")
    # First call: force tool use to ensure the model queries regions
    response = llm_with_tools_required.invoke(messages)
    print(f"🗺️  Geographer: Initial response - tool_calls: {len(response.tool_calls) if response.tool_calls else 0}, content length: {len(response.content) if response.content else 0}")
    if not response.tool_calls:
        print(f"🗺️  Geographer: No tool calls! Response content: {response.content[:500] if response.content else 'Empty'}")
    
    while response.tool_calls and iteration < max_iterations:
        iteration += 1
        print(f"🗺️  Geographer: Iteration {iteration}, executing {len(response.tool_calls)} tool calls")
        
        # Add the AI response with tool calls
        messages.append(response)
        
        # Execute each tool call
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            
            # Execute the appropriate tool
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
        
        # Subsequent calls: use "auto" so the model can choose to finish
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
        
        # Validate structure
        if "province_updates" not in result:
            result["province_updates"] = []
        
        # Validate province updates format
        valid_updates = []
        for update in result.get("province_updates", []):
            if isinstance(update, dict) and "id" in update:
                valid_update = {
                    "id": update["id"],
                    "name": update.get("name", f"Province {update['id']}"),
                    "owner": update.get("owner", ""),
                    "control": update.get("control", "")
                }
                # Include updates even if owner is empty (lost to untracked state)
                # But require at least id to be valid
                valid_updates.append(valid_update)
        
        result["province_updates"] = valid_updates
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse geographer response: {e}")
        print(f"Raw response: {content[:500] if content else 'Empty'}")
        
        # Return empty result on parse failure
        return {
            "province_updates": []
        }
