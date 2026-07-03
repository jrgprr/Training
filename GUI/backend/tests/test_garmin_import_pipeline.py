from __future__ import annotations

import unittest
from unittest.mock import Mock

from app.imports.contracts import GarminImportBatch, GarminImportRequest, ImportFetchMetadata
from app.imports.garmin_connect import GarminConnectImportError
from app.imports.pipeline import GarminImportPipeline


class GarminImportPipelineProfileSyncTests(unittest.TestCase):
    def test_run_appends_profile_sync_notes(self) -> None:
        request = GarminImportRequest(
            season_id=2026,
            date_from="2026-07-01",
            date_to="2026-07-03",
            include_daily_metrics=False,
        )
        batch = GarminImportBatch(
            request=request,
            metadata=ImportFetchMetadata(
                source_system="garmin",
                source_label="garminconnect",
                date_from=request.date_from,
                date_to=request.date_to,
                notes=["batch ok"],
            ),
            activities=[],
            daily_metrics=[],
        )
        adapter = Mock()
        adapter.sync_profile_values.return_value = {
            "status": "updated",
            "notes": ["FTP de ciclismo sincronizado desde Garmin Connect: 270 W."],
        }
        adapter.fetch.return_value = batch

        result = GarminImportPipeline(adapter=adapter).run(request)

        adapter.sync_profile_values.assert_called_once_with(season_id=2026, effective_start_date=None)
        adapter.fetch.assert_called_once_with(request)
        self.assertEqual(
            result.metadata.notes,
            ["batch ok", "FTP de ciclismo sincronizado desde Garmin Connect: 270 W."],
        )

    def test_run_keeps_import_alive_when_profile_sync_fails(self) -> None:
        request = GarminImportRequest(
            season_id=2026,
            date_from="2026-07-01",
            date_to="2026-07-03",
            include_daily_metrics=False,
        )
        batch = GarminImportBatch(
            request=request,
            metadata=ImportFetchMetadata(
                source_system="garmin",
                source_label="garminconnect",
                date_from=request.date_from,
                date_to=request.date_to,
                notes=["batch ok"],
            ),
            activities=[],
            daily_metrics=[],
        )
        adapter = Mock()
        adapter.sync_profile_values.side_effect = GarminConnectImportError("profile endpoint unavailable")
        adapter.fetch.return_value = batch

        result = GarminImportPipeline(adapter=adapter).run(request)

        adapter.fetch.assert_called_once_with(request)
        self.assertIn("No se pudo sincronizar el perfil Garmin con la app: profile endpoint unavailable", result.metadata.notes)


if __name__ == "__main__":
    unittest.main()