"""Kafka producer node for the workflow."""
from workflows.state import WorkflowState
from util.kafka_producer import produce_timeline_event


def produce_to_kafka_node(state: WorkflowState) -> dict:
    """Publish timeline event to Kafka after pipeline completes."""
    game_id = state.get("game_id", "")
    iteration = state.get("iteration", 1)
    scenario_id = state.get("scenario_id", "rome")
    current_year = state.get("current_year", state.get("start_year", 0))
    years_to_progress = state.get("years_to_progress", 20)

    year_range = f"{current_year}-{current_year + years_to_progress}"

    filter_result = {
        "status": "accepted" if state.get("filter_passed", True) else "rejected",
        "divergences": state.get("divergences", []),
        "start_year": state.get("start_year", current_year),
    }

    writer_output = state.get("writer_output", {})
    cartographer_output = state.get("cartographer_output", {})
    ruler_updates_output = state.get("ruler_updates_output", {})

    decision = {
        "narrative": writer_output.get("narrative", ""),
        "territorial_changes": cartographer_output.get("territorial_changes", []),
        "rulers": ruler_updates_output.get("rulers", {}),
        "divergences": writer_output.get("divergences", []),
        "merged": writer_output.get("merged", False),
    }

    if game_id:
        success = produce_timeline_event(
            game_id=game_id,
            iteration=iteration,
            scenario_id=scenario_id,
            year_range=year_range,
            filter_result=filter_result,
            historian_context={},
            dreamer_decision=decision,
        )
        print(f"[Kafka] {'Published' if success else 'FAILED'} event: game={game_id}, iteration={iteration}")

    new_rulers = ruler_updates_output.get("rulers", state.get("rulers", {}))
    all_divergences = writer_output.get("divergences", [])

    return {
        "iteration": iteration + 1,
        "rulers": new_rulers,
        "divergences": all_divergences,
        "merged": writer_output.get("merged", False),
        "writer_output": {},
        "cartographer_output": {},
        "ruler_updates_output": {},
    }
