"""Serialization helpers for API responses."""
from typing import Dict, List, Any


def safe_int(value, default=0) -> int:
    """Safely convert a value to int, handling empty strings and None."""
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def serialize_log(log: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a log entry to a JSON-serializable dict."""
    return {
        "year_range": str(log.get("year_range", "")),
        "narrative": str(log.get("narrative", "")),
        "divergences": list(log.get("divergences", [])),
        "quotes": list(log.get("quotes", []))
    }


def serialize_logs(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert a list of log entries to JSON-serializable format."""
    return [serialize_log(log) for log in logs]


def serialize_ruler(ruler: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a ruler dict to a JSON-serializable format."""
    return {
        "name": str(ruler.get("name", "")),
        "title": str(ruler.get("title", "")),
        "age": safe_int(ruler.get("age"), 0),
        "dynasty": str(ruler.get("dynasty", ""))
    }


def serialize_rulers(rulers: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Convert rulers dict to JSON-serializable format."""
    return {str(tag): serialize_ruler(ruler) for tag, ruler in rulers.items()}


def serialize_province(province) -> Dict[str, Any]:
    """Convert a province object or dict to JSON-serializable format."""
    if hasattr(province, 'id'):
        # Province object
        return {
            "id": province.id,
            "name": province.name,
            "owner": province.owner,
            "control": province.control
        }
    # Already a dict
    return {
        "id": province.get("id"),
        "name": province.get("name"),
        "owner": province.get("owner"),
        "control": province.get("control", "")
    }


def serialize_provinces(provinces: List) -> List[Dict[str, Any]]:
    """Convert a list of provinces to JSON-serializable format."""
    return [serialize_province(p) for p in provinces]


def build_log_entry(
    year_range: str,
    narrative: str,
    divergences: List[str],
    quotes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a log entry dict for the simulation history."""
    return {
        "year_range": year_range,
        "narrative": narrative,
        "divergences": divergences,
        "quotes": quotes,
    }


def build_province_snapshots(
    logs: List[Dict[str, Any]],
    provinces: List[Dict[str, Any]],
    rulers: Dict[str, Dict[str, Any]],
    divergences: List[str],
) -> List[Dict[str, Any]]:
    """Build province snapshots for timeline navigation.
    
    Each snapshot captures the state at a particular log entry.
    For now, we just have one snapshot per log (the latest state).
    In the future, we could track intermediate states.
    """
    snapshots = []
    for i, log in enumerate(logs):
        snapshots.append({
            "log_index": i,
            "year_range": log.get("year_range", ""),
            "provinces": serialize_provinces(provinces),
            "rulers": serialize_rulers(rulers),
            "divergences": divergences,
        })
    return snapshots
