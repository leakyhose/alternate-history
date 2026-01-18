from langgraph.graph import StateGraph, END
from workflows.state import WorkflowState
from workflows.nodes import (
    filter_node,
    initialize_game_node,
    historian_node,
    dreamer_node,
    quotegiver_node,
    illustrator_node,
    geographer_node,
    update_state_node,
    should_continue,
    parallel_quote_geo_node,
)


def build_graph() -> StateGraph:
    """
    Build the alternate history workflow graph.
    
    Flow:
    1. filter_node: Validate user divergence
    2. initialize_game_node: Set up game state, load provinces/rulers
    3. historian_node: Get real historical context for the period
    4. dreamer_node: Make creative decisions based on divergences
    5. parallel_quote_geo_node: Run quotegiver + geographer in PARALLEL
    6. illustrator_node: Generate pixel art portraits (LAZY - async background)
    7. update_state_node: Update state, advance year, check merge
    8. Conditional: Continue iteration or end
    """
    graph = StateGraph(WorkflowState)
    
    # Add all nodes
    graph.add_node("filter", filter_node)
    graph.add_node("initialize", initialize_game_node)
    graph.add_node("historian", historian_node)
    graph.add_node("dreamer", dreamer_node)
    graph.add_node("parallel_quote_geo", parallel_quote_geo_node)  # Combined parallel node
    graph.add_node("illustrator", illustrator_node)
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
    
    # Dreamer -> Parallel (Quotegiver + Geographer run together)
    graph.add_edge("dreamer", "parallel_quote_geo")
    
    # Parallel -> Illustrator (lazy/async portrait generation)
    graph.add_edge("parallel_quote_geo", "illustrator")
    
    # Illustrator -> Update State
    graph.add_edge("illustrator", "update_state")
    
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
    3. parallel_quote_geo_node (quotegiver + geographer in parallel)
    4. illustrator_node (lazy portrait generation)
    5. update_state_node
    """
    graph = StateGraph(WorkflowState)
    
    # Add nodes (skip filter and initialize)
    graph.add_node("historian", historian_node)
    graph.add_node("dreamer", dreamer_node)
    graph.add_node("parallel_quote_geo", parallel_quote_geo_node)
    graph.add_node("illustrator", illustrator_node)
    graph.add_node("update_state", update_state_node)
    
    # Set entry point
    graph.set_entry_point("historian")
    
    # Define edges
    graph.add_edge("historian", "dreamer")
    graph.add_edge("dreamer", "parallel_quote_geo")
    graph.add_edge("parallel_quote_geo", "illustrator")
    graph.add_edge("illustrator", "update_state")

    # Update State -> End (single iteration for continue)
    graph.add_edge("update_state", END)
    
    return graph.compile()


# Compile workflow graphs
workflow = build_graph()
continue_workflow = build_continue_graph()