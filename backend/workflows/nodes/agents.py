"""Agent nodes for the workflow."""
from workflows.state import WorkflowState
from agents.writer_agent import write_narrative
from agents.cartographer_agent import extract_territorial_changes
from agents.ruler_updates_agent import update_rulers
from util.scenario import get_scenario_tags


def writer_node(state: WorkflowState) -> dict:
    """Create alternate history narrative."""
    divergences = state.get("divergences", [])
    condensed_logs = state.get("condensed_logs", "")
    logs = state.get("logs", [])
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")

    print(f"[Writer] {current_year}-{current_year + years_to_progress} AD")
    available_tags = get_scenario_tags(scenario_id)

    try:
        writer_output = write_narrative(
            divergences=divergences,
            condensed_logs=condensed_logs,
            recent_logs=logs,
            current_year=current_year,
            years_to_progress=years_to_progress,
            available_tags=available_tags
        )
        print(f"[Writer] Done: {len(writer_output.get('divergences', []))} divergences")
        return {"writer_output": writer_output}
    except Exception as e:
        print(f"[Writer] ERROR: {e}")
        return {
            "writer_output": {"narrative": f"[Error: {e}]", "updated_divergences": divergences, "merged": False},
            "error": str(e),
            "error_node": "writer"
        }


def cartographer_node(state: WorkflowState) -> dict:
    """Extract territorial changes from narrative."""
    writer_output = state.get("writer_output", {})
    narrative = writer_output.get("narrative", "")
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")

    year_range = f"{current_year}-{current_year + years_to_progress}"
    available_tags = get_scenario_tags(scenario_id)

    print(f"[Cartographer] {year_range} AD")

    try:
        cartographer_output = extract_territorial_changes(
            narrative=narrative,
            year_range=year_range,
            available_tags=available_tags
        )
        print(f"[Cartographer] Done: {len(cartographer_output.get('territorial_changes', []))} changes")
        return {"cartographer_output": cartographer_output}
    except Exception as e:
        print(f"[Cartographer] ERROR: {e}")
        return {"cartographer_output": {"territorial_changes": []}, "error": str(e), "error_node": "cartographer"}


def ruler_updates_node(state: WorkflowState) -> dict:
    """Update rulers based on narrative."""
    rulers = state.get("rulers", {})
    writer_output = state.get("writer_output", {})
    narrative = writer_output.get("narrative", "")
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)

    print(f"[Ruler Updates] {current_year}-{current_year + years_to_progress} AD")

    try:
        ruler_output = update_rulers(
            current_rulers=rulers,
            narrative=narrative,
            current_year=current_year,
            years_to_progress=years_to_progress
        )
        print(f"[Ruler Updates] Done: {len(ruler_output.get('rulers', {}))} rulers")
        return {"ruler_updates_output": ruler_output}
    except Exception as e:
        print(f"[Ruler Updates] ERROR: {e}")
        fallback_rulers = {
            tag: {"name": info.get("name", "Unknown"), "title": info.get("title", "Ruler"),
                  "age": info.get("age", 30) + years_to_progress, "dynasty": info.get("dynasty", "")}
            for tag, info in rulers.items()
        }
        return {"ruler_updates_output": {"rulers": fallback_rulers}, "error": str(e), "error_node": "ruler_updates"}


def illustrator_node(state: WorkflowState) -> dict:
    """Generate portraits for quoted rulers."""
    from util.portrait_cache import (
        request_portrait_async, get_pending_count,
        wait_for_pending_portraits, get_cached_portrait
    )

    quotegiver_output = state.get("quotegiver_output", {})
    quotes = quotegiver_output.get("quotes", [])
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")

    end_year = current_year + years_to_progress
    year_range = f"{end_year} AD"

    print(f"[Illustrator] {end_year} AD")

    if not quotes:
        return {"illustrator_output": {"portraits": [], "enriched_quotes": []}}

    available_tags = get_scenario_tags(scenario_id)
    quote_metadata = []

    for quote_data in quotes[:2]:
        tag = quote_data.get("tag", "")
        ruler_name = quote_data.get("ruler_name", "Unknown Ruler")
        ruler_title = quote_data.get("ruler_title", "Ruler")
        quote_text = quote_data.get("quote", "")
        nation_info = available_tags.get(tag, {})
        nation_name = nation_info.get("name", tag if tag else "Unknown Nation")

        request_portrait_async(
            ruler_name=ruler_name, ruler_title=ruler_title,
            nation_name=nation_name, era_context=year_range, quote_text=quote_text
        )
        quote_metadata.append((quote_data, ruler_name, nation_name, year_range, tag))

    pending = get_pending_count()
    if pending > 0:
        print(f"[Illustrator] Waiting for {pending} portrait(s)...")
        wait_for_pending_portraits(timeout_seconds=20.0)

    portraits = []
    enriched_quotes = []

    for quote_data, ruler_name, nation_name, era, tag in quote_metadata:
        portrait_base64 = get_cached_portrait(ruler_name, nation_name, era)
        enriched_quote = dict(quote_data)
        if portrait_base64:
            portraits.append({"tag": tag, "ruler_name": ruler_name, "portrait_base64": portrait_base64})
            enriched_quote["portrait_base64"] = portrait_base64
        enriched_quotes.append(enriched_quote)

    print(f"[Illustrator] Done: {len(portraits)}/{len(quote_metadata)} portraits")
    return {"illustrator_output": {"portraits": portraits, "enriched_quotes": enriched_quotes}}


