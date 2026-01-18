"""Agent nodes for the alternate history workflow."""
from workflows.state import WorkflowState
from agents.historian_agent import get_historical_context
from agents.dreamer_agent import make_decision
from agents.geographer_agent import interpret_territorial_changes
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
    
    print(f"📚 Historian: {current_year}-{current_year + years_to_progress} AD")
    
    try:
        historian_output = get_historical_context(
            start_year=current_year,
            years_to_progress=years_to_progress,
            tags=tags
        )
        
        events_count = len(historian_output.get("conditional_events", []))
        print(f"✓ Historian: {events_count} conditional events")
        
        return {
            "historian_output": historian_output
        }
    except Exception as e:
        print(f"❌ Historian Error: {e}")
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
    
    print(f"💭 Dreamer: {current_year}-{current_year + years_to_progress} AD")
    
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
        print(f"✓ Dreamer: {div_count} divergences, merged={merged}")
        
        return {
            "dreamer_output": dreamer_output
        }
    except Exception as e:
        print(f"❌ Dreamer Error: {e}")
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
    
    Interprets Dreamer's STRUCTURED territorial changes and converts to OWNER/CONTROL changes.
    Uses tools to query regions and find province IDs, then applies change_type deterministically.
    """
    dreamer_output = state.get("dreamer_output", {})
    territorial_changes = dreamer_output.get("territorial_changes", [])
    scenario_id = state.get("scenario_id", "rome")
    
    print(f"🗺️  Geographer: processing territorial changes")
    
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
        print(f"✓ Geographer: {len(province_updates)} province updates")
        
        return {
            "territorial_changes": province_updates
        }
    except Exception as e:
        print(f"❌ Geographer Error: {e}")
        return {
            "territorial_changes": [],
            "error": str(e),
            "error_node": "geographer"
        }
