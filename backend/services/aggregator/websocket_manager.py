"""WebSocket connection manager for game subscriptions."""
import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per game_id.

    This is a stateless bridge - it only tracks active connections,
    not game state. The frontend stores all game data in browser memory.
    """

    def __init__(self):
        # game_id -> set of connected WebSockets
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, game_id: str) -> None:
        """Accept a WebSocket connection and register it for a game."""
        await websocket.accept()

        async with self._lock:
            if game_id not in self._connections:
                self._connections[game_id] = set()
            self._connections[game_id].add(websocket)

        logger.info(f"Client connected to game {game_id}. Total connections for game: {len(self._connections[game_id])}")

    async def disconnect(self, websocket: WebSocket, game_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if game_id in self._connections:
                self._connections[game_id].discard(websocket)
                if not self._connections[game_id]:
                    del self._connections[game_id]
                    logger.info(f"No more connections for game {game_id}")
                else:
                    logger.info(f"Client disconnected from game {game_id}. Remaining: {len(self._connections[game_id])}")

    async def broadcast_to_game(self, game_id: str, message: dict) -> None:
        """Send a message to all clients subscribed to a game.

        If no clients are connected for this game, the message is simply dropped.
        This is by design - orphaned events are ignored.
        """
        async with self._lock:
            connections = self._connections.get(game_id, set()).copy()

        if not connections:
            # No clients connected for this game - that's fine
            return

        # Send to all connected clients
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(websocket)

        # Clean up failed connections
        if disconnected:
            async with self._lock:
                if game_id in self._connections:
                    for ws in disconnected:
                        self._connections[game_id].discard(ws)

    def get_active_games(self) -> list[str]:
        """Get list of game_ids with active connections."""
        return list(self._connections.keys())

    def get_connection_count(self, game_id: str) -> int:
        """Get number of connections for a game."""
        return len(self._connections.get(game_id, set()))

    def get_total_connections(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self._connections.values())


# Global connection manager instance
manager = ConnectionManager()
