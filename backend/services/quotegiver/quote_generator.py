"""Quote generation using LLM with tool-based output."""
import logging
from typing import Dict, List, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage

from .config import GEMINI_API_KEY, GEMINI_MODEL, LLM_TIMEOUT_SECONDS, MAX_QUOTES_PER_EVENT

logger = logging.getLogger(__name__)

# Module-level storage for collected quotes
_quotes: List[Dict[str, Any]] = []
_available_tags: Dict[str, Dict[str, Any]] = {}


# Tool definitions

@tool
def add_quote(tag: str, quote: str) -> str:
    """
    Add a memorable quote from a ruler.
    
    Args:
        tag: Nation TAG of the ruler (e.g., ROM, BYZ, FRK) - must be from available tags
        quote: A single-sentence memorable quote (15-30 words, first person)
    """
    global _quotes, _available_tags
    
    if tag not in _available_tags:
        return f"Error: '{tag}' is not a valid tag. Available: {', '.join(_available_tags.keys())}"
    
    ruler = _available_tags[tag]
    _quotes.append({
        "tag": tag,
        "ruler_name": ruler.get("name", "Unknown"),
        "ruler_title": ruler.get("title", "Ruler"),
        "quote": quote
    })
    return f"Added quote from {ruler.get('name', tag)}: \"{quote[:50]}...\""


@tool
def mark_complete() -> str:
    """
    Call this AFTER you have added 1-2 quotes from the most relevant rulers.
    """
    global _quotes
    
    if not _quotes:
        return "Error: Must add at least 1 quote before completing."
    
    return "COMPLETE"


TOOLS = [add_quote, mark_complete]


SYSTEM_PROMPT = """You are a historical quote writer. Given a narrative and rulers list,
select up to 2 seperate rulers whose nations are most affected, then write memorable quotes.

GUIDELINES:
- Quotes should feel historically authentic to the era and culture
- Keep each quote to a SINGLE SENTENCE (15-30 words)
- Use first person ("I", "We")
- Make quotes memorable and dramatic
- If there is only one relevant ruler, only write one quote
- If tehre is only one available ruler, only write one quote


Call add_quote() for MAX 2 relevant rulers, then call mark_complete()."""


def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GEMINI_API_KEY,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=2,
    )


llm_with_tools = get_llm().bind_tools(TOOLS)


def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute a tool by name."""
    tool_map = {t.name: t for t in TOOLS}
    tool_func = tool_map.get(tool_name)
    return tool_func.invoke(tool_args) if tool_func else f"Unknown tool: {tool_name}"


def format_rulers_for_prompt(rulers: Dict[str, Dict[str, Any]]) -> str:
    """Format rulers dict for the prompt."""
    if not rulers:
        return "No rulers available."

    lines = []
    for tag, info in rulers.items():
        dynasty = f" of {info.get('dynasty')}" if info.get("dynasty") else ""
        lines.append(f"  - {tag}: {info.get('name', '?')}{dynasty}, {info.get('title', '?')}, age {info.get('age', '?')}")
    return "\n".join(lines)


def generate_quotes_from_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate quotes from a timeline event using tool calls."""
    global _quotes, _available_tags
    
    decision = event.get("dreamer_decision", {})
    narrative = decision.get("narrative", "")
    rulers = decision.get("rulers", {})
    year_range = event.get("year_range", "Unknown period")

    if not rulers or not narrative:
        return []

    # Reset state
    _quotes = []
    _available_tags = rulers

    rulers_ctx = format_rulers_for_prompt(rulers)

    user_prompt = f"""Generate 1-2 memorable quotes from rulers for: {year_range} AD

=== AVAILABLE RULERS ===
{rulers_ctx}

=== NARRATIVE ===
{narrative}

Select 1-2 rulers most affected by these events and write a memorable quote from each.
Call add_quote() for each quote, then call mark_complete()."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Tool-calling loop
    max_iterations = 10
    iteration = 0
    completed = False
    
    try:
        response = llm_with_tools.invoke(messages)

        while iteration < max_iterations and not completed:
            iteration += 1

            if not response.tool_calls:
                logger.info(f"[Quotegiver] Iteration {iteration}: No tool calls, finishing")
                break

            logger.info(f"[Quotegiver] Iteration {iteration}: {len(response.tool_calls)} tool call(s)")
            messages.append(response)

            for tc in response.tool_calls:
                name = tc["name"]
                args = tc.get("args", {})

                if name == "mark_complete":
                    result = execute_tool(name, args)
                    if result == "COMPLETE":
                        logger.info(f"    -> COMPLETE")
                        completed = True
                    else:
                        logger.info(f"    -> {result}")
                else:
                    tag = args.get("tag", "?")
                    logger.info(f"    -> add_quote({tag})")
                    result = execute_tool(name, args)

                messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

            if not completed:
                response = llm_with_tools.invoke(messages)

        quotes_copy = _quotes[:MAX_QUOTES_PER_EVENT]
        logger.info(f"[Quotegiver] Generated {len(quotes_copy)} quotes for {year_range}")
        return quotes_copy

    except Exception as e:
        logger.error(f"Failed to generate quotes: {e}")
        raise
