from celery import Celery

from documind.core.config import Settings


def create_celery_app(settings: Settings) -> Celery:
    if settings.celery_broker_url is None:
        raise ValueError("DOCUMIND_CELERY_BROKER_URL must be set")

    broker_url = settings.celery_broker_url.get_secret_value().strip()

    if not broker_url:
        raise ValueError("DOCUMIND_CELERY_BROKER_URL must not be empty")

    application = Celery(
        "documind",
        broker=broker_url,
        set_as_current=False,
    )
    application.conf.update(
        task_serializer="json",
        accept_content=["json"],
        task_ignore_result=True,
        timezone="UTC",
        enable_utc=True,
    )

    return application
