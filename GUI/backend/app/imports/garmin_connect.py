from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from ..activity_quality import (
    normalize_metric_readings_from_activity_detail,
    normalize_route_points_from_activity_detail,
    normalize_route_points_from_tcx_artifact,
)
from ..db import initialize_database
from .contracts import (
    GarminImportBatch,
    GarminImportRequest,
    ImportFetchMetadata,
    NormalizedActivity,
    NormalizedDailyMetric,
    NormalizedSegmentDefinition,
    NormalizedSegmentEffort,
    NormalizedWeightMeasurement,
    iter_dates,
)


class GarminConnectNotConfiguredError(RuntimeError):
    pass


class GarminConnectImportError(RuntimeError):
    pass


class GarminConnectAuthenticationImportError(GarminConnectImportError):
    pass


class GarminConnectTransportImportError(GarminConnectImportError):
    pass


def classify_garmin_failure(error: Exception) -> dict[str, str]:
    if isinstance(error, GarminConnectNotConfiguredError | GarminConnectAuthenticationImportError):
        return {
            "failure_stage": "configuration",
            "failure_class": "configuration_authentication",
            "operator_detail": str(error),
        }
    if isinstance(error, GarminConnectTransportImportError | GarminConnectImportError):
        return {
            "failure_stage": "fetch",
            "failure_class": "transport_rate_limit",
            "operator_detail": str(error),
        }
    if isinstance(error, NotImplementedError):
        return {
            "failure_stage": "normalize",
            "failure_class": "source_data_normalization",
            "operator_detail": str(error),
        }
    return {
        "failure_stage": "persist",
        "failure_class": "persistence_transaction",
        "operator_detail": str(error),
    }


@dataclass(slots=True)
class GarminConnectConfiguration:
    username: str | None
    password: str | None
    session_path: str | None
    artifacts_path: str | None
    mfa_code: str | None = None

    @classmethod
    def from_environment(cls) -> "GarminConnectConfiguration":
        return cls(
            username=os.getenv("GARMIN_CONNECT_USERNAME"),
            password=os.getenv("GARMIN_CONNECT_PASSWORD"),
            session_path=os.getenv("GARMIN_CONNECT_SESSION_PATH"),
            artifacts_path=os.getenv("GARMIN_CONNECT_ARTIFACTS_PATH"),
            mfa_code=os.getenv("GARMIN_CONNECT_MFA_CODE"),
        )

    @property
    def tokenstore_path(self) -> str | None:
        if not self.session_path:
            return None
        return str(Path(self.session_path).expanduser())

    @property
    def activity_artifacts_root(self) -> str:
        if self.artifacts_path:
            return str(Path(self.artifacts_path).expanduser())
        return str(self.default_activity_artifacts_root_template)

    @property
    def workspace_root(self) -> Path:
        return Path(__file__).resolve().parents[4]

    @property
    def default_activity_artifacts_root_template(self) -> Path:
        return self.workspace_root / "<season_id>" / "Datos" / "Importaciones" / "Garmin" / "Actividades"

    def resolve_activity_artifacts_root(self, season_id: int | str) -> Path:
        if self.artifacts_path:
            return Path(self.activity_artifacts_root)
        return self.workspace_root / str(season_id) / "Datos" / "Importaciones" / "Garmin" / "Actividades"

    def has_credentials(self) -> bool:
        return bool(self.username and self.password)

    def has_tokenstore(self) -> bool:
        tokenstore_path = self.tokenstore_path
        if not tokenstore_path:
            return False
        tokenstore = Path(tokenstore_path)
        if tokenstore.is_file():
            return True
        if tokenstore.is_dir():
            return any(tokenstore.iterdir())
        return False


class GarminConnectAdapter:
    PACE_DISCIPLINES = {
        "hiking",
        "nordic_walking",
        "running",
        "trail_walking",
        "trail_running",
        "walking",
    }
    HIKING_NAME_HINTS = ("senderismo", "hiking", "trek", "trekking")
    CYCLING_DISCIPLINES = {"road_biking", "indoor_cycling", "mountain_biking", "cycling"}
    def __init__(self, configuration: GarminConnectConfiguration | None = None) -> None:
        self.configuration = configuration or GarminConnectConfiguration.from_environment()
        self._client: Garmin | None = None

    def validate_configuration(self) -> None:
        if self.configuration.has_tokenstore():
            return
        if self.configuration.has_credentials():
            return
        raise GarminConnectNotConfiguredError(
            "Garmin Connect no esta configurado. Define GARMIN_CONNECT_SESSION_PATH o GARMIN_CONNECT_USERNAME y GARMIN_CONNECT_PASSWORD."
        )

    def configuration_status(self) -> dict[str, Any]:
        tokenstore_path = self.configuration.tokenstore_path
        activity_artifacts_root = self.configuration.activity_artifacts_root if self.configuration.artifacts_path else None
        activity_artifacts_root_template = (
            None if self.configuration.artifacts_path else self.configuration.activity_artifacts_root
        )
        tokenstore_available = self.configuration.has_tokenstore()
        credentials_available = self.configuration.has_credentials()
        if tokenstore_available:
            return {
                "configured": True,
                "auth_mode": "tokenstore",
                "tokenstore_path": tokenstore_path,
                "activity_artifacts_root": activity_artifacts_root,
                "activity_artifacts_root_template": activity_artifacts_root_template,
                "tokenstore_available": True,
                "credentials_available": credentials_available,
                "detail": "Garmin Connect listo usando tokenstore persistente.",
            }
        if credentials_available:
            return {
                "configured": True,
                "auth_mode": "credentials",
                "tokenstore_path": tokenstore_path,
                "activity_artifacts_root": activity_artifacts_root,
                "activity_artifacts_root_template": activity_artifacts_root_template,
                "tokenstore_available": False,
                "credentials_available": True,
                "detail": "Garmin Connect listo usando credenciales en entorno.",
            }
        return {
            "configured": False,
            "auth_mode": "missing",
            "tokenstore_path": tokenstore_path,
            "activity_artifacts_root": activity_artifacts_root,
            "activity_artifacts_root_template": activity_artifacts_root_template,
            "tokenstore_available": False,
            "credentials_available": False,
            "detail": "Falta configuracion Garmin: define GARMIN_CONNECT_SESSION_PATH con un tokenstore valido o GARMIN_CONNECT_USERNAME/GARMIN_CONNECT_PASSWORD.",
        }

    def _prompt_mfa(self) -> str:
        if self.configuration.mfa_code:
            return self.configuration.mfa_code
        raise GarminConnectNotConfiguredError(
            "Garmin Connect requiere MFA y no se ha definido GARMIN_CONNECT_MFA_CODE para un login no interactivo."
        )

    def _build_client(self) -> Garmin:
        return Garmin(
            self.configuration.username,
            self.configuration.password,
            prompt_mfa=self._prompt_mfa,
        )

    def _login(self) -> Garmin:
        if self._client is not None:
            return self._client
        self.validate_configuration()
        client = self._build_client()
        try:
            client.login(self.configuration.tokenstore_path)
        except GarminConnectAuthenticationError as error:
            raise GarminConnectAuthenticationImportError("Fallo de autenticacion con Garmin Connect.") from error
        except GarminConnectTooManyRequestsError as error:
            raise GarminConnectTransportImportError("Garmin Connect ha limitado temporalmente las peticiones.") from error
        except GarminConnectConnectionError as error:
            raise GarminConnectTransportImportError("No se pudo conectar con Garmin Connect.") from error
        self._client = client
        return client

    @staticmethod
    def _pick_first(payload: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return None

    @staticmethod
    def _normalize_numeric(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _normalize_integer(cls, value: Any) -> int | None:
        numeric_value = cls._normalize_numeric(value)
        if numeric_value is None:
            return None
        return int(round(numeric_value))

    @classmethod
    def _normalize_segment_distance_meters(cls, value: Any) -> float | None:
        numeric_value = cls._normalize_numeric(value)
        if numeric_value is None:
            return None
        if numeric_value <= 100:
            return round(numeric_value * 1000, 3)
        return numeric_value

    @classmethod
    def _derive_pace_seconds_per_km(cls, discipline: str | None, summary: dict[str, Any], payload: dict[str, Any]) -> float | None:
        avg_pace_seconds_per_km = cls._pick_first(summary, "averagePaceInSecondsPerKilometer")
        if avg_pace_seconds_per_km is not None:
            return cls._normalize_numeric(avg_pace_seconds_per_km)
        if discipline not in cls.PACE_DISCIPLINES:
            return None
        average_speed = cls._pick_first(summary, "averageSpeed")
        if average_speed is None:
            average_speed = cls._pick_first(payload, "averageSpeed")
        if average_speed in (None, 0):
            return None
        try:
            return round(1000 / float(average_speed), 2)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @classmethod
    def _derive_training_load(cls, summary: dict[str, Any], payload: dict[str, Any]) -> float | None:
        return cls._normalize_numeric(
            cls._pick_first(summary, "activityTrainingLoad", "trainingStressScore", "trainingLoad")
            or cls._pick_first(payload, "activityTrainingLoad", "trainingStressScore", "trainingLoad", "aerobicTrainingEffect")
        )

    @classmethod
    def _derive_discipline(cls, payload: dict[str, Any], activity_type: dict[str, Any]) -> str | None:
        activity_name = str(cls._pick_first(payload, "activityName") or "").strip().lower()
        type_key = cls._pick_first(activity_type, "typeKey", "parentTypeKey")
        if activity_name and any(hint in activity_name for hint in cls.HIKING_NAME_HINTS):
            return "hiking"
        if type_key:
            return str(type_key)
        sport_type_id = cls._pick_first(payload, "sportTypeId")
        if sport_type_id in (17,):
            return "hiking"
        return str(sport_type_id) if sport_type_id else None

    @classmethod
    def _normalize_activity(cls, payload: dict[str, Any]) -> NormalizedActivity:
        metadata = payload.get("metadataDTO") or {}
        summary = payload.get("summaryDTO") or {}
        activity_type = payload.get("activityTypeDTO") or payload.get("activityType") or {}
        discipline = cls._derive_discipline(payload, activity_type)
        avg_pace_seconds_per_km = cls._derive_pace_seconds_per_km(discipline, summary, payload)

        return NormalizedActivity(
            external_activity_id=str(cls._pick_first(payload, "activityId", "id", "externalId") or ""),
            activity_date=str(cls._pick_first(payload, "startTimeLocal", "activityDate", "startTimeGMT", "date") or "")[:10],
            started_at=cls._pick_first(payload, "startTimeLocal", "startTimeGMT"),
            discipline=discipline,
            activity_type=cls._pick_first(payload, "activityName") or cls._pick_first(activity_type, "typeKey"),
            duration_seconds=cls._normalize_integer(cls._pick_first(summary, "duration", "elapsedDuration") or cls._pick_first(payload, "duration", "elapsedDuration", "movingDuration")),
            distance_meters=cls._normalize_numeric(cls._pick_first(summary, "distance") or cls._pick_first(payload, "distance")),
            ascent_meters=cls._normalize_numeric(
                cls._pick_first(summary, "elevationGain")
                or cls._pick_first(payload, "elevationGain", "totalAscent", "elevationCorrected")
            ),
            calories=cls._normalize_numeric(cls._pick_first(summary, "calories") or cls._pick_first(payload, "calories")),
            avg_hr=cls._normalize_numeric(cls._pick_first(summary, "averageHR") or cls._pick_first(payload, "averageHR")),
            max_hr=cls._normalize_numeric(cls._pick_first(summary, "maxHR") or cls._pick_first(payload, "maxHR")),
            avg_power=cls._normalize_numeric(cls._pick_first(summary, "avgPower", "averagePower") or cls._pick_first(payload, "avgPower", "averagePower")),
            normalized_power=cls._normalize_numeric(cls._pick_first(summary, "normPower") or cls._pick_first(payload, "normPower")),
            training_load=cls._derive_training_load(summary, payload),
            avg_pace_seconds_per_km=avg_pace_seconds_per_km,
            source_file=None,
            raw_payload_path=None,
            notes=metadata.get("deviceName") if isinstance(metadata, dict) else None,
        )

    @classmethod
    def _segment_payloads(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidate_keys = (
            "segmentEfforts",
            "segmentEffortsDTO",
            "segmentEffortDTOs",
            "activitySegments",
            "segments",
        )
        for key in candidate_keys:
            values = payload.get(key)
            if isinstance(values, list):
                return [value for value in values if isinstance(value, dict)]
        for value in payload.values():
            if isinstance(value, dict):
                nested = cls._segment_payloads(value)
                if nested:
                    return nested
        return []

    @staticmethod
    def _normalize_timestamp(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            try:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            except (OverflowError, OSError, ValueError):
                return None
        return None

    @classmethod
    def _parse_timestamp(cls, value: Any) -> datetime | None:
        normalized = cls._normalize_timestamp(value)
        if normalized is None:
            return None
        if isinstance(normalized, str):
            text = normalized.strip()
            if "T" not in text and " " not in text:
                return None
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                return None
        return None

    @classmethod
    def _extract_weight_entry_timestamp(cls, entry: dict[str, Any]) -> tuple[str | None, datetime | None]:
        for candidate in (
            cls._pick_first(entry, "measurementTimeLocal", "sampleTimeLocal", "timestampLocal", "startTimeLocal"),
            cls._pick_first(
                entry,
                "measurementTimeGMT",
                "sampleTimeGMT",
                "timestampGMT",
                "startTimeGMT",
                "measurementTimestamp",
                "timestamp",
                "dateTimestamp",
                "measurementTime",
                "sampleTime",
                "startTime",
            ),
        ):
            parsed = cls._parse_timestamp(candidate)
            normalized = cls._normalize_timestamp(candidate)
            if normalized is not None:
                return normalized, parsed
        return None, None

    @staticmethod
    def _normalize_weight_value(value: Any) -> float | None:
        if value is None:
            return None
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return None
        if numeric_value > 500:
            return round(numeric_value / 1000, 2)
        return round(numeric_value, 2)

    @classmethod
    def _classify_weight_measurement_source(cls, parsed_dt: datetime | None) -> str | None:
        return "timestamped_measurement" if parsed_dt is not None else "daily_aggregate"

    @classmethod
    def _extract_weight_measurements(
        cls,
        body_payload: dict[str, Any] | None,
        metric_date: str,
    ) -> list[NormalizedWeightMeasurement]:
        if not body_payload:
            return []

        raw_entries = body_payload.get("dateWeightList") if isinstance(body_payload.get("dateWeightList"), list) else None
        candidate_entries = [entry for entry in (raw_entries or [body_payload]) if isinstance(entry, dict)]
        measurements: list[tuple[datetime, int, NormalizedWeightMeasurement]] = []
        for index, entry in enumerate(candidate_entries):
            weight = cls._normalize_weight_value(cls._pick_first(entry, "weight", "weightInKg"))
            if weight is None:
                continue
            measured_at, parsed_dt = cls._extract_weight_entry_timestamp(entry)
            measurement_key = str(
                cls._pick_first(entry, "samplePk", "sampleId", "id")
                or f"{metric_date}:{index}:{measured_at or weight}"
            )
            measurements.append(
                (
                    parsed_dt or datetime.max.replace(tzinfo=timezone.utc),
                    index,
                    NormalizedWeightMeasurement(
                        metric_date=metric_date,
                        measurement_key=measurement_key,
                        measured_at=measured_at,
                        weight_kg=weight,
                        measurement_source=cls._classify_weight_measurement_source(parsed_dt),
                    ),
                )
            )

        measurements.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in measurements]

    @classmethod
    def _select_weight_entry(
        cls, body_payload: dict[str, Any] | None
    ) -> tuple[dict[str, Any] | None, float | None, str | None, str | None]:
        # Removed the old normalize_weight function as it is now replaced by _normalize_weight_value

        if not body_payload:
            return None, None, None, None

        raw_entries = body_payload.get("dateWeightList") if isinstance(body_payload.get("dateWeightList"), list) else None
        candidate_entries = [entry for entry in (raw_entries or [body_payload]) if isinstance(entry, dict)]

        candidates: list[tuple[int, datetime, int, dict[str, Any], float, str | None, str | None]] = []
        for index, entry in enumerate(candidate_entries):
            weight = cls._normalize_weight_value(cls._pick_first(entry, "weight", "weightInKg"))
            if weight is None:
                continue
            measured_at, parsed_dt = cls._extract_weight_entry_timestamp(entry)
            source = "first_daily_measurement" if parsed_dt is not None else "daily_aggregate"
            sort_dt = parsed_dt or datetime.max.replace(tzinfo=timezone.utc)
            candidates.append((0 if parsed_dt is not None else 1, sort_dt, index, entry, weight, measured_at, source))

        if not candidates:
            return None, None, None, None

        _, _, _, selected_entry, selected_weight, measured_at, source = min(candidates)
        return selected_entry, selected_weight, measured_at, source

    @staticmethod
    def _fetch_body_composition_payload(client: Garmin, metric_date: str) -> dict[str, Any] | None:
        try:
            payload = client.connectapi(f"/weight-service/weight/dayview/{metric_date}")
        except Exception:
            payload = None
        if isinstance(payload, dict) and payload.get("dateWeightList"):
            return payload
        return client.get_body_composition(metric_date, metric_date)

    @classmethod
    def _normalize_segment_efforts(cls, payload: dict[str, Any], activity: NormalizedActivity) -> list[NormalizedSegmentEffort]:
        efforts: list[NormalizedSegmentEffort] = []
        for item in cls._segment_payloads(payload):
            segment_payload = item.get("segment") if isinstance(item.get("segment"), dict) else None
            if segment_payload is None:
                segment_payload = item.get("segmentDTO") if isinstance(item.get("segmentDTO"), dict) else None
            if segment_payload is None:
                segment_payload = item

            external_segment_id = cls._pick_first(segment_payload, "segmentId", "id", "externalSegmentId")
            if external_segment_id is None:
                continue

            started_at = cls._pick_first(item, "startTimeGMT", "startTimeLocal", "beginTimestamp", "startTime")
            effort_identity = cls._pick_first(item, "segmentEffortId", "effortId", "id", "externalSegmentEffortId")
            if effort_identity is None and started_at:
                effort_identity = f"{external_segment_id}:{started_at}"
            if effort_identity is None:
                continue

            definition = NormalizedSegmentDefinition(
                external_segment_id=str(external_segment_id),
                segment_name=(
                    str(cls._pick_first(segment_payload, "name", "segmentName", "segmentTitle") or "").strip() or None
                ),
                discipline="cycling",
                distance_meters=cls._normalize_segment_distance_meters(
                    cls._pick_first(segment_payload, "distance", "distanceInMeters", "segmentDistance")
                ),
                ascent_meters=cls._normalize_numeric(
                    cls._pick_first(segment_payload, "elevationGain", "ascentMeters", "totalAscent")
                ),
                average_grade_percent=cls._normalize_numeric(
                    cls._pick_first(segment_payload, "averageGrade", "avgGrade", "averageGradePercent")
                ),
            )
            efforts.append(
                NormalizedSegmentEffort(
                    definition=definition,
                    external_segment_effort_id=str(effort_identity),
                    started_at=cls._normalize_timestamp(started_at),
                    elapsed_time_seconds=cls._normalize_integer(
                        cls._pick_first(item, "elapsedDuration", "duration", "elapsedTime", "time")
                    ),
                    avg_power=cls._normalize_numeric(cls._pick_first(item, "averagePower", "avgPower")),
                    avg_cadence=cls._normalize_numeric(
                        cls._pick_first(item, "averageCadence", "averageBikeCadence", "avgBikeCadence", "avgCadence")
                    ),
                    avg_heart_rate=cls._normalize_numeric(cls._pick_first(item, "averageHR", "avgHR")),
                    max_heart_rate=cls._normalize_numeric(cls._pick_first(item, "maxHR", "maximumHR")),
                    notes=None,
                )
            )
        return efforts

    @staticmethod
    def _segment_identity_keys(payload: dict[str, Any] | None) -> set[str]:
        if not isinstance(payload, dict):
            return set()
        keys: set[str] = set()
        for field_name in ("segmentUuid", "segmentPk", "segmentId", "id", "externalSegmentId"):
            value = payload.get(field_name)
            if value is not None:
                keys.add(str(value))
        return keys

    @classmethod
    def _favorite_segment_items(cls, payload: list[dict[str, Any]] | dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict) and bool(item.get("favorite"))]

    @classmethod
    def _filter_detail_efforts_to_favorites(
        cls,
        payload: dict[str, Any] | None,
        favorite_segment_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        if not favorite_segment_items:
            return {}

        allowed_keys: set[str] = set()
        for item in favorite_segment_items:
            allowed_keys.update(cls._segment_identity_keys(item))

        filtered_items: list[dict[str, Any]] = []
        for item in cls._segment_payloads(payload):
            segment_payload = item.get("segment") if isinstance(item.get("segment"), dict) else None
            if segment_payload is None:
                segment_payload = item.get("segmentDTO") if isinstance(item.get("segmentDTO"), dict) else None
            if segment_payload is None:
                segment_payload = item
            if cls._segment_identity_keys(segment_payload) & allowed_keys:
                filtered_items.append(item)

        if not filtered_items:
            return {}
        return {"segmentEfforts": filtered_items}

    @classmethod
    def _normalize_segment_memberships(
        cls,
        payload: list[dict[str, Any]] | dict[str, Any] | None,
        activity: NormalizedActivity,
    ) -> list[NormalizedSegmentEffort]:
        if not isinstance(payload, list):
            return []

        efforts: list[NormalizedSegmentEffort] = []
        seen_effort_ids: set[str] = set()
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                continue

            external_segment_id = cls._pick_first(item, "segmentUuid", "segmentPk", "segmentId", "id")
            if external_segment_id is None:
                continue

            effort_identity = f"{activity.external_activity_id}:{external_segment_id}"
            if effort_identity in seen_effort_ids:
                effort_identity = f"{effort_identity}:{index}"
            seen_effort_ids.add(effort_identity)

            efforts.append(
                NormalizedSegmentEffort(
                    definition=NormalizedSegmentDefinition(
                        external_segment_id=str(external_segment_id),
                        segment_name=(str(cls._pick_first(item, "segmentName", "name") or "").strip() or None),
                        discipline="cycling",
                        distance_meters=cls._normalize_segment_distance_meters(
                            cls._pick_first(item, "segmentDistance", "distance", "distanceInMeters")
                        ),
                        ascent_meters=cls._normalize_numeric(
                            cls._pick_first(item, "ascent", "elevationGain", "ascentMeters", "totalAscent")
                        ),
                        average_grade_percent=cls._normalize_numeric(
                            cls._pick_first(item, "grade", "averageGrade", "avgGrade", "averageGradePercent")
                        ),
                    ),
                    external_segment_effort_id=effort_identity,
                    started_at=None,
                    elapsed_time_seconds=None,
                    avg_power=None,
                    avg_cadence=None,
                    avg_heart_rate=None,
                    max_heart_rate=None,
                    notes=None,
                )
            )
        return efforts

    @classmethod
    def _activity_detail_points(cls, payload: dict[str, Any]) -> list[dict[str, float]]:
        metric_descriptors = payload.get("metricDescriptors")
        metric_rows = payload.get("activityDetailMetrics")
        if not isinstance(metric_descriptors, list) or not isinstance(metric_rows, list):
            return []

        descriptor_indexes: dict[str, int] = {}
        for item in metric_descriptors:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            index = item.get("metricsIndex")
            if isinstance(key, str) and isinstance(index, int):
                descriptor_indexes[key] = index

        required_keys = {
            "directLatitude": "latitude",
            "directLongitude": "longitude",
            "directTimestamp": "timestamp",
            "sumDistance": "distance",
            "sumElapsedDuration": "elapsed_duration",
        }
        if not all(key in descriptor_indexes for key in required_keys):
            return []

        optional_keys = {
            "directPower": "power",
            "directBikeCadence": "cadence",
            "directRunCadence": "cadence",
            "directHeartRate": "heart_rate",
        }

        points: list[dict[str, float]] = []
        for row in metric_rows:
            if not isinstance(row, dict):
                continue
            metrics = row.get("metrics")
            if not isinstance(metrics, list):
                continue

            point: dict[str, float] = {}
            valid_point = True
            for source_key, target_key in required_keys.items():
                index = descriptor_indexes[source_key]
                if index >= len(metrics):
                    valid_point = False
                    break
                value = cls._normalize_numeric(metrics[index])
                if value is None:
                    valid_point = False
                    break
                point[target_key] = value
            if not valid_point:
                continue

            for source_key, target_key in optional_keys.items():
                index = descriptor_indexes.get(source_key)
                if index is None or index >= len(metrics):
                    continue
                value = cls._normalize_numeric(metrics[index])
                if value is not None:
                    point[target_key] = value
            points.append(point)
        return points

    @staticmethod
    def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius_m = 6_371_000
        phi1 = radians(lat1)
        phi2 = radians(lat2)
        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)
        a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return earth_radius_m * c

    @classmethod
    def _reconstruct_segment_effort_candidates(
        cls,
        *,
        activity: NormalizedActivity,
        membership_effort: NormalizedSegmentEffort,
        membership_payload: dict[str, Any],
        segment_detail_payload: dict[str, Any],
        activity_points: list[dict[str, float]],
    ) -> list[NormalizedSegmentEffort]:
        geo_points = segment_detail_payload.get("geoPoints")
        if not isinstance(geo_points, list) or len(geo_points) < 2 or len(activity_points) < 2:
            return []

        start_geo = geo_points[0]
        end_geo = geo_points[-1]
        if not isinstance(start_geo, dict) or not isinstance(end_geo, dict):
            return []
        start_lat = cls._normalize_numeric(start_geo.get("latitude"))
        start_lon = cls._normalize_numeric(start_geo.get("longitude"))
        end_lat = cls._normalize_numeric(end_geo.get("latitude"))
        end_lon = cls._normalize_numeric(end_geo.get("longitude"))
        segment_distance_m = cls._normalize_segment_distance_meters(
            cls._pick_first(segment_detail_payload, "distance", "segmentDistance")
            or membership_effort.definition.distance_meters
        )
        target_start_ts = cls._normalize_numeric(membership_payload.get("timeEnteredSegment"))
        if None in (start_lat, start_lon, end_lat, end_lon, segment_distance_m):
            return []

        activity_start_ts = activity_points[0]["timestamp"]
        activity_end_ts = activity_points[-1]["timestamp"]
        if target_start_ts is not None and not (activity_start_ts - 300_000 <= target_start_ts <= activity_end_ts + 300_000):
            target_start_ts = None

        start_candidates: list[tuple[float, int, float]] = []
        for index, point in enumerate(activity_points):
            start_geo_error = cls._haversine_meters(start_lat, start_lon, point["latitude"], point["longitude"])
            if target_start_ts is not None:
                timestamp_delta_ms = abs(point["timestamp"] - target_start_ts)
                if timestamp_delta_ms <= 90_000 and start_geo_error <= 80:
                    start_candidates.append((timestamp_delta_ms + start_geo_error * 1000, index, start_geo_error))
            elif start_geo_error <= 120:
                start_candidates.append((start_geo_error * 1000, index, start_geo_error))
        if not start_candidates:
            return []

        candidate_windows: list[tuple[float, int, int, float, float, float]] = []
        min_distance_m = segment_distance_m * 0.75
        max_distance_m = segment_distance_m * 1.35

        for _, start_index, start_geo_error in sorted(start_candidates)[:12]:
            start_point = activity_points[start_index]
            best_for_start: tuple[float, int, int, float, float, float] | None = None
            for index in range(start_index + 1, len(activity_points)):
                point = activity_points[index]
                distance_delta = point["distance"] - start_point["distance"]
                if distance_delta < min_distance_m:
                    continue
                if distance_delta > max_distance_m:
                    break
                end_geo_error = cls._haversine_meters(end_lat, end_lon, point["latitude"], point["longitude"])
                distance_error = abs(distance_delta - segment_distance_m)
                score = start_geo_error + end_geo_error + distance_error / 4
                candidate = (score, start_index, index, start_geo_error, end_geo_error, distance_delta)
                if best_for_start is None or candidate < best_for_start:
                    best_for_start = candidate
            if best_for_start is not None:
                candidate_windows.append(best_for_start)
        if not candidate_windows:
            return []

        deduped_windows: list[tuple[float, int, int, float, float, float]] = []
        for candidate in sorted(candidate_windows, key=lambda item: (activity_points[item[1]]["timestamp"], item[0])):
            if not deduped_windows:
                deduped_windows.append(candidate)
                continue
            previous = deduped_windows[-1]
            previous_start_ts = activity_points[previous[1]]["timestamp"]
            current_start_ts = activity_points[candidate[1]]["timestamp"]
            if abs(current_start_ts - previous_start_ts) < 120_000:
                if candidate[0] < previous[0]:
                    deduped_windows[-1] = candidate
                continue
            deduped_windows.append(candidate)

        selected_windows: list[tuple[float, int, int, float, float, float]] = []
        last_end_index = -1
        for candidate in sorted(deduped_windows, key=lambda item: (item[1], item[2], item[0])):
            if candidate[1] <= last_end_index:
                continue
            selected_windows.append(candidate)
            last_end_index = candidate[2]

        reconstructed_efforts: list[NormalizedSegmentEffort] = []
        for occurrence_index, (_, start_index, end_index, start_geo_error, end_geo_error, _) in enumerate(selected_windows, start=1):
            start_point = activity_points[start_index]
            end_point = activity_points[end_index]
            duration_seconds = (end_point["timestamp"] - start_point["timestamp"]) / 1000
            if duration_seconds <= 0 or start_geo_error > 120 or end_geo_error > 120:
                continue

            window = activity_points[start_index : end_index + 1]

            def average(metric_name: str) -> float | None:
                values = [point[metric_name] for point in window if metric_name in point]
                if not values:
                    return None
                return round(sum(values) / len(values), 2)

            started_at = datetime.fromtimestamp(start_point["timestamp"] / 1000, tz=timezone.utc).isoformat()
            reconstructed_efforts.append(
                NormalizedSegmentEffort(
                    definition=NormalizedSegmentDefinition(
                        external_segment_id=membership_effort.definition.external_segment_id,
                        segment_name=membership_effort.definition.segment_name,
                        discipline=membership_effort.definition.discipline,
                        distance_meters=segment_distance_m,
                        ascent_meters=membership_effort.definition.ascent_meters,
                        average_grade_percent=membership_effort.definition.average_grade_percent,
                    ),
                    external_segment_effort_id=(
                        f"{activity.external_activity_id}:{membership_effort.definition.external_segment_id}:{int(start_point['timestamp'])}"
                    ),
                    started_at=started_at,
                    elapsed_time_seconds=cls._normalize_integer(duration_seconds),
                    avg_power=average("power"),
                    avg_cadence=average("cadence"),
                    avg_heart_rate=average("heart_rate"),
                    max_heart_rate=max((point["heart_rate"] for point in window if "heart_rate" in point), default=None),
                    notes="reconstructed_from_activity_detail_stream" if occurrence_index >= 1 else None,
                )
            )
        return reconstructed_efforts

    @classmethod
    def _reconstruct_segment_efforts(
        cls,
        *,
        client: Garmin,
        activity: NormalizedActivity,
        membership_payload: list[dict[str, Any]] | dict[str, Any] | None,
    ) -> list[NormalizedSegmentEffort]:
        membership_efforts = cls._normalize_segment_memberships(membership_payload, activity)
        if not membership_efforts or not isinstance(membership_payload, list):
            return membership_efforts

        try:
            activity_detail_payload = client.connectapi(f"/activity-service/activity/{activity.external_activity_id}/details")
        except Exception:
            return membership_efforts

        activity_points = cls._activity_detail_points(activity_detail_payload)
        if not activity_points:
            return membership_efforts

        reconstructed_efforts: list[NormalizedSegmentEffort] = []
        for item, membership_effort in zip(membership_payload, membership_efforts):
            if not isinstance(item, dict):
                continue
            segment_id = cls._pick_first(item, "segmentUuid", "segmentPk", "segmentId", "id")
            if segment_id is None:
                reconstructed_efforts.append(membership_effort)
                continue
            try:
                segment_detail_payload = client.connectapi(f"/segment-service/segment/{segment_id}")
            except Exception:
                reconstructed_efforts.append(membership_effort)
                continue
            reconstructed_candidates = cls._reconstruct_segment_effort_candidates(
                activity=activity,
                membership_effort=membership_effort,
                membership_payload=item,
                segment_detail_payload=segment_detail_payload,
                activity_points=activity_points,
            )
            reconstructed_efforts.extend(reconstructed_candidates or [membership_effort])
        return reconstructed_efforts or membership_efforts

    @classmethod
    def _apply_segment_details(
        cls,
        client: Garmin | None,
        activity: NormalizedActivity,
        detail_payload: dict[str, Any] | None,
        segment_list_payload: list[dict[str, Any]] | dict[str, Any] | None,
    ) -> None:
        if activity.discipline not in cls.CYCLING_DISCIPLINES:
            activity.segment_data_status = "not_applicable"
            activity.segment_effort_count = 0
            activity.segments = []
            activity.segment_checked_at = None
            return

        favorite_segment_items = cls._favorite_segment_items(segment_list_payload)
        filtered_detail_payload = cls._filter_detail_efforts_to_favorites(detail_payload, favorite_segment_items)
        detail_efforts = cls._normalize_segment_efforts(filtered_detail_payload, activity)
        reconstructed_efforts = (
            cls._reconstruct_segment_efforts(client=client, activity=activity, membership_payload=favorite_segment_items)
            if client is not None and not detail_efforts
            else cls._normalize_segment_memberships(favorite_segment_items, activity)
        )
        activity.segments = detail_efforts or reconstructed_efforts
        activity.segment_effort_count = len(activity.segments)
        activity.segment_data_status = "available" if activity.segments else "not_available"
        activity.segment_checked_at = None

    @classmethod
    def _extract_sleep_hours(cls, sleep_payload: dict[str, Any]) -> float | None:
        daily_sleep = sleep_payload.get("dailySleepDTO") if isinstance(sleep_payload, dict) else None
        if isinstance(daily_sleep, dict):
            sleep_payload = daily_sleep
        seconds = cls._pick_first(sleep_payload, "sleepTimeSeconds", "deepSleepSeconds", "lightSleepSeconds")
        if seconds is None:
            return None
        try:
            return round(float(seconds) / 3600, 2)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _extract_sleep_quality(cls, sleep_payload: dict[str, Any]) -> str | None:
        daily_sleep = sleep_payload.get("dailySleepDTO") if isinstance(sleep_payload, dict) else None
        if isinstance(daily_sleep, dict):
            sleep_payload = daily_sleep
        score = cls._pick_first(sleep_payload, "sleepScore", "overallSleepScore")
        if score is None:
            return None
        return str(score)

    @classmethod
    def _extract_resting_hr(cls, heart_rates_payload: dict[str, Any]) -> float | None:
        return cls._pick_first(heart_rates_payload, "restingHeartRate", "lastSevenDaysAvgRestingHeartRate")

    @classmethod
    def _extract_profile_metric(cls, user_profile_payload: dict[str, Any] | None, *keys: str) -> float | None:
        if not user_profile_payload:
            return None
        user_data = user_profile_payload.get("userData") if isinstance(user_profile_payload, dict) else None
        if not isinstance(user_data, dict):
            return None
        return cls._normalize_numeric(cls._pick_first(user_data, *keys))

    @classmethod
    def _extract_hrv(cls, hrv_payload: dict[str, Any] | None) -> float | None:
        if not hrv_payload:
            return None
        hrv_summary = hrv_payload.get("hrvSummary") if isinstance(hrv_payload, dict) else None
        if isinstance(hrv_summary, dict):
            return cls._pick_first(hrv_summary, "lastNightAvg", "weeklyAvg")
        return cls._pick_first(hrv_payload, "lastNightAvg", "weeklyAvg")

    @classmethod
    def _extract_body_battery(cls, body_battery_payload: list[dict[str, Any]] | dict[str, Any] | None, metric_date: str) -> float | None:
        if isinstance(body_battery_payload, list):
            for item in body_battery_payload:
                if not isinstance(item, dict):
                    continue
                calendar_date = str(cls._pick_first(item, "calendarDate", "date") or "")
                if calendar_date[:10] == metric_date:
                    direct_value = cls._pick_first(item, "bodyBatteryHigh", "endOfDayBodyBattery", "startOfDayBodyBattery")
                    if direct_value is not None:
                        return direct_value
                    values = item.get("bodyBatteryValuesArray")
                    if isinstance(values, list):
                        non_null_values = [entry[1] for entry in values if isinstance(entry, list) and len(entry) > 1 and entry[1] is not None]
                        if non_null_values:
                            return max(non_null_values)
            return None
        if isinstance(body_battery_payload, dict):
            return cls._pick_first(body_battery_payload, "bodyBatteryHigh", "endOfDayBodyBattery", "startOfDayBodyBattery")
        return None

    @classmethod
    def _extract_stress_avg(cls, stress_payload: dict[str, Any] | None) -> float | None:
        if not stress_payload:
            return None
        direct_value = cls._pick_first(stress_payload, "avgStressLevel")
        if direct_value is not None:
            return direct_value
        values = stress_payload.get("stressValuesArray") if isinstance(stress_payload, dict) else None
        if isinstance(values, list):
            normalized_values = [entry[1] for entry in values if isinstance(entry, list) and len(entry) > 1 and isinstance(entry[1], (int, float)) and entry[1] >= 0]
            if normalized_values:
                return round(sum(normalized_values) / len(normalized_values), 2)
        return None

    @classmethod
    def _extract_stress_max(cls, stress_payload: dict[str, Any] | None) -> float | None:
        if not stress_payload:
            return None
        direct_value = cls._pick_first(stress_payload, "maxStressLevel")
        if direct_value is not None:
            return direct_value
        values = stress_payload.get("stressValuesArray") if isinstance(stress_payload, dict) else None
        if isinstance(values, list):
            normalized_values = [entry[1] for entry in values if isinstance(entry, list) and len(entry) > 1 and isinstance(entry[1], (int, float)) and entry[1] >= 0]
            if normalized_values:
                return max(normalized_values)
        return None

    @classmethod
    def _extract_spo2_avg(cls, spo2_payload: dict[str, Any] | None) -> float | None:
        if not spo2_payload:
            return None
        return cls._pick_first(spo2_payload, "averageSpO2")

    @classmethod
    def _extract_spo2_sleep_avg(cls, spo2_payload: dict[str, Any] | None) -> float | None:
        if not spo2_payload:
            return None
        return cls._pick_first(spo2_payload, "avgSleepSpO2")

    @classmethod
    def _extract_spo2_7d_avg(cls, spo2_payload: dict[str, Any] | None) -> float | None:
        if not spo2_payload:
            return None
        return cls._pick_first(spo2_payload, "lastSevenDaysAvgSpO2")

    @classmethod
    def _extract_spo2_lowest(cls, spo2_payload: dict[str, Any] | None) -> float | None:
        if not spo2_payload:
            return None
        return cls._pick_first(spo2_payload, "lowestSpO2")

    @classmethod
    def _extract_weight(cls, body_payload: dict[str, Any] | None) -> float | None:
        _, weight, _, _ = cls._select_weight_entry(body_payload)
        return weight

    @classmethod
    def _extract_weight_measured_at(cls, body_payload: dict[str, Any] | None) -> str | None:
        _, _, measured_at, _ = cls._select_weight_entry(body_payload)
        return measured_at

    @classmethod
    def _extract_weight_measurement_source(cls, body_payload: dict[str, Any] | None) -> str | None:
        _, _, _, source = cls._select_weight_entry(body_payload)
        return source

    @classmethod
    def _first_body_composition_entry(cls, body_payload: dict[str, Any] | None) -> dict[str, Any] | None:
        entry, _, _, _ = cls._select_weight_entry(body_payload)
        if entry is not None:
            return entry
        if not body_payload:
            return None
        return body_payload

    @classmethod
    def _normalize_mass_kg(cls, value: Any) -> float | None:
        numeric_value = cls._normalize_numeric(value)
        if numeric_value is None:
            return None
        if numeric_value > 500:
            numeric_value = numeric_value / 1000
        return round(numeric_value, 2)

    @classmethod
    def _normalize_percentage(cls, value: Any) -> float | None:
        numeric_value = cls._normalize_numeric(value)
        if numeric_value is None:
            return None
        return round(numeric_value, 2)

    @classmethod
    def _extract_body_fat_pct(cls, body_payload: dict[str, Any] | None) -> float | None:
        entry = cls._first_body_composition_entry(body_payload)
        return cls._normalize_percentage(cls._pick_first(entry or {}, "bodyFat"))

    @classmethod
    def _extract_body_water_pct(cls, body_payload: dict[str, Any] | None) -> float | None:
        entry = cls._first_body_composition_entry(body_payload)
        return cls._normalize_percentage(cls._pick_first(entry or {}, "bodyWater"))

    @classmethod
    def _extract_bone_mass_kg(cls, body_payload: dict[str, Any] | None) -> float | None:
        entry = cls._first_body_composition_entry(body_payload)
        return cls._normalize_mass_kg(cls._pick_first(entry or {}, "boneMass"))

    @classmethod
    def _extract_muscle_mass_kg(cls, body_payload: dict[str, Any] | None) -> float | None:
        entry = cls._first_body_composition_entry(body_payload)
        return cls._normalize_mass_kg(cls._pick_first(entry or {}, "muscleMass"))

    @classmethod
    def _extract_bmi(cls, body_payload: dict[str, Any] | None) -> float | None:
        entry = cls._first_body_composition_entry(body_payload)
        return cls._normalize_percentage(cls._pick_first(entry or {}, "bmi"))

    @classmethod
    def _extract_visceral_fat(cls, body_payload: dict[str, Any] | None) -> float | None:
        entry = cls._first_body_composition_entry(body_payload)
        return cls._normalize_percentage(cls._pick_first(entry or {}, "visceralFat"))

    @classmethod
    def _extract_metabolic_age(cls, body_payload: dict[str, Any] | None) -> float | None:
        entry = cls._first_body_composition_entry(body_payload)
        return cls._normalize_percentage(cls._pick_first(entry or {}, "metabolicAge"))

    @classmethod
    def _extract_physique_rating(cls, body_payload: dict[str, Any] | None) -> float | None:
        entry = cls._first_body_composition_entry(body_payload)
        return cls._normalize_percentage(cls._pick_first(entry or {}, "physiqueRating"))

    @classmethod
    def _extract_total_steps(cls, steps_payload: dict[str, Any] | None) -> int | None:
        numeric_value = cls._normalize_numeric(cls._pick_first(steps_payload or {}, "totalSteps", "steps"))
        if numeric_value is None:
            return None
        return int(round(numeric_value))

    @classmethod
    def _extract_total_distance_m(cls, steps_payload: dict[str, Any] | None) -> float | None:
        numeric_value = cls._normalize_numeric(cls._pick_first(steps_payload or {}, "totalDistance", "distance"))
        if numeric_value is None:
            return None
        return round(numeric_value, 2)

    @classmethod
    def _extract_step_goal(cls, steps_payload: dict[str, Any] | None) -> int | None:
        numeric_value = cls._normalize_numeric(cls._pick_first(steps_payload or {}, "stepGoal", "dailyStepGoal"))
        if numeric_value is None:
            return None
        return int(round(numeric_value))

    @classmethod
    def _normalize_daily_metric(
        cls,
        metric_date: str,
        stats_payload: dict[str, Any],
        sleep_payload: dict[str, Any],
        heart_rates_payload: dict[str, Any],
        user_profile_payload: dict[str, Any] | None,
        hrv_payload: dict[str, Any] | None,
        body_battery_payload: list[dict[str, Any]] | dict[str, Any] | None,
        stress_payload: dict[str, Any] | None,
        spo2_payload: dict[str, Any] | None,
        body_payload: dict[str, Any] | None,
        steps_payload: dict[str, Any] | None,
    ) -> NormalizedDailyMetric:
        return NormalizedDailyMetric(
            metric_date=metric_date,
            weight_kg=cls._extract_weight(body_payload),
            weight_measured_at=cls._extract_weight_measured_at(body_payload),
            weight_measurement_source=cls._extract_weight_measurement_source(body_payload),
            weight_measurements=cls._extract_weight_measurements(body_payload, metric_date),
            body_fat_pct=cls._extract_body_fat_pct(body_payload),
            body_water_pct=cls._extract_body_water_pct(body_payload),
            bone_mass_kg=cls._extract_bone_mass_kg(body_payload),
            muscle_mass_kg=cls._extract_muscle_mass_kg(body_payload),
            bmi=cls._extract_bmi(body_payload),
            visceral_fat=cls._extract_visceral_fat(body_payload),
            metabolic_age=cls._extract_metabolic_age(body_payload),
            physique_rating=cls._extract_physique_rating(body_payload),
            sleep_hours=cls._extract_sleep_hours(sleep_payload),
            sleep_quality=cls._extract_sleep_quality(sleep_payload),
            resting_hr=cls._extract_resting_hr(heart_rates_payload),
            vo2max_cycling=cls._extract_profile_metric(user_profile_payload, "vo2MaxCycling"),
            vo2max_running=cls._extract_profile_metric(user_profile_payload, "vo2MaxRunning"),
            lactate_threshold_hr=cls._extract_profile_metric(
                user_profile_payload,
                "lactateThresholdHeartRateCycling",
                "lactateThresholdHeartRate",
            ),
            hrv=cls._extract_hrv(hrv_payload),
            body_battery=cls._extract_body_battery(body_battery_payload, metric_date),
            total_steps=cls._extract_total_steps(steps_payload),
            total_distance_m=cls._extract_total_distance_m(steps_payload),
            step_goal=cls._extract_step_goal(steps_payload),
            stress_avg=cls._extract_stress_avg(stress_payload),
            stress_max=cls._extract_stress_max(stress_payload),
            spo2_avg=cls._extract_spo2_avg(spo2_payload),
            spo2_sleep_avg=cls._extract_spo2_sleep_avg(spo2_payload),
            spo2_7d_avg=cls._extract_spo2_7d_avg(spo2_payload),
            spo2_lowest=cls._extract_spo2_lowest(spo2_payload),
            subjective_energy=None,
            subjective_fatigue=None,
            notes=str(cls._pick_first(stats_payload, "wellnessDescription", "calendarDate") or "") or None,
            raw_payload_path=None,
        )

    def _download_activity_artifact(self, client: Garmin, season_id: int, activity: NormalizedActivity) -> str | None:
        if not activity.external_activity_id:
            return None
        artifact_bytes = client.download_activity(activity.external_activity_id, Garmin.ActivityDownloadFormat.TCX)
        artifact_root = self.configuration.resolve_activity_artifacts_root(season_id)
        activity_date = activity.activity_date or "unknown-date"
        artifact_path = artifact_root / activity_date / f"{activity.external_activity_id}.tcx"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(artifact_bytes)
        return str(artifact_path)

    def _fetch_activities(self, client: Garmin, request: GarminImportRequest) -> tuple[list[NormalizedActivity], list[str], int]:
        activities_payload = client.get_activities_by_date(request.date_from, request.date_to, sortorder="asc")
        activities = [
            self._normalize_activity(activity)
            for activity in activities_payload
            if isinstance(activity, dict)
            and self._pick_first(activity, "activityId", "id", "externalId") is not None
        ]
        artifact_paths: list[str] = []
        artifact_failures = 0
        for activity in activities:
            activity_detail_stream_payload: dict[str, Any] | None = None
            if activity.external_activity_id and activity.discipline in self.CYCLING_DISCIPLINES:
                try:
                    segment_list_payload = client.connectapi(f"/segment-service/segment/list/{activity.external_activity_id}")
                except Exception as error:
                    raise GarminConnectImportError(
                        f"No se pudo obtener la lista de segmentos para la actividad {activity.external_activity_id}."
                    ) from error
                try:
                    detail_payload = client.get_activity_details(activity.external_activity_id) or {}
                except Exception as error:
                    detail_payload = {}
                try:
                    activity_detail_stream_payload = client.connectapi(
                        f"/activity-service/activity/{activity.external_activity_id}/details"
                    )
                except Exception:
                    activity_detail_stream_payload = None
                self._apply_segment_details(client, activity, detail_payload, segment_list_payload)
            else:
                self._apply_segment_details(None, activity, None, None)
                if activity.external_activity_id:
                    try:
                        activity_detail_stream_payload = client.connectapi(
                            f"/activity-service/activity/{activity.external_activity_id}/details"
                        )
                    except Exception:
                        activity_detail_stream_payload = None
            activity.metric_readings = normalize_metric_readings_from_activity_detail(activity_detail_stream_payload)
            activity.route_points = normalize_route_points_from_activity_detail(activity_detail_stream_payload)
            try:
                artifact_path = self._download_activity_artifact(client, request.season_id, activity)
            except Exception:
                artifact_failures += 1
                continue
            if artifact_path:
                activity.raw_payload_path = artifact_path
                if not activity.route_points:
                    activity.route_points = normalize_route_points_from_tcx_artifact(artifact_path)
                artifact_paths.append(artifact_path)
        return activities, artifact_paths, artifact_failures

    def _fetch_daily_metrics(self, client: Garmin, request: GarminImportRequest) -> list[NormalizedDailyMetric]:
        metrics: list[NormalizedDailyMetric] = []
        try:
            user_profile_payload = client.get_user_profile() or {}
        except Exception:
            user_profile_payload = None
        try:
            daily_steps_payload = client.get_daily_steps(request.date_from, request.date_to) or []
        except Exception:
            daily_steps_payload = []
        daily_steps_by_date: dict[str, dict[str, Any]] = {}
        for item in daily_steps_payload:
            if not isinstance(item, dict):
                continue
            metric_date = str(self._pick_first(item, "calendarDate", "date") or "").strip()
            if metric_date:
                daily_steps_by_date[metric_date] = item
        for metric_date in iter_dates(request.date_from, request.date_to):
            stats_payload = client.get_stats(metric_date) or {}
            sleep_payload = client.get_sleep_data(metric_date) or {}
            heart_rates_payload = client.get_heart_rates(metric_date) or {}
            hrv_payload = client.get_hrv_data(metric_date)
            body_battery_payload = client.get_body_battery(metric_date, metric_date)
            stress_payload = client.get_all_day_stress(metric_date)
            spo2_payload = client.get_spo2_data(metric_date)
            body_payload = self._fetch_body_composition_payload(client, metric_date)
            metrics.append(
                self._normalize_daily_metric(
                    metric_date=metric_date,
                    stats_payload=stats_payload,
                    sleep_payload=sleep_payload,
                    heart_rates_payload=heart_rates_payload,
                    user_profile_payload=user_profile_payload,
                    hrv_payload=hrv_payload,
                    body_battery_payload=body_battery_payload,
                    stress_payload=stress_payload,
                    spo2_payload=spo2_payload,
                    body_payload=body_payload,
                    steps_payload=daily_steps_by_date.get(metric_date),
                )
            )
        return metrics

    def fetch(self, request: GarminImportRequest) -> GarminImportBatch:
        client = self._login()
        activities, artifact_paths, artifact_failures = self._fetch_activities(client, request)
        daily_metrics = []
        if request.include_daily_metrics:
            daily_metrics = self._fetch_daily_metrics(client, request)

        notes = [
            "Fetch realizado con la libreria Python garminconnect.",
            "Carga preparada para persistencia en staging y tablas finales.",
        ]
        if artifact_paths:
            notes.append(f"Artefactos TCX locales guardados: {len(artifact_paths)}.")
        if artifact_failures:
            notes.append(f"Descarga TCX no disponible en {artifact_failures} actividades.")

        return GarminImportBatch(
            request=request,
            metadata=ImportFetchMetadata(
                source_system="garmin",
                source_label="garminconnect",
                date_from=request.date_from,
                date_to=request.date_to,
                raw_payload_paths=artifact_paths,
                notes=notes,
            ),
            activities=activities,
            daily_metrics=daily_metrics,
        )

    def preview_metadata(self, request: GarminImportRequest) -> ImportFetchMetadata:
        batch = self.fetch(request)
        daily_metrics_note = "Se incluiran metricas diarias del rango." if request.include_daily_metrics else "No se incluiran metricas diarias en esta ejecucion."
        notes = [
            "Autenticacion Garmin Connect valida.",
            f"Actividades detectadas en el rango: {len(batch.activities)}.",
            daily_metrics_note,
        ]
        return ImportFetchMetadata(
            source_system=batch.metadata.source_system,
            source_label=batch.metadata.source_label,
            date_from=request.date_from,
            date_to=request.date_to,
            notes=notes,
        )


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Importacion Garmin Connect para V0.3.")
    parser.add_argument("--season", type=int, required=True, dest="season_id", help="Temporada destino, por ejemplo 2026.")
    parser.add_argument("--from", required=True, dest="date_from", help="Fecha inicial ISO, por ejemplo 2026-05-04.")
    parser.add_argument("--to", required=True, dest="date_to", help="Fecha final ISO, por ejemplo 2026-05-10.")
    execution_mode = parser.add_mutually_exclusive_group(required=True)
    execution_mode.add_argument("--dry-run", action="store_true", help="Consulta Garmin y devuelve un resumen sin persistir.")
    execution_mode.add_argument("--apply", action="store_true", help="Consulta Garmin y persiste staging, tablas finales e import job.")
    parser.add_argument(
        "--no-daily-metrics",
        action="store_true",
        help="No traer metricas diarias en esta ejecucion.",
    )
    return parser


def _request_from_cli_args(args: argparse.Namespace) -> GarminImportRequest:
    return GarminImportRequest(
        season_id=args.season_id,
        date_from=args.date_from,
        date_to=args.date_to,
        include_daily_metrics=not args.no_daily_metrics,
    )


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    request = _request_from_cli_args(args)
    initialize_database()

    from ..activity_weather import backfill_activity_weather_for_external_ids
    from .pipeline import GarminImportPipeline
    from .storage import GarminImportStorage

    pipeline = GarminImportPipeline()
    storage = GarminImportStorage()

    try:
        if args.dry_run:
            preview = pipeline.preview(request)
            print(json.dumps({"status": "ok", "mode": "dry-run", **preview.to_dict()}, ensure_ascii=False, indent=2))
            return 0

        import_job_id = storage.start_import_job(
            season_id=request.season_id,
            source_system="garmin",
            import_type="garminconnect",
            source_path=f"{request.date_from}:{request.date_to}",
            request_date_from=request.date_from,
            request_date_to=request.date_to,
            include_daily_metrics=request.include_daily_metrics,
            notes=["Importacion Garmin iniciada.", "Pendiente de fetch desde Garmin Connect."],
        )
        try:
            batch = pipeline.run(request)
        except (GarminConnectNotConfiguredError, GarminConnectImportError, NotImplementedError) as error:
            failure = classify_garmin_failure(error)
            storage.fail_import_job(
                import_job_id,
                notes=["Importacion Garmin fallida durante fetch.", str(error)],
                failure_stage=failure["failure_stage"],
                failure_class=failure["failure_class"],
                operator_detail=failure["operator_detail"],
            )
            raise

        try:
            summary = storage.persist_batch(batch, import_job_id=import_job_id)
        except Exception as error:
            counts = batch.counts()
            rows_detected = counts["activities_detected"] + counts["daily_metrics_detected"]
            failure = classify_garmin_failure(error)
            storage.fail_import_job(
                import_job_id,
                notes=["Importacion Garmin fallida durante persistencia.", str(error)],
                rows_detected=rows_detected,
                failure_stage=failure["failure_stage"],
                failure_class=failure["failure_class"],
                operator_detail=failure["operator_detail"],
            )
            raise

        weather_summary: dict[str, Any] | None = None
        weather_external_ids = [activity.external_activity_id for activity in batch.activities if activity.external_activity_id]
        if weather_external_ids:
            try:
                weather_summary = backfill_activity_weather_for_external_ids(
                    season_id=request.season_id,
                    source_system="garmin",
                    external_activity_ids=weather_external_ids,
                )
            except Exception as error:
                weather_summary = {
                    "activity_count": 0,
                    "processed_count": 0,
                    "completed_count": 0,
                    "results": [],
                    "status": "failed",
                    "detail": str(error),
                }

        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": "apply",
                    "counts": batch.counts(),
                    "metadata": {
                        **batch.metadata.to_dict(),
                        "weather_summary": weather_summary,
                    },
                    "import_job": summary.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (GarminConnectNotConfiguredError, GarminConnectImportError, NotImplementedError, ValueError) as error:
        print(json.dumps({"status": "error", "detail": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
