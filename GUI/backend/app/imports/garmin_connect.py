from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .contracts import (
    GarminImportBatch,
    GarminImportRequest,
    ImportFetchMetadata,
    NormalizedActivity,
    NormalizedDailyMetric,
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
        "running",
        "trail_running",
        "walking",
    }
    HIKING_NAME_HINTS = ("senderismo", "hiking", "trek", "trekking")

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
    def _extract_weight(cls, body_payload: dict[str, Any] | None) -> float | None:
        def normalize_weight(value: Any) -> float | None:
            if value is None:
                return None
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                return None
            if numeric_value > 500:
                return round(numeric_value / 1000, 2)
            return round(numeric_value, 2)

        if not body_payload:
            return None
        if isinstance(body_payload.get("dateWeightList"), list):
            for item in body_payload["dateWeightList"]:
                if isinstance(item, dict):
                    return normalize_weight(cls._pick_first(item, "weight", "weightInKg"))
        return normalize_weight(cls._pick_first(body_payload, "weight", "weightInKg"))

    @classmethod
    def _normalize_daily_metric(
        cls,
        metric_date: str,
        stats_payload: dict[str, Any],
        sleep_payload: dict[str, Any],
        heart_rates_payload: dict[str, Any],
        hrv_payload: dict[str, Any] | None,
        body_battery_payload: list[dict[str, Any]] | dict[str, Any] | None,
        body_payload: dict[str, Any] | None,
    ) -> NormalizedDailyMetric:
        return NormalizedDailyMetric(
            metric_date=metric_date,
            weight_kg=cls._extract_weight(body_payload),
            sleep_hours=cls._extract_sleep_hours(sleep_payload),
            sleep_quality=cls._extract_sleep_quality(sleep_payload),
            resting_hr=cls._extract_resting_hr(heart_rates_payload),
            hrv=cls._extract_hrv(hrv_payload),
            body_battery=cls._extract_body_battery(body_battery_payload, metric_date),
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
            try:
                artifact_path = self._download_activity_artifact(client, request.season_id, activity)
            except Exception:
                artifact_failures += 1
                continue
            if artifact_path:
                activity.raw_payload_path = artifact_path
                artifact_paths.append(artifact_path)
        return activities, artifact_paths, artifact_failures

    def _fetch_daily_metrics(self, client: Garmin, request: GarminImportRequest) -> list[NormalizedDailyMetric]:
        metrics: list[NormalizedDailyMetric] = []
        for metric_date in iter_dates(request.date_from, request.date_to):
            stats_payload = client.get_stats(metric_date) or {}
            sleep_payload = client.get_sleep_data(metric_date) or {}
            heart_rates_payload = client.get_heart_rates(metric_date) or {}
            hrv_payload = client.get_hrv_data(metric_date)
            body_battery_payload = client.get_body_battery(metric_date, metric_date)
            body_payload = client.get_body_composition(metric_date, metric_date)
            metrics.append(
                self._normalize_daily_metric(
                    metric_date=metric_date,
                    stats_payload=stats_payload,
                    sleep_payload=sleep_payload,
                    heart_rates_payload=heart_rates_payload,
                    hrv_payload=hrv_payload,
                    body_battery_payload=body_battery_payload,
                    body_payload=body_payload,
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

        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": "apply",
                    "counts": batch.counts(),
                    "metadata": batch.metadata.to_dict(),
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
