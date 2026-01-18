from typing import TypedDict, Optional, Any, List, Dict


class RulerInfo(TypedDict):
    """Information about a ruler."""
    name: str
    title: str
    age: int
    dynasty: str


class LogEntry(TypedDict):
    """A single log entry for the simulation history."""
    year_range: str                    # e.g., "630-650 AD" or "-630 AD" for initial
    narrative: str                     # Human-readable story
    divergences: List[str]             # Divergences active at this point
    territorial_changes_description: str  # Prose describing territorial changes


class HistorianOutput(TypedDict, total=False):
    """Output from the Historian agent."""
    period: str
    real_events: List[str]
    keep_in_mind: List[str]
    conditional_events: List[Dict[str, str]]


class DreamerOutput(TypedDict, total=False):
    """Output from the Dreamer agent."""
    rulers: Dict[str, RulerInfo]
    narrative: str
    territorial_changes_description: str
    updated_divergences: List[str]
    merged: bool


class ProvinceUpdate(TypedDict):
    """A single province update from the Geographer."""
    id: int
    name: str
    owner: str
    control: str


class GeographerOutput(TypedDict):
    """Output from the Geographer agent."""
    province_updates: List[ProvinceUpdate]


class WorkflowState(TypedDict, total=False):
    """Main workflow state for the alternate history simulation."""
    
    # Filter state (from filter node)
    filter_passed: bool             # True if divergence passed filter
    filter_reason: str              # Reason for rejection (if rejected)
    filter_alternative: str         # Alternative suggestion (if rejected)
    
    # Scenario identification
    scenario_id: str                # Which scenario folder to use (e.g., "rome")
    
    # Core simulation parameters
    divergences: List[str]          # Stack of active divergences
    start_year: int                 # Year when divergence begins (user-provided)
    years_to_progress: int          # Years remaining to simulate
    current_year: int               # Year after this iteration completes
    
    # Ruler tracking - Dict keyed by nation tag (supports empire splits)
    # e.g., {"ROM": {...}, "ROM_EAST": {...}}
    rulers: Dict[str, RulerInfo]
    
    # Running history
    logs: List[LogEntry]            # Full logs for frontend display
    condensed_logs: str             # Summarized older logs for agent context
    
    # Inter-agent data (not persisted long-term)
    historian_output: HistorianOutput   # Era events/trends from Historian
    dreamer_output: DreamerOutput       # Changes/decisions from Dreamer
    territorial_changes: List[ProvinceUpdate]  # Changes for Geographer to apply
    
    # Merge state
    merged: bool                    # True if timeline converged back (at current_year)
    
    # Error handling
    error: str                      # Error message if something went wrong
    error_node: str                 # Which node produced the error

