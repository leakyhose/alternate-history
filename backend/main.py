from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return {"message": "Hello World!", "status": "running"}

@app.get("/rome/provinces")
def get_roman_provinces():
    file_path = os.path.join("static", "rome", "provinces.json")
    
    return FileResponse(
        file_path,
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )
    
@app.get("/rome/rulers")
def get_roman_rulers():
    file_path = os.path.join("static", "rome", "rulers.json")
    
    return FileResponse(
        file_path,
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )