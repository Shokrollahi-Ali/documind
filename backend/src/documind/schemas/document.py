from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from documind.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime
