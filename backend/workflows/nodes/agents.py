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
