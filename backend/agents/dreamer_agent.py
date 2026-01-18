"""
Dreamer Agent - The creative decision-maker.

The Dreamer synthesizes divergences + historian context to decide what ACTUALLY
happens in the alternate timeline. This is the "brain" of the simulation.
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any, Optional, Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from pydantic import BaseModel, Field

load_dotenv()

# Module-level variable to store available tags for tool access
_available_tags: Dict[str, Dict[str, Any]] = {}


class RulerInfo(BaseModel):
    """Information about a ruler."""
    name: str = Field(description="The ruler's name")
    title: str = Field(description="The ruler's title (e.g., Emperor, King)")
    age: int = Field(description="The ruler's age")
    dynasty: str = Field(description="The dynasty name")


class TerritorialChange(BaseModel):
    """A single structured territorial change.
    
    This provides an unambiguous way to communicate territorial changes between
    the Dreamer and Geographer agents. The location is natural language (flexible),
    but the change_type and nation tags are structured (no ambiguity).
    
    IMPORTANT: These changes describe the NET RESULT at the END of the period compared
    to the beginning. If territory changed hands multiple times during the period,
    only the final state matters. Do NOT list intermediate changes.
    """
    location: str = Field(
        description="DETAILED natural language description of the location/region affected. "
                    "Be as SPECIFIC as possible to help the geographer identify exact provinces: "
                    "- Name multiple regions if applicable: 'Egypt, Cyrenaica, and Libya' "
                    "- Use geographic boundaries: 'Syria south of Antioch to the Egyptian border' "
                    "- Reference major cities: 'Asia Minor including Ephesus, Smyrna, and Pergamon' "
                    "- Use rivers/mountains as boundaries: 'Mesopotamia east of the Euphrates' "
                    "- Include sub-regions: 'Greece including Achaea, Macedonia, and Epirus' "
                    "AVOID vague descriptions like 'eastern territories' or 'some land in the east'."
    )
    change_type: Literal[
        "CONQUEST",      # Nation permanently gains territory from an untracked state
        "LOSS",          # Nation permanently loses territory to an untracked state
        "TRANSFER",      # Territory transfers between two tracked nations
    ] = Field(
        description="The type of territorial change representing the NET RESULT at period end. "
                    "Use CONQUEST when a tracked nation ends the period controlling territory it didn't have before "
                    "(gained from untracked peoples). Use LOSS when a tracked nation no longer controls territory "
                    "it had at period start (lost to untracked peoples). Use TRANSFER when territory moved between "
                    "two tracked nations by period end."
    )
    from_nation: Optional[str] = Field(
        default=None,
        description="Nation tag that owned this territory at the START of the period. "
                    "Required for LOSS and TRANSFER. Null for CONQUEST (territory was untracked)."
    )
    to_nation: Optional[str] = Field(
        default=None,
        description="Nation tag that owns this territory at the END of the period. "
                    "Required for CONQUEST and TRANSFER. Null for LOSS (territory becomes untracked)."
    )
    context: str = Field(
        default="",
        description="Brief context explaining why this change happened (for narrative purposes)"
    )


class DreamerOutput(BaseModel):
    """Structured output from the Dreamer agent."""
    rulers: Dict[str, RulerInfo] = Field(
        description="Dictionary of nation tag -> ruler info. Only use valid tags from scenario metadata."
    )
    narrative: str = Field(
        description="A concise narrative of what happened in this period. 2-4 sentences, around 50-80 words."
    )
    territorial_changes: List[TerritorialChange] = Field(
        default_factory=list,
        description="List of structured territorial changes. Each change specifies location (natural language), "
                    "change_type (CONQUEST/LOSS/TRANSFER/OCCUPATION/LIBERATION), and the nations involved."
    )
    territorial_changes_summary: str = Field(
        description="Human-readable summary of territorial changes for display in the narrative log. "
                    "This is prose for the user to read, separate from the detailed location data."
    )
    updated_divergences: List[str] = Field(
        description="List of current divergences that will affect future events"
    )
    merged: bool = Field(
        description="True if the timeline has merged back to real history, False otherwise"
    )


@tool
def get_available_nation_tags() -> str:
    """
    Get the list of valid nation tags that can be used for rulers.
    Call this tool before creating or modifying rulers to ensure you only use valid tags.
    You CANNOT invent new tags - only use tags returned by this tool.
    """
    if not _available_tags:
        return "No nation tags defined for this scenario."
    
    lines = ["Available nation tags (you can ONLY use these):"]
    for tag, info in _available_tags.items():
        name = info.get("name", "Unknown")
        lines.append(f"  - {tag}: {name}")
    
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a creative alternate history writer. Your job is to decide what ACTUALLY happens given divergences from real history.

You receive:
1. Historical context from the Historian (real events that would normally occur)
2. Current divergences affecting the timeline
3. Previous alternate history (summary + recent logs)
4. Current rulers and their information

=== YOUR CORE TASKS ===
1. Evaluate which historical events are triggered, prevented, or altered by divergences
2. Generate a compelling, entertaining narrative (2-4 sentences, ~50-80 words)
3. Update rulers (deaths, successions, plausible heirs with culturally appropriate names)
4. Specify territorial changes using the STRUCTURED FORMAT
5. Update divergences (remove resolved ones, add cascading effects)
6. Determine if the timeline has merged back to normal history

=== CRITICAL: REAL-WORLD LOGIC ===
The Historian provides context but may miss implications. YOU must consider:

**Political Systems:**
- Democracies/Republics: Leaders MUST change after term limits unless a divergence explains otherwise
- Constitutional monarchies: Monarchs have limited power; parliaments matter
- Authoritarian states: Succession crises are common; coups are possible

**Modern Geopolitics (post-1900):**
- Alliance systems: NATO Article 5, mutual defense pacts, UN responses
- Economic interdependence: Sanctions, trade wars, economic collapse
- Nuclear deterrence: MAD doctrine, escalation risks
- International organizations: UN, EU, ASEAN reactions to major events

**General Considerations:**
- Geography matters: Supply lines, natural barriers, climate
- Technology level: What's militarily/economically possible for the era
- Cultural/religious factors: Legitimacy, popular support, resistance movements
- Demographic realities: Population, manpower, economic capacity

=== BE CREATIVE BUT GROUNDED ===
Make history ENTERTAINING - unexpected twists, dramatic moments, colorful characters.
But ground it in plausible cause-and-effect. Every outcome should feel like it COULD happen.

=== TERRITORIAL CHANGES FORMAT ===
Describe NET changes from period START to END (not intermediate events).

Each change needs:
- location: DETAILED description - list ALL regions, use cities as landmarks, geographic boundaries
- change_type: CONQUEST (gain from untracked) | LOSS (lose to untracked) | TRANSFER (between tracked nations)
- from_nation: Nation losing territory (null for CONQUEST)
- to_nation: Nation gaining territory (null for LOSS)
- context: Brief explanation

=== DIVERGENCE RULES ===
- Divergences are changes that will affect FUTURE events
- Remove resolved ones (effects played out)
- Add new ones for major changes with ongoing impact
- If all divergences resolve and timeline returns to real history's trajectory, set merged: true

=== RULER RULES ===
- ONLY use nation tags from the VALID NATION TAGS list in the prompt
- NEVER invent new tags
- Update ages by adding years_to_progress
- Handle deaths with plausible successions
- If a state splits, REMOVE original tag and ADD successor tags with TRANSFER changes

Return ONLY valid JSON matching the schema. No markdown, no extra text."""


llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=120,  # 2 minute timeout
    max_retries=2
)

# Create a structured output version of the LLM
llm_structured = llm.with_structured_output(DreamerOutput)

# Bind tools to LLM for tag lookup (fallback mode)
tools = [get_available_nation_tags]
llm_with_tools = llm.bind_tools(tools)


def format_historian_output(historian_output: Dict[str, Any]) -> str:
    """Format historian output for the prompt."""
    if not historian_output:
        return "No historical context available."
    
    parts = []
    
    period = historian_output.get("period", "Unknown period")
    parts.append(f"Period: {period}")
    
    conditional_events = historian_output.get("conditional_events", [])
    if conditional_events:
        parts.append("\nHistorical events (evaluate if conditions are met in alternate timeline):")
        for cond in conditional_events:
            condition = cond.get("condition", "Unknown condition")
            outcome = cond.get("outcome", "Unknown outcome")
            parts.append(f"  - IF: {condition}")
            parts.append(f"    THEN: {outcome}")
    
    return "\n".join(parts)


def format_logs_context(
    condensed_logs: str,
    recent_logs: List[Dict[str, Any]],
    max_recent: int = 3
) -> str:
    """Format log history for the prompt."""
    parts = []
    
    if condensed_logs:
        parts.append("=== Earlier History (Summary) ===")
        parts.append(condensed_logs)
        parts.append("")
    
    if recent_logs:
        # Take only the last max_recent logs
        logs_to_show = recent_logs[-max_recent:]
        parts.append("=== Recent Detailed History ===")
        for log in logs_to_show:
            year_range = log.get("year_range", "Unknown period")
            narrative = log.get("narrative", "No narrative")
            divergences = log.get("divergences", [])
            territorial = log.get("territorial_changes_summary", log.get("territorial_changes_description", ""))
            
            parts.append(f"\n[{year_range}]")
            parts.append(f"Narrative: {narrative}")
            if divergences:
                parts.append(f"Divergences at this time: {', '.join(divergences)}")
            if territorial:
                parts.append(f"Territorial state: {territorial}")
    
    return "\n".join(parts) if parts else "No previous history - this is the first iteration."


def format_rulers(rulers: Dict[str, Dict[str, Any]]) -> str:
    """Format current rulers for the prompt."""
    if not rulers:
        return "No rulers currently tracked."
    
    lines = []
    for tag, info in rulers.items():
        name = info.get("name", "Unknown")
        title = info.get("title", "Ruler")
        age = info.get("age", "unknown")
        dynasty = info.get("dynasty", "unknown")
        lines.append(f"  - {tag}: {name}, {title}, age {age}, {dynasty} dynasty")
    
    return "\n".join(lines)


def make_decision(
    historian_output: Dict[str, Any],
    divergences: List[str],
    condensed_logs: str,
    recent_logs: List[Dict[str, Any]],
    rulers: Dict[str, Dict[str, Any]],
    current_year: int,
    years_to_progress: int,
    available_tags: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Make creative decisions about what happens in the alternate timeline.
    
    Args:
        historian_output: Real historical context from Historian agent
        divergences: Current active divergences
        condensed_logs: Summarized older history
        recent_logs: Recent detailed log entries (2-3)
        rulers: Current rulers by nation tag
        current_year: Starting year of this period
        years_to_progress: Number of years to simulate
        available_tags: Dict of valid nation tags from scenario metadata
        
    Returns:
        Dict with rulers, narrative, territorial_changes (structured list),
        territorial_changes_summary, updated_divergences, and merged flag
    """
    global _available_tags
    _available_tags = available_tags or {}
    
    end_year = current_year + years_to_progress
    
    # Format all the context
    historian_context = format_historian_output(historian_output)
    logs_context = format_logs_context(condensed_logs, recent_logs)
    rulers_context = format_rulers(rulers)
    
    divergences_text = "\n".join([f"  - {d}" for d in divergences]) if divergences else "  (No current divergences - timeline may be converging)"
    
    # Format available tags directly in prompt
    available_tags_text = "NONE DEFINED - do not add new ruler tags"
    if _available_tags:
        tag_lines = [f"  - {tag}: {info.get('name', 'Unknown')}" for tag, info in _available_tags.items()]
        available_tags_text = "\n".join(tag_lines)
    
    user_prompt = f"""Decide what happens in the period {current_year}-{end_year} in this alternate timeline.

=== VALID NATION TAGS (ONLY USE THESE) ===
{available_tags_text}

=== CURRENT DIVERGENCES ===
{divergences_text}

=== HISTORICAL CONTEXT ===
{historian_context}

=== PREVIOUS HISTORY ===
{logs_context}

=== CURRENT RULERS ===
{rulers_context}

Decide:
1. Which events occur, are prevented, or altered?
2. Ruler updates (add {years_to_progress} years to ages, handle deaths/successions)
3. Territorial changes (be SPECIFIC with locations)
4. Which divergences remain or emerge?
5. Has timeline merged back to real history?

Remember: Consider political systems, alliances, and real-world logic the Historian may have missed!
Make it entertaining but plausible. Return JSON only."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    # Try structured output first for guaranteed JSON compliance
    try:
        structured_response = llm_structured.invoke(messages)
        
        # Convert Pydantic model to dict
        result = {
            "rulers": {tag: ruler.model_dump() for tag, ruler in structured_response.rulers.items()},
            "narrative": structured_response.narrative,
            "territorial_changes": [change.model_dump() for change in structured_response.territorial_changes],
            "territorial_changes_summary": structured_response.territorial_changes_summary,
            "updated_divergences": structured_response.updated_divergences,
            "merged": structured_response.merged
        }
        
        # Validate that all ruler tags are in available_tags
        if available_tags:
            valid_tags = set(available_tags.keys())
            invalid_tags = [tag for tag in result["rulers"].keys() if tag not in valid_tags]
            if invalid_tags:
                print(f"Warning: Dreamer created invalid tags: {invalid_tags}. Removing them.")
                for tag in invalid_tags:
                    del result["rulers"][tag]
        
        return result
        
    except Exception as structured_error:
        print(f"Structured output failed: {structured_error}")
        print("Falling back to tool-based approach...")
    
    # Fallback: Call LLM with tools - handle potential tool calls
    response = llm_with_tools.invoke(messages)
    
    # Check if the model wants to call a tool
    max_tool_iterations = 3
    iteration = 0
    while response.tool_calls and iteration < max_tool_iterations:
        iteration += 1
        # Add the AI message with tool calls
        messages.append(response)
        
        # Execute each tool call and add results
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            if tool_name == "get_available_nation_tags":
                tool_result = get_available_nation_tags.invoke({})
                messages.append({
                    "role": "tool",
                    "content": tool_result,
                    "tool_call_id": tool_call["id"]
                })
        
        # Continue the conversation
        response = llm_with_tools.invoke(messages)
    
    # If response still has tool calls but no content, try once more without tools
    if not response.content or (isinstance(response.content, str) and not response.content.strip()):
        # Fallback: Call without tools to get final response
        response = llm.invoke(messages)
    
    try:
        # Get content - handle both string and list responses
        content = response.content
        if isinstance(content, list):
            # Extract text from list of content blocks, join them
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    text_parts.append(block.get("text", ""))
                else:
                    text_parts.append(str(block))
            content = "\n".join(text_parts)
        content = content.strip() if content else ""
        
        # Clean up response - sometimes LLMs wrap JSON in markdown
        # Find JSON block if wrapped in markdown
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
        
        # Also try to find JSON by looking for opening brace
        if not content.startswith("{"):
            brace_start = content.find("{")
            if brace_start != -1:
                # Find matching closing brace
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
        
        # Validate required fields - handle both old and new format for backward compatibility
        if "rulers" not in result:
            result["rulers"] = rulers  # Keep existing rulers
        if "narrative" not in result:
            result["narrative"] = f"The period {current_year}-{end_year} AD saw continued developments."
        
        # Handle territorial changes - support both old and new format
        if "territorial_changes" not in result:
            result["territorial_changes"] = []
        if "territorial_changes_summary" not in result:
            # Fall back to old field name if present
            result["territorial_changes_summary"] = result.get(
                "territorial_changes_description", 
                "No significant territorial changes occurred."
            )
        
        if "updated_divergences" not in result:
            result["updated_divergences"] = divergences  # Keep existing
        if "merged" not in result:
            result["merged"] = False
        
        # Validate that all ruler tags are in available_tags
        if available_tags:
            valid_tags = set(available_tags.keys())
            invalid_tags = [tag for tag in result["rulers"].keys() if tag not in valid_tags]
            if invalid_tags:
                print(f"Warning: Dreamer created invalid tags: {invalid_tags}. Removing them.")
                for tag in invalid_tags:
                    del result["rulers"][tag]
            
        return result
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse dreamer response: {e}")
        print(f"Raw response: {response.content[:500]}")
        
        # Return a fallback response
        return {
            "rulers": rulers,
            "narrative": f"The period {current_year}-{end_year} AD saw continued developments as divergences shaped events.",
            "territorial_changes": [],
            "territorial_changes_summary": "Unable to determine territorial changes due to parsing error.",
            "updated_divergences": divergences,
            "merged": False
        }
