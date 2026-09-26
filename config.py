import os
from dotenv import load_dotenv

load_dotenv()

MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./factory.db").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DEFAULT_BOT_LIMIT = int(os.getenv("DEFAULT_BOT_LIMIT", "3"))
REQUIRED_CHANNELS = os.getenv("REQUIRED_CHANNELS", "").strip()

WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY", "CHANGE_THIS_SECRET_KEY")
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

TELEGRAM_LOGIN_BOT_USERNAME = os.getenv("TELEGRAM_LOGIN_BOT_USERNAME", "").strip().lstrip("@")
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()

PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "manual").strip().lower()
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "").strip()

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip()
WORKER_ID = os.getenv("WORKER_ID", "worker-1").strip()
WEBHOOK_PATH_PREFIX = os.getenv("WEBHOOK_PATH_PREFIX", "/telegram/webhook").rstrip("/")
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip()

HEALTHCHECK_INTERVAL = int(os.getenv("HEALTHCHECK_INTERVAL", "30"))
MAX_BOTS_PER_WORKER = int(os.getenv("MAX_BOTS_PER_WORKER", "100"))
WORKER_TTL = int(os.getenv("WORKER_TTL", "60"))
TASK_MAX_RETRIES = int(os.getenv("TASK_MAX_RETRIES", "5"))
RETRY_BASE_SECONDS = int(os.getenv("RETRY_BASE_SECONDS", "5"))
LOCK_TTL = int(os.getenv("LOCK_TTL", "60"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))

if not MAIN_BOT_TOKEN:
    raise RuntimeError("MAIN_BOT_TOKEN is missing in .env")
if not TOKEN_ENCRYPTION_KEY:
    raise RuntimeError("TOKEN_ENCRYPTION_KEY is missing in .env")
