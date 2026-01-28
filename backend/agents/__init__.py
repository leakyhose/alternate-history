"""Agent modules for the alternate history simulation."""

from agents.filter_agent import filter_command, filter_continuation_divergence
from agents.writer_agent import write_narrative
from agents.cartographer_agent import extract_territorial_changes
from agents.ruler_updates_agent import update_rulers
from agents.geographer_agent import interpret_territorial_changes
from agents.quotegiver_agent import generate_quotes
from agents.illustrator_agent import generate_portraits, enrich_quotes_with_portraits

__all__ = [
    # Filter
    "filter_command",
    "filter_continuation_divergence",
    # Main pipeline: Writer -> Cartographer -> Ruler Updates
    "write_narrative",
    "extract_territorial_changes",
    "update_rulers",
    # Microservices (Quotegiver, Geographer, Illustrator)
    "interpret_territorial_changes",
    "generate_quotes",
    "generate_portraits",
    "enrich_quotes_with_portraits",
]
