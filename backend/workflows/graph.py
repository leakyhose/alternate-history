from langgraph.graph import StateGraph, END
from workflows.state import WorkflowState
from workflows.nodes import (
    filter_node,
    initialize_game_node,
    historian_node,
    dreamer_node,
    geographer_node,
    update_state_node,
    should_continue
)


def build_graph() -> StateGraph:
    """
    Build the alternate history workflow graph.
    
    Flow:
    1. filter_node: Validate user divergence
    2. initialize_game_node: Set up game state, load provinces/rulers
    3. historian_node: Get real historical context for the period
    4. dreamer_node: Make creative decisions based on divergences
    5. geographer_node: Translate territorial changes to province updates
    6. update_state_node: Update state, advance year, check merge
    7. Conditional: Continue iteration or end
    """
    graph = StateGraph(WorkflowState)
    
    # Add all nodes
    graph.add_node("filter", filter_node)
    graph.add_node("initialize", initialize_game_node)
    graph.add_node("historian", historian_node)
    graph.add_node("dreamer", dreamer_node)
    graph.add_node("geographer", geographer_node)
    graph.add_node("update_state", update_state_node)
    
    # Set entry point
    graph.set_entry_point("filter")
    
    # Define edges
    # Filter -> Initialize (if accepted) or END (if rejected)
    graph.add_conditional_edges(
        "filter",
        lambda state: "initialize" if state.get("filter_passed", False) else END,
        {
            "initialize": "initialize",
            END: END
        }
    )
    
    # Initialize -> Historian
    graph.add_edge("initialize", "historian")
    
    # Historian -> Dreamer
    graph.add_edge("historian", "dreamer")
    
    # Dreamer -> Geographer
    graph.add_edge("dreamer", "geographer")
    
    # Geographer -> Update State
    graph.add_edge("geographer", "update_state")
    
    # Update State -> Conditional (continue or end)
    graph.add_conditional_edges(
        "update_state",
        should_continue,
        {
            "continue": "historian",  # Loop back for next iteration
            "end": END
        }
    )
    
    return graph.compile()


def build_continue_graph() -> StateGraph:
    """
    Build a graph for continuing an existing game.
    
    This skips the filter and initialize steps since the game
    already exists. Useful for "Continue" button.
    
    Flow:
    1. historian_node
    2. dreamer_node
    3. geographer_node
    4. update_state_node
    """
    graph = StateGraph(WorkflowState)
    
    # Add nodes (skip filter and initialize)
    graph.add_node("historian", historian_node)
    graph.add_node("dreamer", dreamer_node)
    graph.add_node("geographer", geographer_node)
    graph.add_node("update_state", update_state_node)
    
    # Set entry point
    graph.set_entry_point("historian")
    
    # Define edges
    graph.add_edge("historian", "dreamer")
    graph.add_edge("dreamer", "geographer")
    graph.add_edge("geographer", "update_state")
    
    # Update State -> End (single iteration for continue)
    graph.add_edge("update_state", END)
    
    return graph.compile()


# Compile workflow graphs
workflow = build_graph()
continue_workflow = build_continue_graph()
