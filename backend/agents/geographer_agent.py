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
    reasoning: str = Field(
        default="",
        description="Brief explanation of how territorial changes were interpreted"
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
    Use this to get the province IDs and names for a region mentioned in territorial changes.
    
    Args:
        region_name: The exact region name (e.g., 'egypt_region', 'syria_region')
        
    Returns:
        List of provinces with their IDs in that region
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
        lines.append(f"  - ID: {p['id']}, Name: {p['name']}")
    
    return "\n".join(lines)


@tool
def get_nation_tags() -> str:
    """
    Get the valid nation tags that can be used as owner/control values.
    Call this to ensure you're using valid tags for province updates.
    """
    if not _available_tags:
        return "No nation tags defined. Use generic tags like 'ROM', 'BYZ', 'ARB'."
    
    lines = ["Valid nation tags:"]
    for tag, info in _available_tags.items():
        name = info.get("name", "Unknown")
        lines.append(f"  - {tag}: {name}")
    
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a geographer assistant for an alternate history simulation.
Your job is to translate prose descriptions of territorial changes into specific province-level updates.

You will receive a territorial description from the Dreamer agent that describes what happened to various regions.
Your task is to:
1. Identify which regions are mentioned in the description
2. Use the tools to find the corresponding region names and province IDs
3. Determine if each change is PERMANENT (conquest) or TEMPORARY (occupation/contested)
4. Create province update entries with the correct owner and control values

OWNER vs CONTROL LOGIC:
- PERMANENT changes (change OWNER):
  - Language: "conquered", "annexed", "ceded to", "now belongs to", "permanently lost", "fell to"
  - Set: owner = new_nation, control = ""
  
- TEMPORARY changes (set CONTROL, keep OWNER):
  - Language: "occupied by", "contested", "under siege", "raided", "temporarily held", "disputed"
  - Set: control = occupier (owner stays the same)
  
- CLEARING occupation (restore control to owner):
  - Language: "liberated", "retook", "recovered", "restored control"
  - Set: control = "" (cleared)

- LOST TO UNTRACKED STATE:
  - If a province is conquered by a state that does NOT have a valid nation tag (e.g., Bulgars, Avars, Slavs, etc.)
  - Set: owner = "" (empty string), control = ""
  - This marks the province as "lost" to an entity we don't track
  - IMPORTANT: You can ONLY mark provinces as lost (owner="") if they are CURRENTLY TRACKED
  - Example: If Bulgarians conquer Thrace but 'BUL' is not a valid tag, set owner = ""

PROVINCE TRACKING RULES:
- The game only tracks provinces owned by player nations (like Byzantium)
- Provinces owned by external nations (Arabs, Persians, etc.) are NOT tracked unless conquered
- CONQUESTS: When you conquer territory FROM untracked nations, include name + owner to ADD them
- LOSSES: When losing territory TO untracked nations, ONLY include provinces that are currently tracked
- If a province is not in the "currently tracked provinces" list, you CANNOT mark it as lost

WORKFLOW:
1. First, check the "Currently Tracked Provinces" list to see what provinces exist in the game state
2. Use get_available_regions to see all available region names
3. Identify which regions match the areas mentioned in the territorial description
4. Use query_region_provinces to get the province IDs for each relevant region
5. Use get_nation_tags to verify you're using valid nation tags
6. Cross-reference: Only update/lose provinces that are currently tracked, but you CAN add new ones

IMPORTANT:
- Only create updates for provinces that are EXPLICITLY affected by the territorial changes
- If no territorial changes are described, return an empty province_updates list
- Be conservative - if the description is vague, don't make updates
- Use the actual province IDs from the query results
- Always include the province "name" field - this is required for adding new provinces

OUTPUT FORMAT:
Return a JSON object with:
{
  "province_updates": [
    {"id": 123, "name": "Province Name", "owner": "TAG", "control": ""},
    ...
  ],
  "reasoning": "Brief explanation of how you interpreted the changes"
}"""


# Initialize LLM with timeout
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=120,  # 2 minute timeout
    max_retries=2
)

# Tools for the geographer
tools = [get_available_regions, query_region_provinces, get_nation_tags]
llm_with_tools = llm.bind_tools(tools)

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
    global _available_tags, _region_names_cache
    
    # Load available nation tags
    _available_tags = get_scenario_tags(scenario_id)
    
    # Pre-load region names
    _region_names_cache = get_all_region_names()
    
    # If no territorial changes described, return empty
    if not territorial_description or territorial_description.strip() == "":
        return {"province_updates": [], "reasoning": "No territorial changes described."}
    
    # Check for explicit "no changes" statements
    no_change_phrases = [
        "no territorial changes",
        "no significant territorial",
        "borders remained",
        "no changes occurred",
        "territory unchanged"
    ]
    if any(phrase in territorial_description.lower() for phrase in no_change_phrases):
        return {"province_updates": [], "reasoning": "Description indicates no territorial changes."}
    
    # Format available tags for the prompt
    tags_text = "Available nation tags:\n"
    if _available_tags:
        for tag, info in _available_tags.items():
            tags_text += f"  - {tag}: {info.get('name', 'Unknown')}\n"
    else:
        tags_text += "  - Use standard tags: ROM, BYZ, ARB, etc.\n"
    
    # Format currently tracked provinces
    tracked_text = ""
    if current_provinces:
        # Group by owner for readability
        by_owner = {}
        for p in current_provinces:
            owner = p.get("owner", "unknown")
            if owner not in by_owner:
                by_owner[owner] = []
            by_owner[owner].append(p)
        
        tracked_text = f"\n=== CURRENTLY TRACKED PROVINCES ({len(current_provinces)} total) ===\n"
        tracked_text += "These are the provinces currently in the game state. You can ONLY mark provinces as lost (owner='') if they appear here.\n"
        for owner, provinces in by_owner.items():
            tracked_text += f"\nOwned by {owner} ({len(provinces)} provinces):\n"
            # Show just ID and name, limit to avoid token overflow
            for p in provinces[:50]:
                tracked_text += f"  - ID {p.get('id')}: {p.get('name', 'Unknown')}\n"
            if len(provinces) > 50:
                tracked_text += f"  ... and {len(provinces) - 50} more\n"
    else:
        tracked_text = "\n=== NO CURRENTLY TRACKED PROVINCES PROVIDED ===\n"
        tracked_text += "Be cautious - only create province updates for conquests (adding new provinces).\n"
    
    user_prompt = f"""Interpret the following territorial changes and create province updates.

=== TERRITORIAL CHANGES DESCRIPTION ===
{territorial_description}

=== {tags_text}
{tracked_text}

INSTRUCTIONS:
1. FIRST check the "Currently Tracked Provinces" list above to see what provinces exist in the game
2. Use get_available_regions to see all region names
3. Identify regions that match the areas mentioned in the description
4. Query each relevant region to get province IDs using query_region_provinces
5. Create province_updates for affected provinces
6. Use proper OWNER vs CONTROL logic based on the language used

CRITICAL RULES:
- CONQUESTS (adding provinces): Include id, name, and owner tag. These will be ADDED to tracking.
- LOSSES (to untracked states): ONLY include provinces that appear in "Currently Tracked Provinces" above.
- If a province ID is NOT in the tracked list, you CANNOT mark it as lost.

If the description is too vague or doesn't specify actual regions, return an empty province_updates list.
Only update provinces that are CLEARLY affected by the described changes."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    # Use tool-calling approach for proper querying
    max_iterations = 10
    iteration = 0
    
    response = llm_with_tools.invoke(messages)
    
    while response.tool_calls and iteration < max_iterations:
        iteration += 1
        
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
            elif tool_name == "get_nation_tags":
                result = get_nation_tags.invoke({})
            else:
                result = f"Unknown tool: {tool_name}"
            
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call["id"]
            })
        
        # Continue the conversation
        response = llm_with_tools.invoke(messages)
    
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
        if "reasoning" not in result:
            result["reasoning"] = ""
        
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
            "province_updates": [],
            "reasoning": f"Failed to parse territorial changes: {str(e)}"
        }
