from typing import TypedDict, Optional, Any, List


class WorkflowState(TypedDict, total=False):
    
    divergences: List[str]     
    start_year: int
    years_to_progress: int
    
    ruler: str
    ruler_title: str
    ruler_age: int
    ruler_dynasty: str
    
    logs: str

