"""Filter node for validating user divergences."""
from workflows.state import WorkflowState
from agents.filter_agent import filter_command
from util.workflow_logger import workflow_logger


def filter_node(state: WorkflowState) -> dict:
    """
    Validate user divergence through the filter agent.
    
    Input: state with divergences list (first item is user's command)
    Output: filter_passed bool, filter_reason if rejected
    """
    print("\n" + "="*60)
    print("FILTER AGENT")
    print("="*60)
    
    workflow_logger.node_start("filter", {"divergences": state.get("divergences", [])})
    
    divergences = state.get("divergences", [])
    
    if not divergences:
        print("❌ No divergence provided")
        workflow_logger.node_end("filter", {"passed": False, "reason": "No divergence"})
        return {
            "filter_passed": False,
            "filter_reason": "No divergence provided"
        }
    
    user_command = divergences[0]
    print(f"Input: \"{user_command}\"")
    print("-"*40)
    
    try:
        filter_result = filter_command(user_command)
        print(f"Filter Result: {filter_result}")
    except Exception as e:
        print(f"❌ Filter Error: {e}")
        workflow_logger.node_error("filter", e)
        return {
            "filter_passed": False,
            "filter_reason": f"Filter agent error: {str(e)}",
            "error": str(e),
            "error_node": "filter"
        }
    
    if filter_result["status"] == "rejected":
        reason = filter_result.get("reason", "Divergence rejected")
        print(f"\n❌ Divergence REJECTED")
        print(f"   Reason: {reason}")
        print(f"   Try instead: {filter_result.get('alternative')}")
        workflow_logger.node_end("filter", {"passed": False, "reason": reason})
        return {
            "filter_passed": False,
            "filter_reason": reason,
            "filter_alternative": filter_result.get("alternative")
        }
    
    # Extract year from filter result
    year = filter_result.get("year")
    print(f"\n✓ Divergence ACCEPTED")
    print(f"  Start year: {year} AD")
    
    workflow_logger.node_end("filter", {"passed": True, "year": year})
    return {
        "filter_passed": True,
        "start_year": year if year else state.get("start_year")
    }
