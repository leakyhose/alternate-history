"""
Quotegiver Agent - Generates memorable quotes from rulers.

Analyzes the narrative and selects 1-2 relevant rulers, then generates
brief, memorable quotes from their perspective.
"""
from dotenv import load_dotenv
import os
import json
from typing import Dict, List, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()


class Quote(BaseModel):
    """A quote from a ruler."""
    tag: str = Field(description="Nation tag of the ruler")
    ruler_name: str = Field(description="Name of the ruler")
    ruler_title: str = Field(description="Title of the ruler")
    quote: str = Field(description="1-sentence memorable quote")


class QuotegiverOutput(BaseModel):
    """Structured output from the Quotegiver agent."""
    quotes: List[Quote] = Field(description="1-2 quotes from relevant rulers", min_length=1, max_length=2)


SYSTEM_PROMPT = """You are a historical quote writer. Given a narrative and rulers list,
select 1-2 rulers whose nations are most affected, then write memorable quotes.

GUIDELINES:
- Quotes should feel historically authentic to the era and culture
- Keep each quote to a SINGLE SENTENCE (15-30 words)
- Use first person ("I", "We")
- Make quotes memorable and dramatic

EXAMPLES:
- "We have shown the world that Rome's legions cannot be stopped by mere walls."
- "Let them come - we shall meet them as our fathers did, with steel and fire."
- "In this treaty lies the foundation of a new age of peace."

Return ONLY valid JSON matching the schema."""


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=30,
    max_retries=2
)


def format_rulers_for_quote(rulers: Dict[str, Dict[str, Any]], available_tags: Dict[str, Dict[str, Any]]) -> str:
    """Format rulers list for the prompt."""
    if not rulers:
        return "No rulers available."

    lines = []
    for tag, info in rulers.items():
        nation = available_tags.get(tag, {}).get("name", tag)
        dynasty = f" of {info.get('dynasty')}" if info.get("dynasty") else ""
        lines.append(f"  - {tag} ({nation}): {info.get('name', '?')}{dynasty}, {info.get('title', '?')}, age {info.get('age', '?')}")
    return "\n".join(lines)


def generate_quotes(
    narrative: str,
    territorial_changes_summary: str,
    rulers: Dict[str, Dict[str, Any]],
    available_tags: Dict[str, Dict[str, Any]],
    year_range: str
) -> List[Dict[str, Any]]:
    """Generate 1-2 memorable quotes from the most relevant rulers."""
    if not rulers:
        return []

    rulers_ctx = format_rulers_for_quote(rulers, available_tags)
    territorial = territorial_changes_summary or "No significant territorial changes."

    user_prompt = f"""Generate 1-2 memorable quotes from rulers for: {year_range}

=== AVAILABLE RULERS ===
{rulers_ctx}

=== NARRATIVE ===
{narrative}

=== TERRITORIAL CHANGES ===
{territorial}

Select 1-2 relevant rulers and write a 1-sentence quote from each.

Return JSON: {{"quotes": [{{"tag": "TAG", "ruler_name": "Name", "ruler_title": "Title", "quote": "The quote."}}]}}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = llm.invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
        content = (content or "").strip()

        # Extract JSON from markdown
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
        quotes = result.get("quotes", [])

        # Validate and enrich quotes with actual ruler info
        valid = []
        for q in quotes[:2]:
            tag = q.get("tag", "")
            if tag in rulers:
                ruler = rulers[tag]
                valid.append({
                    "tag": tag,
                    "ruler_name": ruler.get("name", q.get("ruler_name", "Unknown")),
                    "ruler_title": ruler.get("title", q.get("ruler_title", "Ruler")),
                    "quote": q.get("quote", "")
                })
        return valid

    except Exception as e:
        print(f"Failed to generate quotes: {e}")
        return []
