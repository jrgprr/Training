import hashlib
from typing import List
from fastapi import UploadFile

from app.repositories.import_repository import ImportRepository


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _guess_file_type(upload_file: UploadFile) -> str | None:
    if upload_file.content_type:
        return upload_file.content_type
    if upload_file.filename and '.' in upload_file.filename:
        return upload_file.filename.rsplit('.', 1)[1].lower()
    return None


async def process_garmin_import(files: List[UploadFile]) -> dict[str, object]:
    if not files:
        raise ValueError("No files provided for import")

    repo = ImportRepository()
    user_id = repo.get_or_create_default_user()
    batch = repo.create_import_batch(
        user_id=user_id,
        import_type="garmin_file",
        notes="Uploaded from frontend import screen",
    )

    results: list[dict[str, object]] = []
    for file in files:
        contents = await file.read()
        file_hash = _hash_bytes(contents)
        file_type = _guess_file_type(file)
        metadata = {
            "filename": file.filename,
            "contentType": file.content_type,
            "size": len(contents),
        }

        import_file = repo.create_import_file(
            import_batch_id=batch.id,
            original_filename=file.filename,
            file_type=file_type,
            file_hash=file_hash,
            raw_metadata_json=metadata,
        )

        repo.create_import_record(
            import_file_id=import_file.id,
            record_type="raw_file_import",
            external_id=file_hash,
            payload_json={
                "filename": file.filename,
                "size": len(contents),
                "contentType": file.content_type,
            },
        )

        results.append(
            {
                "originalFilename": file.filename,
                "fileType": file_type,
                "fileHash": file_hash,
                "importedAt": import_file.imported_at.isoformat(),
                "status": import_file.status,
                "rawMetadata": metadata,
            }
        )

    repo.finalize_import_batch(
        import_batch_id=batch.id,
        files_count=len(results),
        records_count=len(results),
        error_count=0,
        status="completed",
    )

    return {
        "importBatchId": batch.id,
        "importType": batch.import_type,
        "filesCount": len(results),
        "status": "completed",
        "files": results,
        "notes": batch.notes,
    }
