"""Filter node for validating user divergences."""
from workflows.state import WorkflowState
from agents.filter_agent import filter_command


def filter_node(state: WorkflowState) -> dict:
    """
    Validate user divergence through the filter agent.
    
    Input: state with divergences list (first item is user's command)
    Output: filter_passed bool, filter_reason if rejected
    """
    divergences = state.get("divergences", [])
    
    if not divergences:
        print("❌ Filter: No divergence provided")
        return {
            "filter_passed": False,
            "filter_reason": "No divergence provided"
        }
    
    user_command = divergences[0]
    print(f"🔍 Filter: \"{user_command}\"")
    
    try:
        filter_result = filter_command(user_command)
    except Exception as e:
        print(f"❌ Filter Error: {e}")
        return {
            "filter_passed": False,
            "filter_reason": f"Filter agent error: {str(e)}",
            "error": str(e),
            "error_node": "filter"
        }
    
    if filter_result["status"] == "rejected":
        reason = filter_result.get("reason", "Divergence rejected")
        print(f"❌ Filter: Rejected - {reason}")
        return {
            "filter_passed": False,
            "filter_reason": reason,
            "filter_alternative": filter_result.get("alternative")
        }
    
    year = filter_result.get("year")
    print(f"✓ Filter: Accepted, start year {year} AD")
    
    return {
        "filter_passed": True,
        "start_year": year if year else state.get("start_year")
    }
