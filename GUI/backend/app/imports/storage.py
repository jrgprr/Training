from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .contracts import GarminImportBatch, ImportJobBreakdown, ImportJobState
from ..db import get_connection

LEGACY_PENDING_NOTE = "Pendiente persistir staging e import jobs en la siguiente fase."
PERSISTENCE_READY_NOTE = "Carga preparada para persistencia en staging y tablas finales."
LEGACY_BREAKDOWN_NOTE = "Detalle inserted/updated no disponible para este job historico."
RETRY_SAFE_TO_RETRY = "safe_to_retry"
RETRY_INSPECT_BEFORE = "inspect_before_retry"


@dataclass(slots=True)
class ImportJobSummary:
    import_job_id: int | None
    status: str
    rows_detected: int
    rows_loaded: int
    source_system: str = "garmin"
    import_type: str = "garminconnect"
    source_path: str | None = None
    imported_at: str | None = None
    finished_at: str | None = None
    request_scope: dict[str, Any] | None = None
    failure_stage: str | None = None
    failure_class: str | None = None
    retry_suitability: str | None = None
    partial_completion: bool = False
    operator_detail: str | None = None
    notes: list[str] = field(default_factory=list)
    breakdown: ImportJobBreakdown = field(default_factory=ImportJobBreakdown)
    has_breakdown_details: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "import_job_id": self.import_job_id,
            "source_system": self.source_system,
            "import_type": self.import_type,
            "source_path": self.source_path,
            "imported_at": self.imported_at,
            "finished_at": self.finished_at,
            "request_scope": self.request_scope,
            "status": self.status,
            "rows_detected": self.rows_detected,
            "rows_loaded": self.rows_loaded,
            "failure_stage": self.failure_stage,
            "failure_class": self.failure_class,
            "retry_suitability": self.retry_suitability,
            "partial_completion": self.partial_completion,
            "operator_detail": self.operator_detail,
            "notes": self.notes,
            "breakdown": self.breakdown.to_dict(),
            "has_breakdown_details": self.has_breakdown_details,
        }


class GarminImportStorage:
    """Persistencia minima para import jobs, staging y carga final de V0.3."""

    AUTO_LINK_NOTE = "Garmin auto-links inserted/updated: {inserted}/{retained}"
    DEFAULT_IMPORT_TYPE = "garminconnect"

    def __init__(self) -> None:
        pass

    @staticmethod
    def _discipline_family(discipline: str | None) -> str | None:
        if discipline in {"road_biking", "indoor_cycling", "mountain_biking"}:
            return "cycling"
        if discipline in {"walking", "hiking"}:
            return "walking"
        if discipline in {"running", "trail_running"}:
            return "running"
        return discipline

    @staticmethod
    def _planned_session_families(planned_type: str | None, primary_session: str | None) -> set[str]:
        normalized_planned_type = (planned_type or "").strip().lower()
        normalized_primary_session = (primary_session or "").strip().lower()

        families_by_planned_type = {
            "bicicleta-z2": {"cycling"},
            "salida-larga": {"cycling"},
            "referencia-aerobica": {"cycling"},
            "fuerza": {"strength_training"},
            "activacion": {"walking", "cycling"},
            "recuperacion": {"walking", "cycling"},
            "complementaria": {"walking", "cycling", "hiking"},
        }
        if normalized_planned_type in families_by_planned_type:
            return families_by_planned_type[normalized_planned_type]

        inferred_families: set[str] = set()
        if "fuerza" in normalized_primary_session:
            inferred_families.add("strength_training")
        if "bicicleta" in normalized_primary_session:
            inferred_families.add("cycling")
        if "monte" in normalized_primary_session or "sender" in normalized_primary_session:
            inferred_families.add("hiking")
        if "paseo" in normalized_primary_session or "caminar" in normalized_primary_session:
            inferred_families.add("walking")
        return inferred_families

    def _auto_link_garmin_activities(self, connection: Any, season_id: int, activity_dates: list[str]) -> tuple[int, int]:
        unique_dates = sorted({activity_date for activity_date in activity_dates if activity_date})
        if not unique_dates:
            return (0, 0)

        placeholders = ", ".join("?" for _ in unique_dates)
        connection.execute(
            f"""
            DELETE FROM link_plan_execution
            WHERE link_type = 'garmin_auto'
              AND planned_session_id IN (
                  SELECT ps.planned_session_id
                  FROM plan_planned_sessions ps
                  JOIN plan_micro_weeks w ON w.week_id = ps.week_id
                  JOIN plan_meso_blocks b ON b.block_id = w.block_id
                  WHERE b.season_id = ?
                    AND ps.session_date IN ({placeholders})
              )
            """,
            (season_id, *unique_dates),
        )

        manual_links = connection.execute(
            f"""
            SELECT l.planned_session_id, ps.session_date, l.compliance_status, l.rationale, ea.discipline
            FROM link_plan_execution l
            JOIN exec_activities ea ON ea.activity_id = l.activity_id
            JOIN plan_planned_sessions ps ON ps.planned_session_id = l.planned_session_id
            JOIN plan_micro_weeks w ON w.week_id = ps.week_id
            JOIN plan_meso_blocks b ON b.block_id = w.block_id
            WHERE b.season_id = ?
              AND ps.session_date IN ({placeholders})
              AND ea.source_system LIKE 'manual%'
            """,
            (season_id, *unique_dates),
        ).fetchall()

        unlinked_sessions = connection.execute(
            f"""
            SELECT ps.planned_session_id, ps.session_date, ps.planned_type, ps.primary_session
            FROM plan_planned_sessions ps
            JOIN plan_micro_weeks w ON w.week_id = ps.week_id
            JOIN plan_meso_blocks b ON b.block_id = w.block_id
            WHERE b.season_id = ?
              AND ps.session_date IN ({placeholders})
              AND NOT EXISTS (
                  SELECT 1
                  FROM link_plan_execution l
                  WHERE l.planned_session_id = ps.planned_session_id
              )
            """,
            (season_id, *unique_dates),
        ).fetchall()

        garmin_candidates = connection.execute(
            f"""
            SELECT activity_id, activity_date, discipline
            FROM exec_activities
            WHERE source_system = 'garmin'
              AND season_id = ?
              AND activity_date IN ({placeholders})
            """,
            (season_id, *unique_dates),
        ).fetchall()

        candidates_by_date: dict[str, list[dict[str, Any]]] = {}
        for candidate in garmin_candidates:
            candidates_by_date.setdefault(candidate["activity_date"], []).append(dict(candidate))

        inserted = 0
        retained = 0
        for manual_link in manual_links:
            target_family = self._discipline_family(manual_link["discipline"])
            compatible_candidates = [
                candidate
                for candidate in candidates_by_date.get(manual_link["session_date"], [])
                if self._discipline_family(candidate.get("discipline")) == target_family
            ]
            if len(compatible_candidates) != 1:
                continue

            candidate = compatible_candidates[0]
            existing = connection.execute(
                """
                SELECT link_id
                FROM link_plan_execution
                WHERE planned_session_id = ? AND activity_id = ?
                """,
                (manual_link["planned_session_id"], candidate["activity_id"]),
            ).fetchone()
            if existing is not None:
                retained += 1
                continue

            connection.execute(
                """
                INSERT INTO link_plan_execution (
                    planned_session_id, activity_id, link_type, compliance_status, rationale
                ) VALUES (?, ?, 'garmin_auto', ?, ?)
                """,
                (
                    manual_link["planned_session_id"],
                    candidate["activity_id"],
                    manual_link["compliance_status"],
                    manual_link["rationale"],
                ),
            )
            inserted += 1

        for planned_session in unlinked_sessions:
            target_families = self._planned_session_families(
                planned_session["planned_type"],
                planned_session["primary_session"],
            )
            if not target_families:
                continue

            compatible_candidates = [
                candidate
                for candidate in candidates_by_date.get(planned_session["session_date"], [])
                if self._discipline_family(candidate.get("discipline")) in target_families
            ]
            if len(compatible_candidates) != 1:
                continue

            candidate = compatible_candidates[0]
            connection.execute(
                """
                INSERT INTO link_plan_execution (
                    planned_session_id, activity_id, link_type, compliance_status, rationale
                ) VALUES (?, ?, 'garmin_auto', 'completed', ?)
                """,
                (
                    planned_session["planned_session_id"],
                    candidate["activity_id"],
                    "Autoenlace Garmin por fecha y familia de disciplina.",
                ),
            )
            inserted += 1

        return (inserted, retained)

    @staticmethod
    def _serialize_job_details(notes: list[str], breakdown: ImportJobBreakdown) -> str:
        return json.dumps({"messages": notes, "breakdown": breakdown.to_dict()}, ensure_ascii=True)

    @staticmethod
    def _derive_retry_suitability(
        *,
        status: str,
        failure_stage: str | None = None,
        failure_class: str | None = None,
        partial_completion: bool = False,
    ) -> str | None:
        if status == "running":
            return None
        if partial_completion or status == "partial_completed":
            return RETRY_INSPECT_BEFORE
        if failure_class in {"source_data_normalization", "persistence_transaction"}:
            return RETRY_INSPECT_BEFORE
        if failure_stage in {"normalize", "persist"}:
            return RETRY_INSPECT_BEFORE
        return RETRY_SAFE_TO_RETRY

    @staticmethod
    def _build_request_scope(
        *,
        season_id: int,
        request_date_from: str | None,
        request_date_to: str | None,
        include_daily_metrics: int | bool | None,
    ) -> dict[str, Any]:
        return {
            "season_id": season_id,
            "date_from": request_date_from,
            "date_to": request_date_to,
            "include_daily_metrics": bool(include_daily_metrics),
        }

    @staticmethod
    def _coerce_notes(notes: list[str] | None, operator_detail: str | None = None) -> list[str]:
        normalized = list(notes or [])
        if operator_detail and operator_detail not in normalized:
            normalized.append(operator_detail)
        return normalized

    def start_import_job(
        self,
        *,
        season_id: int,
        source_system: str = "garmin",
        import_type: str | None = None,
        source_path: str | None = None,
        request_date_from: str | None = None,
        request_date_to: str | None = None,
        include_daily_metrics: bool = True,
        notes: list[str] | None = None,
    ) -> int:
        breakdown = ImportJobBreakdown()
        initial_notes = notes or ["Importacion Garmin iniciada."]
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO meta_import_jobs (
                    season_id, source_system, import_type, source_path,
                    request_date_from, request_date_to, include_daily_metrics,
                    rows_detected, rows_loaded, status, failure_stage, failure_class,
                    retry_suitability, partial_completion, operator_detail,
                    activity_rows_detected, activity_rows_inserted, activity_rows_updated, activity_rows_skipped,
                    daily_metric_rows_detected, daily_metric_rows_inserted, daily_metric_rows_updated, daily_metric_rows_skipped,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 'running', NULL, NULL, NULL, 0, NULL, 0, 0, 0, 0, 0, 0, 0, 0, ?)
                """,
                (
                    season_id,
                    source_system,
                    import_type or self.DEFAULT_IMPORT_TYPE,
                    source_path,
                    request_date_from,
                    request_date_to,
                    1 if include_daily_metrics else 0,
                    self._serialize_job_details(initial_notes, breakdown),
                ),
            )
            return int(cursor.lastrowid)

    def fail_import_job(
        self,
        import_job_id: int,
        *,
        notes: list[str],
        rows_detected: int = 0,
        rows_loaded: int = 0,
        status: str = "failed",
        failure_stage: str | None = None,
        failure_class: str | None = None,
        partial_completion: bool = False,
        operator_detail: str | None = None,
        breakdown: ImportJobBreakdown | None = None,
    ) -> None:
        effective_breakdown = breakdown or ImportJobBreakdown()
        effective_notes = self._coerce_notes(notes, operator_detail)
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE meta_import_jobs
                SET rows_detected = ?, rows_loaded = ?, status = ?,
                    finished_at = CURRENT_TIMESTAMP,
                    failure_stage = ?, failure_class = ?, retry_suitability = ?,
                    partial_completion = ?, operator_detail = ?,
                    activity_rows_detected = ?, activity_rows_inserted = ?, activity_rows_updated = ?, activity_rows_skipped = ?,
                    daily_metric_rows_detected = ?, daily_metric_rows_inserted = ?, daily_metric_rows_updated = ?, daily_metric_rows_skipped = ?,
                    notes = ?
                WHERE import_job_id = ?
                """,
                (
                    rows_detected,
                    rows_loaded,
                    status,
                    failure_stage,
                    failure_class,
                    self._derive_retry_suitability(
                        status=status,
                        failure_stage=failure_stage,
                        failure_class=failure_class,
                        partial_completion=partial_completion,
                    ),
                    1 if partial_completion else 0,
                    operator_detail,
                    effective_breakdown.activity_rows_detected,
                    effective_breakdown.activity_rows_inserted,
                    effective_breakdown.activity_rows_updated,
                    effective_breakdown.activity_rows_skipped,
                    effective_breakdown.daily_metric_rows_detected,
                    effective_breakdown.daily_metric_rows_inserted,
                    effective_breakdown.daily_metric_rows_updated,
                    effective_breakdown.daily_metric_rows_skipped,
                    self._serialize_job_details(effective_notes, effective_breakdown),
                    import_job_id,
                ),
            )

    @staticmethod
    def _normalize_notes(messages: list[str]) -> list[str]:
        normalized: list[str] = []
        for message in messages:
            candidate = PERSISTENCE_READY_NOTE if message == LEGACY_PENDING_NOTE else message
            if candidate not in normalized:
                normalized.append(candidate)
        return normalized

    @staticmethod
    def _has_breakdown_notes(messages: list[str]) -> bool:
        return any(
            message.startswith("Activities inserted/updated:") or message.startswith("Daily metrics inserted/updated:")
            for message in messages
        )

    @staticmethod
    def _deserialize_job_details(raw_notes: str | None) -> dict[str, Any]:
        details = {
            "messages": [],
            "breakdown": ImportJobBreakdown().to_dict(),
            "has_breakdown_details": False,
        }
        if not raw_notes:
            return details
        try:
            payload = json.loads(raw_notes)
        except json.JSONDecodeError:
            messages = GarminImportStorage._normalize_notes([raw_notes])
            messages.append(LEGACY_BREAKDOWN_NOTE)
            details["messages"] = messages
            return details
        if isinstance(payload, list):
            messages = GarminImportStorage._normalize_notes([str(item) for item in payload])
            messages.append(LEGACY_BREAKDOWN_NOTE)
            details["messages"] = messages
            return details
        if isinstance(payload, dict):
            messages = payload.get("messages")
            breakdown = payload.get("breakdown")
            normalized_messages = GarminImportStorage._normalize_notes([str(item) for item in messages] if isinstance(messages, list) else [])
            has_breakdown_details = GarminImportStorage._has_breakdown_notes(normalized_messages)
            if not has_breakdown_details and normalized_messages:
                normalized_messages.append(LEGACY_BREAKDOWN_NOTE)
            details["messages"] = normalized_messages
            details["breakdown"] = breakdown if isinstance(breakdown, dict) else ImportJobBreakdown().to_dict()
            details["has_breakdown_details"] = has_breakdown_details
            return details
        messages = GarminImportStorage._normalize_notes([str(payload)])
        messages.append(LEGACY_BREAKDOWN_NOTE)
        details["messages"] = messages
        return details

    def persist_batch(self, batch: GarminImportBatch, import_job_id: int | None = None) -> ImportJobSummary:
        counts = batch.counts()
        rows_detected = counts["activities_detected"] + counts["daily_metrics_detected"]
        rows_loaded = 0
        breakdown = ImportJobBreakdown(
            activity_rows_detected=counts["activities_detected"],
            daily_metric_rows_detected=counts["daily_metrics_detected"],
        )

        with get_connection() as connection:
            if import_job_id is None:
                cursor = connection.execute(
                    """
                    INSERT INTO meta_import_jobs (
                        season_id, source_system, import_type, source_path,
                        request_date_from, request_date_to, include_daily_metrics,
                        rows_detected, rows_loaded, status, failure_stage, failure_class,
                        retry_suitability, partial_completion, operator_detail,
                        activity_rows_detected, activity_rows_inserted, activity_rows_updated, activity_rows_skipped,
                        daily_metric_rows_detected, daily_metric_rows_inserted, daily_metric_rows_updated, daily_metric_rows_skipped,
                        notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'running', NULL, NULL, NULL, 0, NULL, ?, 0, 0, 0, ?, 0, 0, 0, ?)
                    """,
                    (
                        batch.request.season_id,
                        batch.metadata.source_system,
                        batch.metadata.source_label,
                        f"{batch.request.date_from}:{batch.request.date_to}",
                        batch.request.date_from,
                        batch.request.date_to,
                        1 if batch.request.include_daily_metrics else 0,
                        rows_detected,
                        breakdown.activity_rows_detected,
                        breakdown.daily_metric_rows_detected,
                        self._serialize_job_details(batch.metadata.notes, breakdown),
                    ),
                )
                import_job_id = int(cursor.lastrowid)
            else:
                connection.execute(
                    """
                    UPDATE meta_import_jobs
                    SET request_date_from = ?, request_date_to = ?, include_daily_metrics = ?,
                        rows_detected = ?, status = 'running',
                        activity_rows_detected = ?, daily_metric_rows_detected = ?,
                        notes = ?
                    WHERE import_job_id = ?
                    """,
                    (
                        batch.request.date_from,
                        batch.request.date_to,
                        1 if batch.request.include_daily_metrics else 0,
                        rows_detected,
                        breakdown.activity_rows_detected,
                        breakdown.daily_metric_rows_detected,
                        self._serialize_job_details(batch.metadata.notes, breakdown),
                        import_job_id,
                    ),
                )

            for activity in batch.activities:
                existing_activity = connection.execute(
                    """
                    SELECT activity_id
                    FROM exec_activities
                    WHERE source_system = ? AND external_activity_id = ?
                    """,
                    (batch.metadata.source_system, activity.external_activity_id),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO staging_garmin_activities (
                        import_job_id, season_id, source_system, external_activity_id, activity_date,
                        started_at, discipline, activity_type, duration_seconds, distance_meters,
                        ascent_meters, calories, avg_hr, max_hr, avg_power, normalized_power,
                        training_load, avg_pace_seconds_per_km, raw_payload_path, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        import_job_id,
                        batch.request.season_id,
                        batch.metadata.source_system,
                        activity.external_activity_id,
                        activity.activity_date,
                        activity.started_at,
                        activity.discipline,
                        activity.activity_type,
                        activity.duration_seconds,
                        activity.distance_meters,
                        activity.ascent_meters,
                        activity.calories,
                        activity.avg_hr,
                        activity.max_hr,
                        activity.avg_power,
                        activity.normalized_power,
                        activity.training_load,
                        activity.avg_pace_seconds_per_km,
                        activity.raw_payload_path,
                        activity.notes,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO exec_activities (
                        season_id, source_system, external_activity_id, activity_date, started_at,
                        discipline, activity_type, duration_seconds, distance_meters, ascent_meters,
                        calories, avg_hr, max_hr, avg_power, normalized_power, training_load,
                        avg_pace_seconds_per_km, raw_payload_path, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_system, external_activity_id) DO UPDATE SET
                        activity_date = excluded.activity_date,
                        started_at = excluded.started_at,
                        discipline = excluded.discipline,
                        activity_type = excluded.activity_type,
                        duration_seconds = excluded.duration_seconds,
                        distance_meters = excluded.distance_meters,
                        ascent_meters = excluded.ascent_meters,
                        calories = excluded.calories,
                        avg_hr = excluded.avg_hr,
                        max_hr = excluded.max_hr,
                        avg_power = excluded.avg_power,
                        normalized_power = excluded.normalized_power,
                        training_load = excluded.training_load,
                        avg_pace_seconds_per_km = excluded.avg_pace_seconds_per_km,
                        raw_payload_path = excluded.raw_payload_path,
                        notes = excluded.notes
                    """,
                    (
                        batch.request.season_id,
                        batch.metadata.source_system,
                        activity.external_activity_id,
                        activity.activity_date,
                        activity.started_at,
                        activity.discipline,
                        activity.activity_type,
                        activity.duration_seconds,
                        activity.distance_meters,
                        activity.ascent_meters,
                        activity.calories,
                        activity.avg_hr,
                        activity.max_hr,
                        activity.avg_power,
                        activity.normalized_power,
                        activity.training_load,
                        activity.avg_pace_seconds_per_km,
                        activity.raw_payload_path,
                        activity.notes,
                    ),
                )
                if existing_activity is None:
                    breakdown.activity_rows_inserted += 1
                else:
                    breakdown.activity_rows_updated += 1
                rows_loaded += 1

            for metric in batch.daily_metrics:
                existing_metric = connection.execute(
                    """
                    SELECT daily_metric_id
                    FROM exec_daily_metrics
                    WHERE season_id = ? AND metric_date = ? AND source_system = ?
                    """,
                    (batch.request.season_id, metric.metric_date, batch.metadata.source_system),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO staging_garmin_daily_metrics (
                        import_job_id, season_id, source_system, metric_date, weight_kg, sleep_hours,
                        sleep_quality, resting_hr, hrv, body_battery, subjective_energy,
                        subjective_fatigue, notes, raw_payload_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        import_job_id,
                        batch.request.season_id,
                        batch.metadata.source_system,
                        metric.metric_date,
                        metric.weight_kg,
                        metric.sleep_hours,
                        metric.sleep_quality,
                        metric.resting_hr,
                        metric.hrv,
                        metric.body_battery,
                        metric.subjective_energy,
                        metric.subjective_fatigue,
                        metric.notes,
                        metric.raw_payload_path,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO exec_daily_metrics (
                        season_id, metric_date, source_system, weight_kg, sleep_hours, sleep_quality,
                        resting_hr, hrv, body_battery, subjective_energy, subjective_fatigue, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(season_id, metric_date, source_system) DO UPDATE SET
                        weight_kg = excluded.weight_kg,
                        sleep_hours = excluded.sleep_hours,
                        sleep_quality = excluded.sleep_quality,
                        resting_hr = excluded.resting_hr,
                        hrv = excluded.hrv,
                        body_battery = excluded.body_battery,
                        subjective_energy = excluded.subjective_energy,
                        subjective_fatigue = excluded.subjective_fatigue,
                        notes = excluded.notes
                    """,
                    (
                        batch.request.season_id,
                        metric.metric_date,
                        batch.metadata.source_system,
                        metric.weight_kg,
                        metric.sleep_hours,
                        metric.sleep_quality,
                        metric.resting_hr,
                        metric.hrv,
                        metric.body_battery,
                        metric.subjective_energy,
                        metric.subjective_fatigue,
                        metric.notes,
                    ),
                )
                if existing_metric is None:
                    breakdown.daily_metric_rows_inserted += 1
                else:
                    breakdown.daily_metric_rows_updated += 1
                rows_loaded += 1

            auto_link_inserted, auto_link_retained = self._auto_link_garmin_activities(
                connection,
                batch.request.season_id,
                [activity.activity_date for activity in batch.activities],
            )

            final_notes = list(batch.metadata.notes)
            final_notes.append(f"Activities staged: {len(batch.activities)}")
            final_notes.append(f"Daily metrics staged: {len(batch.daily_metrics)}")
            final_notes.append(f"Activities inserted/updated: {breakdown.activity_rows_inserted}/{breakdown.activity_rows_updated}")
            final_notes.append(f"Daily metrics inserted/updated: {breakdown.daily_metric_rows_inserted}/{breakdown.daily_metric_rows_updated}")
            final_notes.append(self.AUTO_LINK_NOTE.format(inserted=auto_link_inserted, retained=auto_link_retained))
            breakdown.activity_rows_skipped = max(
                breakdown.activity_rows_detected - breakdown.activity_rows_inserted - breakdown.activity_rows_updated,
                0,
            )
            breakdown.daily_metric_rows_skipped = max(
                breakdown.daily_metric_rows_detected - breakdown.daily_metric_rows_inserted - breakdown.daily_metric_rows_updated,
                0,
            )
            operator_detail = "Importacion Garmin completada."
            connection.execute(
                """
                UPDATE meta_import_jobs
                SET rows_loaded = ?, status = 'completed', finished_at = CURRENT_TIMESTAMP,
                    failure_stage = NULL, failure_class = NULL, retry_suitability = ?,
                    partial_completion = 0, operator_detail = ?,
                    activity_rows_detected = ?, activity_rows_inserted = ?, activity_rows_updated = ?, activity_rows_skipped = ?,
                    daily_metric_rows_detected = ?, daily_metric_rows_inserted = ?, daily_metric_rows_updated = ?, daily_metric_rows_skipped = ?,
                    notes = ?
                WHERE import_job_id = ?
                """,
                (
                    rows_loaded,
                    self._derive_retry_suitability(status="completed"),
                    operator_detail,
                    breakdown.activity_rows_detected,
                    breakdown.activity_rows_inserted,
                    breakdown.activity_rows_updated,
                    breakdown.activity_rows_skipped,
                    breakdown.daily_metric_rows_detected,
                    breakdown.daily_metric_rows_inserted,
                    breakdown.daily_metric_rows_updated,
                    breakdown.daily_metric_rows_skipped,
                    self._serialize_job_details(final_notes, breakdown),
                    import_job_id,
                ),
            )

        return ImportJobSummary(
            import_job_id=import_job_id,
            source_system=batch.metadata.source_system,
            import_type=batch.metadata.source_label,
            source_path=f"{batch.request.date_from}:{batch.request.date_to}",
            request_scope=batch.request.to_scope_dict(),
            status="completed",
            rows_detected=rows_detected,
            rows_loaded=rows_loaded,
            retry_suitability=self._derive_retry_suitability(status="completed"),
            operator_detail=operator_detail,
            notes=final_notes,
            breakdown=breakdown,
            has_breakdown_details=True,
        )

    def _state_from_row(self, row: dict[str, Any], notes: list[str], legacy_breakdown: ImportJobBreakdown, has_breakdown_details: bool) -> ImportJobState:
        column_breakdown = ImportJobBreakdown(
            activity_rows_detected=int(row.get("activity_rows_detected") or 0),
            activity_rows_inserted=int(row.get("activity_rows_inserted") or 0),
            activity_rows_updated=int(row.get("activity_rows_updated") or 0),
            activity_rows_skipped=int(row.get("activity_rows_skipped") or 0),
            daily_metric_rows_detected=int(row.get("daily_metric_rows_detected") or 0),
            daily_metric_rows_inserted=int(row.get("daily_metric_rows_inserted") or 0),
            daily_metric_rows_updated=int(row.get("daily_metric_rows_updated") or 0),
            daily_metric_rows_skipped=int(row.get("daily_metric_rows_skipped") or 0),
        )
        effective_breakdown = column_breakdown
        if effective_breakdown.to_dict() == ImportJobBreakdown().to_dict() and legacy_breakdown.to_dict() != ImportJobBreakdown().to_dict():
            effective_breakdown = legacy_breakdown

        return ImportJobState(
            source_system=str(row.get("source_system") or "garmin"),
            import_type=str(row.get("import_type") or self.DEFAULT_IMPORT_TYPE),
            source_path=row.get("source_path"),
            imported_at=row.get("imported_at"),
            finished_at=row.get("finished_at"),
            request_scope=self._build_request_scope(
                season_id=int(row.get("season_id") or 0),
                request_date_from=row.get("request_date_from"),
                request_date_to=row.get("request_date_to"),
                include_daily_metrics=row.get("include_daily_metrics"),
            ),
            status=str(row.get("status") or "unknown"),
            rows_detected=int(row.get("rows_detected") or 0),
            rows_loaded=int(row.get("rows_loaded") or 0),
            failure_stage=row.get("failure_stage"),
            failure_class=row.get("failure_class"),
            retry_suitability=row.get("retry_suitability"),
            partial_completion=bool(row.get("partial_completion")),
            operator_detail=row.get("operator_detail"),
            notes=notes,
            breakdown=effective_breakdown,
            has_breakdown_details=has_breakdown_details or effective_breakdown.to_dict() != ImportJobBreakdown().to_dict(),
        )

    def list_import_jobs(self) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT import_job_id, season_id, source_system, import_type, source_path,
                       imported_at, finished_at, request_date_from, request_date_to, include_daily_metrics,
                       rows_detected, rows_loaded, status, failure_stage, failure_class,
                       retry_suitability, partial_completion, operator_detail,
                       activity_rows_detected, activity_rows_inserted, activity_rows_updated, activity_rows_skipped,
                       daily_metric_rows_detected, daily_metric_rows_inserted, daily_metric_rows_updated, daily_metric_rows_skipped,
                       notes
                FROM meta_import_jobs
                ORDER BY import_job_id DESC
                """
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            result = dict(row)
            details = self._deserialize_job_details(result.get("notes"))
            state = self._state_from_row(
                result,
                details["messages"],
                ImportJobBreakdown.from_dict(details["breakdown"]),
                bool(details["has_breakdown_details"]),
            )
            result["request_scope"] = state.request_scope
            result["finished_at"] = state.finished_at
            result["failure_stage"] = state.failure_stage
            result["failure_class"] = state.failure_class
            result["retry_suitability"] = state.retry_suitability
            result["partial_completion"] = state.partial_completion
            result["operator_detail"] = state.operator_detail
            result["notes"] = state.notes
            result["breakdown"] = state.breakdown.to_dict()
            result["has_breakdown_details"] = state.has_breakdown_details
            results.append(result)
        return results

    def get_import_job(self, import_job_id: int) -> dict[str, Any] | None:
        with get_connection() as connection:
            job = connection.execute(
                """
                  SELECT import_job_id, season_id, source_system, import_type, source_path,
                      imported_at, finished_at, request_date_from, request_date_to, include_daily_metrics,
                      rows_detected, rows_loaded, status, failure_stage, failure_class,
                      retry_suitability, partial_completion, operator_detail,
                      activity_rows_detected, activity_rows_inserted, activity_rows_updated, activity_rows_skipped,
                      daily_metric_rows_detected, daily_metric_rows_inserted, daily_metric_rows_updated, daily_metric_rows_skipped,
                      notes
                FROM meta_import_jobs
                WHERE import_job_id = ?
                """,
                (import_job_id,),
            ).fetchone()
            if job is None:
                return None
            activities = connection.execute(
                "SELECT COUNT(*) AS total FROM staging_garmin_activities WHERE import_job_id = ?",
                (import_job_id,),
            ).fetchone()
            daily_metrics = connection.execute(
                "SELECT COUNT(*) AS total FROM staging_garmin_daily_metrics WHERE import_job_id = ?",
                (import_job_id,),
            ).fetchone()

        result = dict(job)
        details = self._deserialize_job_details(result.get("notes"))
        state = self._state_from_row(
            result,
            details["messages"],
            ImportJobBreakdown.from_dict(details["breakdown"]),
            bool(details["has_breakdown_details"]),
        )
        result["request_scope"] = state.request_scope
        result["finished_at"] = state.finished_at
        result["failure_stage"] = state.failure_stage
        result["failure_class"] = state.failure_class
        result["retry_suitability"] = state.retry_suitability
        result["partial_completion"] = state.partial_completion
        result["operator_detail"] = state.operator_detail
        result["notes"] = state.notes
        result["breakdown"] = state.breakdown.to_dict()
        result["has_breakdown_details"] = state.has_breakdown_details
        result["staging_counts"] = {
            "activities": int(activities["total"]),
            "daily_metrics": int(daily_metrics["total"]),
        }
        return result
