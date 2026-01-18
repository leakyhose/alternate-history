import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.scenarios import router as scenarios_router
from api.workflow import router as workflow_router

app = FastAPI()

# CORS middleware - allow all origins for hackathon demo
# Note: allow_credentials must be False when using allow_origins=["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False with wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# API routers
app.include_router(scenarios_router)
app.include_router(workflow_router)

@app.get("/")
def read_root():
    return {"message": "Hello World!", "status": "running"}