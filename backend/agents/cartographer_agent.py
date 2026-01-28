"""
Cartographer Agent - Translates narrative into territorial changes.

The Cartographer reads the Writer's narrative and extracts structured
territorial changes representing the NET difference between the START
and END of the period. Uses tool-based output for reliability.

KEY CONCEPT: Think of having two maps - one at the start of the period,
one at the end. The Cartographer describes what changed between them,
ignoring intermediate events.
"""
from dotenv import load_dotenv
import os
from typing import Dict, List, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

load_dotenv()

# Module-level storage for collected changes
_territorial_changes: List[Dict[str, Any]] = []
_available_tags: List[str] = []


# Tool definitions

@tool
def register_conquest(location: str, to_nation: str, context: str = "") -> str:
    """
    Register a CONQUEST: a tracked nation ENDS the period with territory it didn't have at the START.
    The source is untracked (barbarians, rebels, minor states outside the scenario).
    
    Args:
        location: VERY SPECIFIC location (e.g., "Brittany", "Northern Syria", "ALL OF VAN")
        to_nation: Nation TAG that holds this territory at END of period
        context: Brief context (e.g., "conquered during the Gothic War")
    """
    global _territorial_changes
    
    if to_nation not in _available_tags:
        return f"Error: '{to_nation}' is not a valid tag. Available: {', '.join(_available_tags)}"
    
    _territorial_changes.append({
        "location": location,
        "change_type": "CONQUEST",
        "to_nation": to_nation,
        "context": context
    })
    return f"Registered CONQUEST: {to_nation} gains {location}"


@tool
def register_loss(location: str, from_nation: str, context: str = "") -> str:
    """
    Register a LOSS: a tracked nation ENDS the period WITHOUT territory it had at the START.
    The new owner is untracked (barbarians, rebels, minor states outside the scenario).
    
    Args:
        location: VERY SPECIFIC location (e.g., "Pannonia", "Lower Egypt", "ALL OF ROM")
        from_nation: Nation TAG that held this territory at START but not at END
        context: Brief context (e.g., "overrun by Hunnic invasions")
    """
    global _territorial_changes
    
    if from_nation not in _available_tags:
        return f"Error: '{from_nation}' is not a valid tag. Available: {', '.join(_available_tags)}"
    
    _territorial_changes.append({
        "location": location,
        "change_type": "LOSS",
        "from_nation": from_nation,
        "context": context
    })
    return f"Registered LOSS: {from_nation} loses {location}"


@tool
def register_transfer(location: str, from_nation: str, to_nation: str, context: str = "") -> str:
    """
    Register a TRANSFER: territory changes hands between two TRACKED nations.
    One tracked nation held it at START, a different tracked nation holds it at END.
    
    IMPORTANT: ONLY use this when BOTH from_nation AND to_nation are in the available tags list.
    If one side is untracked, use register_conquest or register_loss instead.
    
    Args:
        location: VERY SPECIFIC location (e.g., "Gaul", "Anatolia", "ALL OF WRO")
        from_nation: Nation TAG that held territory at START (MUST be in available tags)
        to_nation: Nation TAG that holds territory at END (MUST be in available tags)
        context: Brief context (e.g., "ceded in peace treaty")
    """
    global _territorial_changes
    
    if from_nation not in _available_tags:
        return f"Error: '{from_nation}' is not a valid tag. Available: {', '.join(_available_tags)}"
    if to_nation not in _available_tags:
        return f"Error: '{to_nation}' is not a valid tag. Available: {', '.join(_available_tags)}"
    if from_nation == to_nation:
        return f"Error: from_nation and to_nation cannot be the same"
    
    _territorial_changes.append({
        "location": location,
        "change_type": "TRANSFER",
        "from_nation": from_nation,
        "to_nation": to_nation,
        "context": context
    })
    return f"Registered TRANSFER: {location} from {from_nation} to {to_nation}"


@tool
def mark_complete() -> str:
    """
    Call this when you have registered ALL territorial changes from the narrative.
    If there are no territorial changes, call this immediately.
    """
    return "COMPLETE"


TOOLS = [register_conquest, register_loss, register_transfer, mark_complete]


SYSTEM_PROMPT = """You are a cartographer extracting NET territorial changes from historical narratives.

Think of having two maps: one at the START of the period, one at the END.
Your job is to describe what changed between them - ignore intermediate events.

CRITICAL - TRANSFER vs CONQUEST/LOSS:
- **TRANSFER**: ONLY when BOTH the gainer AND loser are in your available tags list
- **CONQUEST**: A tracked nation gained territory (from anyone - tracked or untracked)
- **LOSS**: A tracked nation lost territory (to anyone - tracked or untracked)

NEVER use a tag that isn't in your available tags list. If only one side of a transfer is tracked:
- France (tracked) takes land from rebels (untracked) → use CONQUEST for France
- Rebels (untracked) take land from France (tracked) → use LOSS for France
- DO NOT use TRANSFER with an invented or untracked tag

EXAMPLES:
- Rome conquers Gaul, loses it, reconquers it → NET change is nothing (skip)
- Persia (tracked) takes Syria from Rome (tracked) → TRANSFER (both tracked)
- Rome (tracked) conquers barbarian lands → CONQUEST for Rome (barbarians not tracked)
- Barbarians take Pannonia from Rome (tracked) → LOSS for Rome (barbarians not tracked)
- Two untracked nations fight → skip entirely (neither is tracked)

RULES:
1. **NET CHANGES ONLY**: Compare START vs END of period, not intermediate events
2. **ONLY USE AVAILABLE TAGS**: Never invent tags or use nations not in your list
3. **Be specific about locations**: Use clear region names that can be mapped
4. **Use "ALL OF [TAG]"** when an entire nation is conquered/annexed
5. **Don't invent changes**: Only extract what's explicitly described in the narrative
6. **Call mark_complete()** when done (even if no changes found)

If a territorial change involves nations you can't represent with available tags, skip it entirely."""


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


def extract_territorial_changes(
    narrative: str,
    year_range: str,
    available_tags: List[str]
) -> Dict[str, Any]:
    """
    Extract territorial changes from a narrative using tool calls.

    Args:
        narrative: The Writer's narrative describing what happened
        year_range: The time period (e.g., "450-470")
        available_tags: List of valid nation tags for this scenario

    Returns:
        Dict with territorial_changes list
    """
    global _territorial_changes, _available_tags
    
    # Reset state
    _territorial_changes = []
    _available_tags = available_tags

    tags_str = ", ".join(available_tags) if available_tags else "None specified"

    user_prompt = f"""Extract NET territorial changes from this narrative.

Compare the world at the START of the period to the END. What territories changed hands?

=== PERIOD ===
{year_range} AD

=== AVAILABLE NATION TAGS ===
{tags_str}
(Nations NOT in this list are "untracked" - use CONQUEST/LOSS, not TRANSFER)

=== NARRATIVE ===
{narrative}

Register each NET territorial change using the appropriate tool.
If no territorial changes occurred, just call mark_complete().
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    # Tool-calling loop
    max_iterations = 15
    iteration = 0
    completed = False
    response = llm_with_tools.invoke(messages)

    while iteration < max_iterations and not completed:
        iteration += 1

        if not response.tool_calls:
            print(f"[Cartographer] Iteration {iteration}: No tool calls, finishing")
            break

        print(f"[Cartographer] Iteration {iteration}: {len(response.tool_calls)} tool call(s)")
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

    changes = _territorial_changes.copy()
    print(f"[Cartographer] Done: {len(changes)} territorial change(s)")

    return {"territorial_changes": changes}

