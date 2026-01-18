"""State update node and continuation logic."""
from workflows.state import WorkflowState, LogEntry
from workflows.nodes.memory import get_province_memory
from util.log_condenser import condense_logs, should_condense


def update_state_node(state: WorkflowState) -> dict:
    """
    Update workflow state after agent iteration.
    
    - Apply territorial changes to province memory
    - Append new log entry
    - Update rulers and divergences from Dreamer output
    - Advance current_year
    - Condense old logs if needed
    - Check merge status
    """
    dreamer_output = state.get("dreamer_output", {})
    territorial_changes = state.get("territorial_changes", [])
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    logs = state.get("logs", []).copy()
    condensed_logs = state.get("condensed_logs", "")
    
    # Apply territorial changes to province memory
    memory = get_province_memory()
    if territorial_changes:
        memory.apply_updates(territorial_changes)
    
    # Create new log entry
    new_year = current_year + years_to_progress
    new_log: LogEntry = {
        "year_range": f"{current_year}-{new_year} AD",
        "narrative": dreamer_output.get("narrative", ""),
        "divergences": dreamer_output.get("updated_divergences", []),
        "territorial_changes_description": dreamer_output.get("territorial_changes_description", "")
    }
    logs.append(new_log)
    
    # Condense logs if needed
    if should_condense(logs):
        logs, condensed_logs = condense_logs(logs, condensed_logs)
    
    # Get updated values from dreamer
    updated_rulers = dreamer_output.get("rulers", state.get("rulers", {}))
    updated_divergences = dreamer_output.get("updated_divergences", state.get("divergences", []))
    merged = dreamer_output.get("merged", False)
    
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
        "territorial_changes": []
    }


def should_continue(state: WorkflowState) -> str:
    """
    Decide whether to continue iteration or end.
    
    Returns 'continue' if more iterations needed, 'end' otherwise.
    
    Current logic: End after one iteration (user clicks Continue for more)
    Future: Could implement automatic multi-iteration based on conditions
    """
    merged = state.get("merged", False)
    
    # Always end after one iteration for now
    # User will click "Continue" to run more iterations
    return "end"
