"""Environment-backed configuration with reviewer-safe defaults."""
import os

API_BASE = os.getenv("MOCK_API_BASE", "http://localhost:8090").rstrip("/")
AI_MODE = os.getenv("AI_MODE", "reviewer").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8080"))
REQUEST_TIMEOUT = float(os.getenv("ENTERPRISE_TIMEOUT", "4"))
LEGACY_TIMEOUT = float(os.getenv("LEGACY_TIMEOUT", "4"))
MAX_RETRIES = max(0, min(3, int(os.getenv("MAX_RETRIES", "1"))))
MAX_BODY_BYTES = 16_384
SESSION_TTL_SECONDS = 3600
MAX_TURNS = 16
