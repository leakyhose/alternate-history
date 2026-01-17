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

@app.get("/history/roman")
def get_roman_history():
    file_path = os.path.join("static", "history", "roman.json")
    
    return FileResponse(
        file_path,
        media_type="application/json",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"roman-history-v1"'
        }
    )