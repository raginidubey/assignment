import os

class Config:
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/app.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

settings = Config()
