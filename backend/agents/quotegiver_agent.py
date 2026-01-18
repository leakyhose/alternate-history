"""
Quotegiver Agent - Generates memorable quotes from rulers.

The Quotegiver analyzes the narrative and selects 1-2 most relevant rulers,
then generates brief, memorable quotes as if spoken by those rulers at the
end of the period.
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()


class Quote(BaseModel):
    """A quote from a ruler."""
    tag: str = Field(description="The nation tag of the ruler giving the quote")
    ruler_name: str = Field(description="The name of the ruler")
    ruler_title: str = Field(description="The title of the ruler")
    quote: str = Field(description="A 1-sentence memorable quote in the ruler's voice")


class QuotegiverOutput(BaseModel):
    """Structured output from the Quotegiver agent."""
    quotes: List[Quote] = Field(
        description="1-2 quotes from the most relevant rulers for this period's events",
        min_length=1,
        max_length=2
    )


SYSTEM_PROMPT = """You are a historical quote writer. Given a narrative of events and a list of rulers, 
you select 1-2 rulers whose perspectives are most relevant to the events described, then write 
brief, memorable quotes as if spoken by those rulers.

=== YOUR TASK ===
1. Analyze the narrative to identify the most impactful events
2. Select 1-2 rulers (by their nation tag) whose nations are most affected or involved
3. Write a 1-sentence quote for each selected ruler that captures their perspective

=== QUOTE GUIDELINES ===
- Quotes should feel historically authentic to the era and culture
- Capture the ruler's personality, concerns, or triumph
- Keep each quote to a SINGLE SENTENCE (15-30 words)
- The quote should relate to the events in the narrative
- Use first person ("I", "We") as if the ruler is speaking
- Make quotes memorable, quotable, and dramatic

=== EXAMPLES ===
- "We have shown the world that Rome's legions cannot be stopped by mere walls." - A triumphant conqueror
- "Let them come - we shall meet them as our fathers did, with steel and fire." - A defiant defender
- "In this treaty lies the foundation of a new age of peace." - A diplomatic ruler
- "The gods have abandoned those who abandoned their duty to the Empire." - A vengeful emperor

Return ONLY valid JSON matching the schema. No markdown, no extra text."""


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=30,  # 30 second timeout - this is a quick task
    max_retries=2
)


def format_rulers_for_quote(rulers: Dict[str, Dict[str, Any]], available_tags: Dict[str, Dict[str, Any]]) -> str:
    """Format rulers list for the prompt."""
    if not rulers:
        return "No rulers available."
    
    lines = []
    for tag, info in rulers.items():
        name = info.get("name", "Unknown")
        title = info.get("title", "Ruler")
        age = info.get("age", "unknown")
        dynasty = info.get("dynasty", "")
        
        # Get nation name from tags
        nation_name = available_tags.get(tag, {}).get("name", tag)
        
        dynasty_str = f" of {dynasty}" if dynasty else ""
        lines.append(f"  - {tag} ({nation_name}): {name}{dynasty_str}, {title}, age {age}")
    
    return "\n".join(lines)


def generate_quotes(
    narrative: str,
    territorial_changes_summary: str,
    rulers: Dict[str, Dict[str, Any]],
    available_tags: Dict[str, Dict[str, Any]],
    year_range: str
) -> List[Dict[str, Any]]:
    """
    Generate 1-2 memorable quotes from the most relevant rulers.
    
    Args:
        narrative: The narrative of events from the Dreamer
        territorial_changes_summary: Summary of territorial changes
        rulers: Current rulers by nation tag (at end of period)
        available_tags: Dict of valid nation tags with metadata
        year_range: The year range string (e.g., "117-137 AD")
        
    Returns:
        List of quote dicts with tag, ruler_name, ruler_title, and quote
    """
    if not rulers:
        return []
    
    rulers_context = format_rulers_for_quote(rulers, available_tags)
    
    user_prompt = f"""Generate 1-2 memorable quotes from rulers for this period: {year_range}

=== AVAILABLE RULERS ===
{rulers_context}

=== NARRATIVE OF EVENTS ===
{narrative}

=== TERRITORIAL CHANGES ===
{territorial_changes_summary if territorial_changes_summary else "No significant territorial changes."}

Select 1-2 of the most relevant rulers (those whose nations are most involved in or affected by these events) and write a memorable 1-sentence quote from each one's perspective at the end of this period.

Return JSON only with this format:
{{
  "quotes": [
    {{"tag": "TAG", "ruler_name": "Name", "ruler_title": "Title", "quote": "The quote here."}}
  ]
}}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        response = llm.invoke(messages)
        
        # Get content - handle both string and list responses
        content = response.content
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    text_parts.append(block.get("text", ""))
                else:
                    text_parts.append(str(block))
            content = "\n".join(text_parts)
        content = content.strip() if content else ""
        
        # Clean up response - sometimes LLMs wrap JSON in markdown
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
        
        # Find JSON by looking for opening brace
        if not content.startswith("{"):
            brace_start = content.find("{")
            if brace_start != -1:
                depth = 0
                for i, char in enumerate(content[brace_start:], brace_start):
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            content = content[brace_start:i+1]
                            break
        
        result = json.loads(content)
        quotes = result.get("quotes", [])
        
        # Validate quotes - ensure they reference valid rulers
        valid_quotes = []
        for quote in quotes[:2]:  # Max 2 quotes
            tag = quote.get("tag", "")
            if tag in rulers:
                # Use actual ruler info from state
                ruler = rulers[tag]
                valid_quotes.append({
                    "tag": tag,
                    "ruler_name": ruler.get("name", quote.get("ruler_name", "Unknown")),
                    "ruler_title": ruler.get("title", quote.get("ruler_title", "Ruler")),
                    "quote": quote.get("quote", "")
                })
        
        return valid_quotes if valid_quotes else []
        
    except (json.JSONDecodeError, Exception) as e:
        print(f"Failed to generate quotes: {e}")
        return []
