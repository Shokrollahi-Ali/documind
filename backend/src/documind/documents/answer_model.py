import httpx
from langchain_openai import ChatOpenAI

from documind.core.config import Settings


def create_answer_model(
    settings: Settings,
    *,
    http_client: httpx.Client,
    http_async_client: httpx.AsyncClient,
) -> ChatOpenAI:
    if settings.answer_model is None or not settings.answer_model.strip():
        raise ValueError("DOCUMIND_ANSWER_MODEL must be set to generate answers")

    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value().strip():
        raise ValueError("DOCUMIND_OPENAI_API_KEY must be set to generate answers")

    return ChatOpenAI(
        model=settings.answer_model.strip(),
        api_key=settings.openai_api_key,
        timeout=settings.answer_request_timeout_seconds,
        max_completion_tokens=settings.answer_max_output_tokens,
        max_retries=0,
        use_responses_api=True,
        store=False,
        http_client=http_client,
        http_async_client=http_async_client,
    )
