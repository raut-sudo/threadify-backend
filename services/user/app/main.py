from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()

settings = get_settings()
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
    