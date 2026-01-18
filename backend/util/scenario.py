"""Scenario metadata utilities."""
import json
import os
from typing import Dict

# Scenario data cache
_scenario_metadata_cache: Dict[str, dict] = {}


def get_scenario_path(scenario_id: str) -> str:
    """Get the path to a scenario's data folder."""
    return os.path.join("static", "scenarios", scenario_id)


def load_scenario_metadata(scenario_id: str) -> dict:
    """Load and cache scenario metadata."""
    if scenario_id in _scenario_metadata_cache:
        return _scenario_metadata_cache[scenario_id]
    
    metadata_path = os.path.join(get_scenario_path(scenario_id), "metadata.json")
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            _scenario_metadata_cache[scenario_id] = metadata
            return metadata
    except (FileNotFoundError, json.JSONDecodeError):
        return {"name": "Unknown Scenario", "tags": {}}


def get_scenario_tags(scenario_id: str) -> Dict[str, dict]:
    """Get all nation tags for a scenario from its metadata."""
    metadata = load_scenario_metadata(scenario_id)
    return metadata.get("tags", {})


def get_scenario_name(scenario_id: str) -> str:
    """Get the display name for a scenario."""
    metadata = load_scenario_metadata(scenario_id)
    return metadata.get("name", "Unknown Scenario")


def clear_scenario_cache() -> None:
    """Clear the scenario metadata cache."""
    global _scenario_metadata_cache
    _scenario_metadata_cache = {}
