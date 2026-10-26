import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

import pytest

from documind.documents.lease_heartbeat import (
    ProcessingLeaseLostError,
    maintain_processing_lease,
)


def test_heartbeat_stops_when_renewal_is_rejected() -> None:
    session_factory = MagicMock()
    document_id = uuid4()
    owner_id = uuid4()
    attempt_id = uuid4()

    with (
        patch(
            "documind.documents.lease_heartbeat.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
        patch(
            "documind.documents.lease_heartbeat.renew_document_processing_lease",
            new_callable=AsyncMock,
            side_effect=[True, False],
        ) as renew,
    ):
        with pytest.raises(ProcessingLeaseLostError, match=str(document_id)):
            asyncio.run(
                maintain_processing_lease(
                    session_factory=session_factory,
                    document_id=document_id,
                    owner_id=owner_id,
                    attempt_id=attempt_id,
                    lease_seconds=300,
                )
            )

    assert sleep.await_args_list == [call(100.0), call(100.0)]
    assert session_factory.call_count == 2
    assert renew.await_args_list == [
        call(
            database_session=session_factory.return_value.__aenter__.return_value,
            document_id=document_id,
            owner_id=owner_id,
            attempt_id=attempt_id,
            lease_seconds=300,
        ),
        call(
            database_session=session_factory.return_value.__aenter__.return_value,
            document_id=document_id,
            owner_id=owner_id,
            attempt_id=attempt_id,
            lease_seconds=300,
        ),
    ]
