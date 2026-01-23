"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from api.scenarios import router as scenarios_router
from api.workflow import router as workflow_router

app = FastAPI(title="Alternate History API")

# CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(scenarios_router)
app.include_router(workflow_router)


@app.get("/")
def read_root():
    return {"message": "Alternate History API", "status": "running"}
