from typing import TypedDict, Optional, Any, List, Dict


class RulerInfo(TypedDict):
    """Information about a ruler."""
    name: str
    title: str
    age: int
    dynasty: str


class Quote(TypedDict, total=False):
    """A quote from a ruler."""
    tag: str
    ruler_name: str
    ruler_title: str
    quote: str
    portrait_base64: str  # Optional base64-encoded pixel art portrait


class LogEntry(TypedDict):
    """A single log entry for the simulation history."""
    year_range: str                    # e.g., "630-650 AD" or "-630 AD" for initial
    narrative: str                     # Human-readable story
    divergences: List[str]             # Divergences active at this point
    quotes: List[Quote]                # 1-2 quotes from relevant rulers


class WriterOutput(TypedDict, total=False):
    """Output from the Writer agent."""
    narrative: str                     # 100-200 word narrative
    updated_divergences: List[str]     # Divergences still affecting the timeline
    new_divergences: List[str]         # New butterfly effects from this period
    merged: bool                       # True if timeline merged back to real history


class TerritorialChange(TypedDict, total=False):
    """A single structured territorial change from the Cartographer.
    
    These describe NET territorial changes from period START to END,
    not intermediate events during the period.
    
    Change types and required fields:
    - CONQUEST: location, to_nation, context (gained from untracked nation)
    - LOSS: location, from_nation, context (lost to untracked nation)
    - TRANSFER: location, from_nation, to_nation, context (between tracked nations)
    """
    location: str           # VERY SPECIFIC location description for Geographer
    change_type: str        # CONQUEST | LOSS | TRANSFER
    from_nation: str        # Nation losing territory (required for LOSS, TRANSFER)
    to_nation: str          # Nation gaining territory (required for CONQUEST, TRANSFER)
    context: str            # Brief explanation


class CartographerOutput(TypedDict, total=False):
    """Output from the Cartographer agent."""
    territorial_changes: List[TerritorialChange]  # Structured changes for Geographer


class RulerUpdatesOutput(TypedDict, total=False):
    """Output from the Ruler Updates agent."""
    rulers: Dict[str, RulerInfo]  # Updated rulers with ages, deaths, successions


class ProvinceUpdate(TypedDict):
    """A single province update from the Geographer."""
    id: int
    name: str
    owner: str      # Empty string "" means UNTRACKED (lost to non-scenario nation)


class GeographerOutput(TypedDict, total=False):
    """Output from the Geographer agent."""
    province_updates: List[ProvinceUpdate]
    status: str     # Status message for logging only (not processed by workflow)


class QuotegiverOutput(TypedDict):
    """Output from the Quotegiver agent."""
    quotes: List[Quote]


class Portrait(TypedDict, total=False):
    """A portrait of a ruler."""
    tag: str
    ruler_name: str
    portrait_base64: str


class IllustratorOutput(TypedDict):
    """Output from the Illustrator agent."""
    portraits: List[Portrait]
    enriched_quotes: List[Quote]  # Quotes with portrait_base64 field added


class WorkflowState(TypedDict, total=False):
    """Main workflow state for the alternate history simulation."""

    # Game identification (for Kafka events)
    game_id: str                    # Unique identifier for this game session
    iteration: int                  # Current iteration number (1, 2, 3, ...)

    # Filter state (from filter node)
    filter_passed: bool             # True if divergence passed filter
    filter_reason: str              # Reason for rejection (if rejected)
    filter_alternative: str         # Alternative suggestion (if rejected)
    
    # Scenario identification
    scenario_id: str                # Which scenario folder to use (e.g., "rome")
    start_year: int                 # Year when divergence begins (user-provided)
    years_to_progress: int          # Years remaining to simulate
    current_year: int               # Year after this iteration completes

    # Divergences (user-provided alternate history changes)
    divergences: List[str]          # List of divergence commands
    
    # Ruler tracking - Dict keyed by nation tag (supports empire splits)
    # e.g., {"ROM": {...}, "ROM_EAST": {...}}
    rulers: Dict[str, RulerInfo]
    
    # Running history
    logs: List[LogEntry]            # Full logs for frontend display
    condensed_logs: str             # Summarized older logs for agent context
    
    # Inter-agent data (cleared after each iteration)
    # Main pipeline: Writer -> Cartographer -> Ruler Updates
    writer_output: WriterOutput             # Narrative, divergences, merged from Writer
    cartographer_output: CartographerOutput # Territorial changes from Cartographer
    ruler_updates_output: RulerUpdatesOutput # Updated rulers from Ruler Updates
    
    # Microservice outputs (Quotegiver, Geographer, Illustrator)
    territorial_changes: List[ProvinceUpdate]  # Changes for Geographer to apply
    quotegiver_output: QuotegiverOutput # Quotes from the Quotegiver
    illustrator_output: IllustratorOutput  # Portraits from the Illustrator
    
    # Merge state
    merged: bool                    # True if timeline converged back (at current_year)
    
    # Error handling
    error: str                      # Error message if something went wrong
    error_node: str                 # Which node produced the error

