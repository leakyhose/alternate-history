"""Portrait generation using Gemini."""
import logging
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

from .config import GEMINI_API_KEY, GEMINI_MODEL, MAX_PORTRAITS_PER_EVENT
from .redis_cache import get_cached_portrait, cache_portrait

logger = logging.getLogger(__name__)


def generate_portrait_prompt(
    ruler_name: str,
    ruler_title: str,
    nation_name: str,
    era_context: str,
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


def _extract_image_base64(response: AIMessage) -> Optional[str]:
    """Extract base64 image data from response."""
    if not hasattr(response, "content") or not isinstance(response.content, list):
        return None

    for block in response.content:
        if isinstance(block, dict) and block.get("image_url"):
            url = block["image_url"].get("url", "")
            if "," in url:
                return url.split(",")[-1]
    return None


def _generate_single_portrait(
    model: ChatGoogleGenerativeAI,
    ruler_name: str,
    ruler_title: str,
    nation_name: str,
    era_context: str,
) -> Optional[str]:
    """Generate a single portrait."""
    prompt = generate_portrait_prompt(ruler_name, ruler_title, nation_name, era_context)

    try:
        response: AIMessage = model.invoke(prompt)
        image_base64 = _extract_image_base64(response)

        if image_base64:
            # Cache the result
            cache_portrait(ruler_name, nation_name, era_context, image_base64)
            return image_base64
        else:
            logger.warning(f"No image data for {ruler_name}")
            return None

    except Exception as e:
        logger.error(f"Generation failed for {ruler_name}: {e}")
        return None


def generate_portraits_from_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate portraits for quoted rulers.

    Args:
        event: QuotesReady event with quotes list

    Returns:
        List of portrait dicts with tag, ruler_name, portrait_base64
    """
    quotes = event.get("quotes", [])
    if not quotes:
        logger.info("No quotes to illustrate")
        return []

    # Extract year from the event (quotegiver doesn't include it, so we default)
    # The quotes event doesn't have year_range, so we'll construct from context
    iteration = event.get("iteration", 1)

    # Initialize model
    try:
        model = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY,
        )
    except Exception as e:
        logger.error(f"Failed to initialize model: {e}")
        raise

    portraits = []

    for quote_data in quotes[:MAX_PORTRAITS_PER_EVENT]:
        tag = quote_data.get("tag", "")
        ruler_name = quote_data.get("ruler_name", "Unknown Ruler")
        ruler_title = quote_data.get("ruler_title", "Ruler")

        # Use tag as nation name fallback (quotes don't include full nation info)
        nation_name = tag if tag else "Unknown"

        # Era context - we'll use a generic context since quotes.ready doesn't include year
        # The cache key uses this, so consistency matters
        era_context = f"Iteration {iteration}"

        logger.info(f"Processing portrait: {ruler_name} ({tag})")

        # Check cache first
        cached = get_cached_portrait(ruler_name, nation_name, era_context)
        if cached:
            logger.info(f"Cache hit: {ruler_name}")
            portraits.append({
                "tag": tag,
                "ruler_name": ruler_name,
                "portrait_base64": cached,
            })
            continue

        # Generate new portrait
        logger.info(f"Generating: {ruler_name}")
        portrait_base64 = _generate_single_portrait(
            model, ruler_name, ruler_title, nation_name, era_context
        )

        if portrait_base64:
            portraits.append({
                "tag": tag,
                "ruler_name": ruler_name,
                "portrait_base64": portrait_base64,
            })
            logger.info(f"Generated: {ruler_name}")
        else:
            logger.warning(f"Failed to generate portrait for {ruler_name}")

    logger.info(f"Completed: {len(portraits)}/{len(quotes[:MAX_PORTRAITS_PER_EVENT])} portraits")
    return portraits
