from hashlib import sha256
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.base_models import ImportBatch, ImportFile, ImportRecord, UserProfile
from app.repositories.base_repository import BaseRepository


class ImportRepository(BaseRepository):
    def __init__(self, db: Session = None):
        super().__init__(db)

    def _next_id(self, model):
        max_id = self.db.query(func.max(model.id)).scalar()
        return int(max_id or 0) + 1

    def get_or_create_default_user(self) -> int:
        profile = self.db.query(UserProfile).first()
        if profile:
            return profile.id

        profile = UserProfile(
            id=self._next_id(UserProfile),
            display_name="Usuario MVP",
            preferred_units={},
            timezone="Europe/Madrid",
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile.id

    def create_import_batch(self, user_id: int, import_type: str, notes: str | None = None) -> ImportBatch:
        batch = ImportBatch(
            id=self._next_id(ImportBatch),
            user_id=user_id,
            import_type=import_type,
            status="started",
            notes=notes,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def create_import_file(
        self,
        import_batch_id: int,
        original_filename: str,
        file_type: str | None,
        file_hash: str | None,
        raw_metadata_json: dict,
    ) -> ImportFile:
        import_file = ImportFile(
            id=self._next_id(ImportFile),
            import_batch_id=import_batch_id,
            original_filename=original_filename,
            file_type=file_type,
            file_hash=file_hash,
            raw_metadata_json=raw_metadata_json,
            status="imported",
        )
        self.db.add(import_file)
        self.db.commit()
        self.db.refresh(import_file)
        return import_file

    def create_import_record(
        self,
        import_file_id: int,
        record_type: str,
        external_id: str | None,
        payload_json: dict,
    ) -> ImportRecord:
        record = ImportRecord(
            id=self._next_id(ImportRecord),
            import_file_id=import_file_id,
            record_type=record_type,
            external_id=external_id,
            payload_json=payload_json,
            normalized=False,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def finalize_import_batch(
        self,
        import_batch_id: int,
        files_count: int,
        records_count: int,
        error_count: int = 0,
        status: str = "completed",
    ) -> ImportBatch:
        batch = self.db.query(ImportBatch).filter(ImportBatch.id == import_batch_id).first()
        if not batch:
            raise ValueError("Import batch not found")

        batch.files_count = files_count
        batch.records_count = records_count
        batch.error_count = error_count
        batch.status = status
        batch.finished_at = datetime.utcnow()

        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch
