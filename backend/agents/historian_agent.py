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

load_dotenv()

SYSTEM_PROMPT = """You are a historian specializing in the Roman/Byzantine Empire (117-1453).
Your job is to provide REAL historical context for a specific time period.

You will be given:
- A start year
- Years to progress (how long the period covers)
- Current rulers and their info. All information should concern the states these rulers rule.

Your response must include:
1. "period": The year range as a string (e.g., "630-650")
2. "real_events": Key events that actually happened in this period in real history
3. "keep_in_mind": General trends of this era. Dont get into specifics or not events here. This part should be short.
4. "conditional_events": Things that happened with their triggers. These events MUST have actually happened as their triggers happened, should include the biggest events/trends of this era. 

Important guidelines:
- Include succession crises, wars, invasions, major political changes
- Note any "fragile" historical moments
- Be specific with dates when known

ONLY RETURN VALID JSON. No markdown, no extra text.

Example output:
{
  "period": "630-650",
  "real_events": [
    "634: Arab invasions begin after Byzantine-Sassanid exhaustion",
    "636: Battle of Yarmouk - Byzantines lose Syria",
    "641: Heraclius dies, succession crisis begins",
    "642: Arabs conquer Egypt"
  ],
  "keep_in_mind": [
    "Byzantium and Persia should be exhausted from decades of war",
    "Religious tensions in eastern provinces",
    "Arab armies are highly mobile and motivated by religious zeal",
    "Byzantine navy is the key to defending Constantinople"
  ],
  "conditional_events": [
    {
      "condition": "Empire exhausted from Persian wars",
      "outcome": "Arab conquests proceed rapidly through weakened eastern defenses"
    },
    {
      "condition": "Heraclius dies before securing succession",
      "outcome": "Civil war between Constantine III and Heraclonas, further weakening defense"
    },
  ]
}
"""

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY")
)


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

    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ])
    
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
            "real_events": [],
            "keep_in_mind": ["Failed to parse historian response"],
            "conditional_events": []
        }