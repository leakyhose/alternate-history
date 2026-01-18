from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.filter_agent import filter_command
from workflows.graph import workflow

router = APIRouter(tags=["workflow"])


class StartRequest(BaseModel):
    command: str


class StartResponse(BaseModel):
    status: str
    year: int | None = None
    reason: str | None = None
    alternative: str | None = None
    result: dict | None = None


@router.post("/start")
async def start_workflow(request: StartRequest) -> StartResponse:
    
    # Filter
    filter_result = filter_command(request.command)
    
    if filter_result["status"] == "rejected":
        return StartResponse(
            status="rejected",
            reason=filter_result.get("reason"),
            alternative=filter_result.get("alternative")
        )
    
    # Runs if accepted by filter
    year = filter_result["year"]
    
    try:
        final_state = workflow.invoke({
            "divergences": [request.command],
            "start_year": year,
            "end_year": year + 20
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return StartResponse(
        status="accepted",
        year=year,
        result=final_state.get("result")
    )
