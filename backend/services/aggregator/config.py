"""Configuration for the Aggregator microservice."""
import os
from dotenv import load_dotenv

load_dotenv()

# Server settings
HOST = os.getenv("AGGREGATOR_HOST", "0.0.0.0")
PORT = int(os.getenv("AGGREGATOR_PORT", "8001"))

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_CONSUMER_GROUP = "aggregator-consumer-group"

# Topics to consume
TOPIC_TIMELINE_EVENTS = "timeline.events"
TOPIC_QUOTES_READY = "quotes.ready"
TOPIC_PROVINCES_UPDATED = "provinces.updated"
TOPIC_PORTRAITS_READY = "portraits.ready"

ALL_TOPICS = [
    TOPIC_TIMELINE_EVENTS,
    TOPIC_QUOTES_READY,
    TOPIC_PROVINCES_UPDATED,
    TOPIC_PORTRAITS_READY,
]

# WebSocket settings
WS_HEARTBEAT_INTERVAL = 30  # seconds
GAME_CLEANUP_DELAY = 60  # seconds after last disconnect before cleanup
