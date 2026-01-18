"""State update node and continuation logic."""
from workflows.state import WorkflowState, LogEntry
from workflows.nodes.memory import get_province_memory
from util.log_condenser import condense_logs, should_condense
from util.workflow_logger import workflow_logger


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
    
    print("\n" + "="*60)
    print("UPDATE STATE")
    print("="*60)
    
    workflow_logger.node_start("update_state", {
        "current_year": current_year,
        "territorial_changes": len(territorial_changes)
    })
    
    try:
        # Apply territorial changes to province memory
        memory = get_province_memory()
        if territorial_changes:
            # Log any provinces being set to untracked (empty owner)
            untracked = [u for u in territorial_changes if not u.get("owner")]
            if untracked:
                print(f"  📍 {len(untracked)} provinces becoming untracked (lost to non-tracked states):")
                for u in untracked[:5]:  # Show first 5
                    print(f"      ID {u.get('id')} ({u.get('name', 'unknown')})")
                if len(untracked) > 5:
                    print(f"      ... and {len(untracked) - 5} more")
            
            applied = memory.apply_updates(territorial_changes)
            print(f"✓ Applied {applied} province updates")
            workflow_logger.info(f"  Applied {applied} province updates")
        else:
            print("  No province updates to apply")
        
        # Create new log entry
        new_year = current_year + years_to_progress
        new_log: LogEntry = {
            "year_range": f"{current_year}-{new_year} AD",
            "narrative": dreamer_output.get("narrative", ""),
            "divergences": dreamer_output.get("updated_divergences", []),
            "territorial_changes_description": dreamer_output.get("territorial_changes_description", "")
        }
        logs.append(new_log)
        print(f"✓ Created log entry for {current_year}-{new_year} AD")
        
        # Condense logs if needed
        logs_condensed = False
        if should_condense(logs):
            logs, condensed_logs = condense_logs(logs, condensed_logs)
            logs_condensed = True
            print(f"✓ Condensed older logs (now {len(logs)} full logs)")
        
        # Get updated values from dreamer
        updated_rulers = dreamer_output.get("rulers", state.get("rulers", {}))
        updated_divergences = dreamer_output.get("updated_divergences", state.get("divergences", []))
        merged = dreamer_output.get("merged", False)
        
        print(f"\n  New Year: {new_year} AD")
        print(f"  Total Logs: {len(logs)}")
        print(f"  Merged: {merged}")
        
        print("\n" + "="*60)
        print("WORKFLOW ITERATION COMPLETE")
        print("="*60)
        
        workflow_logger.node_end("update_state", {
            "new_year": new_year,
            "total_logs": len(logs),
            "logs_condensed": logs_condensed,
            "merged": merged
        })
        
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
    except Exception as e:
        print(f"❌ Update State Error: {e}")
        workflow_logger.node_error("update_state", e)
        # Return minimal update to avoid breaking the workflow
        return {
            "current_year": current_year + years_to_progress,
            "error": str(e),
            "error_node": "update_state"
        }


def should_continue(state: WorkflowState) -> str:
    """
    Decide whether to continue iteration or end.
    
    Returns 'continue' if more iterations needed, 'end' otherwise.
    
    Current logic: End after one iteration (user clicks Continue for more)
    Future: Could implement automatic multi-iteration based on conditions
    """
    merged = state.get("merged", False)
    
    if merged:
        workflow_logger.info("Timeline merged - ending workflow")
    
    # Always end after one iteration for now
    # User will click "Continue" to run more iterations
    return "end"
