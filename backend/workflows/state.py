from typing import TypedDict, Optional, Any, List, Dict


class RulerInfo(TypedDict):
    """Information about a ruler."""
    name: str
    title: str
    age: int
    dynasty: str


class Quote(TypedDict):
    """A quote from a ruler."""
    tag: str
    ruler_name: str
    ruler_title: str
    quote: str


class LogEntry(TypedDict):
    """A single log entry for the simulation history."""
    year_range: str                    # e.g., "630-650 AD" or "-630 AD" for initial
    narrative: str                     # Human-readable story
    divergences: List[str]             # Divergences active at this point
    territorial_changes_summary: str   # Prose summary of territorial changes (for display)
    quotes: List[Quote]                # 1-2 quotes from relevant rulers


class HistorianOutput(TypedDict, total=False):
    """Output from the Historian agent."""
    period: str
    real_events: List[str]
    keep_in_mind: List[str]
    conditional_events: List[Dict[str, str]]


class TerritorialChange(TypedDict, total=False):
    """A single structured territorial change from the Dreamer.
    
    These describe NET territorial changes from period START to END,
    not intermediate events during the period.
    """
    location: str           # Natural language description of WHERE
    change_type: str        # CONQUEST | LOSS | TRANSFER
    from_nation: str        # Nation losing territory (optional)
    to_nation: str          # Nation gaining territory (optional)
    context: str            # Brief explanation (optional)


class DreamerOutput(TypedDict, total=False):
    """Output from the Dreamer agent."""
    rulers: Dict[str, RulerInfo]
    narrative: str
    territorial_changes: List[TerritorialChange]  # Structured changes for Geographer
    territorial_changes_summary: str              # Human-readable summary for display
    updated_divergences: List[str]
    merged: bool


class ProvinceUpdate(TypedDict):
    """A single province update from the Geographer."""
    id: int
    name: str
    owner: str      # Empty string "" means UNTRACKED (lost to non-scenario nation)


class GeographerOutput(TypedDict):
    """Output from the Geographer agent."""
    province_updates: List[ProvinceUpdate]


class QuotegiverOutput(TypedDict):
    """Output from the Quotegiver agent."""
    quotes: List[Quote]


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
    quotegiver_output: QuotegiverOutput # Quotes from the Quotegiver
    
    # Merge state
    merged: bool                    # True if timeline converged back (at current_year)
    
    # Error handling
    error: str                      # Error message if something went wrong
    error_node: str                 # Which node produced the error

