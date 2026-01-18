from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import os
import json

router = APIRouter(prefix="/scenarios", tags=["scenarios"])
SCENARIOS_DIR = os.path.join("static", "scenarios")

@router.get("")
def list_scenarios():
    """Return list of available scenarios with id and name."""
    scenarios = []
    if os.path.exists(SCENARIOS_DIR):
        for scenario_id in os.listdir(SCENARIOS_DIR):
            scenario_path = os.path.join(SCENARIOS_DIR, scenario_id)
            if os.path.isdir(scenario_path):
                metadata_path = os.path.join(scenario_path, "metadata.json")
                name = scenario_id.title()
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        name = metadata.get("name", name)
                scenarios.append({"id": scenario_id, "name": name})
    return JSONResponse(content=scenarios)

@router.get("/{scenario_id}/provinces")
def get_scenario_provinces(scenario_id: str):
    """Return provinces data for a specific scenario."""
    file_path = os.path.join(SCENARIOS_DIR, scenario_id, "provinces.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return FileResponse(
        file_path,
        media_type="application/json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@router.get("/{scenario_id}/rulers")
def get_scenario_rulers(scenario_id: str):
    """Return rulers data for a specific scenario."""
    file_path = os.path.join(SCENARIOS_DIR, scenario_id, "rulers.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return FileResponse(
        file_path,
        media_type="application/json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@router.get("/{scenario_id}/metadata")
def get_scenario_metadata(scenario_id: str):
    """Return metadata for a specific scenario (tags, name, description)."""
    file_path = os.path.join(SCENARIOS_DIR, scenario_id, "metadata.json")
    if not os.path.exists(file_path):
        return JSONResponse(content={"name": scenario_id.title(), "tags": {}})
    return FileResponse(
        file_path,
        media_type="application/json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@router.get("/{scenario_id}/logo")
def get_scenario_logo(scenario_id: str):
    """Return logo image for a specific scenario."""
    file_path = os.path.join(SCENARIOS_DIR, scenario_id, "logo.png")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Logo for scenario '{scenario_id}' not found")
    return FileResponse(
        file_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"}
    )
