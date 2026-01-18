from langgraph.graph import StateGraph, END
from workflows.state import WorkflowState
from workflows.nodes import placeholder_node


def build_graph() -> StateGraph:

    graph = StateGraph(WorkflowState)
    
    # Nodes
    graph.add_node("process", placeholder_node)

    
    # Edges
    graph.set_entry_point("process")
    graph.add_edge("process", END)
    
    return graph.compile()


workflow = build_graph()
