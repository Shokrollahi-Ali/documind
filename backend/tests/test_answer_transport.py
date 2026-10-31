import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from documind.core.config import Settings
from documind.documents.answer_generation import (
    AnswerGenerationError,
    AnswerRefusedError,
    GeneratedAnswer,
    generate_answer,
)
from documind.documents.answer_model import create_answer_model
from documind.documents.retrieval import RetrievedChunk


@pytest.mark.parametrize("outcome", ["success", "refusal", "invalid_citation", "truncated"])
def test_real_client_parses_simulated_responses(outcome: str) -> None:
    requests: list[dict[str, object]] = []
    chunk = RetrievedChunk(uuid4(), 7, 3, "Refunds are available within 30 days.", 0.1)

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        payload = json.loads(request.content)
        requests.append(payload)
        content: list[dict[str, object]]
        if outcome == "refusal":
            content = [{"type": "refusal", "refusal": "I cannot answer this question."}]
        else:
            text = json.dumps(
                {
                    "answer": "Refunds are available within 30 days [chunk 7].",
                    "has_supporting_context": True,
                    "cited_chunk_indexes": [9] if outcome == "invalid_citation" else [7],
                }
            )
            if outcome == "truncated":
                text = '{"answer": "unfinished'
            content = [{"type": "output_text", "text": text, "annotations": []}]

        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "model": "test-model",
                "status": "incomplete" if outcome == "truncated" else "completed",
                "error": None,
                "incomplete_details": {"reason": "max_output_tokens"}
                if outcome == "truncated"
                else None,
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "incomplete" if outcome == "truncated" else "completed",
                        "content": content,
                    }
                ],
                "text": payload["text"],
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 30,
                    "total_tokens": 130,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0},
                },
            },
        )

    async def run_generation() -> GeneratedAnswer:
        transport = httpx.MockTransport(respond)
        with httpx.Client(transport=transport) as http_client:
            async with httpx.AsyncClient(transport=transport) as http_async_client:
                model = create_answer_model(
                    Settings(
                        answer_model="test-model",
                        openai_api_key=SecretStr("test-key"),
                        answer_max_output_tokens=500,
                    ),
                    http_client=http_client,
                    http_async_client=http_async_client,
                )
                return await generate_answer("What is the refund policy?", [chunk], model)

    if outcome == "success":
        answer = asyncio.run(run_generation())
        assert answer.answer == "Refunds are available within 30 days [chunk 7]."
        assert answer.cited_chunk_indexes == [7]
    elif outcome == "refusal":
        with pytest.raises(AnswerRefusedError):
            asyncio.run(run_generation())
    else:
        with pytest.raises(AnswerGenerationError):
            asyncio.run(run_generation())

    assert len(requests) == 1
    payload = requests[0]
    assert payload["model"] == "test-model"
    assert payload["max_output_tokens"] == 500
    assert payload["store"] is False
    serialized = json.loads(json.dumps(payload))
    assert serialized["text"]["format"]["type"] == "json_schema"
    assert serialized["text"]["format"]["strict"] is True
    messages = serialized["input"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Refunds are available within 30 days." in json.dumps(messages[1])
