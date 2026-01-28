"""Configuration for the Quotegiver microservice."""
import os
from dotenv import load_dotenv

load_dotenv()

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_CONSUMER_GROUP = "quotegiver-consumer-group"

# Topics
TOPIC_TIMELINE_EVENTS = "timeline.events"
TOPIC_QUOTES_READY = "quotes.ready"

# LLM settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash-lite"

# Processing settings
MAX_QUOTES_PER_EVENT = 2
LLM_TIMEOUT_SECONDS = 30
