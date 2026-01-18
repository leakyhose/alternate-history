"""Game/Session model for alternate history simulation."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from workflows.state import WorkflowState, RulerInfo, LogEntry


@dataclass
class TagInfo:
    """Information about a nation tag."""
    name: str
    color: str  # Hex color code


@dataclass 
class Province:
    """In-memory province representation."""
    id: int
    name: str
    owner: str
    control: str = ""


@dataclass
class Game:
    """
    Represents an alternate history simulation session.
    
    Each game tracks:
    - Unique ID for API access
    - Nation metadata (tags, colors)
    - Current workflow state
    - Province state (in-memory, not in WorkflowState)
    - Full log history
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    
    # Metadata - all nation tags in use with their info
    nation_tags: Dict[str, TagInfo] = field(default_factory=dict)
    
    # Current simulation state
    workflow_state: WorkflowState = field(default_factory=dict)
    
    # In-memory province data (not serialized with WorkflowState)
    province_state: List[Province] = field(default_factory=list)
    
    # Full log history for UI
    full_logs: List[LogEntry] = field(default_factory=list)
    
    def add_nation_tag(self, tag: str, name: str, color: str) -> None:
        """Register a new nation tag."""
        self.nation_tags[tag] = TagInfo(name=name, color=color)
    
    def get_ruler(self, tag: str) -> Optional[RulerInfo]:
        """Get ruler info for a nation tag."""
        rulers = self.workflow_state.get("rulers", {})
        return rulers.get(tag)
    
    def update_ruler(self, tag: str, ruler: RulerInfo) -> None:
        """Update ruler info for a nation tag."""
        if "rulers" not in self.workflow_state:
            self.workflow_state["rulers"] = {}
        self.workflow_state["rulers"][tag] = ruler
    
    def add_log(self, log_entry: LogEntry) -> None:
        """Add a log entry to both workflow state and full logs."""
        if "logs" not in self.workflow_state:
            self.workflow_state["logs"] = []
        self.workflow_state["logs"].append(log_entry)
        self.full_logs.append(log_entry)
    
    def get_current_year(self) -> int:
        """Get the current simulation year."""
        return self.workflow_state.get("current_year", self.workflow_state.get("start_year", 0))
    
    def is_merged(self) -> bool:
        """Check if timeline has merged back to real history."""
        return self.workflow_state.get("merged", False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize game state for API response."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
            "nation_tags": {
                tag: {"name": info.name, "color": info.color}
                for tag, info in self.nation_tags.items()
            },
            "workflow_state": dict(self.workflow_state),
            "provinces": [
                {"id": p.id, "name": p.name, "owner": p.owner, "control": p.control}
                for p in self.province_state
            ],
            "full_logs": list(self.full_logs),
            "current_year": self.get_current_year(),
            "merged": self.is_merged()
        }


# In-memory game storage (for MVP - replace with database later)
_games: Dict[str, Game] = {}


def create_game(user_id: Optional[str] = None) -> Game:
    """Create a new game session."""
    game = Game(user_id=user_id)
    _games[game.id] = game
    return game


def get_game(game_id: str) -> Optional[Game]:
    """Retrieve a game by ID."""
    return _games.get(game_id)


def delete_game(game_id: str) -> bool:
    """Delete a game session."""
    if game_id in _games:
        del _games[game_id]
        return True
    return False


def list_games(user_id: Optional[str] = None) -> List[Game]:
    """List all games, optionally filtered by user."""
    if user_id:
        return [g for g in _games.values() if g.user_id == user_id]
    return list(_games.values())
