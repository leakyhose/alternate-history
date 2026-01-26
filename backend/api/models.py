"""Request and response models for the workflow API."""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class StartRequest(BaseModel):
    """Request to start a new game."""
    command: str
    scenario_id: str
    years_to_progress: int = 15


class StartResponse(BaseModel):
    """Response after starting a game."""
    status: str  # "started" | "rejected"
    game_id: Optional[str] = None
    year: Optional[int] = None
    reason: Optional[str] = None  # If rejected
    alternative: Optional[str] = None  # If rejected
    result: Optional[Dict[str, Any]] = None  # {scenario_id, iteration, nation_tags}


class ContinueRequest(BaseModel):
    """Request to continue an existing game."""
    new_divergences: Optional[List[str]] = None
    years_to_progress: int = 15


class ContinueResponse(BaseModel):
    """Response after continuing a game."""
    status: str  # "iteration_started" | "merged"
    current_year: int
    merged: bool
    logs: List[Dict[str, Any]]  # Empty - frontend gets logs via WebSocket
    result: Optional[Dict[str, Any]] = None  # {iteration, years_to_progress}


class FilterDivergenceRequest(BaseModel):
    """Request to validate a divergence for an existing game."""
    command: str


class FilterDivergenceResponse(BaseModel):
    """Response after validating a divergence."""
    status: str  # "accepted" | "rejected"
    reason: Optional[str] = None
    alternative: Optional[str] = None
