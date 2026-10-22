import asyncio
import logging
from contextlib import closing

from documind.core.celery import create_celery_app
from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.dispatch import dispatch_processing_requests


async def run_dispatcher(settings: Settings) -> None:
    engine = create_database_engine(settings)

    try:
        session_factory = create_session_factory(engine)

        with closing(create_celery_app(settings)) as celery_app:
            await dispatch_processing_requests(
                session_factory=session_factory,
                celery_app=celery_app,
                interval_seconds=settings.processing_dispatch_interval_seconds,
            )
    finally:
        await engine.dispose()


def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    try:
        asyncio.run(run_dispatcher(settings))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
