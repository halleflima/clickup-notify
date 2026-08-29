import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    CLICKUP_WEBHOOK_SECRET = os.environ.get("CLICKUP_WEBHOOK_SECRET", "")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "clickup_notfy.db")
    API_BEARER_TOKEN = os.environ.get("API_BEARER_TOKEN", "")
    CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
