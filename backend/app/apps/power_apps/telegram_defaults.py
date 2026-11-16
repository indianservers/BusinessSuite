"""Optional server-only Telegram bootstrap credential from private runtime settings."""
from app.core.config import settings

DEFAULT_BOT_TOKEN = settings.TELEGRAM_DEFAULT_BOT_TOKEN
