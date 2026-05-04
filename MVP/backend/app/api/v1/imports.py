from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.imports import ImportUploadResponse
from app.services.import_service import process_garmin_import

router = APIRouter()


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_garmin_files(files: List[UploadFile] = File(...)) -> ImportUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    try:
        result = await process_garmin_import(files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ImportUploadResponse(**result)
