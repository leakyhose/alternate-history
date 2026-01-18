from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from api.scenarios import router as scenarios_router
from api.workflow import router as workflow_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

# API routers
app.include_router(scenarios_router)
app.include_router(workflow_router)

@app.get("/")
def read_root():
    return {"message": "Hello World!", "status": "running"}