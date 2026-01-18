from dotenv import load_dotenv
import os
import json

from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

SYSTEM_PROMPT = """
You are a filtering agent for the prompts on an alterante history of the Roman empire. You must determine whether the command satisifes certain rules.
1. Related to Roman history, from the death of Trajan (117 AD) to the fall of Constantinople (1453 AD).
2. Specific enough. "What if Rome never fell" is not specific enough. "What if the empire never split" is, as the year can be pinned down to final split of the empire not happening.
However, where the users intentioned start date can be guessed, allow it. Things like "What if Justinian died early", you can just choose a time where it makes sense for him to havea died.
3. Fantastical, ridiculous or ahistorical things are ALLOWED, as long as the other rules are satisfied. "What if Rome had dragons in 200 AD" is allowed.
If doesnt satisfy the rules, return this {"status": "rejected", "reason": "<SHORT CONCISE REASON HERE>", "alternative":"<USERS PROMPT ALTERED SO THAT IT IS VALID>"}.
If satisfy the rules, return this {"status": "accepted", "year": <SPECIFIC_YEAR_HERE>}
ONLY RETURN JSON. NO OTHER TEXT.
"""

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=os.getenv("GEMINI_API_KEY")
)


def filter_command(command: str) -> dict:
    """
    Filters a command to determine if it's valid.
    Returns {"status": "accepted", "year": int} or {"status": "rejected", "reason": str, "alternative": str}
    """
    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": command}
    ])
    
    # Parse the JSON response
    try:
        result = json.loads(response.content)
        return result
    except json.JSONDecodeError:
        return {"status": "rejected", "reason": "Failed to parse response", "alternative": None}