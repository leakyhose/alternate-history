"""Agent nodes for the alternate history workflow.

These are placeholder implementations that will be replaced
with actual LLM calls in later phases.
"""
from workflows.state import WorkflowState


def historian_node(state: WorkflowState) -> dict:
    """
    Historian Agent: Provide real historical context for the period.
    
    The Historian does NOT see current alternate state - only provides
    the baseline of what would happen in real history.
    
    TODO: Implement actual LLM call (Phase 2)
    """
    start_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    rulers = state.get("rulers", {})
    
    # Get primary nation tag (first ruler)
    primary_tag = list(rulers.keys())[0] if rulers else "ROM"
    
    # Placeholder output - replace with actual LLM call in Phase 2
    historian_output = {
        "period": f"{start_year}-{start_year + years_to_progress} AD",
        "keep_in_mind": [
            f"Placeholder: Real historical events for {start_year}-{start_year + years_to_progress} AD",
            "This will be replaced with actual LLM-generated historical context"
        ],
        "conditional_events": [
            {
                "condition": "Placeholder condition",
                "outcome": "Placeholder outcome - to be replaced with actual historical conditionals"
            }
        ]
    }
    
    return {
        "historian_output": historian_output
    }


def dreamer_node(state: WorkflowState) -> dict:
    """
    Dreamer Agent: Make creative decisions based on divergences.
    
    Synthesizes divergences + historian context to decide what actually happens.
    
    TODO: Implement actual LLM call (Phase 3)
    """
    historian_output = state.get("historian_output", {})
    divergences = state.get("divergences", [])
    condensed_logs = state.get("condensed_logs", "")
    logs = state.get("logs", [])
    rulers = state.get("rulers", {})
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    
    # Placeholder output - replace with actual LLM call in Phase 3
    end_year = current_year + years_to_progress
    
    dreamer_output = {
        "rulers": rulers,  # Keep rulers unchanged for now
        "narrative": f"[Placeholder narrative for {current_year}-{end_year} AD] " \
                    f"The divergence '{divergences[0] if divergences else 'unknown'}' " \
                    "continues to affect the timeline. This will be replaced with " \
                    "actual LLM-generated narrative.",
        "territorial_changes_description": "Placeholder: No territorial changes in this period. " \
                                          "This will be replaced with actual territorial descriptions.",
        "updated_divergences": divergences,  # Keep divergences unchanged for now
        "merged": False
    }
    
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
