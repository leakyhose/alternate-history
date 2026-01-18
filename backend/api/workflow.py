from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from agents.filter_agent import filter_command
from workflows.graph import workflow, continue_workflow
from workflows.nodes import get_current_provinces, reset_province_memory, get_province_memory, get_scenario_tags
from models.game import (
    Game, create_game, get_game, delete_game, list_games,
    TagInfo, Province
)
from workflows.state import LogEntry, RulerInfo

router = APIRouter(tags=["workflow"])


# Request/Response Models

class StartRequest(BaseModel):
    """Request to start a new game."""
    command: str  # The divergence/what-if scenario
    scenario_id: str  # Which scenario to use (e.g., "rome")
    years_to_progress: int = 20  # Default 20 years per iteration


class StartResponse(BaseModel):
    """Response after starting a game."""
    status: str
    game_id: Optional[str] = None
    year: Optional[int] = None
    reason: Optional[str] = None
    alternative: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class ContinueRequest(BaseModel):
    """Request to continue an existing game."""
    new_divergences: Optional[List[str]] = None  # Optional additional divergences
    years_to_progress: int = 20


class ContinueResponse(BaseModel):
    """Response after continuing a game."""
    status: str
    current_year: int
    merged: bool
    logs: List[Dict[str, Any]]
    result: Optional[Dict[str, Any]] = None


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


# Endpoints

@router.post("/start")
async def start_workflow(request: StartRequest) -> StartResponse:
    """
    Start a new alternate history game.
    
    1. Validate divergence through filter agent
    2. Create new Game
    3. Run first workflow iteration
    4. Return game_id and initial state
    """
    # Step 1: Filter validation
    filter_result = filter_command(request.command)
    
    if filter_result["status"] == "rejected":
        return StartResponse(
            status="rejected",
            reason=filter_result.get("reason"),
            alternative=filter_result.get("alternative")
        )
    
    # Step 2: Extract year and create game
    year = filter_result["year"]
    game = create_game()
    
    # Load nation tags from scenario metadata
    scenario_tags = get_scenario_tags(request.scenario_id)
    for tag, info in scenario_tags.items():
        game.add_nation_tag(tag, info.get("name", tag), info.get("color", "#888888"))
    
    # Step 3: Run workflow
    try:
        initial_state = {
            "divergences": [request.command],
            "scenario_id": request.scenario_id,
            "start_year": year,
            "years_to_progress": request.years_to_progress,
            "filter_passed": True  # Already passed filter
        }
        
        final_state = workflow.invoke(initial_state)
        
        # Update game with final state
        game.workflow_state = dict(final_state)
        
        # Store province state
        provinces = get_current_provinces()
        game.province_state = [
            Province(id=p["id"], name=p["name"], owner=p["owner"], control=p.get("control", ""))
            for p in provinces
        ]
        
        # Sync logs
        game.full_logs = final_state.get("logs", [])
        
    except Exception as e:
        delete_game(game.id)
        raise HTTPException(status_code=500, detail=str(e))
    
    return StartResponse(
        status="accepted",
        game_id=game.id,
        year=year,
        result={
            "current_year": final_state.get("current_year", year),
            "merged": final_state.get("merged", False),
            "rulers": final_state.get("rulers", {}),
            "logs": final_state.get("logs", []),
            "divergences": final_state.get("divergences", [])
        }
    )


@router.post("/continue/{game_id}")
async def continue_game(game_id: str, request: ContinueRequest) -> ContinueResponse:
    """
    Continue an existing game for more iterations.
    
    Optionally add new divergences before continuing.
    """
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if game.is_merged():
        return ContinueResponse(
            status="merged",
            current_year=game.get_current_year(),
            merged=True,
            logs=game.full_logs,
            result={"message": "Timeline has merged back to real history"}
        )
    
    # Prepare state for continuation
    state = dict(game.workflow_state)
    state["years_to_progress"] = request.years_to_progress
    
    # Add new divergences if provided
    if request.new_divergences:
        current_divergences = state.get("divergences", [])
        state["divergences"] = current_divergences + request.new_divergences
    
    # Reload province memory from game state
    # (In case server restarted between requests)
    reset_province_memory()
    memory = get_province_memory()
    if game.province_state:
        for p in game.province_state:
            memory._provinces[p.id] = p
    else:
        memory.load_from_year(state.get("current_year", state.get("start_year", 117)))
    
    try:
        final_state = continue_workflow.invoke(state)
        
        # Update game state
        game.workflow_state = dict(final_state)
        
        # Update province state
        provinces = get_current_provinces()
        game.province_state = [
            Province(id=p["id"], name=p["name"], owner=p["owner"], control=p.get("control", ""))
            for p in provinces
        ]
        
        # Sync logs
        game.full_logs = final_state.get("logs", [])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return ContinueResponse(
        status="continued",
        current_year=final_state.get("current_year", 0),
        merged=final_state.get("merged", False),
        logs=game.full_logs,
        result={
            "rulers": final_state.get("rulers", {}),
            "divergences": final_state.get("divergences", [])
        }
    )


@router.get("/game/{game_id}")
async def get_game_state(game_id: str) -> GameStateResponse:
    """
    Get current state of a game.
    
    Useful for page refresh or reconnecting to a game.
    """
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    state = game.workflow_state
    
    return GameStateResponse(
        id=game.id,
        scenario_id=state.get("scenario_id", "rome"),
        current_year=game.get_current_year(),
        merged=game.is_merged(),
        rulers=state.get("rulers", {}),
        nation_tags={
            tag: {"name": info.name, "color": info.color}
            for tag, info in game.nation_tags.items()
        },
        logs=game.full_logs,
        provinces=[
            {"id": p.id, "name": p.name, "owner": p.owner, "control": p.control}
            for p in game.province_state
        ],
        divergences=state.get("divergences", [])
    )


@router.delete("/game/{game_id}")
async def delete_game_endpoint(game_id: str) -> dict:
    """Delete a game session."""
    if delete_game(game_id):
        return {"status": "deleted", "game_id": game_id}
    raise HTTPException(status_code=404, detail="Game not found")


@router.get("/games")
async def list_games_endpoint(user_id: Optional[str] = None) -> dict:
    """List all games, optionally filtered by user."""
    games = list_games(user_id)
    return {
        "games": [
            {
                "id": g.id,
                "created_at": g.created_at.isoformat(),
                "current_year": g.get_current_year(),
                "merged": g.is_merged()
            }
            for g in games
        ]
    }


# Legacy endpoint for backward compatibility
@router.post("/start-legacy")
async def start_workflow_legacy(request: StartRequest) -> StartResponse:
    """Legacy start endpoint (without game tracking)."""
    filter_result = filter_command(request.command)
    
    if filter_result["status"] == "rejected":
        return StartResponse(
            status="rejected",
            reason=filter_result.get("reason"),
            alternative=filter_result.get("alternative")
        )
    
    year = filter_result["year"]
    
    try:
        final_state = workflow.invoke({
            "divergences": [request.command],
            "scenario_id": request.scenario_id,
            "start_year": year,
            "years_to_progress": request.years_to_progress,
            "filter_passed": True
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return StartResponse(
        status="accepted",
        year=year,
        result={
            "scenario_id": request.scenario_id,
            "current_year": final_state.get("current_year"),
            "merged": final_state.get("merged", False),
            "rulers": final_state.get("rulers", {}),
            "logs": final_state.get("logs", [])
        }
    )
