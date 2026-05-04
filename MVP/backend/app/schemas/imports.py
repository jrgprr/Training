from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ImportFileSummary(BaseModel):
    originalFilename: str
    fileType: str | None
    fileHash: str | None
    importedAt: datetime
    status: str
    rawMetadata: dict[str, Any]


class ImportUploadResponse(BaseModel):
    importBatchId: int
    importType: str
    filesCount: int
    status: str
    files: list[ImportFileSummary]
    notes: str | None
