import json
import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, AsyncGenerator

from agents.filter_agent import filter_command, filter_continuation_divergence
from workflows.graph import workflow, continue_workflow
from workflows.nodes import (
    get_current_provinces, reset_province_memory, get_province_memory, get_scenario_tags,
    initialize_game_node, historian_node, dreamer_node, geographer_node, quotegiver_node, illustrator_node, update_state_node
)
from util.scenario import load_scenario_metadata
from models.game import (
    Game, create_game, get_game, delete_game, list_games,
    TagInfo, Province
)
from util.province_memory import Province as MemoryProvince
from workflows.state import LogEntry, RulerInfo

router = APIRouter(tags=["workflow"])

def safe_int(value, default=0):
    """Safely convert a value to int, handling empty strings and None."""
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# Request/Response Models

class StartRequest(BaseModel):
    """Request to start a new game."""
    command: str  # The divergence/what-if scenario
    scenario_id: str  # Which scenario to use (e.g., "rome")
    years_to_progress: int = 15  # Default 15 years per iteration


class StartResponse(BaseModel):
    """Response after starting a game."""
    status: str
    game_id: Optional[str] = None
    year: Optional[int] = None
    reason: Optional[str] = None
    alternative: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    snapshots: Optional[List[Dict[str, Any]]] = None  # Province snapshots per log entry


class ContinueRequest(BaseModel):
    """Request to continue an existing game."""
    new_divergences: Optional[List[str]] = None  # Optional additional divergences
    years_to_progress: int = 15


class ContinueResponse(BaseModel):
    """Response after continuing a game."""
    status: str
    current_year: int
    merged: bool
    logs: List[Dict[str, Any]]
    result: Optional[Dict[str, Any]] = None
    snapshots: Optional[List[Dict[str, Any]]] = None  # Province snapshots per log entry


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
    snapshots: Optional[List[Dict[str, Any]]] = None  # Province snapshots per log entry


class FilterDivergenceRequest(BaseModel):
    """Request to filter a divergence for an existing game."""
    command: str  # The divergence to filter


class FilterDivergenceResponse(BaseModel):
    """Response after filtering a divergence."""
    status: str  # 'accepted' or 'rejected'
    reason: Optional[str] = None
    alternative: Optional[str] = None


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
    # Load scenario metadata for filter validation
    scenario_metadata = load_scenario_metadata(request.scenario_id)
    
    # Step 1: Filter validation with scenario metadata
    filter_result = filter_command(request.command, scenario_metadata)
    
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
        
        # Capture initial province state BEFORE workflow runs (for Log 0)
        # Load provinces from scenario data for the start year
        from util.province_memory import ProvinceMemory
        initial_memory = ProvinceMemory()
        initial_memory.load_from_year(year, request.scenario_id)
        initial_provinces = [
            Province(id=p["id"], name=p["name"], owner=p["owner"], control=p.get("control", ""))
            for p in initial_memory.get_all_provinces_as_dicts()
        ]
        
        # Load initial rulers
        from workflows.nodes.initialize import _load_rulers_for_year
        initial_rulers = _load_rulers_for_year(year, request.scenario_id)
        
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
        
        # Capture snapshots for timeline scrubbing
        logs = final_state.get("logs", [])
        rulers = final_state.get("rulers", {})
        divergences = final_state.get("divergences", [])
        
        # Log 0 (initial/historical): use the initial province state before any changes
        if len(logs) > 0:
            game.capture_snapshot(initial_provinces, initial_rulers, divergences)
        
        # Log 1+ (after iterations): use the current province state
        # For initial workflow, there's only Log 0 (initial) and Log 1 (first iteration)
        for i in range(1, len(logs)):
            game.capture_snapshot(game.province_state, rulers, divergences)
        
    except Exception as e:
        import traceback
        print(f"❌ Workflow error: {e}")
        traceback.print_exc()
        delete_game(game.id)
        raise HTTPException(status_code=500, detail=str(e))
    
    # Build response with explicit type handling
    try:
        # Ensure logs are serializable - use game.full_logs for complete history
        serializable_logs = []
        for log in game.full_logs:
            serializable_logs.append({
                "year_range": str(log.get("year_range", "")),
                "narrative": str(log.get("narrative", "")),
                "divergences": list(log.get("divergences", [])),
                "territorial_changes_summary": str(log.get("territorial_changes_summary", log.get("territorial_changes_description", ""))),
                "quotes": list(log.get("quotes", []))
            })
        
        # Ensure rulers are serializable
        rulers = final_state.get("rulers", {})
        serializable_rulers = {}
        for tag, ruler in rulers.items():
            serializable_rulers[str(tag)] = {
                "name": str(ruler.get("name", "")),
                "title": str(ruler.get("title", "")),
                "age": safe_int(ruler.get("age"), 0),
                "dynasty": str(ruler.get("dynasty", ""))
            }
        
        # Get snapshots for timeline scrubbing
        snapshots = game.get_all_snapshots_as_dicts()
        
        return StartResponse(
            status="accepted",
            game_id=game.id,
            year=year,
            result={
                "current_year": int(final_state.get("current_year", year)),
                "merged": bool(final_state.get("merged", False)),
                "rulers": serializable_rulers,
                "logs": serializable_logs,
                "divergences": list(final_state.get("divergences", []))
            },
            snapshots=snapshots
        )
    except Exception as e:
        import traceback
        print(f"❌ Response serialization error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Response serialization error: {str(e)}")


@router.post("/start-stream")
async def start_workflow_stream(request: StartRequest):
    """
    Start a new alternate history game with SSE streaming.

    Emits events as each agent completes, allowing the frontend
    to show partial results progressively.

    Events:
    - filter_complete: After filter accepts, includes year and game_id
    - dreamer_complete: After dreamer, includes narrative, rulers, divergences
    - geographer_complete: After geographer, includes provinces
    - complete: After all done, includes final game state and snapshots
    - rejected: If filter rejects the divergence
    - error: On failure
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        game = None
        try:
            # Load scenario metadata for filter validation
            scenario_metadata = load_scenario_metadata(request.scenario_id)

            # Step 1: Filter validation
            filter_result = filter_command(request.command, scenario_metadata)

            if filter_result["status"] == "rejected":
                yield f"data: {json.dumps({'event': 'rejected', 'reason': filter_result.get('reason'), 'alternative': filter_result.get('alternative')})}\n\n"
                return

            # Step 2: Extract year and create game
            year = filter_result["year"]
            game = create_game()

            # Load nation tags from scenario metadata
            scenario_tags = get_scenario_tags(request.scenario_id)
            for tag, info in scenario_tags.items():
                game.add_nation_tag(tag, info.get("name", tag), info.get("color", "#888888"))

            # Emit filter_complete event
            yield f"data: {json.dumps({'event': 'filter_complete', 'year': year, 'game_id': game.id, 'nation_tags': {tag: {'name': info.name, 'color': info.color} for tag, info in game.nation_tags.items()}})}\n\n"

            # Small delay to allow frontend to process
            await asyncio.sleep(0.1)

            # Step 3: Run workflow nodes manually for streaming
            # Initialize state
            initial_state = {
                "divergences": [request.command],
                "scenario_id": request.scenario_id,
                "start_year": year,
                "years_to_progress": request.years_to_progress,
                "filter_passed": True
            }

            # Capture initial province state BEFORE workflow runs (for Log 0)
            from util.province_memory import ProvinceMemory
            initial_memory = ProvinceMemory()
            initial_memory.load_from_year(year, request.scenario_id)
            initial_provinces = [
                Province(id=p["id"], name=p["name"], owner=p["owner"], control=p.get("control", ""))
                for p in initial_memory.get_all_provinces_as_dicts()
            ]

            # Load initial rulers
            from workflows.nodes.initialize import _load_rulers_for_year
            initial_rulers = _load_rulers_for_year(year, request.scenario_id)

            # Run initialize node
            state = {**initial_state}
            state.update(initialize_game_node(state))

            # Run historian node
            state.update(historian_node(state))

            # Run dreamer node
            state.update(dreamer_node(state))

            # Emit dreamer_complete event (without quotes yet)
            dreamer_output = state.get("dreamer_output", {})
            current_year = state.get("current_year", year)
            years_to_progress = state.get("years_to_progress", 20)

            # Build log entry from dreamer output (quotes will be added after quotegiver)
            log_entry = {
                "year_range": f"{current_year}-{current_year + years_to_progress} AD",
                "narrative": dreamer_output.get("narrative", ""),
                "divergences": dreamer_output.get("updated_divergences", []),
                "territorial_changes_summary": dreamer_output.get("territorial_changes_summary", ""),
                "quotes": []
            }

            # Serialize rulers for JSON
            dreamer_rulers = dreamer_output.get("rulers", {})
            serializable_rulers = {}
            for tag, ruler in dreamer_rulers.items():
                serializable_rulers[str(tag)] = {
                    "name": str(ruler.get("name", "")),
                    "title": str(ruler.get("title", "")),
                    "age": safe_int(ruler.get("age"), 0),
                    "dynasty": str(ruler.get("dynasty", ""))
                }

            yield f"data: {json.dumps({'event': 'dreamer_complete', 'log_entry': log_entry, 'rulers': serializable_rulers, 'divergences': dreamer_output.get('updated_divergences', []), 'year_range': f'{current_year}-{current_year + years_to_progress} AD'})}\n\n"

            await asyncio.sleep(0.1)

            # Run quotegiver node to generate quotes
            state.update(quotegiver_node(state))

            # Emit quotegiver_complete event (quotes without portraits yet)
            quotegiver_output = state.get("quotegiver_output", {})
            quotes = quotegiver_output.get("quotes", [])

            yield f"data: {json.dumps({'event': 'quotegiver_complete', 'quotes': quotes})}\n\n"

            await asyncio.sleep(0.1)

            # Run illustrator node to generate portraits
            state.update(illustrator_node(state))

            # Emit illustrator_complete event with enriched quotes (including portraits)
            illustrator_output = state.get("illustrator_output", {})
            enriched_quotes = illustrator_output.get("enriched_quotes", quotes)

            yield f"data: {json.dumps({'event': 'illustrator_complete', 'quotes': enriched_quotes})}\n\n"

            await asyncio.sleep(0.1)

            # Run geographer node
            state.update(geographer_node(state))

            # Run update_state node
            state.update(update_state_node(state))

            # Get current provinces after geographer
            provinces = get_current_provinces()

            # Emit geographer_complete event
            yield f"data: {json.dumps({'event': 'geographer_complete', 'provinces': provinces})}\n\n"

            await asyncio.sleep(0.1)

            # Update game with final state
            game.workflow_state = dict(state)

            # Store province state
            game.province_state = [
                Province(id=p["id"], name=p["name"], owner=p["owner"], control=p.get("control", ""))
                for p in provinces
            ]

            # Sync logs
            game.full_logs = state.get("logs", [])

            # Capture snapshots for timeline scrubbing
            logs = state.get("logs", [])
            rulers = state.get("rulers", {})
            divergences = state.get("divergences", [])

            # Log 0 (initial/historical): use the initial province state before any changes
            if len(logs) > 0:
                game.capture_snapshot(initial_provinces, initial_rulers, divergences)

            # Log 1+ (after iterations): use the current province state
            for i in range(1, len(logs)):
                game.capture_snapshot(game.province_state, rulers, divergences)

            # Build serializable logs for response
            serializable_logs = []
            for log in game.full_logs:
                serializable_logs.append({
                    "year_range": str(log.get("year_range", "")),
                    "narrative": str(log.get("narrative", "")),
                    "divergences": list(log.get("divergences", [])),
                    "territorial_changes_summary": str(log.get("territorial_changes_summary", log.get("territorial_changes_description", ""))),
                    "quotes": list(log.get("quotes", []))
                })

            # Serialize final rulers
            final_rulers = state.get("rulers", {})
            serializable_final_rulers = {}
            for tag, ruler in final_rulers.items():
                serializable_final_rulers[str(tag)] = {
                    "name": str(ruler.get("name", "")),
                    "title": str(ruler.get("title", "")),
                    "age": safe_int(ruler.get("age"), 0),
                    "dynasty": str(ruler.get("dynasty", ""))
                }

            # Get snapshots
            snapshots = game.get_all_snapshots_as_dicts()

            # Emit complete event
            yield f"data: {json.dumps({'event': 'complete', 'game_id': game.id, 'current_year': int(state.get('current_year', year)), 'merged': bool(state.get('merged', False)), 'logs': serializable_logs, 'rulers': serializable_final_rulers, 'divergences': list(state.get('divergences', [])), 'snapshots': snapshots})}\n\n"

        except Exception as e:
            import traceback
            print(f"❌ Streaming workflow error: {e}")
            traceback.print_exc()

            # Clean up game if created
            if game:
                delete_game(game.id)

            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/continue-stream/{game_id}")
async def continue_game_stream(game_id: str, request: ContinueRequest):
    """
    Continue an existing game with SSE streaming.

    Events:
    - dreamer_complete: After dreamer, includes narrative, rulers, divergences
    - geographer_complete: After geographer, includes provinces
    - complete: After all done, includes final game state and snapshots
    - error: On failure
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            game = get_game(game_id)
            if not game:
                yield f"data: {json.dumps({'event': 'error', 'message': 'Game not found'})}\n\n"
                return

            if game.is_merged():
                yield f"data: {json.dumps({'event': 'error', 'message': 'Timeline has merged back to real history'})}\n\n"
                return

            # Prepare state for continuation
            state = dict(game.workflow_state)
            state["years_to_progress"] = request.years_to_progress

            # Add new divergences if provided
            if request.new_divergences:
                current_divergences = state.get("divergences", [])
                state["divergences"] = current_divergences + request.new_divergences

            # Reload province memory from game state
            reset_province_memory()
            memory = get_province_memory()
            if game.province_state:
                for p in game.province_state:
                    memory._provinces[p.id] = MemoryProvince(
                        id=p.id,
                        name=p.name,
                        owner=p.owner,
                        control=p.control
                    )
            else:
                memory.load_from_year(state.get("current_year", state.get("start_year", 117)))

            current_year = state.get("current_year", state.get("start_year"))
            years_to_progress = state.get("years_to_progress", 20)

            # Run historian node
            state.update(historian_node(state))

            # Run dreamer node
            state.update(dreamer_node(state))

            # Emit dreamer_complete event
            dreamer_output = state.get("dreamer_output", {})

            log_entry = {
                "year_range": f"{current_year}-{current_year + years_to_progress} AD",
                "narrative": dreamer_output.get("narrative", ""),
                "divergences": dreamer_output.get("updated_divergences", []),
                "territorial_changes_summary": dreamer_output.get("territorial_changes_summary", ""),
                "quotes": []
            }

            dreamer_rulers = dreamer_output.get("rulers", {})
            serializable_rulers = {}
            for tag, ruler in dreamer_rulers.items():
                serializable_rulers[str(tag)] = {
                    "name": str(ruler.get("name", "")),
                    "title": str(ruler.get("title", "")),
                    "age": safe_int(ruler.get("age"), 0),
                    "dynasty": str(ruler.get("dynasty", ""))
                }

            yield f"data: {json.dumps({'event': 'dreamer_complete', 'log_entry': log_entry, 'rulers': serializable_rulers, 'divergences': dreamer_output.get('updated_divergences', []), 'year_range': f'{current_year}-{current_year + years_to_progress} AD'})}\n\n"

            await asyncio.sleep(0.1)

            # Run quotegiver node to generate quotes
            state.update(quotegiver_node(state))

            # Emit quotegiver_complete event (quotes without portraits yet)
            quotegiver_output = state.get("quotegiver_output", {})
            quotes = quotegiver_output.get("quotes", [])

            yield f"data: {json.dumps({'event': 'quotegiver_complete', 'quotes': quotes})}\n\n"

            await asyncio.sleep(0.1)

            # Run illustrator node to generate portraits
            state.update(illustrator_node(state))

            # Emit illustrator_complete event with enriched quotes (including portraits)
            illustrator_output = state.get("illustrator_output", {})
            enriched_quotes = illustrator_output.get("enriched_quotes", quotes)

            yield f"data: {json.dumps({'event': 'illustrator_complete', 'quotes': enriched_quotes})}\n\n"

            await asyncio.sleep(0.1)

            # Run geographer node
            state.update(geographer_node(state))

            # Run update_state node
            state.update(update_state_node(state))

            # Get current provinces
            provinces = get_current_provinces()

            # Emit geographer_complete event
            yield f"data: {json.dumps({'event': 'geographer_complete', 'provinces': provinces})}\n\n"

            await asyncio.sleep(0.1)

            # Update game state
            game.workflow_state = dict(state)

            game.province_state = [
                Province(id=p["id"], name=p["name"], owner=p["owner"], control=p.get("control", ""))
                for p in provinces
            ]

            # Append new log entry
            workflow_logs = state.get("logs", [])
            if workflow_logs:
                new_log = workflow_logs[-1]
                game.full_logs.append(new_log)

            # Capture snapshot
            rulers = state.get("rulers", {})
            divergences = state.get("divergences", [])
            game.capture_snapshot(game.province_state, rulers, divergences)

            # Build serializable logs
            serializable_logs = []
            for log in game.full_logs:
                serializable_logs.append({
                    "year_range": str(log.get("year_range", "")),
                    "narrative": str(log.get("narrative", "")),
                    "divergences": list(log.get("divergences", [])),
                    "territorial_changes_summary": str(log.get("territorial_changes_summary", log.get("territorial_changes_description", ""))),
                    "quotes": list(log.get("quotes", []))
                })

            # Serialize final rulers
            final_rulers = state.get("rulers", {})
            serializable_final_rulers = {}
            for tag, ruler in final_rulers.items():
                serializable_final_rulers[str(tag)] = {
                    "name": str(ruler.get("name", "")),
                    "title": str(ruler.get("title", "")),
                    "age": safe_int(ruler.get("age"), 0),
                    "dynasty": str(ruler.get("dynasty", ""))
                }

            snapshots = game.get_all_snapshots_as_dicts()

            # Emit complete event
            yield f"data: {json.dumps({'event': 'complete', 'game_id': game.id, 'current_year': int(state.get('current_year', 0)), 'merged': bool(state.get('merged', False)), 'logs': serializable_logs, 'rulers': serializable_final_rulers, 'divergences': list(state.get('divergences', [])), 'snapshots': snapshots})}\n\n"

        except Exception as e:
            import traceback
            print(f"❌ Continue streaming error: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/game/{game_id}/filter-divergence")
async def filter_game_divergence(game_id: str, request: FilterDivergenceRequest) -> FilterDivergenceResponse:
    """
    Filter a divergence for an existing game.
    
    Checks if the divergence is relevant to the current era of the alternate timeline.
    Events in the past (before the current game year) will be rejected.
    """
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if game.is_merged():
        return FilterDivergenceResponse(
            status="rejected",
            reason="Timeline has merged back to real history",
            alternative="Start a new alternate timeline"
        )
    
    # Get current year from game state
    current_year = game.get_current_year()
    
    # Load scenario metadata for filter validation
    scenario_id = game.workflow_state.get("scenario_id", "rome")
    scenario_metadata = load_scenario_metadata(scenario_id)
    
    # Filter the divergence
    filter_result = filter_continuation_divergence(
        request.command, 
        current_year, 
        scenario_metadata
    )
    
    return FilterDivergenceResponse(
        status=filter_result.get("status", "rejected"),
        reason=filter_result.get("reason"),
        alternative=filter_result.get("alternative")
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
        # Convert models.game.Province to util.province_memory.Province
        for p in game.province_state:
            memory._provinces[p.id] = MemoryProvince(
                id=p.id,
                name=p.name,
                owner=p.owner,
                control=p.control
            )
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
        
        # Append only the NEW log entry to full_logs (don't overwrite with condensed logs)
        # The workflow state logs may be condensed, but we keep the full history in game.full_logs
        workflow_logs = final_state.get("logs", [])
        if workflow_logs:
            # The newest log is the last one in the workflow logs
            new_log = workflow_logs[-1]
            game.full_logs.append(new_log)
        
        # Capture snapshot for the new log entry
        rulers = final_state.get("rulers", {})
        divergences = final_state.get("divergences", [])
        game.capture_snapshot(game.province_state, rulers, divergences)
        
    except Exception as e:
        import traceback
        print(f"❌ Continue workflow error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    # Build serializable response
    try:
        serializable_logs = []
        for log in game.full_logs:
            serializable_logs.append({
                "year_range": str(log.get("year_range", "")),
                "narrative": str(log.get("narrative", "")),
                "divergences": list(log.get("divergences", [])),
                "territorial_changes_summary": str(log.get("territorial_changes_summary", log.get("territorial_changes_description", ""))),
                "quotes": list(log.get("quotes", []))
            })
        
        rulers = final_state.get("rulers", {})
        serializable_rulers = {}
        for tag, ruler in rulers.items():
            serializable_rulers[str(tag)] = {
                "name": str(ruler.get("name", "")),
                "title": str(ruler.get("title", "")),
                "age": safe_int(ruler.get("age"), 0),
                "dynasty": str(ruler.get("dynasty", ""))
            }
        
        # Get all snapshots for timeline scrubbing
        snapshots = game.get_all_snapshots_as_dicts()
        
        return ContinueResponse(
            status="continued",
            current_year=int(final_state.get("current_year", 0)),
            merged=bool(final_state.get("merged", False)),
            logs=serializable_logs,
            result={
                "rulers": serializable_rulers,
                "divergences": list(final_state.get("divergences", []))
            },
            snapshots=snapshots
        )
    except Exception as e:
        import traceback
        print(f"❌ Continue response serialization error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Response serialization error: {str(e)}")


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
    
    try:
        # Serialize rulers
        rulers = state.get("rulers", {})
        serializable_rulers = {}
        for tag, ruler in rulers.items():
            serializable_rulers[str(tag)] = {
                "name": str(ruler.get("name", "")),
                "title": str(ruler.get("title", "")),
                "age": safe_int(ruler.get("age"), 0),
                "dynasty": str(ruler.get("dynasty", ""))
            }
        
        # Serialize logs
        serializable_logs = []
        for log in game.full_logs:
            serializable_logs.append({
                "year_range": str(log.get("year_range", "")),
                "narrative": str(log.get("narrative", "")),
                "divergences": list(log.get("divergences", [])),
                "territorial_changes_summary": str(log.get("territorial_changes_summary", log.get("territorial_changes_description", ""))),
                "quotes": list(log.get("quotes", []))
            })
        
        return GameStateResponse(
            id=game.id,
            scenario_id=state.get("scenario_id", "rome"),
            current_year=game.get_current_year(),
            merged=game.is_merged(),
            rulers=serializable_rulers,
            nation_tags={
                tag: {"name": info.name, "color": info.color}
                for tag, info in game.nation_tags.items()
            },
            logs=serializable_logs,
            provinces=[
                {"id": p.id, "name": p.name, "owner": p.owner, "control": p.control}
                for p in game.province_state
            ],
            divergences=list(state.get("divergences", [])),
            snapshots=game.get_all_snapshots_as_dicts()
        )
    except Exception as e:
        import traceback
        print(f"❌ Get game state error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Serialization error: {str(e)}")


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
    """
    Get current province state for a game.
    
    Returns provinces as a list of {id, name, owner, control}.
    Useful for map rendering when you just need province data.
    """
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    return {
        "game_id": game_id,
        "current_year": game.get_current_year(),
        "provinces": [
            {"id": p.id, "name": p.name, "owner": p.owner, "control": p.control}
            for p in game.province_state
        ]
    }


@router.get("/game/{game_id}/logs")
async def get_game_logs(game_id: str, limit: Optional[int] = None) -> dict:
    """
    Get logs for a game.
    
    Args:
        game_id: The game ID
        limit: Optional limit on number of logs to return (most recent first)
    """
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    logs = game.full_logs
    if limit and limit > 0:
        logs = logs[-limit:]
    
    return {
        "game_id": game_id,
        "total_logs": len(game.full_logs),
        "logs": logs
    }


@router.get("/game/{game_id}/rulers")
async def get_game_rulers(game_id: str) -> dict:
    """
    Get current rulers for a game.
    """
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


# =============================================================================
# PORTRAIT CACHE ENDPOINTS
# =============================================================================

class PortraitStatusResponse(BaseModel):
    """Response for portrait cache status."""
    pending_count: int
    cached_count: int


class PortraitCheckRequest(BaseModel):
    """Request to check/get portraits for specific rulers."""
    rulers: List[Dict[str, str]]  # List of {ruler_name, nation_name, era_context}


class PortraitCheckResponse(BaseModel):
    """Response with available portraits."""
    portraits: Dict[str, str]  # {cache_key: base64_image}
    pending: List[str]  # List of cache keys still pending


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
    """
    Check if portraits are available for specific rulers.
    Returns cached portraits and lists which are still pending.
    """
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
        
        # Check cache
        portrait = get_cached_portrait(ruler_name, nation_name, era_context)
        if portrait:
            portraits[cache_key] = portrait
        elif is_portrait_pending(ruler_name, nation_name, era_context):
            pending.append(cache_key)
    
    return PortraitCheckResponse(
        portraits=portraits,
        pending=pending
    )


# Legacy endpoint for backward compatibility
@router.post("/start-legacy")
async def start_workflow_legacy(request: StartRequest) -> StartResponse:
    """Legacy start endpoint (without game tracking)."""
    # Load scenario metadata for filter validation
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
