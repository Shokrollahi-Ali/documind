from pydantic import BaseModel, Field


class DocumentUploadMetadata(BaseModel):
    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(pattern=r"^application/pdf$")
    size_bytes: int = Field(gt=0)
