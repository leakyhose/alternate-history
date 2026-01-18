from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter(prefix="/rome", tags=["rome"])

@router.get("/provinces")
def get_roman_provinces():
    file_path = os.path.join("static", "rome", "provinces.json")
    
    return FileResponse(
        file_path,
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )
    
@router.get("/rulers")
def get_roman_rulers():
    file_path = os.path.join("static", "rome", "rulers.json")
    
    return FileResponse(
        file_path,
        media_type="application/json",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )
