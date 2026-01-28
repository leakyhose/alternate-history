"""
Writer Agent - Creates the narrative for alternate history.

The Writer considers real history, current divergences, and past events
to craft an eventful but grounded narrative (100-200 words).
Uses tool-based output for reliability.
"""
from dotenv import load_dotenv
import os
from typing import Dict, List, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

load_dotenv()

# Module-level storage for writer output
_writer_output: Dict[str, Any] = {}


# Tool definitions

@tool
def set_narrative(narrative: str) -> str:
    """
    Set the narrative for this period (100-200 words).
    
    The narrative should describe what happened during the time period.
    Be eventful, specific about territories, and ground in real history.
    Never use nation tags (ROM, BYZ) - use full names (Rome, Byzantium).
    When rulers die, name their successors.
    
    Args:
        narrative: The 100-200 word narrative describing what happened
    """
    global _writer_output
    _writer_output["narrative"] = narrative
    word_count = len(narrative.split())
    return f"Narrative set ({word_count} words)"


@tool
def keep_divergence(divergence: str) -> str:
    """
    Keep an existing divergence that is STILL relevant going forward.
    Only call this for divergences from the input that still matter.
    Don't call this for divergences that have fizzled out or been resolved.
    
    Args:
        divergence: The divergence text (from input) to keep
    """
    global _writer_output
    if "updated_divergences" not in _writer_output:
        _writer_output["updated_divergences"] = []
    _writer_output["updated_divergences"].append(divergence)
    return f"Kept divergence: {divergence[:50]}..."


@tool
def add_new_divergence(divergence: str) -> str:
    """
    Add a NEW butterfly effect that emerged from this period's events.
    These are cascading consequences that will affect future periods.
    
    Example: If Rome conquers Persia, new divergences might be:
    - "Roman-Chinese trade routes established"
    - "Zoroastrian refugees flee east"
    
    Args:
        divergence: A new divergence/butterfly effect to add
    """
    global _writer_output
    if "new_divergences" not in _writer_output:
        _writer_output["new_divergences"] = []
    _writer_output["new_divergences"].append(divergence)
    return f"Added new divergence: {divergence[:50]}..."


@tool
def set_merged(merged: bool) -> str:
    """
    Set whether the timeline has merged back to real history.
    Only set True if ALL divergences have been resolved and history
    is back on its original track.
    
    Args:
        merged: True if timeline merged back to real history, False otherwise
    """
    global _writer_output
    _writer_output["merged"] = merged
    return f"Merged status set to: {merged}"


@tool
def mark_complete() -> str:
    """
    Call this AFTER you have:
    1. Set the narrative
    2. Called keep_divergence() for each input divergence that's still relevant
    3. Called add_new_divergence() for any new butterfly effects
    4. Set merged status
    """
    global _writer_output
    
    if "narrative" not in _writer_output:
        return "Error: Must set narrative before completing"
    if "merged" not in _writer_output:
        _writer_output["merged"] = False
    if "updated_divergences" not in _writer_output:
        _writer_output["updated_divergences"] = []
    if "new_divergences" not in _writer_output:
        _writer_output["new_divergences"] = []
    
    return "COMPLETE"


TOOLS = [set_narrative, keep_divergence, add_new_divergence, set_merged, mark_complete]


SYSTEM_PROMPT = """You are an alternate history writer. Write compelling, eventful narratives that explore "what if" scenarios.

GUIDELINES:
1. **Ground in real history**: Know what ACTUALLY happened. Divergences should butterfly from real events.
2. **Be eventful**: Make things happen! Wars, treaties, deaths, successions, discoveries.
3. **Be specific about territories**: Name specific regions clearly for the Cartographer.
4. **Consider logistics and time**: Empires can't teleport. Be realistic about what can change.
5. **Future periods**: Invent plausible events based on trends. Present as fact.
6. **NO TAGS**: Use "Rome" not "ROM", "Byzantium" not "BYZ".
7. **Successions**: When rulers die, name successors. "Justinian died, succeeded by Justin II."

DIVERGENCE RULES:
- Use keep_divergence() ONLY for input divergences that still matter
- Use add_new_divergence() for NEW butterfly effects from this period
- Don't keep divergences that have fizzled out or been resolved

Write 100-200 words. Focus on WHAT HAPPENED, not philosophy."""


llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=120,
    max_retries=2
)

llm_with_tools = llm.bind_tools(TOOLS)


def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute a tool by name."""
    tool_map = {t.name: t for t in TOOLS}
    tool_func = tool_map.get(tool_name)
    return tool_func.invoke(tool_args) if tool_func else f"Unknown tool: {tool_name}"


def format_logs_context(condensed: str, recent: List[Dict[str, Any]], max_recent: int = 3) -> str:
    """Format log history for the prompt."""
    parts = []

    if condensed:
        parts.extend(["=== Earlier History (Summary) ===", condensed, ""])

    if recent:
        parts.append("=== Recent History ===")
        for log in recent[-max_recent:]:
            parts.append(f"\n[{log.get('year_range', '?')}]")
            parts.append(log.get('narrative', ''))
            if log.get("divergences"):
                parts.append(f"Active divergences: {', '.join(log['divergences'])}")

    return "\n".join(parts) if parts else "No previous history - this is the beginning."


def write_narrative(
    divergences: List[str],
    condensed_logs: str,
    recent_logs: List[Dict[str, Any]],
    current_year: int,
    years_to_progress: int,
    available_tags: Dict[str, Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Write the alternate history narrative for a time period using tool calls.

    Args:
        divergences: Current divergences affecting the timeline
        condensed_logs: Summarized older history
        recent_logs: Recent detailed log entries
        current_year: Starting year of this period
        years_to_progress: How many years this period covers
        available_tags: Dict of nation tags with metadata (for context)

    Returns:
        Dict with narrative, updated_divergences, new_divergences, and merged flag
    """
    global _writer_output
    
    # Reset state
    _writer_output = {}
    
    end_year = current_year + years_to_progress
    logs_ctx = format_logs_context(condensed_logs, recent_logs)

    # Format divergences
    if divergences:
        divergences_text = "\n".join(f"  - {d}" for d in divergences)
    else:
        divergences_text = "  (None - timeline may be converging back to real history)"

    user_prompt = f"""Write what happens in {current_year}-{end_year} AD in this alternate timeline.

=== CURRENT DIVERGENCES (from input) ===
{divergences_text}

=== PREVIOUS HISTORY ===
{logs_ctx}

STEPS:
1. Call set_narrative() with a 100-200 word narrative
2. For EACH input divergence above that's STILL relevant, call keep_divergence()
3. For any NEW butterfly effects from your narrative, call add_new_divergence()
4. Call set_merged(False) unless timeline has returned to real history
5. Call mark_complete()
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
            print(f"[Writer] Iteration {iteration}: No tool calls, finishing")
            break

        print(f"[Writer] Iteration {iteration}: {len(response.tool_calls)} tool call(s)")
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
                    print(f"    -> {result}")
            elif name == "set_narrative":
                word_count = len(args.get("narrative", "").split())
                print(f"    -> set_narrative ({word_count} words)")
                result = execute_tool(name, args)
            else:
                print(f"    -> {name}()")
                result = execute_tool(name, args)

            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

        if not completed:
            response = llm_with_tools.invoke(messages)

    # Build result with fallbacks
    result = {
        "narrative": _writer_output.get("narrative", f"The period {current_year}-{end_year} AD saw continued developments."),
        "updated_divergences": _writer_output.get("updated_divergences", []),
        "new_divergences": _writer_output.get("new_divergences", []),
        "merged": _writer_output.get("merged", False)
    }
    
    # Fallback: if no divergences were kept and we had input divergences, keep them
    if not result["updated_divergences"] and divergences and not result["merged"]:
        print(f"[Writer] Fallback: keeping all input divergences")
        result["updated_divergences"] = divergences

    print(f"[Writer] Done: {len(result['updated_divergences'])} kept, {len(result['new_divergences'])} new divergences")
    
    return result
