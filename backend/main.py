from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from api.rome import router as rome_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(rome_router)

@app.get("/")
def read_root():
    return {"message": "Hello World!", "status": "running"}