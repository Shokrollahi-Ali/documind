from typing import cast

from fastapi import Request

from documind.core.config import Settings


async def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)
