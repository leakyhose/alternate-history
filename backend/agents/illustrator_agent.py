"""
Illustrator Agent - Generates pixel art portraits of rulers for quotes.

The Illustrator takes the quotes and rulers from the Quotegiver and generates
low-resolution pixel art headshots of each ruler quoted. These portraits
appear alongside the quotes in the game UI.
"""
from dotenv import load_dotenv
import os
import base64
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
    """
    Generate a detailed prompt for creating a ruler portrait.
    
    Args:
        ruler_name: Name of the ruler (e.g., "Hadrian")
        ruler_title: Title (e.g., "Emperor")
        nation_name: Nation they rule (e.g., "Rome")
        era_context: Time period context (e.g., "117-137 AD")
        quote: The quote they gave (for emotional context)
        
    Returns:
        A detailed image generation prompt
    """
    prompt = f"""Create a pixel art portrait headshot in a retro 16-bit video game style.

Subject: {ruler_name}, {ruler_title} of {nation_name}
Time period: {era_context}

CRITICAL: The clothing and appearance MUST match the actual time period ({era_context}). 
- If the time period is modern (1900s-2000s), show modern formal attire like suits, military uniforms, or contemporary political dress. NO robes, crowns, or ancient regalia.
- If the time period is medieval, show period-appropriate medieval attire.
- If the time period is ancient, show period-appropriate ancient attire.
- Always match the fashion and style to the ACTUAL year, not stereotypes about the nation.

Requirements:
- Square 1:1 aspect ratio portrait
- Pixel art style, low resolution aesthetic (like classic strategy games)
- Head and shoulders only, centered composition
- Rich colors with limited palette (16-32 colors max)
- Dark or neutral background
- Clear pixel grid visible
- Style similar to Civilization or Age of Empires unit portraits
- No text or labels in the image"""

    return prompt


def generate_portraits(
    quotes: List[Dict[str, Any]],
    available_tags: Dict[str, Dict[str, Any]],
    year_range: str
) -> List[Dict[str, Any]]:
    """
    Generate pixel art portraits for each quoted ruler.
    
    Args:
        quotes: List of quote dicts from quotegiver (tag, ruler_name, ruler_title, quote)
        available_tags: Dict of nation tags with metadata (name, color)
        year_range: The year range string (e.g., "117-137 AD")
        
    Returns:
        List of portrait dicts with tag, ruler_name, portrait_base64
    """
    if not quotes:
        return []
    
    portraits = []
    
    # Use Gemini Flash model for image generation via LangChain
    try:
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-image")
    except Exception as e:
        print(f"[Illustrator] WARNING: Failed to initialize Gemini model: {e}")
        return []
    
    for quote_data in quotes[:2]:  # Max 2 portraits
        tag = quote_data.get("tag", "")
        ruler_name = quote_data.get("ruler_name", "Unknown Ruler")
        ruler_title = quote_data.get("ruler_title", "Ruler")
        quote_text = quote_data.get("quote", "")
        
        # Get nation name from tags
        nation_info = available_tags.get(tag, {})
        nation_name = nation_info.get("name", tag if tag else "Unknown Nation")
        
        print(f"[Illustrator] Generating portrait for {ruler_name} of {nation_name}")
        
        # Generate the prompt
        prompt = generate_portrait_prompt(
            ruler_name=ruler_name,
            ruler_title=ruler_title,
            nation_name=nation_name,
            era_context=year_range,
            quote=quote_text
        )
        
        try:
            # Generate the image using Gemini via LangChain
            response: AIMessage = model.invoke(prompt)
            
            # Extract image from response content
            image_base64 = _get_image_base64(response)
            
            if image_base64:
                portraits.append({
                    "tag": tag,
                    "ruler_name": ruler_name,
                    "portrait_base64": image_base64
                })
                print(f"[Illustrator] Done: Portrait for {ruler_name}")
            else:
                print(f"[Illustrator] WARNING: No image data for {ruler_name}")
                
        except Exception as e:
            print(f"[Illustrator] WARNING: Failed for {ruler_name}: {e}")
            # Continue with other portraits even if one fails
            continue
    
    return portraits


def _get_image_base64(response: AIMessage) -> Optional[str]:
    """
    Extract base64 image data from a LangChain AIMessage response.
    
    Args:
        response: AIMessage from ChatGoogleGenerativeAI
        
    Returns:
        Base64 encoded image string, or None if no image found
    """
    image_block = next(
        (
            block
            for block in response.content
            if isinstance(block, dict) and block.get("image_url")
        ),
        None
    )
    
    if image_block:
        # The image_url contains a data URL like "data:image/png;base64,..."
        url = image_block["image_url"].get("url", "")
        if "," in url:
            return url.split(",")[-1]
    
    return None


def enrich_quotes_with_portraits(
    quotes: List[Dict[str, Any]],
    portraits: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge portrait data into quotes.
    
    Args:
        quotes: Original quotes from quotegiver
        portraits: Generated portraits from illustrator
        
    Returns:
        Quotes with portrait_base64 field added where available
    """
    # Build lookup by tag
    portrait_lookup = {p["tag"]: p["portrait_base64"] for p in portraits if p.get("portrait_base64")}
    
    enriched = []
    for quote in quotes:
        enriched_quote = dict(quote)
        tag = quote.get("tag", "")
        if tag in portrait_lookup:
            enriched_quote["portrait_base64"] = portrait_lookup[tag]
        enriched.append(enriched_quote)
    
    return enriched