"""
Filter Agent - Validates user divergences against scenario constraints.

Checks that divergences are relevant to the scenario's nations and time period.
"""
from dotenv import load_dotenv
import os
import json
import re
from typing import Optional, Literal, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()


def build_system_prompt(tags: Dict[str, Dict[str, str]], period_start: int, period_end: int) -> str:
    """Build system prompt based on scenario metadata."""
    tag_names = [info.get("name", tag) for tag, info in tags.items()]
    tag_list = ", ".join(tag_names)

    return f"""You are a filtering agent for alternate history prompts.

VALID NATIONS/ENTITIES: {tag_list}
VALID TIME PERIOD: {period_start} AD to {period_end} AD

Rules:
1. Prompt must relate to at least one valid nation/entity
2. Event must occur within the valid time period
3. Must be specific enough to pin down a year
4. Fantastical/ahistorical events are ALLOWED if rules 1-3 satisfied

If rejected: provide succinct reason (1 sentence) and alternative.
If accepted: return year BEFORE the divergence (e.g., death in 1976 -> return 1975).
The year must be within {period_start} to {period_end}."""


def build_continuation_system_prompt(tags: Dict[str, Dict[str, str]], current_year: int) -> str:
    """Build system prompt for filtering continuation divergences."""
    tag_names = [info.get("name", tag) for tag, info in tags.items()]
    tag_list = ", ".join(tag_names)

    return f"""You are a filtering agent for divergences added to an EXISTING timeline.

VALID NATIONS/ENTITIES: {tag_list}
CURRENT YEAR: {current_year} AD

Rules:
1. Prompt must relate to at least one valid nation/entity
2. Event must occur NOW or in FUTURE (year {current_year}+). Past events rejected.
3. Must be specific enough
4. Fantastical events ALLOWED if rules 1-3 satisfied

If rejected: provide succinct reason and alternative.
If accepted: no year needed (applied to current timeline)."""


class ContinuationFilterOutput(BaseModel):
    """Output from the continuation filter agent."""
    status: Literal["accepted", "rejected"]
    reason: Optional[str] = None
    alternative: Optional[str] = None


class FilterOutput(BaseModel):
    """Output from the filter agent."""
    status: Literal["accepted", "rejected"]
    year: Optional[int] = None
    reason: Optional[str] = None
    alternative: Optional[str] = None


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=30,
    max_retries=2
)

llm_structured = llm.with_structured_output(FilterOutput)


def _parse_json_response(raw: str) -> Optional[dict]:
    """Extract JSON from response, handling markdown code blocks."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try markdown code blocks
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try raw JSON object
    match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def filter_command(command: str, scenario_metadata: Optional[Dict[str, Any]] = None) -> dict:
    """
    Filter a command to determine if it's valid.

    Returns {"status": "accepted", "year": int} or
            {"status": "rejected", "reason": str, "alternative": str}
    """
    if not scenario_metadata or not scenario_metadata.get("period") or not scenario_metadata.get("tags"):
        print(f"[Filter] ERROR: Invalid scenario metadata")
        return {
            "status": "rejected",
            "reason": "Scenario metadata missing tags or period",
            "alternative": "Please select a valid scenario"
        }

    period = scenario_metadata["period"]
    tags = scenario_metadata["tags"]
    system_prompt = build_system_prompt(tags, period.get("start", 2), period.get("end", 2025))

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": command}
    ]

    try:
        result = llm_structured.invoke(messages)
        return result.model_dump(exclude_none=True)
    except Exception as e:
        print(f"Structured output failed for filter: {e}")

    # Fallback to manual parsing
    response = llm.invoke(messages)
    result = _parse_json_response(response.content)

    if result:
        return result

    return {
        "status": "rejected",
        "reason": "Failed to parse response",
        "alternative": None,
        "raw_response": response.content
    }


llm_continuation_structured = llm.with_structured_output(ContinuationFilterOutput)


def filter_continuation_divergence(
    command: str,
    current_year: int,
    scenario_metadata: Optional[Dict[str, Any]] = None
) -> dict:
    """
    Filter a divergence being added to an existing timeline.

    Returns {"status": "accepted"} or
            {"status": "rejected", "reason": str, "alternative": str}
    """
    if not scenario_metadata or not scenario_metadata.get("tags"):
        return {
            "status": "rejected",
            "reason": "Scenario metadata missing",
            "alternative": "Please select a valid scenario"
        }

    tags = scenario_metadata["tags"]
    system_prompt = build_continuation_system_prompt(tags, current_year)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": command}
    ]

    try:
        result = llm_continuation_structured.invoke(messages)
        return result.model_dump(exclude_none=True)
    except Exception as e:
        print(f"Structured output failed for continuation filter: {e}")

    # Fallback
    response = llm.invoke(messages)
    result = _parse_json_response(response.content)

    if result:
        return result

    return {
        "status": "rejected",
        "reason": "Failed to parse response",
        "alternative": None
    }
