from dotenv import load_dotenv
import os
import json
from typing import Optional, Union, Literal, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()

def build_system_prompt(scenario_name: str, period_start: int, period_end: int) -> str:
    """Build a dynamic system prompt based on scenario metadata."""
    return f"""
You are a filtering agent for the prompts on an alternate history scenario: "{scenario_name}". You must determine whether the command satisfies certain rules.
1. Related to {scenario_name}, from year {period_start} AD to year {period_end} AD.
2. Specific enough. Vague prompts like "What if things were different" are not specific enough. The divergence should be specific enough that a year can be pinned down.
However, where the user's intended start date can be guessed, allow it. Things like "What if X died early", you can just choose a time where it makes sense.
3. Fantastical, ridiculous or ahistorical things are ALLOWED, as long as the other rules are satisfied. "What if they had dragons" is allowed.

If doesn't satisfy the rules, set status to "rejected" with a reason and alternative.

If satisfies the rules, set status to "accepted" with the year set to THE YEAR BEFORE the divergence event.
CRITICAL: The year must be BEFORE the event happens, so the alternate history can diverge from that point.
- If someone dies in 976 AD, return year 975 (the year BEFORE they die)
- If someone is born in 500 AD, return year 499 (the year BEFORE they are born)  
- If an event happens in 630 AD, return year 629 (the year BEFORE the event)
The person or situation mentioned in the divergence MUST still exist/be alive at the returned year.
The year MUST be within the period {period_start} AD to {period_end} AD.
"""


# Default system prompt for backwards compatibility
DEFAULT_SYSTEM_PROMPT = """
You are a filtering agent for the prompts on an alternate history of the Roman empire. You must determine whether the command satisfies certain rules.
1. Related to Roman history, from the death of Trajan (117 AD) to the fall of Constantinople (1453 AD).
2. Specific enough. "What if Rome never fell" is not specific enough. "What if the empire never split" is, as the year can be pinned down to final split of the empire not happening.
However, where the users intentioned start date can be guessed, allow it. Things like "What if Justinian died early", you can just choose a time where it makes sense for him to have died.
3. Fantastical, ridiculous or ahistorical things are ALLOWED, as long as the other rules are satisfied. "What if Rome had dragons in 200 AD" is allowed.

If doesnt satisfy the rules, set status to "rejected" with a reason and alternative.

If satisfies the rules, set status to "accepted" with the year set to THE YEAR BEFORE the divergence event.
CRITICAL: The year must be BEFORE the event happens, so the alternate history can diverge from that point.
- If someone dies in 976 AD, return year 975 (the year BEFORE they die)
- If someone is born in 500 AD, return year 499 (the year BEFORE they are born)  
- If an event happens in 630 AD, return year 629 (the year BEFORE the event)
The person or situation mentioned in the divergence MUST still exist/be alive at the returned year.
"""


class FilterAccepted(BaseModel):
    """Response when divergence is accepted."""
    status: Literal["accepted"] = Field(description="Must be 'accepted'")
    year: int = Field(description="The year BEFORE the divergence event occurs. If someone dies in 976, return 975.")


class FilterRejected(BaseModel):
    """Response when divergence is rejected."""
    status: Literal["rejected"] = Field(description="Must be 'rejected'")
    reason: str = Field(description="Short, concise reason for rejection")
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
        scenario_metadata: Optional scenario metadata with 'name' and 'period' fields
    """
    # Build system prompt based on scenario metadata
    if scenario_metadata and scenario_metadata.get("period") and scenario_metadata.get("name"):
        period = scenario_metadata["period"]
        system_prompt = build_system_prompt(
            scenario_name=scenario_metadata["name"],
            period_start=period.get("start", 2),
            period_end=period.get("end", 1453)
        )
    else:
        system_prompt = DEFAULT_SYSTEM_PROMPT
    
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