"""Configuration for the Geographer microservice."""
import os
from dotenv import load_dotenv

load_dotenv()

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_CONSUMER_GROUP = "geographer-consumer-group"

# Topics
TOPIC_TIMELINE_EVENTS = "timeline.events"
TOPIC_PROVINCES_UPDATED = "provinces.updated"

# LLM settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# Processing settings
LLM_TIMEOUT_SECONDS = 120
MAX_TOOL_ITERATIONS = 30
