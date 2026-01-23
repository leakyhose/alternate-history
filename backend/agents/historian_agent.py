"""
Historian Agent - Provides real historical context for a time period.

The Historian has NO knowledge of the alternate timeline - it only reports
what actually happened in real history, giving the Dreamer context.
"""
from datetime import datetime
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()


class ConditionalEvent(BaseModel):
    """A conditional historical event."""
    condition: str = Field(description="Condition that triggers this event")
    outcome: str = Field(description="What happens if condition is met")


class HistorianOutput(BaseModel):
    """Structured output from the Historian agent."""
    period: str = Field(description="Year range string (e.g., '630-650')")
    conditional_events: List[ConditionalEvent] = Field(description="Historical events with triggers")


def build_system_prompt(country_names: List[str], is_future: bool, max_events: int) -> str:
    """Build system prompt based on countries and time period."""
    countries = ", ".join(country_names) if country_names else "world history"

    future_note = ""
    if is_future:
        future_note = """
FUTURE PERIOD: You are a historian from this future era, reporting what "actually happened"
as if looking back. Create plausible events based on current trends. Present as fact."""

    return f"""You are an expert historian specializing in {countries}.
{future_note}
Provide historical context for the specified time period as factual events.

Output a MAXIMUM of {max_events} conditional events. Only include significant events.

Format as conditional events:
- "condition": The circumstances or situation that existed
- "outcome": What happened as a result

Focus on: leadership changes, wars, territorial changes, treaties, political events.
Be specific with dates. Keep responses concise."""


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=60,
    max_retries=2
)

llm_structured = llm.with_structured_output(HistorianOutput)


def get_historical_context(
    start_year: int,
    years_to_progress: int,
    tags: Dict[str, dict] = None
) -> Dict[str, Any]:
    """
    Get real historical context for a time period.

    Args:
        start_year: Starting year of the period
        years_to_progress: How many years the period covers
        tags: Dict of nation tags with metadata

    Returns:
        Dict with period and conditional_events from real history
    """
    end_year = start_year + years_to_progress
    country_names = [info.get("name", tag) for tag, info in (tags or {}).items()]
    is_future = start_year > datetime.now().year
    max_events = max(1, years_to_progress // 5)

    system_prompt = build_system_prompt(country_names, is_future, max_events)
    countries = ", ".join(country_names) if country_names else "the region"

    if is_future:
        user_prompt = f"""Provide historical context for {countries} during {start_year}-{end_year}.

As a historian from this future era, report major events:
- Leadership and political changes
- Conflicts and outcomes
- Territorial changes
- Major diplomatic events

Present as fact. Include at most {max_events} significant events."""
    else:
        user_prompt = f"""Provide real historical context for {countries} during {start_year}-{end_year}.

What major events ACTUALLY happened? Include:
- Rulers and succession changes
- Major wars and outcomes
- Territorial changes
- Important political events

Include at most {max_events} significant events."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        result = llm_structured.invoke(messages)
        return {
            "period": result.period,
            "conditional_events": [ce.model_dump() for ce in result.conditional_events]
        }
    except Exception as e:
        print(f"Structured output failed for historian: {e}")

    # Fallback to manual parsing
    response = llm.invoke(messages)
    try:
        content = response.content.strip()
        for marker in ["```json", "```"]:
            if marker in content:
                start = content.find(marker) + len(marker)
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()
                    break
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Failed to parse historian response: {e}")
        return {"period": f"{start_year}-{end_year}", "conditional_events": []}
