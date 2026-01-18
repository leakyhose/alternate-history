"""
Workflow logging utilities.

Provides structured logging for tracking workflow execution through all nodes.
"""
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)


class WorkflowLogger:
    """Logger for tracking workflow execution."""
    
    def __init__(self, name: str = "workflow"):
        self.logger = logging.getLogger(name)
        self._start_times: Dict[str, datetime] = {}
    
    def node_start(self, node_name: str, state_summary: Optional[Dict[str, Any]] = None):
        """Log when a node starts execution."""
        self._start_times[node_name] = datetime.now()
        msg = f"▶ Node '{node_name}' starting"
        if state_summary:
            msg += f" | State: {state_summary}"
        self.logger.info(msg)
    
    def node_end(self, node_name: str, output_summary: Optional[Dict[str, Any]] = None):
        """Log when a node completes execution."""
        elapsed = ""
        if node_name in self._start_times:
            delta = datetime.now() - self._start_times[node_name]
            elapsed = f" ({delta.total_seconds():.2f}s)"
            del self._start_times[node_name]
        
        msg = f"✓ Node '{node_name}' completed{elapsed}"
        if output_summary:
            msg += f" | Output: {output_summary}"
        self.logger.info(msg)
    
    def node_error(self, node_name: str, error: Exception):
        """Log when a node encounters an error."""
        self.logger.error(f"✗ Node '{node_name}' failed: {error}")
    
    def workflow_start(self, workflow_name: str, initial_state: Optional[Dict[str, Any]] = None):
        """Log when a workflow starts."""
        self._start_times["__workflow__"] = datetime.now()
        msg = f"═══ Workflow '{workflow_name}' starting ═══"
        self.logger.info(msg)
        if initial_state:
            self.logger.info(f"  Initial divergences: {initial_state.get('divergences', [])}")
            self.logger.info(f"  Start year: {initial_state.get('start_year')}")
            self.logger.info(f"  Years to progress: {initial_state.get('years_to_progress')}")
    
    def workflow_end(self, workflow_name: str, final_state: Optional[Dict[str, Any]] = None):
        """Log when a workflow completes."""
        elapsed = ""
        if "__workflow__" in self._start_times:
            delta = datetime.now() - self._start_times["__workflow__"]
            elapsed = f" ({delta.total_seconds():.2f}s)"
            del self._start_times["__workflow__"]
        
        msg = f"═══ Workflow '{workflow_name}' completed{elapsed} ═══"
        self.logger.info(msg)
        if final_state:
            self.logger.info(f"  Current year: {final_state.get('current_year')}")
            self.logger.info(f"  Merged: {final_state.get('merged', False)}")
            self.logger.info(f"  Total logs: {len(final_state.get('logs', []))}")
    
    def info(self, message: str):
        """Log an info message."""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log a warning message."""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log an error message."""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log a debug message."""
        self.logger.debug(message)


# Global logger instance
workflow_logger = WorkflowLogger()


def get_state_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a summary of state for logging (avoid logging huge data)."""
    return {
        "year": state.get("current_year", state.get("start_year")),
        "divergences_count": len(state.get("divergences", [])),
        "logs_count": len(state.get("logs", [])),
        "merged": state.get("merged", False)
    }
