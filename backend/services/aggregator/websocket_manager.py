"""WebSocket connection manager for game subscriptions."""
import asyncio
import logging
import time
from collections import deque
from typing import Dict, Set, List, Tuple
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# How long to buffer events for games with no connected clients (seconds)
EVENT_BUFFER_TTL = 60.0
# Maximum events to buffer per game
MAX_BUFFER_PER_GAME = 20


class ConnectionManager:
    """Manages WebSocket connections per game_id.

    This is a stateless bridge - it only tracks active connections,
    not game state. The frontend stores all game data in browser memory.

    Events are buffered briefly for games with no connected clients to handle
    the race condition where the backend produces events before the frontend
    connects its WebSocket.
    """

    def __init__(self):
        # game_id -> set of connected WebSockets
        self._connections: Dict[str, Set[WebSocket]] = {}
        # game_id -> deque of (timestamp, message) for buffering
        self._event_buffer: Dict[str, deque] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, game_id: str) -> None:
        """Accept a WebSocket connection and register it for a game.

        Also sends any buffered events that arrived before the client connected.
        """
        await websocket.accept()

        buffered_events: List[dict] = []

        async with self._lock:
            if game_id not in self._connections:
                self._connections[game_id] = set()
            self._connections[game_id].add(websocket)

            # Get buffered events for this game
            if game_id in self._event_buffer:
                now = time.time()
                # Filter out expired events and extract messages
                valid_events = [
                    (ts, msg) for ts, msg in self._event_buffer[game_id]
                    if now - ts < EVENT_BUFFER_TTL
                ]
                buffered_events = [msg for _, msg in valid_events]
                # Clear the buffer since we're delivering to a client
                del self._event_buffer[game_id]

        logger.info(f"Client connected to game {game_id}. Total connections: {len(self._connections[game_id])}")

        # Send buffered events to the newly connected client
        if buffered_events:
            logger.info(f"Sending {len(buffered_events)} buffered events to new client for game {game_id}")
            for msg in buffered_events:
                try:
                    await websocket.send_json(msg)
                    logger.info(f"Sent buffered {msg.get('type')} to game {game_id}")
                except Exception as e:
                    logger.warning(f"Failed to send buffered event: {e}")

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

        If no clients are connected, buffer the event for a short time
        so late-connecting clients can receive it.
        """
        async with self._lock:
            connections = self._connections.get(game_id, set()).copy()

            if not connections:
                # No clients connected - buffer the event
                if game_id not in self._event_buffer:
                    self._event_buffer[game_id] = deque(maxlen=MAX_BUFFER_PER_GAME)
                self._event_buffer[game_id].append((time.time(), message))
                logger.info(f"Buffered {message.get('type')} for game {game_id} (no clients connected)")
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

    async def cleanup_expired_buffers(self) -> int:
        """Remove expired events from buffers. Returns number of games cleaned up."""
        cleaned = 0
        now = time.time()

        async with self._lock:
            expired_games = []
            for game_id, buffer in self._event_buffer.items():
                # Remove expired events from this game's buffer
                valid_events = deque(
                    [(ts, msg) for ts, msg in buffer if now - ts < EVENT_BUFFER_TTL],
                    maxlen=MAX_BUFFER_PER_GAME
                )
                if valid_events:
                    self._event_buffer[game_id] = valid_events
                else:
                    expired_games.append(game_id)

            for game_id in expired_games:
                del self._event_buffer[game_id]
                cleaned += 1

        if cleaned > 0:
            logger.debug(f"Cleaned up {cleaned} expired game buffers")
        return cleaned

    def get_buffer_stats(self) -> dict:
        """Get statistics about the event buffer."""
        return {
            "buffered_games": len(self._event_buffer),
            "total_buffered_events": sum(len(buf) for buf in self._event_buffer.values()),
        }


# Global connection manager instance
manager = ConnectionManager()
