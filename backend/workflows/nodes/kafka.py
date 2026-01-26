"""Kafka producer node for publishing timeline events."""
from workflows.state import WorkflowState
from util.kafka_producer import produce_timeline_event


def produce_to_kafka_node(state: WorkflowState) -> dict:
    """
    Produce a TimelineEvent to Kafka after the Dreamer completes.

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

    # Extract historian context
    historian_output = state.get("historian_output", {})
    historian_context = {
        "period": historian_output.get("period", year_range),
        "real_events": historian_output.get("real_events", []),
        "keep_in_mind": historian_output.get("keep_in_mind", []),
        "conditional_events": historian_output.get("conditional_events", []),
    }

    # Extract dreamer decision
    dreamer_output = state.get("dreamer_output", {})
    dreamer_decision = {
        "narrative": dreamer_output.get("narrative", ""),
        "territorial_summary": dreamer_output.get("territorial_changes_summary", ""),
        "territorial_changes": dreamer_output.get("territorial_changes", []),
        "rulers": dreamer_output.get("rulers", {}),
        "updated_divergences": dreamer_output.get("updated_divergences", []),
        "merged": dreamer_output.get("merged", False),
    }

    # Produce to Kafka
    if game_id:
        success = produce_timeline_event(
            game_id=game_id,
            iteration=iteration,
            scenario_id=scenario_id,
            year_range=year_range,
            filter_result=filter_result,
            historian_context=historian_context,
            dreamer_decision=dreamer_decision,
        )
        if success:
            print(f"[Kafka] Published timeline event for game={game_id}, iteration={iteration}")
        else:
            print(f"[Kafka] FAILED to publish event for game={game_id}")
    else:
        print("[Kafka] WARNING: No game_id provided, skipping Kafka publish")

    # Return updated iteration for next round
    return {
        "iteration": iteration + 1,
        # Clear inter-agent data (microservices will handle these now)
        "historian_output": {},
        "dreamer_output": {},
    }
