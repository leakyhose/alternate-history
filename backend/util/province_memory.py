"""
In-memory province state management.

The full province map (~29MB) is kept in Python memory, NOT in workflow state.
This module provides utilities to load, update, and query province data.
"""
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


# Get the backend directory path (parent of util/)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Province:
    """Represents a single province."""
    id: int
    name: str
    owner: str
    control: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


class ProvinceMemory:
    """
    Manages in-memory province state for a game session.
    
    Usage:
        memory = ProvinceMemory()
        memory.load_from_year(630, "rome")  # Load historical state for 630 AD
        memory.update_province(234, owner="ARB")  # Update ownership
        provinces = memory.get_all_provinces()  # Get current state
    """
    
    def __init__(self):
        self._provinces: Dict[int, Province] = {}
        self._scenario_id: Optional[str] = None
    
    def _get_provinces_file_path(self, scenario_id: str) -> str:
        """Get path to provinces.json for a scenario."""
        return os.path.join(_BACKEND_DIR, "static", "scenarios", scenario_id, "provinces.json")
    
    def load_from_year(self, year: int, scenario_id: str = "rome") -> bool:
        """
        Load province state for a specific year from the scenario's data file.
        
        Args:
            year: The year to load province data for (e.g., 630 for 630 AD)
            scenario_id: The scenario folder name (e.g., "rome")
            
        Returns:
            True if loaded successfully, False otherwise
        """
        self._scenario_id = scenario_id
        file_path = self._get_provinces_file_path(scenario_id)
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Province data file not found: {file_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"Error parsing province data: {e}")
            return False
        
        year_str = str(year)
        province_list = data.get(year_str, [])
        
        if not province_list:
            # Try to find closest available year
            available_years = sorted([int(y) for y in data.keys()])
            closest = min(available_years, key=lambda y: abs(y - year), default=None)
            if closest:
                province_list = data.get(str(closest), [])
                print(f"Year {year} not found, using closest year {closest}")
        
        self._provinces.clear()
        for p in province_list:
            province = Province(
                id=p["ID"],
                name=p["NAME"],
                owner=p["OWNER"],
                control=p.get("CONTROL", "")
            )
            self._provinces[province.id] = province
        
        return len(self._provinces) > 0
    
    def get_province(self, province_id: int) -> Optional[Province]:
        """Get a province by ID."""
        return self._provinces.get(province_id)
    
    def get_province_by_name(self, name: str) -> Optional[Province]:
        """Get a province by name (case-insensitive)."""
        name_lower = name.lower()
        for p in self._provinces.values():
            if p.name.lower() == name_lower:
                return p
        return None
    
    def get_provinces_by_owner(self, owner: str) -> List[Province]:
        """Get all provinces owned by a specific nation."""
        return [p for p in self._provinces.values() if p.owner == owner]
    
    def get_provinces_by_control(self, controller: str) -> List[Province]:
        """Get all provinces controlled (occupied) by a specific nation."""
        return [p for p in self._provinces.values() if p.control == controller]
    
    def update_province(
        self,
        province_id: int,
        owner: Optional[str] = None,
        control: Optional[str] = None
    ) -> bool:
        """
        Update a province's ownership and/or control.
        
        Args:
            province_id: The ID of the province to update
            owner: New owner tag (permanent conquest)
            control: New controller tag (temporary occupation), use "" to clear
            
        Returns:
            True if updated, False if province not found
        """
        province = self._provinces.get(province_id)
        if not province:
            return False
        
        if owner is not None:
            province.owner = owner
        if control is not None:
            province.control = control
        
        return True
    
    def apply_updates(self, updates: List[dict]) -> int:
        """
        Apply a batch of province updates.
        
        If a province doesn't exist but has a valid owner tag, it will be ADDED
        to the tracked provinces (represents conquest from an untracked nation).
        
        Args:
            updates: List of dicts with keys: id, name (optional), owner (optional), control (optional)
            
        Returns:
            Number of provinces successfully updated or added
        """
        count = 0
        added = []
        failed = []
        
        for update in updates:
            province_id = update.get("id")
            if province_id is None:
                continue
            
            # Try to update existing province
            if self.update_province(
                province_id,
                owner=update.get("owner"),
                control=update.get("control")
            ):
                count += 1
            else:
                # Province doesn't exist - check if we should add it
                owner = update.get("owner", "")
                
                if owner:
                    # Province has an owner - this is a conquest from an untracked nation
                    # Add it to our tracked provinces
                    name = update.get("name", f"Province {province_id}")
                    new_province = Province(
                        id=province_id,
                        name=name,
                        owner=owner,
                        control=update.get("control", "")
                    )
                    self._provinces[province_id] = new_province
                    added.append(f"ID {province_id} ({name})")
                    count += 1
                else:
                    # Province has no owner and doesn't exist - can't mark as "lost"
                    # because we weren't tracking it anyway
                    failed.append(f"ID {province_id} ({update.get('name', 'unknown')})")
        
        if added:
            print(f"    Added {len(added)} newly conquered provinces: {', '.join(added[:5])}")
            if len(added) > 5:
                print(f"      ... and {len(added) - 5} more")
        
        if failed:
            print(f"    WARNING: Skipped {len(failed)} provinces (not tracked): {', '.join(failed)}")
        
        return count
    
    def get_all_provinces(self) -> List[Province]:
        """Get all provinces."""
        return list(self._provinces.values())
    
    def get_all_provinces_as_dicts(self) -> List[dict]:
        """Get all provinces as dictionaries (for API responses)."""
        return [p.to_dict() for p in self._provinces.values()]
    
    def get_province_count(self) -> int:
        """Get the total number of provinces."""
        return len(self._provinces)
    
    def get_owner_counts(self) -> Dict[str, int]:
        """Get province counts per owner."""
        counts: Dict[str, int] = {}
        for p in self._provinces.values():
            counts[p.owner] = counts.get(p.owner, 0) + 1
        return counts
    
    def clone(self) -> "ProvinceMemory":
        """Create a deep copy of the province memory."""
        new_memory = ProvinceMemory()
        for p in self._provinces.values():
            new_memory._provinces[p.id] = Province(
                id=p.id,
                name=p.name,
                owner=p.owner,
                control=p.control
            )
        return new_memory


# Module-level region mapping cache
_region_provinces: Optional[Dict[str, List[dict]]] = None
_areas_cache: Optional[Dict[str, List[dict]]] = None
_regions_to_areas_cache: Optional[Dict[str, List[str]]] = None


def load_region_provinces() -> Dict[str, List[dict]]:
    """
    Load the region to provinces mapping.
    
    Returns:
        Dict mapping region names to lists of province info dicts
    """
    global _region_provinces
    
    if _region_provinces is not None:
        return _region_provinces
    
    file_path = os.path.join(_BACKEND_DIR, "static", "region_provinces.json")
    try:
        with open(file_path, 'r') as f:
            _region_provinces = json.load(f)
    except FileNotFoundError:
        print(f"Region provinces file not found: {file_path}")
        _region_provinces = {}
    except json.JSONDecodeError as e:
        print(f"Error parsing region provinces: {e}")
        _region_provinces = {}
    
    return _region_provinces


def load_areas() -> Dict[str, List[dict]]:
    """
    Load the areas to provinces mapping.
    
    Returns:
        Dict mapping area names to lists of province info dicts with 'id' and 'name'
    """
    global _areas_cache
    
    if _areas_cache is not None:
        return _areas_cache
    
    file_path = os.path.join(_BACKEND_DIR, "static", "areas.json")
    try:
        with open(file_path, 'r') as f:
            _areas_cache = json.load(f)
    except FileNotFoundError:
        print(f"Areas file not found: {file_path}")
        _areas_cache = {}
    except json.JSONDecodeError as e:
        print(f"Error parsing areas: {e}")
        _areas_cache = {}
    
    return _areas_cache


def load_regions_to_areas() -> Dict[str, List[str]]:
    """
    Load the regions to areas mapping.
    
    Returns:
        Dict mapping region names to lists of area names
    """
    global _regions_to_areas_cache
    
    if _regions_to_areas_cache is not None:
        return _regions_to_areas_cache
    
    file_path = os.path.join(_BACKEND_DIR, "static", "regions.json")
    try:
        with open(file_path, 'r') as f:
            _regions_to_areas_cache = json.load(f)
    except FileNotFoundError:
        print(f"Regions file not found: {file_path}")
        _regions_to_areas_cache = {}
    except json.JSONDecodeError as e:
        print(f"Error parsing regions: {e}")
        _regions_to_areas_cache = {}
    
    return _regions_to_areas_cache


def get_all_region_names() -> List[str]:
    """Get all available region names (from regions.json)."""
    regions = load_regions_to_areas()
    return list(regions.keys())


def get_areas_for_region(region_name: str) -> List[str]:
    """
    Get list of area names for a region.
    
    Args:
        region_name: The region name (e.g., "France", "Egypt")
        
    Returns:
        List of area names within that region
    """
    regions = load_regions_to_areas()
    return regions.get(region_name, [])


def get_all_area_names() -> List[str]:
    """Get all available area names."""
    areas = load_areas()
    return list(areas.keys())


def get_provinces_for_area(area_name: str) -> List[dict]:
    """
    Get list of provinces for an area.
    
    Args:
        area_name: The area name (e.g., "Brittany", "Lower Egypt")
        
    Returns:
        List of province dicts with 'id' and 'name' keys
    """
    areas = load_areas()
    return areas.get(area_name, [])


def find_area_by_province(province_id: int) -> Optional[str]:
    """Find which area a province belongs to."""
    areas = load_areas()
    for area_name, provinces in areas.items():
        for p in provinces:
            if p.get("id") == province_id:
                return area_name
    return None


def find_region_by_area(area_name: str) -> Optional[str]:
    """Find which region an area belongs to."""
    regions = load_regions_to_areas()
    for region_name, areas in regions.items():
        if area_name in areas:
            return region_name
    return None
