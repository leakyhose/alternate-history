"""Configuration for the Illustrator microservice."""
import os
from dotenv import load_dotenv

load_dotenv()

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_CONSUMER_GROUP = "illustrator-consumer-group"

# Topics
TOPIC_QUOTES_READY = "quotes.ready"
TOPIC_PORTRAITS_READY = "portraits.ready"

# Redis settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_PORTRAIT_PREFIX = "portrait:"
REDIS_PORTRAIT_TTL_SECONDS = 24 * 60 * 60  # 24 hours

# LLM settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash-image"

# Processing settings
MAX_PORTRAITS_PER_EVENT = 2
