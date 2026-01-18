from typing import TypedDict, Optional, Any, List


class WorkflowState(TypedDict, total=False):
    
    divergences: List[str]     
    start_year: int
    end_year: int
    start_ruler: str
    start_ruler_dynasty: str
    
    provinces: List[str]
    changes: List[str]    


