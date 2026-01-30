"""Portrait generation using Gemini."""
import logging
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

from .config import GEMINI_API_KEY, GEMINI_MODEL, MAX_PORTRAITS_PER_EVENT
from .redis_cache import get_cached_portrait, cache_portrait, store_portrait_for_event

logger = logging.getLogger(__name__)


def generate_portrait_prompt(
    ruler_name: str,
    ruler_title: str,
    nation_name: str,
    era_context: str,
) -> str:
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
    prompt = generate_portrait_prompt(ruler_name, ruler_title, nation_name, era_context)

    try:
        response: AIMessage = model.invoke(prompt)
        image_base64 = _extract_image_base64(response)

        if image_base64:
            cache_portrait(ruler_name, nation_name, era_context, image_base64)
            return image_base64
        else:
            logger.warning(f"No image data for {ruler_name}")
            return None

    except Exception as e:
        logger.error(f"Generation failed for {ruler_name}: {e}")
        return None


def generate_portraits_from_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate portraits for quoted rulers, returning Redis keys."""
    quotes = event.get("quotes", [])
    game_id = event.get("game_id", "unknown")
    iteration = event.get("iteration", 1)

    if not quotes:
        logger.info("No quotes to illustrate")
        return []

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

        nation_name = tag if tag else "Unknown"
        era_context = f"Iteration {iteration}"

        logger.info(f"Processing portrait: {ruler_name} ({tag})")

        cached = get_cached_portrait(ruler_name, nation_name, era_context)
        if cached:
            logger.info(f"Cache hit: {ruler_name}")
            portrait_key = store_portrait_for_event(game_id, iteration, ruler_name, cached)
            portraits.append({
                "tag": tag,
                "ruler_name": ruler_name,
                "portrait_key": portrait_key,
            })
            continue

        logger.info(f"Generating: {ruler_name}")
        portrait_base64 = _generate_single_portrait(
            model, ruler_name, ruler_title, nation_name, era_context
        )

        if portrait_base64:
            portrait_key = store_portrait_for_event(game_id, iteration, ruler_name, portrait_base64)
            portraits.append({
                "tag": tag,
                "ruler_name": ruler_name,
                "portrait_key": portrait_key,
            })
            logger.info(f"Generated: {ruler_name} (key: {portrait_key})")
        else:
            logger.warning(f"Failed to generate portrait for {ruler_name}")

    logger.info(f"Completed: {len(portraits)}/{len(quotes[:MAX_PORTRAITS_PER_EVENT])} portraits")
    return portraits
