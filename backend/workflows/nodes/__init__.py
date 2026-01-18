"""Node functions for the alternate history workflow."""

# Import nodes - these will be imported when the module is loaded
# Note: filter.py depends on agents.filter_agent which requires langchain_google_genai
from workflows.nodes.filter import filter_node
from workflows.nodes.initialize import initialize_game_node
from workflows.nodes.agents import (
    historian_node,
    dreamer_node,
    geographer_node,
    quotegiver_node,
    illustrator_node,
    parallel_quote_geo_node,
)
from workflows.nodes.update import update_state_node, should_continue
from workflows.nodes.memory import (
    get_province_memory,
    reset_province_memory,
    get_current_provinces
)

# Re-export scenario utilities for API use
from util.scenario import get_scenario_tags

__all__ = [
    # Nodes
    "filter_node",
    "initialize_game_node",
    "historian_node",
    "dreamer_node",
    "geographer_node",
    "quotegiver_node",
    "illustrator_node",
    "parallel_quote_geo_node",
    "update_state_node",
    "should_continue",
    # Memory
    "get_province_memory",
    "reset_province_memory",
    "get_current_provinces",
    # Utilities
    "get_scenario_tags",
]
