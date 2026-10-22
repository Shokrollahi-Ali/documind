from documind.core.celery import create_celery_app
from documind.core.config import Settings

settings = Settings()
app = create_celery_app(settings)
