"""
Log condensation utilities for managing context window limits.

Strategy:
- Keep last N full log entries (configurable, default 2-3)
- Older entries get summarized into a condensed string
- Triggered when logs array exceeds threshold (configurable, default 5-10)
"""
from typing import List, Tuple
from workflows.state import LogEntry


# Configuration
DEFAULT_KEEP_FULL_LOGS = 3  # Number of recent logs to keep in full
DEFAULT_CONDENSE_THRESHOLD = 6  # Condense when logs exceed this count


def should_condense(
    logs: List[LogEntry],
    threshold: int = DEFAULT_CONDENSE_THRESHOLD
) -> bool:
    """
    Check if logs should be condensed.
    
    Args:
        logs: Current list of log entries
        threshold: Number of logs that triggers condensation
        
    Returns:
        True if condensation is needed
    """
    return len(logs) > threshold


def condense_logs(
    logs: List[LogEntry],
    existing_condensed: str = "",
    keep_full: int = DEFAULT_KEEP_FULL_LOGS
) -> Tuple[List[LogEntry], str]:
    """
    Condense older log entries into a summary string.
    
    This is a simple implementation that creates a text summary.
    In the future, this could use an LLM for better summarization.
    
    Args:
        logs: Current list of log entries
        existing_condensed: Previously condensed log summary
        keep_full: Number of recent logs to keep in full
        
    Returns:
        Tuple of (remaining_full_logs, new_condensed_summary)
    """
    if len(logs) <= keep_full:
        return logs, existing_condensed
    
    # Split logs: older ones to condense, recent ones to keep
    logs_to_condense = logs[:-keep_full]
    logs_to_keep = logs[-keep_full:]
    
    # Build summary of older logs
    summaries = []
    
    # Add existing condensed history first
    if existing_condensed:
        summaries.append(existing_condensed)
        summaries.append("")  # Blank line separator
    
    # Condense each older log
    for log in logs_to_condense:
        year_range = log.get("year_range", "Unknown period")
        narrative = log.get("narrative", "")
        divergences = log.get("divergences", [])
        
        # Create a brief summary
        # Take first 200 chars of narrative
        brief_narrative = narrative[:200]
        if len(narrative) > 200:
            brief_narrative += "..."
        
        summary_parts = [f"[{year_range}]"]
        if brief_narrative:
            summary_parts.append(brief_narrative)
        if divergences:
            summary_parts.append(f"Active divergences: {', '.join(divergences)}")
        
        summaries.append(" ".join(summary_parts))
    
    new_condensed = "\n\n".join(summaries)
    
    return logs_to_keep, new_condensed


def create_context_for_agents(
    logs: List[LogEntry],
    condensed_logs: str,
    max_recent_logs: int = 3
) -> dict:
    """
    Create context package for agent consumption.
    
    Args:
        logs: Current full log entries
        condensed_logs: Summarized older history
        max_recent_logs: Maximum recent logs to include in full
        
    Returns:
        Dict with 'condensed_history' and 'recent_logs' keys
    """
    recent_logs = logs[-max_recent_logs:] if logs else []
    
    return {
        "condensed_history": condensed_logs or "No prior history.",
        "recent_logs": recent_logs
    }


def format_condensed_for_prompt(condensed_logs: str) -> str:
    """
    Format condensed logs for inclusion in an agent prompt.
    
    Args:
        condensed_logs: The condensed log summary
        
    Returns:
        Formatted string suitable for prompt inclusion
    """
    if not condensed_logs:
        return "This is the beginning of the alternate history."
    
    return f"""Previous History Summary:
---
{condensed_logs}
---"""


def format_recent_logs_for_prompt(logs: List[LogEntry], max_logs: int = 3) -> str:
    """
    Format recent log entries for inclusion in an agent prompt.
    
    Args:
        logs: List of log entries
        max_logs: Maximum number of recent logs to include
        
    Returns:
        Formatted string suitable for prompt inclusion
    """
    if not logs:
        return "No recent events recorded yet."
    
    recent = logs[-max_logs:]
    formatted_entries = []
    
    for log in recent:
        entry = f"""
Period: {log.get('year_range', 'Unknown')}
{log.get('narrative', 'No narrative.')}

Active Divergences: {', '.join(log.get('divergences', [])) or 'None'}
"""
        formatted_entries.append(entry.strip())
    
    return "\n\n---\n\n".join(formatted_entries)


def estimate_token_count(text: str) -> int:
    """
    Rough estimate of token count for a text.
    Uses simple heuristic: ~4 characters per token on average.
    
    Args:
        text: The text to estimate
        
    Returns:
        Estimated token count
    """
    return len(text) // 4


def check_context_budget(
    condensed_logs: str,
    logs: List[LogEntry],
    max_tokens: int = 8000
) -> dict:
    """
    Check if current logs fit within context budget.
    
    Args:
        condensed_logs: Summarized older history
        logs: Current full log entries
        max_tokens: Maximum tokens for log context
        
    Returns:
        Dict with 'within_budget', 'estimated_tokens', and 'recommendation'
    """
    # Estimate token usage
    condensed_tokens = estimate_token_count(condensed_logs or "")
    
    logs_text = ""
    for log in logs:
        logs_text += log.get("narrative", "")
    logs_tokens = estimate_token_count(logs_text)
    
    total_tokens = condensed_tokens + logs_tokens
    
    within_budget = total_tokens <= max_tokens
    recommendation = None
    
    if not within_budget:
        if len(logs) > DEFAULT_KEEP_FULL_LOGS:
            recommendation = "Consider condensing older logs"
        else:
            recommendation = "Consider using more aggressive summarization"
    
    return {
        "within_budget": within_budget,
        "estimated_tokens": total_tokens,
        "condensed_tokens": condensed_tokens,
        "logs_tokens": logs_tokens,
        "recommendation": recommendation
    }
