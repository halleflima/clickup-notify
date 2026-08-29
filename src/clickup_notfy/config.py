import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    CLICKUP_WEBHOOK_SECRET = os.environ.get("CLICKUP_WEBHOOK_SECRET", "")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "clickup_notfy.db")
    API_BEARER_TOKEN = os.environ.get("API_BEARER_TOKEN", "")
    CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT") or "587")
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    EMAIL_REMETENTE = os.environ.get("EMAIL_REMETENTE", "")
    FALLBACK_EMAIL = os.environ.get("FALLBACK_EMAIL", "")
