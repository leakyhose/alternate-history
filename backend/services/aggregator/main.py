#!/usr/bin/env python3
"""Aggregator microservice - Kafka to WebSocket bridge.

This service consumes events from all Kafka topics and forwards them
to connected WebSocket clients. It's a stateless bridge - the frontend
stores all game state in browser memory.

Usage:
    python -m services.aggregator.main
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import HOST, PORT
from .websocket_manager import manager
from .consumers import consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aggregator")

# Queue for events from Kafka consumer thread
event_queue: asyncio.Queue = asyncio.Queue()


async def process_events():
    """Process events from Kafka and broadcast to WebSocket clients.

    Runs as a background task, consuming from the event queue and
    forwarding to the appropriate WebSocket connections.
    """
    logger.info("Event processor started")
    while True:
        try:
            # Wait for events from Kafka consumer
            game_id, message = await event_queue.get()

            # Broadcast to all clients subscribed to this game
            await manager.broadcast_to_game(game_id, message)

            logger.info(
                f"Broadcast {message.get('type')} to game={game_id}, "
                f"clients={manager.get_connection_count(game_id)}"
            )

        except asyncio.CancelledError:
            logger.info("Event processor cancelled")
            break
        except Exception as e:
            logger.error(f"Error processing event: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of background tasks."""
    # Startup
    loop = asyncio.get_event_loop()

    # Start Kafka consumer in background thread
    consumer.start(loop, event_queue)

    # Start event processor task
    processor_task = asyncio.create_task(process_events())

    logger.info("Aggregator service ready")

    yield

    # Shutdown
    processor_task.cancel()
    try:
        await processor_task
    except asyncio.CancelledError:
        pass

    consumer.stop()
    logger.info("Aggregator service shutdown complete")


app = FastAPI(
    title="Alternate History Aggregator",
    description="WebSocket bridge for real-time game updates",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for WebSocket connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "aggregator",
        "status": "healthy",
        "active_games": manager.get_active_games(),
        "total_connections": manager.get_total_connections(),
    }


@app.get("/status")
async def status():
    """Detailed status endpoint."""
    active_games = manager.get_active_games()
    return {
        "service": "aggregator",
        "status": "healthy",
        "active_games": len(active_games),
        "total_connections": manager.get_total_connections(),
        "games": {
            game_id: manager.get_connection_count(game_id)
            for game_id in active_games
        },
    }


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """WebSocket endpoint for game updates.

    Clients connect with their game_id and receive all updates
    for that game (timeline, quotes, provinces, portraits).

    The connection is receive-only - clients don't send messages
    back (except for ping/pong keepalive).
    """
    await manager.connect(websocket, game_id)
    logger.info(f"WebSocket connected for game {game_id}")

    try:
        # Keep connection alive
        # We don't expect messages from client, but need to handle them
        # to detect disconnection
        while True:
            try:
                # Wait for any message (likely just pings) with timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0  # 1 minute timeout
                )
                # If we receive a message, just acknowledge it
                # (frontend might send pings)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # No message received, send a ping to check connection
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for game {game_id}")
    except Exception as e:
        logger.warning(f"WebSocket error for game {game_id}: {e}")
    finally:
        await manager.disconnect(websocket, game_id)


def run_server():
    """Run the aggregator server."""
    logger.info(f"Starting Aggregator service on {HOST}:{PORT}")
    uvicorn.run(
        "services.aggregator.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
