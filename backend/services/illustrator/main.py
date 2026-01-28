#!/usr/bin/env python3
"""Illustrator microservice entry point."""
import logging
import os
import sys
from typing import Optional

from .consumer import QuotesEventConsumer
from .producer import PortraitsProducer
from .portrait_generator import generate_portraits_from_event
from .redis_cache import close_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("illustrator")

_shutdown_requested = False


def process_event(event: dict, producer: PortraitsProducer) -> None:
    """Process a single quotes event."""
    game_id = event.get("game_id", "unknown")
    iteration = event.get("iteration", 0)

    try:
        portraits = generate_portraits_from_event(event)
        producer.produce_portraits(
            game_id=game_id,
            iteration=iteration,
            portraits=portraits,
        )
        logger.info(f"Processed game={game_id}, iteration={iteration}, portraits={len(portraits)}")
    except Exception as e:
        logger.error(f"Failed game={game_id}, iteration={iteration}: {e}")
        producer.produce_failure(game_id=game_id, iteration=iteration, error=str(e))


def run_service() -> None:
    """Main service loop."""
    global _shutdown_requested

    # Only use signal handlers on Unix (Windows has issues with signals + threads)
    if os.name != "nt":
        import signal

        def signal_handler(signum, frame):
            global _shutdown_requested
            logger.info(f"Received signal {signum}, shutting down...")
            _shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, signal_handler)

    consumer: Optional[QuotesEventConsumer] = None
    producer: Optional[PortraitsProducer] = None

    try:
        logger.info("Starting Illustrator service")

        consumer = QuotesEventConsumer()
        consumer.connect()

        producer = PortraitsProducer()
        producer.connect()

        logger.info("Ready, waiting for quote events...")

        for event in consumer.consume():
            if _shutdown_requested:
                break
            process_event(event, producer)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Service error: {e}")
        sys.exit(1)
    finally:
        logger.info("Shutting down...")
        if producer:
            producer.close()
        if consumer:
            consumer.close()
        close_redis()


if __name__ == "__main__":
    run_service()
