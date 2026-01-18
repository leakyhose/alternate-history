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

It purely reports real history.
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


SYSTEM_PROMPT = """You are a historian specializing in the Roman/Byzantine Empire (117-1453 AD).
Your role is to provide REAL historical context for a specific time period.

CRITICAL: You report ONLY what actually happened in real history. You have NO knowledge of any alternate timelines, divergences, or "what if" scenarios. You are purely a reference for actual historical events.

Your response must include:
1. "period": The year range as a string (e.g., "630-650")
2. "conditional_events": Real historical events framed as conditions and outcomes. Format each as:
   - "condition": The historical circumstances or situation that existed
   - "outcome": What actually happened in real history as a result

Focus on major events relevant to the Roman/Byzantine world:
- Succession crises and ruler changes
- Wars and military campaigns
- Invasions by external powers
- Political and administrative changes
- Major territorial gains or losses
- Important treaties and diplomatic events

Be specific with dates when known. Report what ACTUALLY happened, not hypotheticals."""

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
    years_to_progress: int
) -> Dict[str, Any]:
    """
    Get real historical context for a time period.
    
    NOTE: This function intentionally does NOT take any alternate timeline
    information (rulers, divergences, etc.) - only the time period.
    
    Args:
        start_year: The starting year of the period
        years_to_progress: How many years the period covers
        
    Returns:
        Dict with period and conditional_events from real history
    """
    end_year = start_year + years_to_progress

    user_prompt = f"""Provide the real historical context for the Byzantine/Roman Empire during the period {start_year}-{end_year} AD.

What major events ACTUALLY happened in real history during this period? Include:
- Who was ruling and any succession changes
- Major wars and their outcomes
- Territorial changes
- Important political events

Report only factual history - no speculation or alternate scenarios."""

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
