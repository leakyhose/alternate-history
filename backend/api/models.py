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
    status: str
    game_id: Optional[str] = None
    year: Optional[int] = None
    reason: Optional[str] = None
    alternative: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    snapshots: Optional[List[Dict[str, Any]]] = None


class ContinueRequest(BaseModel):
    """Request to continue an existing game."""
    new_divergences: Optional[List[str]] = None
    years_to_progress: int = 15


class ContinueResponse(BaseModel):
    """Response after continuing a game."""
    status: str
    current_year: int
    merged: bool
    logs: List[Dict[str, Any]]
    result: Optional[Dict[str, Any]] = None
    snapshots: Optional[List[Dict[str, Any]]] = None


class GameStateResponse(BaseModel):
    """Full game state for frontend."""
    id: str
    scenario_id: str
    current_year: int
    merged: bool
    rulers: Dict[str, Dict[str, Any]]
    nation_tags: Dict[str, Dict[str, str]]
    logs: List[Dict[str, Any]]
    provinces: List[Dict[str, Any]]
    divergences: List[str]
    snapshots: Optional[List[Dict[str, Any]]] = None


class FilterDivergenceRequest(BaseModel):
    """Request to filter a divergence for an existing game."""
    command: str


class FilterDivergenceResponse(BaseModel):
    """Response after filtering a divergence."""
    status: str
    reason: Optional[str] = None
    alternative: Optional[str] = None


class PortraitStatusResponse(BaseModel):
    """Response for portrait cache status."""
    pending_count: int
    cached_count: int


class PortraitCheckRequest(BaseModel):
    """Request to check/get portraits for specific rulers."""
    rulers: List[Dict[str, str]]


class PortraitCheckResponse(BaseModel):
    """Response with available portraits."""
    portraits: Dict[str, str]
    pending: List[str]
