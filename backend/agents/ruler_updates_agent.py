"""
Ruler Updates Agent - Updates the list of rulers based on the narrative.

The Ruler Updates agent takes the current rulers, the Writer's narrative,
and the year range to produce an updated rulers list at the END of the period with:
- Aged rulers (age += years_to_progress)
- Deaths and successions
- New rulers mentioned in the narrative

Uses tool-based output for reliability.
"""
from dotenv import load_dotenv
import os
from typing import Dict, List, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

from util.text import transliterate

load_dotenv()

# Module-level storage for collected rulers
_rulers: Dict[str, Dict[str, Any]] = {}
_available_tags: List[str] = []


# Tool definitions

@tool
def set_ruler(tag: str, name: str, title: str, age: int, dynasty: str = "") -> str:
    """
    Set a ruler for a nation at the END of the period.
    Call this for EVERY nation tag - both unchanged rulers (with updated age) and new rulers.
    
    Args:
        tag: Nation TAG (e.g., ROM, BYZ, FRK) - must be from available tags
        name: Ruler's name (ASCII only, no accents - use "Francois" not "François")
        title: Ruler's title (Emperor, King, President, etc.)
        age: Ruler's age at the END of this period (after years have passed)
        dynasty: Dynasty name or political party (optional)
    """
    global _rulers
    
    if tag not in _available_tags:
        return f"Error: '{tag}' is not a valid tag. Available: {', '.join(_available_tags)}"
    
    # Transliterate to ASCII
    clean_name = transliterate(name)
    clean_dynasty = transliterate(dynasty) if dynasty else ""
    
    _rulers[tag] = {
        "name": clean_name,
        "title": title,
        "age": age,
        "dynasty": clean_dynasty
    }
    return f"Set ruler for {tag}: {clean_name}, {title}, age {age}"


@tool
def mark_complete() -> str:
    """
    Call this AFTER you have set rulers for ALL nation tags.
    Every nation tag must have a ruler set before calling this.
    """
    global _rulers, _available_tags
    
    missing = [tag for tag in _available_tags if tag not in _rulers]
    if missing:
        return f"Error: Missing rulers for tags: {', '.join(missing)}. Set all rulers before completing."
    
    return "COMPLETE"


TOOLS = [set_ruler, mark_complete]


SYSTEM_PROMPT = """You are updating ruler information for the END of a historical period.

Given:
- Current rulers (at the START of the period)
- How many years pass
- A narrative describing what happened

Your job is to set the ruler for EVERY nation at the END of the period.

RULES:
1. **Age all rulers**: Add years_to_progress to each ruler's starting age
2. **Handle deaths**: If a ruler would be 80+ or the narrative mentions death, use a successor
3. **Handle successions**: If narrative mentions a new ruler, use them
4. **All nations required**: Every nation tag must have a ruler set
5. **ASCII only for names**: Use "Francois" not "François", "Bjorn" not "Björn"
6. **Democracies**: Respect term limits (US presidents max 8 years, etc.)

If unsure about a successor, invent a plausible one for the era/nation."""


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=60,
    max_retries=2
)

llm_with_tools = llm.bind_tools(TOOLS)


def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute a tool by name."""
    tool_map = {t.name: t for t in TOOLS}
    tool_func = tool_map.get(tool_name)
    return tool_func.invoke(tool_args) if tool_func else f"Unknown tool: {tool_name}"


def format_current_rulers(rulers: Dict[str, Dict[str, Any]]) -> str:
    """Format current rulers for the prompt."""
    if not rulers:
        return "No rulers currently tracked."

    lines = []
    for tag, info in rulers.items():
        dynasty = f", {info.get('dynasty')}" if info.get("dynasty") else ""
        lines.append(
            f"  - {tag}: {info.get('name', '?')}, "
            f"{info.get('title', '?')}, age {info.get('age', '?')}{dynasty}"
        )
    return "\n".join(lines)


def update_rulers(
    current_rulers: Dict[str, Dict[str, Any]],
    narrative: str,
    current_year: int,
    years_to_progress: int
) -> Dict[str, Any]:
    """
    Update rulers based on the narrative and time passing using tool calls.

    Args:
        current_rulers: Dict of nation tag -> ruler info (at START of period)
        narrative: The Writer's narrative describing what happened
        current_year: Starting year of this period
        years_to_progress: How many years passed

    Returns:
        Dict with rulers dict (at END of period)
    """
    global _rulers, _available_tags
    
    # Reset state
    _rulers = {}
    _available_tags = list(current_rulers.keys()) if current_rulers else []
    
    if not _available_tags:
        return {"rulers": {}}

    end_year = current_year + years_to_progress
    rulers_ctx = format_current_rulers(current_rulers)
    tags_str = ", ".join(_available_tags)

    user_prompt = f"""Update rulers for the period {current_year}-{end_year} AD.

=== NATION TAGS TO UPDATE ===
{tags_str}

=== CURRENT RULERS (at START of period, year {current_year}) ===
{rulers_ctx}

=== YEARS PASSING ===
{years_to_progress} years

=== NARRATIVE ===
{narrative}

For EACH nation tag, call set_ruler() with the ruler at the END of {end_year} AD.
- Add {years_to_progress} to each ruler's starting age
- Replace rulers who die or are replaced as according to narrataive
- Use ASCII names only (no accents)

Call set_ruler() for EVERY tag, then call mark_complete().
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    # Tool-calling loop
    max_iterations = 20
    iteration = 0
    completed = False
    response = llm_with_tools.invoke(messages)

    while iteration < max_iterations and not completed:
        iteration += 1

        if not response.tool_calls:
            print(f"[RulerUpdates] Iteration {iteration}: No tool calls, finishing")
            break

        print(f"[RulerUpdates] Iteration {iteration}: {len(response.tool_calls)} tool call(s)")
        messages.append(response)

        for tc in response.tool_calls:
            name = tc["name"]
            args = tc.get("args", {})

            if name == "mark_complete":
                result = execute_tool(name, args)
                if result == "COMPLETE":
                    print(f"    -> COMPLETE")
                    completed = True
                else:
                    print(f"    -> {result}")  # Error about missing tags
            else:
                tag = args.get("tag", "?")
                ruler_name = args.get("name", "?")
                print(f"    -> set_ruler({tag}: {ruler_name})")
                result = execute_tool(name, args)

            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

        if not completed:
            response = llm_with_tools.invoke(messages)

    # Fallback: if we're missing rulers, use originals with aged values
    for tag in _available_tags:
        if tag not in _rulers:
            info = current_rulers.get(tag, {})
            _rulers[tag] = {
                "name": info.get("name", "Unknown"),
                "title": info.get("title", "Ruler"),
                "age": info.get("age", 30) + years_to_progress,
                "dynasty": info.get("dynasty", "")
            }
            print(f"[RulerUpdates] Fallback for {tag}: aged existing ruler")

    rulers_copy = _rulers.copy()
    print(f"[RulerUpdates] Done: {len(rulers_copy)} ruler(s)")

    return {"rulers": rulers_copy}

