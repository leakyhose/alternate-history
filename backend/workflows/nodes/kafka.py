"""Kafka producer node for publishing timeline events."""
from workflows.state import WorkflowState
from util.kafka_producer import produce_timeline_event


def produce_to_kafka_node(state: WorkflowState) -> dict:
    """
    Produce a TimelineEvent to Kafka after the pipeline completes.

    This node extracts all relevant data from the workflow state and
    publishes it to the timeline.events topic. Downstream microservices
    (Quotegiver, Geographer, Illustrator) will consume from this topic.

    The node does NOT block waiting for those services - it just publishes
    and returns. The frontend will receive updates via WebSocket from
    the Aggregator service.
    """
    game_id = state.get("game_id", "")
    iteration = state.get("iteration", 1)
    scenario_id = state.get("scenario_id", "rome")
    current_year = state.get("current_year", state.get("start_year", 0))
    years_to_progress = state.get("years_to_progress", 20)

    # Build year_range string
    year_range = f"{current_year}-{current_year + years_to_progress}"

    # Extract filter result (may be empty for continue workflows)
    filter_result = {
        "status": "accepted" if state.get("filter_passed", True) else "rejected",
        "divergences": state.get("divergences", []),
        "start_year": state.get("start_year", current_year),
    }

    # Extract outputs from new pipeline
    writer_output = state.get("writer_output", {})
    cartographer_output = state.get("cartographer_output", {})
    ruler_updates_output = state.get("ruler_updates_output", {})

    # Build the decision payload (combines all agent outputs)
    # This maintains compatibility with the existing Kafka event schema
    decision = {
        "narrative": writer_output.get("narrative", ""),
        "territorial_changes": cartographer_output.get("territorial_changes", []),
        "rulers": ruler_updates_output.get("rulers", {}),
        "divergences": writer_output.get("divergences", []),
        "merged": writer_output.get("merged", False),
    }

    # Produce to Kafka
    if game_id:
        success = produce_timeline_event(
            game_id=game_id,
            iteration=iteration,
            scenario_id=scenario_id,
            year_range=year_range,
            filter_result=filter_result,
            historian_context={},  # No longer used, kept for schema compatibility
            dreamer_decision=decision,  # Renamed internally but same schema
        )
        if success:
            print(f"[Kafka] Published timeline event for game={game_id}, iteration={iteration}")
        else:
            print(f"[Kafka] FAILED to publish event for game={game_id}")
    else:
        print("[Kafka] WARNING: No game_id provided, skipping Kafka publish")

    # Return updated state for next round
    # Update rulers in state from ruler_updates_output
    new_rulers = ruler_updates_output.get("rulers", state.get("rulers", {}))
    all_divergences = writer_output.get("divergences", [])
    
    return {
        "iteration": iteration + 1,
        "rulers": new_rulers,  # Persist updated rulers for next iteration
        "divergences": all_divergences,
        "merged": writer_output.get("merged", False),
        # Clear inter-agent data (microservices will handle these now)
        "writer_output": {},
        "cartographer_output": {},
        "ruler_updates_output": {},
    }
