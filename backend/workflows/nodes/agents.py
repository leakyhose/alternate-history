"""Agent nodes for the alternate history workflow."""
import concurrent.futures
from workflows.state import WorkflowState
from agents.historian_agent import get_historical_context
from agents.dreamer_agent import make_decision
from agents.geographer_agent import interpret_territorial_changes
from agents.quotegiver_agent import generate_quotes
from agents.illustrator_agent import generate_portraits, enrich_quotes_with_portraits
from util.scenario import get_scenario_tags
from workflows.nodes.memory import get_province_memory

def historian_node(state: WorkflowState) -> dict:
    """
    Historian Agent: Provide real historical context for the period.
    
    The Historian does NOT see current alternate state - only provides
    the baseline of what ACTUALLY happened in real history.
    """
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")
    
    # Get nation tags for the scenario
    tags = get_scenario_tags(scenario_id)
    
    print(f"[Historian] {current_year}-{current_year + years_to_progress} AD")
    
    try:
        historian_output = get_historical_context(
            start_year=current_year,
            years_to_progress=years_to_progress,
            tags=tags
        )
        
        events_count = len(historian_output.get("conditional_events", []))
        print(f"[Historian] Done: {events_count} conditional events")
        
        return {
            "historian_output": historian_output
        }
    except Exception as e:
        print(f"[Historian] ERROR: {e}")
        return {
            "historian_output": {
                "period": f"{current_year}-{current_year + years_to_progress}",
                "conditional_events": []
            },
            "error": str(e),
            "error_node": "historian"
        }


def dreamer_node(state: WorkflowState) -> dict:
    """
    Dreamer Agent: Make creative decisions based on divergences.
    
    Synthesizes divergences + historian context to decide what actually happens.
    Only allows nation tags defined in the scenario metadata.
    """
    historian_output = state.get("historian_output", {})
    divergences = state.get("divergences", [])
    condensed_logs = state.get("condensed_logs", "")
    logs = state.get("logs", [])
    rulers = state.get("rulers", {})
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")
    
    print(f"[Dreamer] {current_year}-{current_year + years_to_progress} AD")
    
    # Get available nation tags from scenario metadata
    available_tags = get_scenario_tags(scenario_id)
    
    try:
        dreamer_output = make_decision(
            historian_output=historian_output,
            divergences=divergences,
            condensed_logs=condensed_logs,
            recent_logs=logs,
            rulers=rulers,
            current_year=current_year,
            years_to_progress=years_to_progress,
            available_tags=available_tags
        )
        
        merged = dreamer_output.get('merged', False)
        div_count = len(dreamer_output.get("updated_divergences", []))
        print(f"[Dreamer] Done: {div_count} divergences, merged={merged}")
        
        return {
            "dreamer_output": dreamer_output
        }
    except Exception as e:
        print(f"[Dreamer] ERROR: {e}")
        return {
            "dreamer_output": {
                "rulers": rulers,
                "narrative": f"[Error in Dreamer agent: {str(e)}]",
                "territorial_changes": [],
                "territorial_changes_summary": "",
                "updated_divergences": divergences,
                "merged": False
            },
            "error": str(e),
            "error_node": "dreamer"
        }


def geographer_node(state: WorkflowState) -> dict:
    """
    Geographer Agent: Translate territorial descriptions to province updates.
    
    The Geographer uses ACTION TOOLS to directly apply territorial changes:
    - transfer_areas: Move areas between nations
    - transfer_provinces: Move specific provinces (rare)
    - annex_nation: Transfer all territory from one nation to another
    - untrack_areas/provinces: Mark territory as lost to untracked nations
    
    The agent processes changes one-by-one, calling tools as needed, then
    returns the accumulated province updates.
    """
    dreamer_output = state.get("dreamer_output", {})
    territorial_changes = dreamer_output.get("territorial_changes", [])
    scenario_id = state.get("scenario_id", "rome")
    
    print(f"[Geographer] Processing territorial changes")
    
    # Get current province state for context
    memory = get_province_memory()
    current_provinces = memory.get_all_provinces_as_dicts()
    
    try:
        geographer_output = interpret_territorial_changes(
            territorial_changes=territorial_changes,
            scenario_id=scenario_id,
            current_provinces=current_provinces
        )
        
        province_updates = geographer_output.get("province_updates", [])
        print(f"[Geographer] Done: {len(province_updates)} province updates")
        
        return {
            "territorial_changes": province_updates
        }
    except Exception as e:
        print(f"[Geographer] ERROR: {e}")
        return {
            "territorial_changes": [],
            "error": str(e),
            "error_node": "geographer"
        }


def quotegiver_node(state: WorkflowState) -> dict:
    """
    Quotegiver Agent: Generate memorable quotes from relevant rulers.
    
    Analyzes the narrative and territorial changes, selects 1-2 most relevant
    rulers, and generates quotes from their perspective.
    
    IMPORTANT: Uses rulers from dreamer_output (AFTER the time period), not
    the state's rulers (which are from BEFORE the time period).
    """
    dreamer_output = state.get("dreamer_output", {})
    # Use rulers from dreamer output - these are the rulers AFTER the time period
    # (with updated ages, successors for deceased rulers, etc.)
    rulers = dreamer_output.get("rulers", state.get("rulers", {}))
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")
    
    year_range = f"{current_year}-{current_year + years_to_progress} AD"
    
    print(f"[Quotegiver] Generating quotes for {year_range}")
    
    # Get available nation tags from scenario metadata
    available_tags = get_scenario_tags(scenario_id)
    
    narrative = dreamer_output.get("narrative", "")
    territorial_summary = dreamer_output.get("territorial_changes_summary", "")
    
    try:
        quotes = generate_quotes(
            narrative=narrative,
            territorial_changes_summary=territorial_summary,
            rulers=rulers,
            available_tags=available_tags,
            year_range=year_range
        )
        
        print(f"[Quotegiver] Done: {len(quotes)} quotes generated")
        
        return {
            "quotegiver_output": {
                "quotes": quotes
            }
        }
    except Exception as e:
        print(f"[Quotegiver] ERROR: {e}")
        return {
            "quotegiver_output": {
                "quotes": []
            },
            "error": str(e),
            "error_node": "quotegiver"
        }


def illustrator_node(state: WorkflowState) -> dict:
    """
    Illustrator Agent: Portrait generation with caching and waiting.
    
    Flow:
    1. Check cache for existing portraits
    2. Queue uncached portraits for background generation
    3. WAIT for pending portraits to complete (with timeout)
    4. Re-check cache and attach portraits to quotes
    
    This ensures portraits are available when quotes are sent to frontend.
    """
    from util.portrait_cache import (
        request_portrait_async, get_pending_count, 
        wait_for_pending_portraits, get_cached_portrait
    )
    
    quotegiver_output = state.get("quotegiver_output", {})
    quotes = quotegiver_output.get("quotes", [])
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")
    
    # Use end year for portraits since rulers are from AFTER the time period
    end_year = current_year + years_to_progress
    year_range = f"{end_year} AD"
    
    print(f"[Illustrator] Generating portraits for {end_year} AD")
    
    if not quotes:
        print("[Illustrator] No quotes to illustrate")
        return {
            "illustrator_output": {
                "portraits": [],
                "enriched_quotes": []
            }
        }
    
    # Get available nation tags from scenario metadata
    available_tags = get_scenario_tags(scenario_id)
    
    # First pass: check cache and queue any missing portraits
    quote_metadata = []  # Store (quote_data, ruler_name, nation_name, year_range)
    
    for quote_data in quotes[:2]:  # Max 2 quotes/portraits
        tag = quote_data.get("tag", "")
        ruler_name = quote_data.get("ruler_name", "Unknown Ruler")
        ruler_title = quote_data.get("ruler_title", "Ruler")
        quote_text = quote_data.get("quote", "")
        
        # Get nation name from tags
        nation_info = available_tags.get(tag, {})
        nation_name = nation_info.get("name", tag if tag else "Unknown Nation")
        
        # Try to get cached portrait or queue for generation
        request_portrait_async(
            ruler_name=ruler_name,
            ruler_title=ruler_title,
            nation_name=nation_name,
            era_context=year_range,
            quote_text=quote_text
        )
        
        quote_metadata.append((quote_data, ruler_name, nation_name, year_range, tag))
    
    pending = get_pending_count()
    if pending > 0:
        print(f"[Illustrator] Waiting for {pending} portrait(s) to generate...")
        wait_for_pending_portraits(timeout_seconds=20.0)
    
    # Second pass: collect all portraits from cache
    portraits = []
    enriched_quotes = []
    success_count = 0
    
    for quote_data, ruler_name, nation_name, era, tag in quote_metadata:
        portrait_base64 = get_cached_portrait(ruler_name, nation_name, era)
        
        enriched_quote = dict(quote_data)
        
        if portrait_base64:
            success_count += 1
            portraits.append({
                "tag": tag,
                "ruler_name": ruler_name,
                "portrait_base64": portrait_base64
            })
            enriched_quote["portrait_base64"] = portrait_base64
        
        enriched_quotes.append(enriched_quote)
    
    print(f"[Illustrator] Done: {success_count}/{len(quote_metadata)} portraits generated")
    
    return {
        "illustrator_output": {
            "portraits": portraits,
            "enriched_quotes": enriched_quotes
        }
    }


# =============================================================================
# PARALLEL NODE - Runs Quotegiver + Geographer concurrently
# =============================================================================

def _run_quotegiver(state: WorkflowState) -> dict:
    """Internal function to run quotegiver (for parallel execution)."""
    dreamer_output = state.get("dreamer_output", {})
    rulers = dreamer_output.get("rulers", state.get("rulers", {}))
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")
    
    year_range = f"{current_year}-{current_year + years_to_progress} AD"
    available_tags = get_scenario_tags(scenario_id)
    
    narrative = dreamer_output.get("narrative", "")
    territorial_summary = dreamer_output.get("territorial_changes_summary", "")
    
    try:
        quotes = generate_quotes(
            narrative=narrative,
            territorial_changes_summary=territorial_summary,
            rulers=rulers,
            available_tags=available_tags,
            year_range=year_range
        )
        return {"quotes": quotes, "error": None}
    except Exception as e:
        return {"quotes": [], "error": str(e)}


def _run_geographer(state: WorkflowState) -> dict:
    """Internal function to run geographer (for parallel execution)."""
    dreamer_output = state.get("dreamer_output", {})
    territorial_changes = dreamer_output.get("territorial_changes", [])
    scenario_id = state.get("scenario_id", "rome")
    
    # Get current province state for context
    memory = get_province_memory()
    current_provinces = memory.get_all_provinces_as_dicts()
    
    try:
        geographer_output = interpret_territorial_changes(
            territorial_changes=territorial_changes,
            scenario_id=scenario_id,
            current_provinces=current_provinces
        )
        province_updates = geographer_output.get("province_updates", [])
        return {"province_updates": province_updates, "error": None}
    except Exception as e:
        return {"province_updates": [], "error": str(e)}


def parallel_quote_geo_node(state: WorkflowState) -> dict:
    """
    Parallel Node: Run Quotegiver and Geographer concurrently.
    
    Both agents only depend on dreamer_output, so they can run in parallel.
    This saves significant time since they don't need to wait for each other.
    """
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    
    print(f"[Parallel] Running Quotegiver + Geographer concurrently")
    
    # Run both agents in parallel using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        quote_future = executor.submit(_run_quotegiver, state)
        geo_future = executor.submit(_run_geographer, state)
        
        # Wait for both to complete
        quote_result = quote_future.result()
        geo_result = geo_future.result()
    
    # Process results
    quotes = quote_result.get("quotes", [])
    province_updates = geo_result.get("province_updates", [])
    
    # Log results
    if quote_result.get("error"):
        print(f"[Quotegiver] ERROR: {quote_result['error']}")
    else:
        print(f"[Quotegiver] Done: {len(quotes)} quotes generated")
    
    if geo_result.get("error"):
        print(f"[Geographer] ERROR: {geo_result['error']}")
    else:
        print(f"[Geographer] Done: {len(province_updates)} province updates")
    
    # Build combined result
    result = {
        "quotegiver_output": {"quotes": quotes},
        "territorial_changes": province_updates,
    }
    
    # Add any errors
    if quote_result.get("error"):
        result["error"] = quote_result["error"]
        result["error_node"] = "quotegiver"
    elif geo_result.get("error"):
        result["error"] = geo_result["error"]
        result["error_node"] = "geographer"
    
    return result

