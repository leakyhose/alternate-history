from dotenv import load_dotenv
import os
import json
from typing import Optional, Union, Literal, Dict, Any, List

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()

def build_system_prompt(tags: Dict[str, Dict[str, str]], period_start: int, period_end: int) -> str:
    """Build a dynamic system prompt based on scenario metadata."""
    # Build list of nations/entities from tags
    tag_names = [info.get("name", tag) for tag, info in tags.items()]
    tag_list = ", ".join(tag_names)
    
    return f"""
You are a filtering agent for alternate history prompts. You must determine whether the command satisfies certain rules.

VALID NATIONS/ENTITIES for this scenario: {tag_list}
VALID TIME PERIOD: {period_start} AD to {period_end} AD

Rules:  
1. The prompt must be related to AT LEAST ONE of the valid nations/entities listed above.
2. The event must occur within the valid time period ({period_start} AD to {period_end} AD).
3. Specific enough. Vague prompts like "What if things were different" are not specific enough. The divergence should be specific enough that a year can be pinned down.
   However, where the user's intended start date can be guessed, allow it. Things like "What if X died early", you can just choose a time where it makes sense.
4. Fantastical, ridiculous or ahistorical things are ALLOWED, as long as the other rules are satisfied.

If doesn't satisfy the rules, set status to "rejected" with a SUCCINCT reason (1 sentence max) and an alternative.

If satisfies the rules, set status to "accepted" with the year set to THE YEAR BEFORE the divergence event.
CRITICAL: The year must be BEFORE the event happens, so the alternate history can diverge from that point.
- If someone dies in 1976, return year 1975 (the year BEFORE they die)
- If someone is born in 1900, return year 1899 (the year BEFORE they are born)  
- If an event happens in 2001, return year 2000 (the year BEFORE the event)
The person or situation mentioned in the divergence MUST still exist/be alive at the returned year.
The year MUST be within the period {period_start} to {period_end}.
"""


def build_continuation_system_prompt(tags: Dict[str, Dict[str, str]], current_year: int) -> str:
    """Build a system prompt for filtering continuation divergences (events that must happen NOW or in the FUTURE)."""
    tag_names = [info.get("name", tag) for tag, info in tags.items()]
    tag_list = ", ".join(tag_names)
    
    return f"""
You are a filtering agent for alternate history divergences being added to an EXISTING alternate timeline.

VALID NATIONS/ENTITIES for this scenario: {tag_list}
CURRENT YEAR in the alternate timeline: {current_year} AD

The user wants to add a new "what if" event to their alternate timeline which is currently at year {current_year}.

Rules:
1. The prompt must be related to AT LEAST ONE of the valid nations/entities listed above.
2. The event must occur NOW or in the FUTURE (year {current_year} AD or later). Events in the past are NOT allowed since we're adding to an existing timeline.
   - If someone mentions a historical event that already happened (before {current_year}), reject it.
   - If the divergence could reasonably happen starting from {current_year}, accept it.
3. Specific enough. Vague prompts like "What if things were different" are not specific enough.
4. Fantastical, ridiculous or ahistorical things are ALLOWED, as long as they apply to the current or future time.

If doesn't satisfy the rules, set status to "rejected" with a SUCCINCT reason (1 sentence max) and an alternative.

If satisfies the rules, set status to "accepted". No year field is needed - the divergence will be applied to the current timeline year.
"""


class ContinuationFilterOutput(BaseModel):
    """Output from the continuation filter agent."""
    status: Literal["accepted", "rejected"] = Field(description="Whether the divergence is accepted or rejected")
    reason: Optional[str] = Field(default=None, description="Reason for rejection")
    alternative: Optional[str] = Field(default=None, description="Alternative suggestion for rejected prompts")


class FilterAccepted(BaseModel):
    """Response when divergence is accepted."""
    status: Literal["accepted"] = Field(description="Must be 'accepted'")
    year: int = Field(description="The year BEFORE the divergence event occurs. If someone dies in 976, return 975.")


class FilterRejected(BaseModel):
    """Response when divergence is rejected."""
    status: Literal["rejected"] = Field(description="Must be 'rejected'")
    reason: str = Field(description="Very short, succinct reason for rejection (1 sentence max)")
    alternative: str = Field(description="User's prompt altered to be valid")


class FilterOutput(BaseModel):
    """Output from the filter agent."""
    status: Literal["accepted", "rejected"] = Field(description="Whether the divergence is accepted or rejected")
    year: Optional[int] = Field(default=None, description="The year (AD) for accepted divergences")
    reason: Optional[str] = Field(default=None, description="Reason for rejection")
    alternative: Optional[str] = Field(default=None, description="Alternative suggestion for rejected prompts")


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=30,  # 30 second timeout for filter
    max_retries=2
)

# Create structured output version
llm_structured = llm.with_structured_output(FilterOutput)


def filter_command(command: str, scenario_metadata: Optional[Dict[str, Any]] = None) -> dict:
    """
    Filters a command to determine if it's valid.
    Returns {"status": "accepted", "year": int} or {"status": "rejected", "reason": str, "alternative": str}
    
    Args:
        command: The divergence/what-if scenario command
        scenario_metadata: Optional scenario metadata with 'tags' and 'period' fields
    """
    # Build system prompt based on scenario metadata
    if scenario_metadata and scenario_metadata.get("period") and scenario_metadata.get("tags"):
        period = scenario_metadata["period"]
        tags = scenario_metadata["tags"]
        system_prompt = build_system_prompt(
            tags=tags,
            period_start=period.get("start", 2),
            period_end=period.get("end", 2025)
        )
        tag_names = [info.get("name", tag) for tag, info in tags.items()]
        print(f"✅ Using dynamic prompt for tags: {tag_names}, period: {period}")
    else:
        # Reject if no valid metadata - scenarios must have tags and period defined
        print(f"❌ No valid scenario metadata. Metadata received: {scenario_metadata}")
        return {
            "status": "rejected",
            "reason": "Scenario metadata missing tags or period",
            "alternative": "Please select a valid scenario"
        }
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": command}
    ]
    
    # Try structured output first
    try:
        result = llm_structured.invoke(messages)
        return result.model_dump(exclude_none=True)
    except Exception as e:
        print(f"Structured output failed for filter: {e}")
        print("Falling back to JSON parsing...")
    
    # Fallback to manual parsing
    response = llm.invoke(messages)
    raw_content = response.content
    
    try:
        # Try direct parse first
        result = json.loads(raw_content)
        return result
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return result
            except json.JSONDecodeError:
                pass
        
        # Try to find raw JSON object
        json_match = re.search(r'\{[^{}]*\}', raw_content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                return result
            except json.JSONDecodeError:
                pass
        
        return {
            "status": "rejected", 
            "reason": "Failed to parse response", 
            "alternative": None,
            "raw_response": raw_content
        }


# Create structured output for continuation filter
llm_continuation_structured = llm.with_structured_output(ContinuationFilterOutput)


def filter_continuation_divergence(command: str, current_year: int, scenario_metadata: Optional[Dict[str, Any]] = None) -> dict:
    """
    Filters a divergence being added to an existing alternate timeline.
    Ensures the divergence is relevant to the current era (not the past).
    
    Returns {"status": "accepted"} or {"status": "rejected", "reason": str, "alternative": str}
    
    Args:
        command: The divergence/what-if scenario command
        current_year: The current year in the alternate timeline
        scenario_metadata: Optional scenario metadata with 'tags' field
    """
    if not scenario_metadata or not scenario_metadata.get("tags"):
        return {
            "status": "rejected",
            "reason": "Scenario metadata missing",
            "alternative": "Please select a valid scenario"
        }
    
    tags = scenario_metadata["tags"]
    system_prompt = build_continuation_system_prompt(tags, current_year)
    tag_names = [info.get("name", tag) for tag, info in tags.items()]
    print(f"✅ Using continuation filter for tags: {tag_names}, current year: {current_year}")
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": command}
    ]
    
    # Try structured output first
    try:
        result = llm_continuation_structured.invoke(messages)
        return result.model_dump(exclude_none=True)
    except Exception as e:
        print(f"Structured output failed for continuation filter: {e}")
        print("Falling back to JSON parsing...")
    
    # Fallback to manual parsing
    response = llm.invoke(messages)
    raw_content = response.content
    
    try:
        result = json.loads(raw_content)
        return result
    except json.JSONDecodeError:
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return result
            except json.JSONDecodeError:
                pass
        
        json_match = re.search(r'\{[^{}]*\}', raw_content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                return result
            except json.JSONDecodeError:
                pass
        
        return {
            "status": "rejected", 
            "reason": "Failed to parse response", 
            "alternative": None
        }