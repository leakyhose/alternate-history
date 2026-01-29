"""Workflow API endpoints for alternate history simulation."""
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.models import (
    StartRequest, StartResponse, ContinueRequest, ContinueResponse,
    FilterDivergenceRequest, FilterDivergenceResponse,
)
from agents.filter_agent import filter_command, filter_continuation_divergence
from workflows.graph import workflow, continue_workflow
from workflows.nodes import get_scenario_tags
from util.scenario import load_scenario_metadata
from models.game import Game, create_game, get_game, delete_game, list_games

router = APIRouter(tags=["workflow"])


def _setup_game_tags(game: Game, scenario_id: str):
    """Load nation tags from scenario metadata into game."""
    scenario_tags = get_scenario_tags(scenario_id)
    for tag, info in scenario_tags.items():
        game.add_nation_tag(tag, info.get("name", tag), info.get("color", "#888888"))


@router.post("/start")
async def start_workflow(request: StartRequest) -> StartResponse:
    """Start a new alternate history game. Publishes to Kafka."""
    scenario_metadata = load_scenario_metadata(request.scenario_id)
    filter_result = filter_command(request.command, scenario_metadata)

    if filter_result["status"] == "rejected":
        return StartResponse(
            status="rejected",
            reason=filter_result.get("reason"),
            alternative=filter_result.get("alternative")
        )

    year = filter_result["year"]
    game = create_game()
    _setup_game_tags(game, request.scenario_id)

    try:
        final_state = workflow.invoke({
            "game_id": game.id,
            "iteration": 1,
            "divergences": [request.command],
            "scenario_id": request.scenario_id,
            "start_year": year,
            "years_to_progress": request.years_to_progress,
            "filter_passed": True
        })

        game.workflow_state = dict(final_state)
        game.workflow_state["scenario_id"] = request.scenario_id

    except Exception as e:
        import traceback
        print(f"Workflow error: {e}")
        traceback.print_exc()
        delete_game(game.id)
        raise HTTPException(status_code=500, detail=str(e))

    # Return enough data for frontend to create the timeline branch
    return StartResponse(
        status="started",
        game_id=game.id,
        year=year,
        result={
            "scenario_id": request.scenario_id,
            "iteration": 1,
            "current_year": final_state.get("current_year", year),
            "nation_tags": {tag: {"name": info["name"], "color": info["color"]} for tag, info in game.nation_tags.items()},
            "divergences": [request.command],
            "merged": final_state.get("merged", False),
            # Empty placeholders - WebSocket will fill these in
            "logs": [],
            "rulers": {},
            "provinces": [],
            "snapshots": [],
        }
    )


@router.post("/continue/{game_id}")
async def continue_game(game_id: str, request: ContinueRequest) -> ContinueResponse:
    """Continue an existing game. Publishes to Kafka."""
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.is_merged():
        return ContinueResponse(
            status="merged",
            current_year=game.get_current_year(),
            merged=True,
            logs=[],
            result={"message": "Timeline has merged back to real history"}
        )

    state = dict(game.workflow_state)
    state["game_id"] = game_id
    state["years_to_progress"] = request.years_to_progress
    if request.new_divergences:
        state["divergences"] = state.get("divergences", []) + request.new_divergences

    try:
        final_state = continue_workflow.invoke(state)
        game.workflow_state = dict(final_state)

        current_year = final_state.get("current_year", state.get("current_year", 0))
        iteration = final_state.get("iteration", 1)
        merged = final_state.get("merged", False)

    except Exception as e:
        import traceback
        print(f"Continue workflow error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    return ContinueResponse(
        status="iteration_complete",
        current_year=current_year,
        merged=merged,
        logs=[],
        result={
            "iteration": iteration,
            "message": "Timeline event published to Kafka. Await WebSocket for full state."
        }
    )


@router.post("/game/{game_id}/filter-divergence")
async def filter_game_divergence(game_id: str, request: FilterDivergenceRequest) -> FilterDivergenceResponse:
    """Validate a divergence command before adding via /continue."""
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.is_merged():
        return FilterDivergenceResponse(
            status="rejected",
            reason="Timeline has merged back to real history",
            alternative="Start a new alternate timeline"
        )

    scenario_id = game.workflow_state.get("scenario_id", "rome")
    scenario_metadata = load_scenario_metadata(scenario_id)
    filter_result = filter_continuation_divergence(
        request.command, game.get_current_year(), scenario_metadata
    )

    return FilterDivergenceResponse(
        status=filter_result.get("status", "rejected"),
        reason=filter_result.get("reason"),
        alternative=filter_result.get("alternative")
    )


@router.delete("/game/{game_id}")
async def delete_game_endpoint(game_id: str) -> dict:
    """Delete a game session (cleanup)."""
    if delete_game(game_id):
        return {"status": "deleted", "game_id": game_id}
    raise HTTPException(status_code=404, detail="Game not found")


@router.get("/games")
async def list_games_endpoint(user_id: Optional[str] = None) -> dict:
    """List all active games (for debugging/admin)."""
    games = list_games(user_id)
    return {
        "games": [
            {
                "id": g.id,
                "created_at": g.created_at.isoformat(),
                "scenario_id": g.workflow_state.get("scenario_id", "rome")
            }
            for g in games
        ]
    }
