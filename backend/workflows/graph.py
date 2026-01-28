"""
Simplified workflow graph for the event-driven architecture.

This workflow runs the CORE pipeline only:
  Filter -> Initialize -> Writer -> Cartographer -> Ruler Updates -> Kafka

The auxiliary processing (Quotegiver, Geographer, Illustrator) is now
handled by separate microservices that consume from Kafka.
"""
from langgraph.graph import StateGraph, END
from workflows.state import WorkflowState
from workflows.nodes import (
    filter_node,
    initialize_game_node,
    writer_node,
    cartographer_node,
    ruler_updates_node,
)
from workflows.nodes.kafka import produce_to_kafka_node


def build_graph() -> StateGraph:
    """
    Build the simplified alternate history workflow graph.

    Flow:
    1. filter_node: Validate user divergence
    2. initialize_game_node: Set up game state, load provinces/rulers
    3. writer_node: Create the alternate history narrative
    4. cartographer_node: Extract territorial changes from narrative
    5. ruler_updates_node: Update rulers based on narrative
    6. produce_to_kafka_node: Publish TimelineEvent to Kafka
    7. END

    Note: Quotegiver, Geographer, and Illustrator are now separate
    microservices that consume from the timeline.events Kafka topic.
    """
    graph = StateGraph(WorkflowState)

    # Add core nodes only
    graph.add_node("filter", filter_node)
    graph.add_node("initialize", initialize_game_node)
    graph.add_node("writer", writer_node)
    graph.add_node("cartographer", cartographer_node)
    graph.add_node("ruler_updates", ruler_updates_node)
    graph.add_node("produce_to_kafka", produce_to_kafka_node)

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

    # Initialize -> Writer
    graph.add_edge("initialize", "writer")

    # Writer -> Cartographer
    graph.add_edge("writer", "cartographer")

    # Cartographer -> Ruler Updates
    graph.add_edge("cartographer", "ruler_updates")

    # Ruler Updates -> Kafka
    graph.add_edge("ruler_updates", "produce_to_kafka")

    # Kafka -> END (single iteration, frontend will call /continue for more)
    graph.add_edge("produce_to_kafka", END)

    return graph.compile()


def build_continue_graph() -> StateGraph:
    """
    Build a graph for continuing an existing game.

    This skips the filter and initialize steps since the game
    already exists.

    Flow:
    1. writer_node
    2. cartographer_node
    3. ruler_updates_node
    4. produce_to_kafka_node
    5. END
    """
    graph = StateGraph(WorkflowState)

    # Add nodes (skip filter and initialize)
    graph.add_node("writer", writer_node)
    graph.add_node("cartographer", cartographer_node)
    graph.add_node("ruler_updates", ruler_updates_node)
    graph.add_node("produce_to_kafka", produce_to_kafka_node)

    # Set entry point
    graph.set_entry_point("writer")

    # Define edges
    graph.add_edge("writer", "cartographer")
    graph.add_edge("cartographer", "ruler_updates")
    graph.add_edge("ruler_updates", "produce_to_kafka")
    graph.add_edge("produce_to_kafka", END)

    return graph.compile()


# Compile workflow graphs
workflow = build_graph()
continue_workflow = build_continue_graph()
