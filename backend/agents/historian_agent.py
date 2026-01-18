"""
Historian Agent - Provides real historical context for a time period.

The Historian does NOT see the alternate timeline. It only provides
the baseline of what ACTUALLY happened in real history, giving the Dreamer
context to make decisions about how divergences alter events.

IMPORTANT: The Historian has NO knowledge of:
- Current divergences
- Alternate timeline rulers  
- Previous alternate history events
- What the Dreamer decided in past iterations

It purely reports real history. For future time periods, it acts as a historian
from that future time, reporting plausible events as if they happened.
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
    condition: str = Field(description="The condition that triggers this event")
    outcome: str = Field(description="What happens if the condition is met")


class HistorianOutput(BaseModel):
    """Structured output from the Historian agent."""
    period: str = Field(description="The year range as a string (e.g., '630-650')")
    conditional_events: List[ConditionalEvent] = Field(
        description="Historical events with their conditions/triggers"
    )


def build_system_prompt(country_names: List[str], is_future: bool, max_events: int) -> str:
    """Build a dynamic system prompt based on the countries involved."""
    countries_str = ", ".join(country_names) if country_names else "world history"
    
    future_note = ""
    if is_future:
        future_note = """
FUTURE PERIOD: The time period requested is in the future. You are a historian from that future era, 
reporting what "actually happened" as if looking back. Create plausible, realistic events based on 
current trends and geopolitical dynamics. Present these as historical fact, not speculation."""
    
    return f"""You are an expert historian specializing in {countries_str}.
{future_note}
Provide historical context for the specified time period as factual events.

IMPORTANT: Output a MAXIMUM of {max_events} conditional events. Only include the most significant events.

Format your response as conditional events:
- "condition": The circumstances or situation that existed
- "outcome": What happened as a result

Focus on major events:
- Leadership changes and political transitions
- Wars, conflicts, and military campaigns  
- Territorial changes
- Major treaties and diplomatic events
- Significant political or administrative changes

Be specific with dates. Keep responses concise and relevant."""

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=60,  # 1 minute timeout
    max_retries=2
)

# Create structured output version
llm_structured = llm.with_structured_output(HistorianOutput)


def get_historical_context(
    start_year: int,
    years_to_progress: int,
    tags: Dict[str, dict] = None
) -> Dict[str, Any]:
    """
    Get real historical context for a time period.
    
    NOTE: This function intentionally does NOT take any alternate timeline
    information (rulers, divergences, etc.) - only the time period and countries.
    
    Args:
        start_year: The starting year of the period
        years_to_progress: How many years the period covers
        tags: Dict of nation tags with their metadata (e.g., {"ROM": {"name": "Roman Empire"}})
        
    Returns:
        Dict with period and conditional_events from real history
    """
    end_year = start_year + years_to_progress
    
    # Extract country names from tags
    country_names = []
    if tags:
        country_names = [tag_info.get("name", tag) for tag, tag_info in tags.items()]
    
    # Check if this is a future period
    current_real_year = datetime.now().year
    is_future = start_year > current_real_year
    
    # Calculate max events: 1 event per 5 years of the period
    max_events = max(1, years_to_progress // 5)
    
    # Build dynamic system prompt
    system_prompt = build_system_prompt(country_names, is_future, max_events)
    
    # Build user prompt
    countries_str = ", ".join(country_names) if country_names else "the region"
    
    if is_future:
        user_prompt = f"""Provide historical context for {countries_str} during the period {start_year}-{end_year}.

As a historian from this future era, report what major events occurred:
- Leadership and political changes
- Conflicts and their outcomes
- Territorial changes
- Major diplomatic events

Present these as established historical fact. Include at most {max_events} events (the most significant ones only)."""
    else:
        user_prompt = f"""Provide the real historical context for {countries_str} during the period {start_year}-{end_year}.

What major events ACTUALLY happened during this period? Include:
- Who was ruling and any succession changes
- Major wars and their outcomes
- Territorial changes
- Important political events

Include at most {max_events} events (the most significant ones only)."""

    messages = [
        {"role": "system", "content": system_prompt},
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
