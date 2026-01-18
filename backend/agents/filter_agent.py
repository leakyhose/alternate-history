from dotenv import load_dotenv
import os
import json
from typing import Optional, Union, Literal

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()

SYSTEM_PROMPT = """
You are a filtering agent for the prompts on an alterante history of the Roman empire. You must determine whether the command satisifes certain rules.
1. Related to Roman history, from the death of Trajan (117 AD) to the fall of Constantinople (1453 AD).
2. Specific enough. "What if Rome never fell" is not specific enough. "What if the empire never split" is, as the year can be pinned down to final split of the empire not happening.
However, where the users intentioned start date can be guessed, allow it. Things like "What if Justinian died early", you can just choose a time where it makes sense for him to havea died.
3. Fantastical, ridiculous or ahistorical things are ALLOWED, as long as the other rules are satisfied. "What if Rome had dragons in 200 AD" is allowed.
If doesnt satisfy the rules, set status to "rejected" with a reason and alternative.
If satisfies the rules, set status to "accepted" with the specific year minus one. 
"""


class FilterAccepted(BaseModel):
    """Response when divergence is accepted."""
    status: Literal["accepted"] = Field(description="Must be 'accepted'")
    year: int = Field(description="The specific year (AD) when the divergence begins (before the event occurs) minus one")


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
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# Create structured output version
llm_structured = llm.with_structured_output(FilterOutput)


def filter_command(command: str) -> dict:
    """
    Filters a command to determine if it's valid.
    Returns {"status": "accepted", "year": int} or {"status": "rejected", "reason": str, "alternative": str}
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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