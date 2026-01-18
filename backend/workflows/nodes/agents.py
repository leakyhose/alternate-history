"""Agent nodes for the alternate history workflow."""
from workflows.state import WorkflowState
from agents.historian_agent import get_historical_context
from agents.dreamer_agent import make_decision
from util.scenario import get_scenario_tags


def historian_node(state: WorkflowState) -> dict:
    """
    Historian Agent: Provide real historical context for the period.
    
    The Historian does NOT see current alternate state - only provides
    the baseline of what would happen in real history.
    """
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    rulers = state.get("rulers", {})
    
    historian_output = get_historical_context(
        start_year=current_year,
        years_to_progress=years_to_progress,
        rulers=rulers
    )
    
    return {
        "historian_output": historian_output
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
    
    # Get available nation tags from scenario metadata
    available_tags = get_scenario_tags(scenario_id)
    
    # Call the actual Dreamer agent
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
    
    return {
        "dreamer_output": dreamer_output
    }


def geographer_node(state: WorkflowState) -> dict:
    """
    Geographer Agent: Translate territorial descriptions to province updates.
    
    Interprets Dreamer's prose and converts to OWNER/CONTROL changes.
    
    TODO: Implement actual LLM call (Phase 4)
    """
    dreamer_output = state.get("dreamer_output", {})
    territorial_description = dreamer_output.get("territorial_changes_description", "")
    
    # Placeholder - no actual province updates yet
    # Will be replaced with LLM-based interpretation in Phase 4
    province_updates = []
    
    # In future: Parse territorial_description, query region_provinces.json,
    # determine OWNER vs CONTROL based on language used
    
    return {
        "territorial_changes": province_updates
    }
