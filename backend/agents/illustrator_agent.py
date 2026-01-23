"""
Illustrator Agent - Generates pixel art portraits of rulers for quotes.

Creates low-resolution pixel art headshots of each quoted ruler.
"""
from dotenv import load_dotenv
import os
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

load_dotenv()


def generate_portrait_prompt(
    ruler_name: str,
    ruler_title: str,
    nation_name: str,
    era_context: str,
    quote: str
) -> str:
    """Generate a prompt for creating a ruler portrait."""
    return f"""Create a pixel art portrait headshot in a retro 16-bit video game style.

Subject: {ruler_name}, {ruler_title} of {nation_name}
Time period: {era_context}

CRITICAL: Clothing and appearance MUST match the time period ({era_context}).
- Modern (1900s-2000s): suits, military uniforms, contemporary dress. NO robes/crowns.
- Medieval: period-appropriate medieval attire.
- Ancient: period-appropriate ancient attire.

Requirements:
- Square 1:1 aspect ratio portrait
- Pixel art style, low resolution aesthetic
- Head and shoulders only, centered
- Rich colors with limited palette (16-32 colors)
- Dark or neutral background
- Clear pixel grid visible
- Style similar to Civilization or Age of Empires portraits
- No text or labels"""


def generate_portraits(
    quotes: List[Dict[str, Any]],
    available_tags: Dict[str, Dict[str, Any]],
    year_range: str
) -> List[Dict[str, Any]]:
    """Generate pixel art portraits for each quoted ruler."""
    if not quotes:
        return []

    try:
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-image")
    except Exception as e:
        print(f"[Illustrator] Failed to initialize model: {e}")
        return []

    portraits = []
    for quote_data in quotes[:2]:
        tag = quote_data.get("tag", "")
        ruler_name = quote_data.get("ruler_name", "Unknown Ruler")
        ruler_title = quote_data.get("ruler_title", "Ruler")
        quote_text = quote_data.get("quote", "")

        nation_info = available_tags.get(tag, {})
        nation_name = nation_info.get("name", tag or "Unknown Nation")

        print(f"[Illustrator] Generating portrait for {ruler_name} of {nation_name}")

        prompt = generate_portrait_prompt(
            ruler_name=ruler_name,
            ruler_title=ruler_title,
            nation_name=nation_name,
            era_context=year_range,
            quote=quote_text
        )

        try:
            response: AIMessage = model.invoke(prompt)
            image_base64 = _get_image_base64(response)

            if image_base64:
                portraits.append({
                    "tag": tag,
                    "ruler_name": ruler_name,
                    "portrait_base64": image_base64
                })
                print(f"[Illustrator] Done: Portrait for {ruler_name}")
            else:
                print(f"[Illustrator] No image data for {ruler_name}")

        except Exception as e:
            print(f"[Illustrator] Failed for {ruler_name}: {e}")
            continue

    return portraits


def _get_image_base64(response: AIMessage) -> Optional[str]:
    """Extract base64 image data from a LangChain AIMessage response."""
    image_block = next(
        (b for b in response.content if isinstance(b, dict) and b.get("image_url")),
        None
    )

    if image_block:
        url = image_block["image_url"].get("url", "")
        if "," in url:
            return url.split(",")[-1]
    return None


def enrich_quotes_with_portraits(
    quotes: List[Dict[str, Any]],
    portraits: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge portrait data into quotes."""
    portrait_lookup = {p["tag"]: p["portrait_base64"] for p in portraits if p.get("portrait_base64")}

    enriched = []
    for quote in quotes:
        eq = dict(quote)
        tag = quote.get("tag", "")
        if tag in portrait_lookup:
            eq["portrait_base64"] = portrait_lookup[tag]
        enriched.append(eq)

    return enriched
