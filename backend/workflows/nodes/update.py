"""State update node and continuation logic."""
from workflows.state import WorkflowState, LogEntry
from workflows.nodes.memory import get_province_memory
from util.log_condenser import condense_logs, should_condense


def update_state_node(state: WorkflowState) -> dict:
    """
    Update workflow state after agent iteration.
    
    - Apply territorial changes to province memory
    - Append new log entry (with quotes from quotegiver/illustrator)
    - Update rulers and divergences from Dreamer output
    - Advance current_year
    - Condense old logs if needed
    - Check merge status
    """
    dreamer_output = state.get("dreamer_output", {})
    quotegiver_output = state.get("quotegiver_output", {})
    illustrator_output = state.get("illustrator_output", {})
    territorial_changes = state.get("territorial_changes", [])
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    logs = state.get("logs", []).copy()
    condensed_logs = state.get("condensed_logs", "")
    
    try:
        # Apply territorial changes to province memory
        memory = get_province_memory()
        if territorial_changes:
            applied = memory.apply_updates(territorial_changes)
            print(f"[Update] Applied {applied} province changes")
        
        # Get quotes - prefer enriched quotes from illustrator (with portraits),
        # fall back to quotegiver quotes (without portraits)
        quotes = illustrator_output.get("enriched_quotes", quotegiver_output.get("quotes", []))
        
        # Create new log entry with quotes
        new_year = current_year + years_to_progress
        new_log: LogEntry = {
            "year_range": f"{current_year}-{new_year} AD",
            "narrative": dreamer_output.get("narrative", ""),
            "divergences": dreamer_output.get("updated_divergences", []),
            "territorial_changes_summary": dreamer_output.get("territorial_changes_summary", ""),
            "quotes": quotes
        }
        logs.append(new_log)
        
        # Condense logs if needed
        if should_condense(logs):
            logs, condensed_logs = condense_logs(logs, condensed_logs)
        
        # Get updated values from dreamer - fall back to existing if empty
        dreamer_rulers = dreamer_output.get("rulers", {})
        updated_rulers = dreamer_rulers if dreamer_rulers else state.get("rulers", {})
        updated_divergences = dreamer_output.get("updated_divergences", state.get("divergences", []))
        merged = dreamer_output.get("merged", False)
        
        print(f"[Update] Done: Year {new_year} AD, {len(logs)} logs, merged={merged}")
        
        return {
            "rulers": updated_rulers,
            "divergences": updated_divergences,
            "logs": logs,
            "condensed_logs": condensed_logs,
            "current_year": new_year,
            "merged": merged,
            # Clear inter-agent data
            "historian_output": {},
            "dreamer_output": {},
            "territorial_changes": [],
            "quotegiver_output": {},
            "illustrator_output": {}
        }
    except Exception as e:
        print(f"[Update] ERROR: {e}")
        return {
            "current_year": current_year + years_to_progress,
            "error": str(e),
            "error_node": "update_state"
        }


def should_continue(state: WorkflowState) -> str:
    """
    Decide whether to continue iteration or end.
    
    Returns 'continue' if more iterations needed, 'end' otherwise.
    """
    # Always end after one iteration for now
    # User will click "Continue" to run more iterations
    return "end"
