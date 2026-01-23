"""Workflow API endpoints for alternate history simulation."""
import json
import asyncio
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.models import (
    StartRequest, StartResponse, ContinueRequest, ContinueResponse,
    GameStateResponse, FilterDivergenceRequest, FilterDivergenceResponse,
    PortraitStatusResponse, PortraitCheckRequest, PortraitCheckResponse
)
from api.serializers import serialize_logs, serialize_rulers, serialize_provinces, safe_int
from agents.filter_agent import filter_command, filter_continuation_divergence
from workflows.graph import workflow, continue_workflow
from workflows.nodes import (
    get_current_provinces, reset_province_memory, get_province_memory, get_scenario_tags,
    initialize_game_node, historian_node, dreamer_node, geographer_node,
    quotegiver_node, illustrator_node, update_state_node
)
from util.scenario import load_scenario_metadata
from util.province_memory import ProvinceMemory, Province as MemoryProvince
from models.game import Game, create_game, get_game, delete_game, list_games, Province
from workflows.nodes.initialize import _load_rulers_for_year

router = APIRouter(tags=["workflow"])


def _create_province_list(provinces_data):
    """Convert province dicts to Province objects."""
    return [
        Province(
            id=p["id"], name=p["name"],
            owner=p["owner"], control=p.get("control", "")
        )
        for p in provinces_data
    ]


def _load_initial_state(year: int, scenario_id: str):
    """Load initial province state and rulers for a given year."""
    memory = ProvinceMemory()
    memory.load_from_year(year, scenario_id)
    provinces = _create_province_list(memory.get_all_provinces_as_dicts())
    rulers = _load_rulers_for_year(year, scenario_id)
    return provinces, rulers


def _setup_game_tags(game: Game, scenario_id: str):
    """Load nation tags from scenario metadata into game."""
    scenario_tags = get_scenario_tags(scenario_id)
    for tag, info in scenario_tags.items():
        game.add_nation_tag(tag, info.get("name", tag), info.get("color", "#888888"))


def _capture_snapshots(game: Game, logs, initial_provinces, initial_rulers,
                       current_provinces, current_rulers, divergences):
    """Capture province snapshots for timeline scrubbing."""
    if len(logs) > 0:
        game.capture_snapshot(initial_provinces, initial_rulers, divergences)
    for _ in range(1, len(logs)):
        game.capture_snapshot(current_provinces, current_rulers, divergences)


def _reload_province_memory(game: Game, state: dict):
    """Reload province memory from game state."""
    reset_province_memory()
    memory = get_province_memory()
    if game.province_state:
        for p in game.province_state:
            memory._provinces[p.id] = MemoryProvince(
                id=p.id, name=p.name, owner=p.owner, control=p.control
            )
    else:
        year = state.get("current_year", state.get("start_year", 117))
        memory.load_from_year(year)


# Main endpoints

@router.post("/start")
async def start_workflow(request: StartRequest) -> StartResponse:
    """Start a new alternate history game."""
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
        initial_provinces, initial_rulers = _load_initial_state(year, request.scenario_id)

        final_state = workflow.invoke({
            "divergences": [request.command],
            "scenario_id": request.scenario_id,
            "start_year": year,
            "years_to_progress": request.years_to_progress,
            "filter_passed": True
        })

        game.workflow_state = dict(final_state)
        provinces = get_current_provinces()
        game.province_state = _create_province_list(provinces)
        game.full_logs = final_state.get("logs", [])

        logs = final_state.get("logs", [])
        rulers = final_state.get("rulers", {})
        divergences = final_state.get("divergences", [])
        _capture_snapshots(game, logs, initial_provinces, initial_rulers,
                          game.province_state, rulers, divergences)

    except Exception as e:
        import traceback
        print(f"Workflow error: {e}")
        traceback.print_exc()
        delete_game(game.id)
        raise HTTPException(status_code=500, detail=str(e))

    return StartResponse(
        status="accepted",
        game_id=game.id,
        year=year,
        result={
            "current_year": int(final_state.get("current_year", year)),
            "merged": bool(final_state.get("merged", False)),
            "rulers": serialize_rulers(final_state.get("rulers", {})),
            "logs": serialize_logs(game.full_logs),
            "divergences": list(final_state.get("divergences", []))
        },
        snapshots=game.get_all_snapshots_as_dicts()
    )


@router.post("/start-stream")
async def start_workflow_stream(request: StartRequest):
    """Start a new game with SSE streaming for progressive updates."""
    async def event_generator() -> AsyncGenerator[str, None]:
        game = None
        try:
            scenario_metadata = load_scenario_metadata(request.scenario_id)
            filter_result = filter_command(request.command, scenario_metadata)

            if filter_result["status"] == "rejected":
                yield f"data: {json.dumps({'event': 'rejected', 'reason': filter_result.get('reason'), 'alternative': filter_result.get('alternative')})}\n\n"
                return

            year = filter_result["year"]
            game = create_game()
            _setup_game_tags(game, request.scenario_id)

            yield f"data: {json.dumps({'event': 'filter_complete', 'year': year, 'game_id': game.id, 'nation_tags': {tag: {'name': info.name, 'color': info.color} for tag, info in game.nation_tags.items()}})}\n\n"
            await asyncio.sleep(0.1)

            initial_provinces, initial_rulers = _load_initial_state(year, request.scenario_id)

            state = {
                "divergences": [request.command],
                "scenario_id": request.scenario_id,
                "start_year": year,
                "years_to_progress": request.years_to_progress,
                "filter_passed": True
            }

            # Run nodes sequentially with streaming updates
            state.update(initialize_game_node(state))
            state.update(historian_node(state))
            state.update(dreamer_node(state))

            dreamer_output = state.get("dreamer_output", {})
            current_year = state.get("current_year", year)
            years = state.get("years_to_progress", 20)

            log_entry = {
                "year_range": f"{current_year}-{current_year + years} AD",
                "narrative": dreamer_output.get("narrative", ""),
                "divergences": dreamer_output.get("updated_divergences", []),
                "territorial_changes_summary": dreamer_output.get("territorial_changes_summary", ""),
                "quotes": []
            }

            yield f"data: {json.dumps({'event': 'dreamer_complete', 'log_entry': log_entry, 'rulers': serialize_rulers(dreamer_output.get('rulers', {})), 'divergences': dreamer_output.get('updated_divergences', []), 'year_range': f'{current_year}-{current_year + years} AD'})}\n\n"
            await asyncio.sleep(0.1)

            state.update(quotegiver_node(state))
            quotes = state.get("quotegiver_output", {}).get("quotes", [])
            yield f"data: {json.dumps({'event': 'quotegiver_complete', 'quotes': quotes})}\n\n"
            await asyncio.sleep(0.1)

            state.update(illustrator_node(state))
            enriched_quotes = state.get("illustrator_output", {}).get("enriched_quotes", quotes)
            yield f"data: {json.dumps({'event': 'illustrator_complete', 'quotes': enriched_quotes})}\n\n"
            await asyncio.sleep(0.1)

            state.update(geographer_node(state))
            state.update(update_state_node(state))
            provinces = get_current_provinces()
            yield f"data: {json.dumps({'event': 'geographer_complete', 'provinces': provinces})}\n\n"
            await asyncio.sleep(0.1)

            # Update game state
            game.workflow_state = dict(state)
            game.province_state = _create_province_list(provinces)
            game.full_logs = state.get("logs", [])

            logs = state.get("logs", [])
            rulers = state.get("rulers", {})
            divergences = state.get("divergences", [])
            _capture_snapshots(game, logs, initial_provinces, initial_rulers,
                              game.province_state, rulers, divergences)

            yield f"data: {json.dumps({'event': 'complete', 'game_id': game.id, 'current_year': int(state.get('current_year', year)), 'merged': bool(state.get('merged', False)), 'logs': serialize_logs(game.full_logs), 'rulers': serialize_rulers(state.get('rulers', {})), 'divergences': list(state.get('divergences', [])), 'snapshots': game.get_all_snapshots_as_dicts()})}\n\n"

        except Exception as e:
            import traceback
            print(f"Streaming workflow error: {e}")
            traceback.print_exc()
            if game:
                delete_game(game.id)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.post("/continue-stream/{game_id}")
async def continue_game_stream(game_id: str, request: ContinueRequest):
    """Continue an existing game with SSE streaming."""
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            game = get_game(game_id)
            if not game:
                yield f"data: {json.dumps({'event': 'error', 'message': 'Game not found'})}\n\n"
                return

            if game.is_merged():
                yield f"data: {json.dumps({'event': 'error', 'message': 'Timeline has merged back to real history'})}\n\n"
                return

            state = dict(game.workflow_state)
            state["years_to_progress"] = request.years_to_progress
            if request.new_divergences:
                state["divergences"] = state.get("divergences", []) + request.new_divergences

            _reload_province_memory(game, state)

            current_year = state.get("current_year", state.get("start_year"))
            years = state.get("years_to_progress", 20)

            state.update(historian_node(state))
            state.update(dreamer_node(state))

            dreamer_output = state.get("dreamer_output", {})
            log_entry = {
                "year_range": f"{current_year}-{current_year + years} AD",
                "narrative": dreamer_output.get("narrative", ""),
                "divergences": dreamer_output.get("updated_divergences", []),
                "territorial_changes_summary": dreamer_output.get("territorial_changes_summary", ""),
                "quotes": []
            }

            yield f"data: {json.dumps({'event': 'dreamer_complete', 'log_entry': log_entry, 'rulers': serialize_rulers(dreamer_output.get('rulers', {})), 'divergences': dreamer_output.get('updated_divergences', []), 'year_range': f'{current_year}-{current_year + years} AD'})}\n\n"
            await asyncio.sleep(0.1)

            state.update(quotegiver_node(state))
            quotes = state.get("quotegiver_output", {}).get("quotes", [])
            yield f"data: {json.dumps({'event': 'quotegiver_complete', 'quotes': quotes})}\n\n"
            await asyncio.sleep(0.1)

            state.update(illustrator_node(state))
            enriched_quotes = state.get("illustrator_output", {}).get("enriched_quotes", quotes)
            yield f"data: {json.dumps({'event': 'illustrator_complete', 'quotes': enriched_quotes})}\n\n"
            await asyncio.sleep(0.1)

            state.update(geographer_node(state))
            state.update(update_state_node(state))
            provinces = get_current_provinces()
            yield f"data: {json.dumps({'event': 'geographer_complete', 'provinces': provinces})}\n\n"
            await asyncio.sleep(0.1)

            # Update game state
            game.workflow_state = dict(state)
            game.province_state = _create_province_list(provinces)

            workflow_logs = state.get("logs", [])
            if workflow_logs:
                game.full_logs.append(workflow_logs[-1])

            rulers = state.get("rulers", {})
            divergences = state.get("divergences", [])
            game.capture_snapshot(game.province_state, rulers, divergences)

            yield f"data: {json.dumps({'event': 'complete', 'game_id': game.id, 'current_year': int(state.get('current_year', 0)), 'merged': bool(state.get('merged', False)), 'logs': serialize_logs(game.full_logs), 'rulers': serialize_rulers(state.get('rulers', {})), 'divergences': list(state.get('divergences', [])), 'snapshots': game.get_all_snapshots_as_dicts()})}\n\n"

        except Exception as e:
            import traceback
            print(f"Continue streaming error: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.post("/game/{game_id}/filter-divergence")
async def filter_game_divergence(game_id: str, request: FilterDivergenceRequest) -> FilterDivergenceResponse:
    """Filter a divergence for an existing game."""
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


@router.post("/continue/{game_id}")
async def continue_game(game_id: str, request: ContinueRequest) -> ContinueResponse:
    """Continue an existing game for more iterations."""
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

    state = dict(game.workflow_state)
    state["years_to_progress"] = request.years_to_progress
    if request.new_divergences:
        state["divergences"] = state.get("divergences", []) + request.new_divergences

    _reload_province_memory(game, state)

    try:
        final_state = continue_workflow.invoke(state)
        game.workflow_state = dict(final_state)

        provinces = get_current_provinces()
        game.province_state = _create_province_list(provinces)

        workflow_logs = final_state.get("logs", [])
        if workflow_logs:
            game.full_logs.append(workflow_logs[-1])

        rulers = final_state.get("rulers", {})
        divergences = final_state.get("divergences", [])
        game.capture_snapshot(game.province_state, rulers, divergences)

    except Exception as e:
        import traceback
        print(f"Continue workflow error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    return ContinueResponse(
        status="continued",
        current_year=int(final_state.get("current_year", 0)),
        merged=bool(final_state.get("merged", False)),
        logs=serialize_logs(game.full_logs),
        result={
            "rulers": serialize_rulers(final_state.get("rulers", {})),
            "divergences": list(final_state.get("divergences", []))
        },
        snapshots=game.get_all_snapshots_as_dicts()
    )


@router.get("/game/{game_id}")
async def get_game_state(game_id: str) -> GameStateResponse:
    """Get current state of a game."""
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    state = game.workflow_state
    return GameStateResponse(
        id=game.id,
        scenario_id=state.get("scenario_id", "rome"),
        current_year=game.get_current_year(),
        merged=game.is_merged(),
        rulers=serialize_rulers(state.get("rulers", {})),
        nation_tags={
            tag: {"name": info.name, "color": info.color}
            for tag, info in game.nation_tags.items()
        },
        logs=serialize_logs(game.full_logs),
        provinces=serialize_provinces(game.province_state),
        divergences=list(state.get("divergences", [])),
        snapshots=game.get_all_snapshots_as_dicts()
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
                "merged": g.is_merged(),
                "scenario_id": g.workflow_state.get("scenario_id", "rome")
            }
            for g in games
        ]
    }


@router.get("/game/{game_id}/provinces")
async def get_game_provinces(game_id: str) -> dict:
    """Get current province state for a game."""
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return {
        "game_id": game_id,
        "current_year": game.get_current_year(),
        "provinces": serialize_provinces(game.province_state)
    }


@router.get("/game/{game_id}/logs")
async def get_game_logs(game_id: str, limit: Optional[int] = None) -> dict:
    """Get logs for a game."""
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    logs = game.full_logs[-limit:] if limit and limit > 0 else game.full_logs
    return {
        "game_id": game_id,
        "total_logs": len(game.full_logs),
        "logs": logs
    }


@router.get("/game/{game_id}/rulers")
async def get_game_rulers(game_id: str) -> dict:
    """Get current rulers for a game."""
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return {
        "game_id": game_id,
        "current_year": game.get_current_year(),
        "rulers": game.workflow_state.get("rulers", {}),
        "nation_tags": {
            tag: {"name": info.name, "color": info.color}
            for tag, info in game.nation_tags.items()
        }
    }


# Portrait endpoints

@router.get("/portraits/status")
async def get_portrait_status() -> PortraitStatusResponse:
    """Get the current portrait cache status."""
    from util.portrait_cache import get_pending_count, get_all_cached_portraits
    cached_portraits = get_all_cached_portraits()
    return PortraitStatusResponse(
        pending_count=get_pending_count(),
        cached_count=len(cached_portraits)
    )


@router.post("/portraits/check")
async def check_portraits(request: PortraitCheckRequest) -> PortraitCheckResponse:
    """Check if portraits are available for specific rulers."""
    from util.portrait_cache import get_cached_portrait, is_portrait_pending, _make_cache_key

    portraits = {}
    pending = []

    for ruler in request.rulers:
        ruler_name = ruler.get("ruler_name", "")
        nation_name = ruler.get("nation_name", "")
        era_context = ruler.get("era_context", "")

        if not ruler_name or not nation_name:
            continue

        cache_key = _make_cache_key(ruler_name, nation_name, era_context)
        portrait = get_cached_portrait(ruler_name, nation_name, era_context)

        if portrait:
            portraits[cache_key] = portrait
        elif is_portrait_pending(ruler_name, nation_name, era_context):
            pending.append(cache_key)

    return PortraitCheckResponse(portraits=portraits, pending=pending)


# Legacy endpoint

@router.post("/start-legacy")
async def start_workflow_legacy(request: StartRequest) -> StartResponse:
    """Legacy start endpoint (without game tracking)."""
    scenario_metadata = load_scenario_metadata(request.scenario_id)
    filter_result = filter_command(request.command, scenario_metadata)

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
