"""
Portrait Cache - Caches and lazily generates ruler portraits.

Instead of blocking the workflow on portrait generation, this module:
1. Returns cached portraits immediately if available
2. Queues new portrait generation in the background
3. Provides an API endpoint to check/retrieve pending portraits
"""
import os
import threading
import hashlib
from typing import Dict, List, Any, Optional
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

# Import LangChain at module level so it's available in threads
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

# Global portrait cache - stores completed portraits
# Key: cache_key (hash of ruler name + nation + era)
# Value: base64-encoded portrait image
_portrait_cache: Dict[str, str] = {}
_cache_lock = threading.Lock()

# Maximum cache size (number of portraits)
MAX_CACHE_SIZE = 100

# Pending portrait requests - currently being generated
# Key: cache_key
# Value: dict with request info
_pending_requests: Dict[str, Dict[str, Any]] = {}
_pending_lock = threading.Lock()

# Background thread pool for portrait generation
_executor: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the background thread pool."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="portrait_gen")
    return _executor


def _make_cache_key(ruler_name: str, nation_name: str, era_context: str) -> str:
    """Create a cache key for a portrait."""
    key_str = f"{ruler_name}|{nation_name}|{era_context}"
    return hashlib.md5(key_str.encode()).hexdigest()[:16]


def get_cached_portrait(ruler_name: str, nation_name: str, era_context: str) -> Optional[str]:
    """
    Get a cached portrait if available.
    
    Args:
        ruler_name: Name of the ruler
        nation_name: Name of the nation
        era_context: Time period (e.g., "650 AD")
        
    Returns:
        Base64-encoded portrait image, or None if not cached
    """
    cache_key = _make_cache_key(ruler_name, nation_name, era_context)
    
    with _cache_lock:
        return _portrait_cache.get(cache_key)


def is_portrait_pending(ruler_name: str, nation_name: str, era_context: str) -> bool:
    """Check if a portrait is currently being generated."""
    cache_key = _make_cache_key(ruler_name, nation_name, era_context)
    
    with _pending_lock:
        return cache_key in _pending_requests


def cache_portrait(ruler_name: str, nation_name: str, era_context: str, portrait_base64: str) -> None:
    """
    Store a portrait in the cache.
    
    Args:
        ruler_name: Name of the ruler
        nation_name: Name of the nation  
        era_context: Time period
        portrait_base64: Base64-encoded portrait image
    """
    cache_key = _make_cache_key(ruler_name, nation_name, era_context)
    
    with _cache_lock:
        # Evict old entries if cache is full (simple LRU by just limiting size)
        if len(_portrait_cache) >= MAX_CACHE_SIZE:
            # Remove oldest entry (first key in dict)
            oldest_key = next(iter(_portrait_cache))
            del _portrait_cache[oldest_key]
        
        _portrait_cache[cache_key] = portrait_base64


def _generate_portrait_background(
    cache_key: str,
    ruler_name: str,
    ruler_title: str,
    nation_name: str,
    era_context: str,
    quote_text: str
) -> None:
    """Background task to generate a portrait and cache it."""
    try:
        print(f"[Portrait] Generating: {ruler_name} of {nation_name}")
        
        # Get API key from environment (should already be loaded by main process)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print(f"[Portrait] ERROR: No GEMINI_API_KEY found")
            return
        
        # Initialize model (using module-level import)
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-image",
            google_api_key=api_key
        )
        
        # Generate prompt inline (avoid importing from illustrator_agent)
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
        
        # Generate image
        response: AIMessage = model.invoke(prompt)
        
        # Extract image from response
        image_base64 = None
        if hasattr(response, 'content') and isinstance(response.content, list):
            for block in response.content:
                if isinstance(block, dict) and block.get("image_url"):
                    url = block["image_url"].get("url", "")
                    if "," in url:
                        image_base64 = url.split(",")[-1]
                        break
        
        if image_base64:
            # Cache the result
            cache_portrait(ruler_name, nation_name, era_context, image_base64)
            print(f"[Portrait] Cached: {ruler_name}")
        else:
            print(f"[Portrait] WARNING: No image data for {ruler_name}")
            
    except Exception as e:
        import traceback
        print(f"[Portrait] ERROR: Failed for {ruler_name}: {e}")
        traceback.print_exc()
    finally:
        # Remove from pending
        with _pending_lock:
            _pending_requests.pop(cache_key, None)


def request_portrait_async(
    ruler_name: str,
    ruler_title: str,
    nation_name: str,
    era_context: str,
    quote_text: str = ""
) -> Optional[str]:
    """
    Request a portrait - returns cached version or starts background generation.
    
    Args:
        ruler_name: Name of the ruler
        ruler_title: Title of the ruler
        nation_name: Name of the nation
        era_context: Time period
        quote_text: The quote (for emotional context)
        
    Returns:
        Base64-encoded portrait if cached, None if generation started
    """
    cache_key = _make_cache_key(ruler_name, nation_name, era_context)
    
    # Check cache first
    cached = get_cached_portrait(ruler_name, nation_name, era_context)
    if cached:
        return cached
    
    # Check if already pending
    with _pending_lock:
        if cache_key in _pending_requests:
            return None  # Already being generated
        
        # Mark as pending
        _pending_requests[cache_key] = {
            "ruler_name": ruler_name,
            "nation_name": nation_name,
            "era_context": era_context
        }
    
    # Submit background generation task
    executor = _get_executor()
    executor.submit(
        _generate_portrait_background,
        cache_key,
        ruler_name,
        ruler_title,
        nation_name,
        era_context,
        quote_text
    )
    
    return None


def get_all_cached_portraits() -> Dict[str, str]:
    """Get all cached portraits (for debugging/API)."""
    with _cache_lock:
        return dict(_portrait_cache)


def get_pending_count() -> int:
    """Get number of portraits currently being generated."""
    with _pending_lock:
        return len(_pending_requests)


def clear_cache() -> None:
    """Clear the portrait cache (for testing)."""
    global _portrait_cache
    with _cache_lock:
        _portrait_cache = {}


def wait_for_pending_portraits(timeout_seconds: float = 15.0, poll_interval: float = 0.5) -> bool:
    """
    Wait for all pending portrait generation to complete.
    
    Args:
        timeout_seconds: Maximum time to wait (default 15s)
        poll_interval: How often to check (default 0.5s)
        
    Returns:
        True if all portraits completed, False if timed out
    """
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        with _pending_lock:
            if len(_pending_requests) == 0:
                return True
        time.sleep(poll_interval)
    
    # Timed out
    with _pending_lock:
        remaining = len(_pending_requests)
        if remaining > 0:
            print(f"[Portrait] WARNING: Wait timed out, {remaining} still pending")
    return False
