"""
Dreamer Agent - The creative decision-maker for alternate history simulation.

Synthesizes divergences + historian context to decide what actually happens
in the alternate timeline.
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any, Optional, Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from util.text import transliterate

load_dotenv()

_available_tags: Dict[str, Dict[str, Any]] = {}


class RulerInfo(BaseModel):
    """Information about a ruler."""
    tag: str = Field(description="Nation tag (e.g., CAN, USA, QUE)")
    name: str = Field(description="Ruler's name")
    title: str = Field(description="Ruler's title (Emperor, King, President, etc.)")
    age: int = Field(description="Ruler's age in years")
    dynasty: str = Field(default="", description="Dynasty or political party")


class TerritorialChange(BaseModel):
    """A structured territorial change describing the NET result at period end."""
    location: str = Field(
        description="Detailed description of location. Use 'ALL OF [TAG]' for all provinces "
                    "of a nation, or natural language for partial changes."
    )
    change_type: Literal["CONQUEST", "LOSS", "TRANSFER"] = Field(
        description="CONQUEST: gain from untracked, LOSS: lose to untracked, TRANSFER: between tracked"
    )
    from_nation: Optional[str] = Field(default=None, description="Nation losing territory")
    to_nation: Optional[str] = Field(default=None, description="Nation gaining territory")
    context: str = Field(default="", description="Brief context for the change")


class DreamerOutput(BaseModel):
    """Structured output from the Dreamer agent."""
    rulers: List[RulerInfo] = Field(description="All rulers with updated ages")
    narrative: str = Field(description="Concise narrative (2-4 sentences, 50-80 words)")
    territorial_changes: List[TerritorialChange] = Field(default_factory=list)
    territorial_changes_summary: str = Field(description="Human-readable summary for display")
    updated_divergences: List[str] = Field(description="Current divergences affecting future")
    merged: bool = Field(description="True if timeline merged back to real history")


@tool
def get_available_nation_tags() -> str:
    """Get valid nation tags for rulers. Only use tags returned by this tool."""
    if not _available_tags:
        return "No nation tags defined for this scenario."
    lines = ["Available nation tags (only use these):"]
    for tag, info in _available_tags.items():
        lines.append(f"  - {tag}: {info.get('name', 'Unknown')}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a creative alternate history writer deciding what happens given divergences.

You receive:
1. Historical context from the Historian
2. Current divergences affecting the timeline
3. Previous alternate history
4. Current rulers

YOUR TASKS:
1. Evaluate which historical events are triggered, prevented, or altered
2. Generate a compelling narrative (2-4 sentences, ~50-80 words)
3. Update rulers (deaths, successions, age += years_to_progress)
4. Specify territorial changes using structured format
5. Update divergences (remove resolved, add new cascading effects)
6. Determine if timeline merged back to normal history

TERRITORIAL CHANGES - BE CONSERVATIVE:
- 5 years: Minor border adjustments, single provinces
- 10 years: Small regional war conclusion
- 20 years: Major war, moderate territorial shifts
- 50+ years: Large-scale empire building/collapse

Consider logistics: armies need time, supply lines limit range, conquered territories need garrisons.

POLITICAL SYSTEMS:
- Democracies: Leaders MUST change after term limits
- US Presidents: 4-year terms, max 8 years total
- Prime Ministers: Elections every 4-5 years, turnover every 8-12 years typical

TERRITORIAL CHANGES FORMAT:
- Use "ALL OF [TAG]" for complete transfers
- Use natural language for partial changes with specific regions
- change_type: CONQUEST (from untracked) | LOSS (to untracked) | TRANSFER (between tracked)

RULER FORMAT (ASCII only - no accents):
- tag, name, title, age, dynasty
- Convert: Chretien not Chretien, Francois not Francois

Return ONLY valid JSON matching the schema."""


llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=120,
    max_retries=2
)


def format_historian_output(historian_output: Dict[str, Any]) -> str:
    """Format historian output for the prompt."""
    if not historian_output:
        return "No historical context available."

    parts = [f"Period: {historian_output.get('period', 'Unknown')}"]

    events = historian_output.get("conditional_events", [])
    if events:
        parts.append("\nHistorical events (evaluate if conditions met):")
        for e in events:
            parts.append(f"  - IF: {e.get('condition', '?')}")
            parts.append(f"    THEN: {e.get('outcome', '?')}")

    return "\n".join(parts)


def format_logs_context(condensed: str, recent: List[Dict[str, Any]], max_recent: int = 3) -> str:
    """Format log history for the prompt."""
    parts = []

    if condensed:
        parts.extend(["=== Earlier History (Summary) ===", condensed, ""])

    if recent:
        parts.append("=== Recent Detailed History ===")
        for log in recent[-max_recent:]:
            parts.append(f"\n[{log.get('year_range', '?')}]")
            parts.append(f"Narrative: {log.get('narrative', '')}")
            if log.get("divergences"):
                parts.append(f"Divergences: {', '.join(log['divergences'])}")
            if log.get("territorial_changes_summary"):
                parts.append(f"Territorial: {log['territorial_changes_summary']}")

    return "\n".join(parts) if parts else "No previous history."


def format_rulers(rulers: Dict[str, Dict[str, Any]]) -> str:
    """Format current rulers for the prompt."""
    if not rulers:
        return "No rulers tracked."

    lines = []
    for tag, info in rulers.items():
        dynasty = f", {info.get('dynasty')}" if info.get("dynasty") else ""
        lines.append(f"  - {tag}: {info.get('name', '?')}, {info.get('title', '?')}, age {info.get('age', '?')}{dynasty}")
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
    """Make creative decisions about what happens in the alternate timeline."""
    global _available_tags
    _available_tags = available_tags or {}

    end_year = current_year + years_to_progress
    historian_ctx = format_historian_output(historian_output)
    logs_ctx = format_logs_context(condensed_logs, recent_logs)
    rulers_ctx = format_rulers(rulers)

    divergences_text = "\n".join(f"  - {d}" for d in divergences) if divergences else "  (None - timeline may converge)"

    tags_text = "NONE - do not add new ruler tags"
    if _available_tags:
        tags_text = "\n".join(f"  - {t}: {i.get('name', '?')}" for t, i in _available_tags.items())

    user_prompt = f"""Decide what happens in {current_year}-{end_year} in this alternate timeline.

=== VALID NATION TAGS ===
{tags_text}

=== CURRENT DIVERGENCES ===
{divergences_text}

=== HISTORICAL CONTEXT ===
{historian_ctx}

=== PREVIOUS HISTORY ===
{logs_ctx}

=== CURRENT RULERS ===
{rulers_ctx}

Decide:
1. Events triggered, prevented, or altered?
2. Ruler updates (ages += {years_to_progress}, handle deaths)
3. Territorial changes (be specific)
4. Divergences remaining or emerging?
5. Timeline merged back?

Return JSON only."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    response = llm.invoke(messages)

    try:
        content = response.content
        if isinstance(content, list):
            content = "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            )
        content = (content or "").strip()

        # Extract JSON from markdown if needed
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

        if not content.startswith("{"):
            brace = content.find("{")
            if brace != -1:
                depth = 0
                for i, c in enumerate(content[brace:], brace):
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            content = content[brace:i+1]
                            break

        result = json.loads(content)

        # Normalize rulers
        if "rulers" not in result:
            result["rulers"] = rulers
        elif isinstance(result["rulers"], list):
            result["rulers"] = {r.pop("tag"): r for r in result["rulers"] if isinstance(r, dict) and "tag" in r}
        if not result["rulers"]:
            result["rulers"] = rulers

        # Transliterate names
        for ruler in result["rulers"].values():
            if isinstance(ruler, dict):
                if "name" in ruler:
                    ruler["name"] = transliterate(ruler["name"])
                if "dynasty" in ruler:
                    ruler["dynasty"] = transliterate(ruler["dynasty"])

        # Ensure required fields
        result.setdefault("narrative", f"The period {current_year}-{end_year} AD saw continued developments.")
        result.setdefault("territorial_changes", [])
        result.setdefault("territorial_changes_summary",
                         result.get("territorial_changes_description", "No significant changes."))
        result.setdefault("updated_divergences", divergences)
        result.setdefault("merged", False)

        # Validate tags
        if available_tags and isinstance(result["rulers"], dict):
            valid = set(available_tags.keys())
            invalid = [t for t in result["rulers"] if t not in valid]
            if invalid:
                print(f"Warning: Invalid tags {invalid}, removing")
                for t in invalid:
                    del result["rulers"][t]

        return result

    except json.JSONDecodeError as e:
        print(f"Failed to parse dreamer response: {e}")
        print(f"Raw: {response.content[:500]}")
        return {
            "rulers": rulers,
            "narrative": f"The period {current_year}-{end_year} AD saw continued developments.",
            "territorial_changes": [],
            "territorial_changes_summary": "Unable to determine changes due to parsing error.",
            "updated_divergences": divergences,
            "merged": False
        }
