"""
Historian Agent - Provides real historical context for a time period.

The Historian does NOT see the alternate timeline. It only provides
the baseline of what would happen in real history, giving the Dreamer
context to make decisions about how divergences alter events.
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()


class ConditionalEvent(BaseModel):
    """A conditional historical event."""
    condition: str = Field(description="The condition that triggers this event")
    outcome: str = Field(description="What happens if the condition is met")


class HistorianOutput(BaseModel):
    """Structured output from the Historian agent."""
    period: str = Field(description="The year range as a string (e.g., '630-650')")
    conditional_events: List[ConditionalEvent] = Field(
        description="Historical events with their conditions/triggers"
    )


SYSTEM_PROMPT = """You are a historian specializing in the Roman/Byzantine Empire (117-1453).
Provide historical context as conditional events for a specific time period.

You will be given a start year, years to progress, and current rulers.

Your response must include:
1. "period": The year range as a string (e.g., "630-650")
2. "conditional_events": Historical events with their conditions. Format each as:
   - "condition": What circumstance or situation led to this event
   - "outcome": What actually happened as a result

Focus on major events: succession crises, wars, invasions, political changes, territorial shifts.
Be specific with dates when known.
"""

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# Create structured output version
llm_structured = llm.with_structured_output(HistorianOutput)


def get_historical_context(
    start_year: int,
    years_to_progress: int,
    rulers: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get real historical context for a time period.
    
    Args:
        start_year: The starting year of the period
        years_to_progress: How many years the period covers
        rulers: Dict of current rulers keyed by nation tag
        
    Returns:
        Dict with period, real_events, keep_in_mind, and conditional_events
    """
    end_year = start_year + years_to_progress
    
    # Format ruler info for the prompt
    ruler_info = ""
    if rulers:
        ruler_lines = []
        for tag, info in rulers.items():
            name = info.get("name", "Unknown")
            title = info.get("title", "Ruler")
            age = info.get("age", "unknown age")
            dynasty = info.get("dynasty", "unknown dynasty")
            ruler_lines.append(f"- {tag}: {name}, {title}, age {age}, {dynasty} dynasty")
        ruler_info = "\n".join(ruler_lines)
    else:
        ruler_info = "No rulers specified"
    
    user_prompt = f"""Provide historical context for the period {start_year}-{end_year}.

Current rulers:
{ruler_info}

What actually happened in real history during this period? What trends and events should be kept in mind?"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    # Try structured output first
    try:
        result = llm_structured.invoke(messages)
        # Convert to dict, handling nested ConditionalEvent objects
        return {
            "period": result.period,
            "conditional_events": [ce.model_dump() for ce in result.conditional_events]
        }
    except Exception as e:
        print(f"Structured output failed for historian: {e}")
        print("Falling back to JSON parsing...")
    
    # Fallback to manual parsing
    response = llm.invoke(messages)
    
    try:
        # Clean up response - sometimes LLMs wrap JSON in markdown
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        return result
    except json.JSONDecodeError as e:
        # Return a minimal valid response on parse failure
        print(f"Failed to parse historian response: {e}")
        print(f"Raw response: {response.content[:500]}")
        return {
            "period": f"{start_year}-{end_year}",
            "conditional_events": []
        }
