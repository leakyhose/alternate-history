import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.scenarios import router as scenarios_router
from api.workflow import router as workflow_router

app = FastAPI()

# CORS middleware - configure allowed origins
# In production, set CORS_ORIGINS env var to your frontend URL(s)
# e.g., CORS_ORIGINS=https://your-app.vercel.app,https://custom-domain.com
cors_origins_env = os.getenv("CORS_ORIGINS", "")
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if cors_origins_env:
    cors_origins.extend([origin.strip() for origin in cors_origins_env.split(",")])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
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