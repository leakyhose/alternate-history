"""Game initialization node."""
import json
import os
from typing import Dict

from workflows.state import WorkflowState, RulerInfo, LogEntry
from workflows.nodes.memory import reset_province_memory, get_province_memory
from util.scenario import get_scenario_path, load_scenario_metadata


def initialize_game_node(state: WorkflowState) -> dict:
    """
    Initialize game state after filter passes.
    
    - Load province state for start_year
    - Load ruler(s) for start_year
    - Create initial log entry (Log 0)
    """
    scenario_id = state.get("scenario_id", "rome")
    start_year = state.get("start_year")
    years_to_progress = state.get("years_to_progress", 20)
    divergences = state.get("divergences", [])
    
    if start_year is None:
        print("[Initialize] ERROR: start_year is required")
        raise ValueError("start_year is required")
    
    print(f"[Initialize] {scenario_id}, year {start_year} AD")
    
    try:
        # Reset and load province memory for the scenario
        reset_province_memory()
        memory = get_province_memory()
        loaded = memory.load_from_year(start_year, scenario_id)
        province_count = len(memory.get_all_provinces()) if loaded else 0
        
        # Load rulers for start year from scenario
        rulers = _load_rulers_for_year(start_year, scenario_id)
        
        print(f"[Initialize] Done: {province_count} provinces, {len(rulers)} rulers")
        
        # Create initial log entry (Log 0)
        initial_log: LogEntry = {
            "year_range": f"-{start_year} AD",
            "narrative": _generate_initial_narrative(start_year, scenario_id),
            "divergences": divergences.copy(),
            "quotes": []  # No quotes for initial log
        }
        
        return {
            "scenario_id": scenario_id,
            "rulers": rulers,
            "logs": [initial_log],
            "condensed_logs": "",
            "current_year": start_year,
            "years_to_progress": years_to_progress,
            "merged": False,
            # Clear all agent outputs
            "writer_output": {},
            "cartographer_output": {},
            "ruler_updates_output": {},
            "historian_output": {},
            "dreamer_output": {},
            "territorial_changes": []
        }
    except Exception as e:
        print(f"[Initialize] ERROR: {e}")
        raise


def _load_rulers_for_year(year: int, scenario_id: str = "rome") -> Dict[str, RulerInfo]:
    """Load rulers from static data for a given year and scenario."""
    file_path = os.path.join(get_scenario_path(scenario_id), "rulers.json")
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return empty dict if file not found - tags come from metadata
        return {}
    
    year_str = str(year)
    ruler_list = data.get(year_str, [])
    
    if not ruler_list:
        # Try to find closest year
        available_years = sorted([int(y) for y in data.keys()])
        closest = min(available_years, key=lambda y: abs(y - year), default=None)
        if closest:
            ruler_list = data.get(str(closest), [])
    
    rulers: Dict[str, RulerInfo] = {}
    for r in ruler_list:
        tag = r.get("TAG")
        if tag:
            rulers[tag] = {
                "name": r.get("NAME", "Unknown"),
                "title": r.get("TITLE", "Ruler"),
                "age": r.get("AGE", 40),
                "dynasty": r.get("DYNASTY", "Unknown")
            }
    
    return rulers


def _generate_initial_narrative(year: int, scenario_id: str = "rome") -> str:
    """Generate placeholder initial narrative for a year."""
    metadata = load_scenario_metadata(scenario_id)
    scenario_name = metadata.get("name", "the world")
    
    return f"{scenario_name} in {year} AD."
