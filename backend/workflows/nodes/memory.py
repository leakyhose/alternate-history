"""Province memory management for workflow nodes."""
from typing import Optional

from util.province_memory import ProvinceMemory


# Global province memory - shared across nodes within a workflow execution
_province_memory: Optional[ProvinceMemory] = None


def get_province_memory() -> ProvinceMemory:
    """Get or create the province memory instance."""
    global _province_memory
    if _province_memory is None:
        _province_memory = ProvinceMemory()
    return _province_memory


def reset_province_memory() -> None:
    """Reset the province memory (for new games)."""
    global _province_memory
    _province_memory = None


def get_current_provinces() -> list:
    """Get current province state as list of dicts (for API responses)."""
    memory = get_province_memory()
    return memory.get_all_provinces_as_dicts()
