import json
import os
from typing import Optional


def get_provinces_at_date(year: int) -> list[dict]:

    file_path = os.path.join("static", "rome", "provinces.json")
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    
    provinces = data.get(str(year), [])
    return provinces

def get_rulers_atdate(year: int) -> list[dict]:

    file_path = os.path.join("static", "rome", "rulers.json")
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    
    provinces = data.get(str(year), [])
    return provinces