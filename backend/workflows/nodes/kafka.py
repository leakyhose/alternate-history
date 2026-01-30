"""Kafka producer node for the workflow."""
from typing import List, Dict, Any
from workflows.state import WorkflowState
from util.kafka_producer import produce_timeline_event
from workflows.nodes.memory import get_current_provinces, get_province_memory
from util.province_memory import (
    load_areas,
    load_regions_to_areas,
    get_provinces_for_area,
    ProvinceMemory,
)


def produce_to_kafka_node(state: WorkflowState) -> dict:
    """Publish timeline event to Kafka and apply territorial changes to memory."""
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
            current_provinces=get_current_provinces(),
        )
        print(f"[Kafka] {'Published' if success else 'FAILED'} event: game={game_id}, iteration={iteration}")

    # apply changes to memory so next iteration has updated state
    territorial_changes = cartographer_output.get("territorial_changes", [])
    if territorial_changes:
        memory = get_province_memory()
        province_updates = _convert_territorial_to_province_updates(territorial_changes, memory)
        if province_updates:
            applied = memory.apply_updates(province_updates)
            print(f"[Kafka] Applied {applied} territorial changes to memory")

    new_rulers = ruler_updates_output.get("rulers", state.get("rulers", {}))
    all_divergences = writer_output.get("divergences", [])

    return {
        "iteration": iteration + 1,
        "current_year": current_year + years_to_progress,
        "rulers": new_rulers,
        "divergences": all_divergences,
        "merged": writer_output.get("merged", False),
        "writer_output": {},
        "cartographer_output": {},
        "ruler_updates_output": {},
    }


def _convert_territorial_to_province_updates(
    territorial_changes: List[Dict[str, Any]],
    memory: ProvinceMemory,
) -> List[Dict[str, Any]]:
    """Convert territorial changes to province updates by matching locations to areas."""
    updates = []
    areas = load_areas()
    regions = load_regions_to_areas()

    area_lookup = {name.lower(): name for name in areas.keys()}
    region_lookup = {name.lower(): name for name in regions.keys()}

    for change in territorial_changes:
        location = change.get("location", "")
        change_type = change.get("change_type", "")
        to_nation = change.get("to_nation", "")

        if not location or not change_type:
            continue

        location_lower = location.lower()

        matched_areas = []
        if location_lower in area_lookup:
            matched_areas = [area_lookup[location_lower]]
        elif location_lower in region_lookup:
            region_name = region_lookup[location_lower]
            matched_areas = regions.get(region_name, [])
        else:
            for area_name in areas.keys():
                if location_lower in area_name.lower() or area_name.lower() in location_lower:
                    matched_areas.append(area_name)
                    break

        if not matched_areas:
            print(f"[Kafka] Warning: Could not match location '{location}' to any area")
            continue

        for area_name in matched_areas:
            provinces = get_provinces_for_area(area_name)
            for p in provinces:
                pid = p.get("id")
                pname = p.get("name", f"Province {pid}")

                if change_type == "CONQUEST" and to_nation:
                    updates.append({"id": pid, "name": pname, "owner": to_nation})
                elif change_type == "LOSS":
                    updates.append({"id": pid, "name": pname, "owner": ""})
                elif change_type == "TRANSFER" and to_nation:
                    updates.append({"id": pid, "name": pname, "owner": to_nation})

    return updates
