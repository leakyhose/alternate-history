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
        return {
            "filter_passed": False,
            "filter_reason": "No divergence provided"
        }
    
    user_command = divergences[0]
    filter_result = filter_command(user_command)
    
    if filter_result["status"] == "rejected":
        return {
            "filter_passed": False,
            "filter_reason": filter_result.get("reason", "Divergence rejected"),
            "filter_alternative": filter_result.get("alternative")
        }
    
    # Extract year from filter result
    year = filter_result.get("year")
    
    return {
        "filter_passed": True,
        "start_year": year if year else state.get("start_year")
    }
