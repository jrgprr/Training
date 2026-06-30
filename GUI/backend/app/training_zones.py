from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta
from statistics import median
from typing import Any

from .activity_quality import ActivityQualityEvaluation
from .db import get_connection
from .imports.contracts import NormalizedActivity, NormalizedMetricReading
from .planned_prescriptions import derive_zone_target_from_prescription, get_planned_session_prescription


SUPPORTED_ZONE_BASES = {
    "heart_rate": "bpm",
    "power": "watts",
}

CYCLING_DISCIPLINES = {
    "cycling",
    "road_biking",
    "indoor_cycling",
    "mountain_biking",
}

ZONE_METRIC_STREAMS = {
    "heart_rate": "heart_rate",
    "power": "power",
}

MIN_ZONE_SAMPLE_COUNT = {
    "heart_rate": 2,
    "power": 2,
}

MIN_REFINEMENT_ACTIVITY_COUNT = 2
REFINEMENT_ACTIVITY_LOOKBACK_DAYS = 42
REFINEMENT_RECOVERY_LOOKBACK_DAYS = 14
MIN_REFINEMENT_DELTA = {
    "heart_rate": 3,
    "power": 5,
}

SUPPORTED_ZONE_MODELS = {
    "heart_rate": {"heart_rate_reserve_5_zone"},
    "power": {"ftp_coggan_7_zone"},
}


def normalize_zone_basis(metric_basis: str | None) -> str | None:
    if metric_basis is None:
        return None
    normalized = metric_basis.strip().lower()
    if not normalized:
        return None
    aliases = {
        "hr": "heart_rate",
        "heart-rate": "heart_rate",
        "heart rate": "heart_rate",
        "ftp": "power",
        "watts": "power",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_ZONE_BASES:
        return None
    return normalized


def is_zone_supported_discipline(discipline: str | None) -> bool:
    if discipline is None:
        return False
    return discipline.strip().lower() in CYCLING_DISCIPLINES


def normalize_zone_discipline(discipline: str | None) -> str | None:
    if not is_zone_supported_discipline(discipline):
        return None
    return "cycling"


def persist_accepted_zone_profile(
    connection: Any,
    *,
    season_id: int,
    discipline: str,
    metric_basis: str,
    profile_label: str,
    effective_start_date: str,
    boundaries: list[dict[str, Any]],
    accepted_at: str | None = None,
    derived_from_proposal_id: int | None = None,
    source_metric_profile_id: int | None = None,
    calculation_model_key: str | None = None,
) -> int:
    normalized_discipline = normalize_zone_discipline(discipline)
    normalized_metric_basis = normalize_zone_basis(metric_basis)
    if normalized_discipline is None:
        raise ValueError(f"Disciplina no soportada para zonas: {discipline}.")
    if normalized_metric_basis is None:
        raise ValueError(f"Base de zonas no soportada: {metric_basis}.")
    if not boundaries:
        raise ValueError("Un perfil de zonas aceptado requiere al menos un boundary.")

    previous_effective_end_date = _previous_iso_date(effective_start_date)
    connection.execute(
        """
        UPDATE zone_profiles
        SET effective_end_date = ?
        WHERE season_id = ?
          AND discipline = ?
          AND metric_basis = ?
          AND governance_status = 'accepted'
          AND (effective_end_date IS NULL OR effective_end_date = '')
          AND effective_start_date < ?
        """,
        (
            previous_effective_end_date,
            season_id,
            normalized_discipline,
            normalized_metric_basis,
            effective_start_date,
        ),
    )
    cursor = connection.execute(
        """
        INSERT INTO zone_profiles (
            season_id, discipline, metric_basis, profile_label, governance_status,
            effective_start_date, accepted_at, derived_from_proposal_id,
            source_metric_profile_id, calculation_model_key
        ) VALUES (?, ?, ?, ?, 'accepted', ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?)
        """,
        (
            season_id,
            normalized_discipline,
            normalized_metric_basis,
            profile_label,
            effective_start_date,
            accepted_at,
            derived_from_proposal_id,
            source_metric_profile_id,
            calculation_model_key,
        ),
    )
    zone_profile_id = int(cursor.lastrowid)
    bound_unit = SUPPORTED_ZONE_BASES[normalized_metric_basis]
    for fallback_index, boundary in enumerate(boundaries, start=1):
        connection.execute(
            """
            INSERT INTO zone_profile_boundaries (
                zone_profile_id, zone_index, zone_code, zone_name,
                lower_bound_value, upper_bound_value, bound_unit, target_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                zone_profile_id,
                int(boundary.get("zone_index", fallback_index)),
                boundary["zone_code"],
                boundary.get("zone_name"),
                boundary.get("lower_bound_value"),
                boundary.get("upper_bound_value"),
                boundary.get("bound_unit", bound_unit),
                boundary.get("target_kind", "closed"),
            ),
        )
    return zone_profile_id


def persist_accepted_zone_metric_profile(
    connection: Any,
    *,
    season_id: int,
    discipline: str,
    metric_basis: str,
    model_key: str,
    effective_start_date: str,
    profile_label: str | None = None,
    resting_hr: float | None = None,
    max_hr: float | None = None,
    ftp: float | None = None,
    accepted_at: str | None = None,
    notes: str | None = None,
) -> int:
    normalized_discipline = normalize_zone_discipline(discipline)
    normalized_metric_basis = normalize_zone_basis(metric_basis)
    if normalized_discipline is None:
        raise ValueError(f"Disciplina no soportada para zonas: {discipline}.")
    if normalized_metric_basis is None:
        raise ValueError(f"Base de zonas no soportada: {metric_basis}.")
    _validate_zone_metric_profile_parameters(
        metric_basis=normalized_metric_basis,
        model_key=model_key,
        resting_hr=resting_hr,
        max_hr=max_hr,
        ftp=ftp,
    )

    previous_effective_end_date = _previous_iso_date(effective_start_date)
    connection.execute(
        """
        UPDATE zone_metric_profiles
        SET effective_end_date = ?
        WHERE season_id = ?
          AND discipline = ?
          AND metric_basis = ?
          AND (effective_end_date IS NULL OR effective_end_date = '')
          AND effective_start_date < ?
        """,
        (
            previous_effective_end_date,
            season_id,
            normalized_discipline,
            normalized_metric_basis,
            effective_start_date,
        ),
    )
    cursor = connection.execute(
        """
        INSERT INTO zone_metric_profiles (
            season_id, discipline, metric_basis, profile_label, model_key,
            resting_hr, max_hr, ftp, effective_start_date, accepted_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
        """,
        (
            season_id,
            normalized_discipline,
            normalized_metric_basis,
            profile_label,
            model_key,
            resting_hr,
            max_hr,
            ftp,
            effective_start_date,
            accepted_at,
            notes,
        ),
    )
    return int(cursor.lastrowid)


def accept_zone_metric_profile(
    *,
    season_id: int,
    discipline: str,
    metric_basis: str,
    model_key: str,
    effective_start_date: str,
    profile_label: str | None = None,
    resting_hr: float | None = None,
    max_hr: float | None = None,
    ftp: float | None = None,
    accepted_at: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    normalized_metric_basis = normalize_zone_basis(metric_basis)
    if normalized_metric_basis is None:
        raise ValueError(f"Base de zonas no soportada: {metric_basis}.")
    boundaries = derive_zone_boundaries_from_metrics(
        metric_basis=normalized_metric_basis,
        model_key=model_key,
        resting_hr=resting_hr,
        max_hr=max_hr,
        ftp=ftp,
    )
    resolved_profile_label = profile_label or _default_metric_profile_label(
        metric_basis=normalized_metric_basis,
        model_key=model_key,
    )
    with get_connection() as connection:
        source_metric_profile_id = persist_accepted_zone_metric_profile(
            connection,
            season_id=season_id,
            discipline=discipline,
            metric_basis=normalized_metric_basis,
            model_key=model_key,
            effective_start_date=effective_start_date,
            profile_label=resolved_profile_label,
            resting_hr=resting_hr,
            max_hr=max_hr,
            ftp=ftp,
            accepted_at=accepted_at,
            notes=notes,
        )
        zone_profile_id = persist_accepted_zone_profile(
            connection,
            season_id=season_id,
            discipline=discipline,
            metric_basis=normalized_metric_basis,
            profile_label=resolved_profile_label,
            effective_start_date=effective_start_date,
            boundaries=boundaries,
            accepted_at=accepted_at,
            source_metric_profile_id=source_metric_profile_id,
            calculation_model_key=model_key,
        )
        connection.commit()
    return {
        "season_id": season_id,
        "discipline": normalize_zone_discipline(discipline),
        "metric_basis": normalized_metric_basis,
        "model_key": model_key,
        "source_metric_profile_id": source_metric_profile_id,
        "zone_profile_id": zone_profile_id,
        "effective_start_date": effective_start_date,
        "boundaries": boundaries,
    }


def list_current_zone_metric_profiles(season_id: int, discipline: str) -> dict[str, Any]:
    normalized_discipline = normalize_zone_discipline(discipline)
    if normalized_discipline is None:
        return {
            "season_id": season_id,
            "discipline": discipline.strip().lower(),
            "profiles": {},
        }
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT zone_metric_profile_id,
                   metric_basis,
                   profile_label,
                   model_key,
                   resting_hr,
                   max_hr,
                   ftp,
                   effective_start_date,
                   effective_end_date,
                   accepted_at,
                   notes
            FROM zone_metric_profiles
            WHERE season_id = ?
              AND discipline = ?
              AND (effective_end_date IS NULL OR effective_end_date = '')
            ORDER BY metric_basis, effective_start_date DESC, zone_metric_profile_id DESC
            """,
            (season_id, normalized_discipline),
        ).fetchall()

    profiles: dict[str, Any] = {}
    for row in rows:
        metric_basis = row["metric_basis"]
        if metric_basis in profiles:
            continue
        profiles[metric_basis] = _serialize_zone_metric_profile_row(row)
    return {
        "season_id": season_id,
        "discipline": normalized_discipline,
        "profiles": profiles,
    }


def list_current_zone_profiles(season_id: int, discipline: str) -> dict[str, Any]:
    normalized_discipline = normalize_zone_discipline(discipline)
    if normalized_discipline is None:
        return {
            "season_id": season_id,
            "discipline": discipline.strip().lower(),
            "profiles": {},
        }
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT profile.zone_profile_id,
                   profile.metric_basis,
                   profile.profile_label,
                   profile.source_metric_profile_id,
                   profile.calculation_model_key,
                   profile.governance_status,
                   profile.effective_start_date,
                   profile.effective_end_date,
                   profile.accepted_at,
                   boundary.zone_index,
                   boundary.zone_code,
                   boundary.zone_name,
                   boundary.lower_bound_value,
                   boundary.upper_bound_value,
                   boundary.bound_unit,
                   boundary.target_kind
            FROM zone_profiles profile
            LEFT JOIN zone_profile_boundaries boundary
              ON boundary.zone_profile_id = profile.zone_profile_id
            WHERE profile.season_id = ?
              AND profile.discipline = ?
              AND profile.governance_status = 'accepted'
              AND (
                    profile.effective_end_date IS NULL
                    OR profile.effective_end_date = ''
                  )
            ORDER BY profile.metric_basis, boundary.zone_index
            """,
            (season_id, normalized_discipline),
        ).fetchall()

    profiles: dict[str, Any] = {}
    for row in rows:
        metric_basis = row["metric_basis"]
        if metric_basis not in profiles:
            profiles[metric_basis] = {
                "zone_profile_id": row["zone_profile_id"],
                "metric_basis": metric_basis,
                "profile_label": row["profile_label"],
                "source_metric_profile_id": row["source_metric_profile_id"],
                "calculation_model_key": row["calculation_model_key"],
                "governance_status": row["governance_status"],
                "effective_start_date": row["effective_start_date"],
                "effective_end_date": row["effective_end_date"],
                "accepted_at": row["accepted_at"],
                "boundaries": [],
            }
        if row["zone_index"] is not None:
            profiles[metric_basis]["boundaries"].append(
                {
                    "zone_index": row["zone_index"],
                    "zone_code": row["zone_code"],
                    "zone_name": row["zone_name"],
                    "lower_bound_value": row["lower_bound_value"],
                    "upper_bound_value": row["upper_bound_value"],
                    "bound_unit": row["bound_unit"],
                    "target_kind": row["target_kind"],
                }
            )

    if profiles:
        current_metric_profiles = list_current_zone_metric_profiles(season_id, normalized_discipline)["profiles"]
        for metric_basis, profile in profiles.items():
            metric_profile = current_metric_profiles.get(metric_basis)
            if metric_profile is not None:
                profile["metric_profile"] = metric_profile

    return {
        "season_id": season_id,
        "discipline": normalized_discipline,
        "profiles": profiles,
    }


def get_planned_session_zone_target(planned_session_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        prescription = get_planned_session_prescription(connection, planned_session_id)
        return derive_zone_target_from_prescription(prescription)


def get_active_zone_profile_for_date(
    season_id: int,
    *,
    discipline: str,
    metric_basis: str,
    activity_date: str,
) -> dict[str, Any] | None:
    normalized_discipline = normalize_zone_discipline(discipline)
    normalized_metric_basis = normalize_zone_basis(metric_basis)
    if normalized_discipline is None or normalized_metric_basis is None:
        return None

    with get_connection() as connection:
        profile = _get_active_zone_profile(
            connection,
            season_id=season_id,
            discipline=normalized_discipline,
            metric_basis=normalized_metric_basis,
            activity_date=activity_date,
        )
        if profile is None:
            return None
        boundaries = _get_profile_boundaries(connection, int(profile["zone_profile_id"]))
    return {
        **profile,
        "discipline": normalized_discipline,
        "boundaries": boundaries,
    }


def get_activity_zone_detail(activity_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        activity_row = connection.execute(
            """
            SELECT activity_id, season_id, activity_date, discipline, quality_status
            FROM exec_activities
            WHERE activity_id = ?
            """,
            (activity_id,),
        ).fetchone()
        if activity_row is None:
            return None

        result_rows = connection.execute(
            """
            SELECT result.activity_zone_result_id,
                   result.metric_basis,
                   result.calculation_status,
                   result.quality_status_snapshot,
                   result.supported_sample_count,
                   result.total_supported_seconds,
                   result.dominant_zone_code,
                   result.dominant_zone_share,
                   result.calculation_notes,
                   result.calculated_at,
                   profile.zone_profile_id,
                   profile.profile_label
            FROM exec_activity_zone_results result
            JOIN zone_profiles profile
              ON profile.zone_profile_id = result.zone_profile_id
            WHERE result.activity_id = ?
            ORDER BY result.metric_basis
            """,
            (activity_id,),
        ).fetchall()

        results: dict[str, Any] = {}
        for row in result_rows:
            buckets = connection.execute(
                """
                SELECT zone_index, zone_code, seconds_in_zone, share_in_zone, sample_count
                FROM exec_activity_zone_buckets
                WHERE activity_zone_result_id = ?
                ORDER BY zone_index
                """,
                (row["activity_zone_result_id"],),
            ).fetchall()
            bucket_dicts = [dict(bucket) for bucket in buckets]
            training_zone_code, training_zone_share, training_zone_rule = _resolve_training_zone_from_buckets(
                bucket_dicts,
                total_supported_seconds=int(row["total_supported_seconds"] or 0),
            )
            results[row["metric_basis"]] = {
                "metric_basis": row["metric_basis"],
                "calculation_status": row["calculation_status"],
                "zone_profile_id": row["zone_profile_id"],
                "profile_label": row["profile_label"],
                "quality_status_snapshot": row["quality_status_snapshot"],
                "supported_sample_count": row["supported_sample_count"],
                "total_supported_seconds": row["total_supported_seconds"],
                "dominant_zone_code": row["dominant_zone_code"],
                "dominant_zone_share": row["dominant_zone_share"],
                "training_zone_code": training_zone_code,
                "training_zone_share": training_zone_share,
                "training_zone_rule": training_zone_rule,
                "calculation_notes": row["calculation_notes"],
                "calculated_at": row["calculated_at"],
                "buckets": bucket_dicts,
            }

    return {
        "activity": {
            "activity_id": activity_row["activity_id"],
            "season_id": activity_row["season_id"],
            "activity_date": activity_row["activity_date"],
            "discipline": activity_row["discipline"],
            "quality_status": activity_row["quality_status"],
        },
        "results": results,
    }


def list_activity_zone_summaries(activity_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not activity_ids:
        return {}

    placeholders = ", ".join("?" for _ in activity_ids)
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT activity_id,
                   activity_zone_result_id,
                   metric_basis,
                   zone_profile_id,
                   calculation_status,
                   dominant_zone_code,
                   dominant_zone_share,
                   calculation_notes
            FROM exec_activity_zone_results
            WHERE activity_id IN ({placeholders})
            ORDER BY activity_id, metric_basis
            """,
            tuple(activity_ids),
        ).fetchall()

        result_ids = [int(row["activity_zone_result_id"]) for row in rows if row["activity_zone_result_id"] is not None]
        buckets_by_result_id: dict[int, list[dict[str, Any]]] = {}
        if result_ids:
            placeholders = ", ".join("?" for _ in result_ids)
            bucket_rows = connection.execute(
                f"""
                SELECT activity_zone_result_id, zone_index, zone_code, seconds_in_zone, share_in_zone, sample_count
                FROM exec_activity_zone_buckets
                WHERE activity_zone_result_id IN ({placeholders})
                ORDER BY activity_zone_result_id, zone_index
                """,
                tuple(result_ids),
            ).fetchall()
            for bucket_row in bucket_rows:
                buckets_by_result_id.setdefault(int(bucket_row["activity_zone_result_id"]), []).append(dict(bucket_row))

    summaries: dict[int, dict[str, Any]] = {}
    for row in rows:
        bucket_rows = buckets_by_result_id.get(int(row["activity_zone_result_id"]), [])
        training_zone_code, training_zone_share, training_zone_rule = _resolve_training_zone_from_buckets(
            bucket_rows,
            total_supported_seconds=int(sum(int(bucket.get("seconds_in_zone") or 0) for bucket in bucket_rows)),
        )
        summary = {
            "calculation_status": row["calculation_status"],
            "dominant_zone_code": row["dominant_zone_code"],
            "dominant_zone_share": row["dominant_zone_share"],
            "training_zone_code": training_zone_code,
            "training_zone_share": training_zone_share,
            "training_zone_rule": training_zone_rule,
            "zone_profile_id": row["zone_profile_id"],
        }
        limiting_reasons = _parse_calculation_notes(row["calculation_notes"])
        if limiting_reasons:
            summary["limiting_reasons"] = limiting_reasons
        summaries.setdefault(int(row["activity_id"]), {})[row["metric_basis"]] = summary
    return summaries


def list_zone_proposals(season_id: int, discipline: str) -> dict[str, Any]:
    normalized_discipline = normalize_zone_discipline(discipline)
    if normalized_discipline is None:
        normalized_input = discipline.strip().lower() if discipline else ""
        return {
            "season_id": season_id,
            "discipline": normalized_input,
            "review_state": "no_actionable_proposals",
            "basis_summary": _empty_zone_proposal_basis_summary(),
            "items": [],
        }

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT proposal.proposal_id,
                   proposal.discipline,
                   proposal.metric_basis,
                   proposal.proposal_status,
                   proposal.confidence_level,
                   proposal.recommendation_kind,
                   proposal.proposal_summary,
                   proposal.limiting_factors,
                   proposal.source_zone_profile_id,
                   proposal.proposed_effective_start_date,
                   proposal.created_at
            FROM zone_refinement_proposals proposal
            WHERE proposal.season_id = ?
              AND proposal.discipline = ?
              AND proposal.proposal_status IN ('pending', 'deferred', 'accepted', 'rejected', 'expired')
            ORDER BY CASE proposal.proposal_status WHEN 'pending' THEN 0 ELSE 1 END,
                     proposal.created_at DESC,
                     proposal.proposal_id DESC
            """,
            (season_id, normalized_discipline),
        ).fetchall()

    items = [
        {
            "proposal_id": row["proposal_id"],
            "discipline": row["discipline"],
            "metric_basis": row["metric_basis"],
            "proposal_status": row["proposal_status"],
            "confidence_level": row["confidence_level"],
            "recommendation_kind": row["recommendation_kind"],
            "proposal_summary": row["proposal_summary"],
            "limiting_factors": _parse_calculation_notes(row["limiting_factors"]),
            "source_zone_profile_id": row["source_zone_profile_id"],
            "proposed_effective_start_date": row["proposed_effective_start_date"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    basis_summary = _summarize_zone_proposals_by_basis(items)
    return {
        "season_id": season_id,
        "discipline": normalized_discipline,
        "review_state": _resolve_zone_proposal_review_state(basis_summary),
        "basis_summary": basis_summary,
        "items": items,
    }


def get_zone_proposal_detail(proposal_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        proposal_row = connection.execute(
            """
            SELECT proposal_id,
                   season_id,
                   discipline,
                   metric_basis,
                   source_zone_profile_id,
                   proposal_status,
                   confidence_level,
                   recommendation_kind,
                   proposal_summary,
                   limiting_factors,
                   proposed_effective_start_date,
                   created_at,
                   decided_at,
                   decision_notes
            FROM zone_refinement_proposals
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()
        if proposal_row is None:
            return None

        boundary_rows = connection.execute(
            """
            SELECT zone_index,
                   zone_code,
                   proposed_lower_bound_value,
                   proposed_upper_bound_value,
                   delta_vs_current_lower,
                   delta_vs_current_upper,
                   bound_unit
            FROM zone_refinement_proposal_boundaries
            WHERE proposal_id = ?
            ORDER BY zone_index
            """,
            (proposal_id,),
        ).fetchall()
        evidence_rows = connection.execute(
            """
            SELECT evidence_type,
                   evidence_role,
                   activity_id,
                   daily_metric_id,
                   evidence_date,
                   metric_basis,
                   summary_json
            FROM zone_refinement_evidence
            WHERE proposal_id = ?
            ORDER BY evidence_date, proposal_evidence_id
            """,
            (proposal_id,),
        ).fetchall()

    return {
        "proposal": {
            "proposal_id": proposal_row["proposal_id"],
            "season_id": proposal_row["season_id"],
            "discipline": proposal_row["discipline"],
            "metric_basis": proposal_row["metric_basis"],
            "source_zone_profile_id": proposal_row["source_zone_profile_id"],
            "proposal_status": proposal_row["proposal_status"],
            "confidence_level": proposal_row["confidence_level"],
            "recommendation_kind": proposal_row["recommendation_kind"],
            "proposal_summary": proposal_row["proposal_summary"],
            "limiting_factors": _parse_calculation_notes(proposal_row["limiting_factors"]),
            "proposed_effective_start_date": proposal_row["proposed_effective_start_date"],
            "created_at": proposal_row["created_at"],
            "decided_at": proposal_row["decided_at"],
            "decision_notes": proposal_row["decision_notes"],
        },
        "boundaries": [dict(boundary) for boundary in boundary_rows],
        "evidence": [
            {
                "evidence_type": row["evidence_type"],
                "evidence_role": row["evidence_role"],
                "activity_id": row["activity_id"],
                "daily_metric_id": row["daily_metric_id"],
                "evidence_date": row["evidence_date"],
                "metric_basis": row["metric_basis"],
                "summary": _parse_json_object(row["summary_json"]),
            }
            for row in evidence_rows
        ],
    }


def generate_zone_refinement_proposals(
    season_id: int,
    *,
    discipline: str,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    normalized_discipline = normalize_zone_discipline(discipline)
    if normalized_discipline is None:
        return {"items": []}

    reference_date = as_of_date or date.today().isoformat()
    created_ids: list[int] = []
    with get_connection() as connection:
        for metric_basis in sorted(SUPPORTED_ZONE_BASES):
            proposal_id = _generate_zone_refinement_proposal_for_basis(
                connection,
                season_id=season_id,
                discipline=normalized_discipline,
                metric_basis=metric_basis,
                as_of_date=reference_date,
            )
            if proposal_id is not None:
                created_ids.append(proposal_id)
        connection.commit()

    if not created_ids:
        return {"items": []}

    proposal_index = {
        item["proposal_id"]: item
        for item in list_zone_proposals(season_id, normalized_discipline)["items"]
    }
    return {"items": [proposal_index[proposal_id] for proposal_id in created_ids if proposal_id in proposal_index]}


def accept_zone_refinement_proposal(
    proposal_id: int,
    *,
    effective_start_date: str | None = None,
    accepted_at: str | None = None,
    decision_notes: str | None = None,
) -> dict[str, Any]:
    with get_connection() as connection:
        proposal_row = connection.execute(
            """
            SELECT proposal_id,
                   season_id,
                   discipline,
                   metric_basis,
                   source_zone_profile_id,
                   proposal_status,
                   proposed_effective_start_date,
                   created_at
            FROM zone_refinement_proposals
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchone()
        if proposal_row is None:
            raise LookupError(f"No existe la propuesta {proposal_id}.")
        if proposal_row["proposal_status"] not in {"pending", "deferred"}:
            raise ValueError(f"La propuesta {proposal_id} ya no esta pendiente de aceptacion.")

        source_profile = connection.execute(
            """
            SELECT zone_profile_id, season_id, discipline, metric_basis, profile_label
            FROM zone_profiles
            WHERE zone_profile_id = ?
            """,
            (proposal_row["source_zone_profile_id"],),
        ).fetchone()
        if source_profile is None:
            raise LookupError(f"No existe el perfil base de la propuesta {proposal_id}.")

        source_boundaries = _get_profile_boundaries(connection, int(source_profile["zone_profile_id"]))
        proposal_boundaries = connection.execute(
            """
            SELECT zone_index,
                   zone_code,
                   proposed_lower_bound_value,
                   proposed_upper_bound_value,
                   bound_unit
            FROM zone_refinement_proposal_boundaries
            WHERE proposal_id = ?
            ORDER BY zone_index
            """,
            (proposal_id,),
        ).fetchall()
        if not proposal_boundaries:
            raise ValueError(f"La propuesta {proposal_id} no contiene boundaries aceptables.")

        merged_boundaries = _merge_refined_boundaries(
            source_boundaries,
            [dict(boundary) for boundary in proposal_boundaries],
        )
        accepted_effective_start_date = (
            effective_start_date
            or proposal_row["proposed_effective_start_date"]
            or _next_iso_date(_iso_date_portion(proposal_row["created_at"]))
        )
        profile_label = f"{source_profile['profile_label']} refined {accepted_effective_start_date}"
        new_zone_profile_id = persist_accepted_zone_profile(
            connection,
            season_id=int(source_profile["season_id"]),
            discipline=source_profile["discipline"],
            metric_basis=source_profile["metric_basis"],
            profile_label=profile_label,
            effective_start_date=accepted_effective_start_date,
            boundaries=merged_boundaries,
            accepted_at=accepted_at,
            derived_from_proposal_id=proposal_id,
        )
        connection.execute(
            """
            UPDATE zone_refinement_proposals
            SET proposal_status = 'accepted',
                decided_at = COALESCE(?, CURRENT_TIMESTAMP),
                decision_notes = ?
            WHERE proposal_id = ?
            """,
            (accepted_at, decision_notes, proposal_id),
        )
        connection.commit()

    return {
        "proposal_id": proposal_id,
        "proposal_status": "accepted",
        "zone_profile_id": new_zone_profile_id,
        "effective_start_date": accepted_effective_start_date,
    }


def list_session_zone_comparisons(week_id: int) -> dict[int, list[dict[str, Any]]]:
    with get_connection() as connection:
        session_rows = connection.execute(
            """
            SELECT planned_session_id, session_date
            FROM plan_planned_sessions
            WHERE week_id = ?
            ORDER BY planned_session_id
            """,
            (week_id,),
        ).fetchall()

        payload: dict[int, list[dict[str, Any]]] = {}
        for session_row in session_rows:
            planned_session_id = int(session_row["planned_session_id"])
            prescription = get_planned_session_prescription(connection, planned_session_id)
            target = derive_zone_target_from_prescription(prescription)
            if target is None:
                continue

            segments = target.get("segments") or []
            min_index = min(
                (_zone_index_from_code(segment.get("target_zone_min_code")) for segment in segments),
                default=None,
            )
            max_index = max(
                (_zone_index_from_code(segment.get("target_zone_max_code")) for segment in segments),
                default=None,
            )
            link_row = connection.execute(
                "SELECT activity_id FROM link_plan_execution WHERE planned_session_id = ? ORDER BY link_id DESC LIMIT 1",
                (planned_session_id,),
            ).fetchone()
            activity_id = int(link_row["activity_id"]) if link_row is not None and link_row["activity_id"] is not None else None
            result_row = None
            any_result_count = 0
            training_zone_code = None
            training_zone_share = None
            if activity_id is not None:
                result_row = connection.execute(
                    """
                    SELECT activity_zone_result_id, calculation_status, dominant_zone_code, dominant_zone_share
                    FROM exec_activity_zone_results
                    WHERE activity_id = ? AND metric_basis = ?
                    ORDER BY activity_zone_result_id DESC
                    LIMIT 1
                    """,
                    (activity_id, target.get("target_basis")),
                ).fetchone()
                any_result_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM exec_activity_zone_results WHERE activity_id = ?",
                        (activity_id,),
                    ).fetchone()[0]
                )
                if result_row is not None and result_row["activity_zone_result_id"] is not None:
                    bucket_rows = connection.execute(
                        """
                        SELECT zone_index, zone_code, seconds_in_zone, share_in_zone, sample_count
                        FROM exec_activity_zone_buckets
                        WHERE activity_zone_result_id = ?
                        ORDER BY zone_index
                        """,
                        (result_row["activity_zone_result_id"],),
                    ).fetchall()
                    training_zone_code, training_zone_share, _training_zone_rule = _resolve_training_zone_from_buckets(
                        [dict(bucket) for bucket in bucket_rows],
                        total_supported_seconds=int(sum(int(bucket["seconds_in_zone"] or 0) for bucket in bucket_rows)),
                    )

            item = {
                "planned_session_id": planned_session_id,
                "session_date": session_row["session_date"],
                "metric_basis": target.get("target_basis"),
                "target_kind": target.get("target_kind"),
                "comparison_eligibility": target.get("comparison_eligibility"),
                "target_zone_min_code": _zone_code_from_index(min_index),
                "target_zone_max_code": _zone_code_from_index(max_index),
                "activity_id": activity_id,
                "calculation_status": result_row["calculation_status"] if result_row is not None else None,
                "dominant_zone_code": result_row["dominant_zone_code"] if result_row is not None else None,
                "dominant_zone_share": result_row["dominant_zone_share"] if result_row is not None else None,
                "training_zone_code": training_zone_code,
                "training_zone_share": training_zone_share,
            }
            item["comparison_status"] = _resolve_session_zone_comparison_status(
                target_basis=target.get("target_basis"),
                comparison_eligibility=target.get("comparison_eligibility"),
                activity_id=activity_id,
                calculation_status=item["calculation_status"],
                target_kind=target.get("target_kind"),
                training_zone_code=item["training_zone_code"],
                target_zone_min_index=min_index,
                target_zone_max_index=max_index,
                any_result_count=any_result_count,
            )
            payload.setdefault(planned_session_id, []).append(item)
    return payload


def get_week_zone_comparison_summary(week_id: int) -> dict[str, Any]:
    session_comparisons = list_session_zone_comparisons(week_id)
    summary_by_basis: dict[str, dict[str, Any]] = {}
    for planned_session_id, items in session_comparisons.items():
        for item in items:
            metric_basis = item["metric_basis"]
            summary = summary_by_basis.setdefault(
                metric_basis,
                {
                    "metric_basis": metric_basis,
                    "planned_session_count": 0,
                    "linked_activity_count": 0,
                    "aligned_count": 0,
                    "misaligned_count": 0,
                    "limited_count": 0,
                    "not_comparable_count": 0,
                    "sessions": [],
                },
            )
            summary["planned_session_count"] += 1
            if item["activity_id"] is not None:
                summary["linked_activity_count"] += 1
            status = item["comparison_status"]
            summary[f"{status}_count"] += 1
            summary["sessions"].append(
                {
                    "planned_session_id": planned_session_id,
                    "comparison_status": status,
                    "dominant_zone_code": item["dominant_zone_code"],
                    "training_zone_code": item["training_zone_code"],
                }
            )
    return {"items": [summary_by_basis[key] for key in sorted(summary_by_basis)]}


def get_week_zone_coherence_assessment(week_id: int) -> dict[str, Any]:
    with get_connection() as connection:
        week_row = connection.execute(
            """
            SELECT mw.week_id, mw.start_date, mw.end_date, mb.season_id
            FROM plan_micro_weeks mw
            JOIN plan_meso_blocks mb ON mb.block_id = mw.block_id
            WHERE mw.week_id = ?
            """,
            (week_id,),
        ).fetchone()
        if week_row is None:
            raise LookupError(f"No existe la semana {week_id}.")

        season_id = int(week_row["season_id"])
        as_of_date = str(week_row["end_date"])
        weekly_summary_index = {
            item["metric_basis"]: item for item in get_week_zone_comparison_summary(week_id)["items"]
        }
        current_profiles = list_current_zone_profiles(season_id, "cycling")["profiles"]
        proposal_payload = list_zone_proposals(season_id, "cycling")

        basis_assessments = []
        for metric_basis in sorted(SUPPORTED_ZONE_BASES):
            basis_assessments.append(
                _assess_week_zone_coherence_for_basis(
                    connection,
                    season_id=season_id,
                    as_of_date=as_of_date,
                    metric_basis=metric_basis,
                    weekly_summary=weekly_summary_index.get(metric_basis),
                    current_profile=current_profiles.get(metric_basis),
                    proposal_items=proposal_payload["items"],
                )
            )

    return {
        "week_id": week_id,
        "season_id": season_id,
        "discipline": "cycling",
        "assessment_date": as_of_date,
        "overall_status": _resolve_week_zone_coherence_overall_status(basis_assessments),
        "basis_assessments": basis_assessments,
        "proposal_review_state": proposal_payload["review_state"],
    }


def _assess_week_zone_coherence_for_basis(
    connection: Any,
    *,
    season_id: int,
    as_of_date: str,
    metric_basis: str,
    weekly_summary: dict[str, Any] | None,
    current_profile: dict[str, Any] | None,
    proposal_items: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = weekly_summary or _empty_week_zone_summary(metric_basis)
    basis_proposals = [
        item
        for item in proposal_items
        if item.get("metric_basis") == metric_basis and item.get("proposal_status") in {"pending", "deferred"}
    ]
    latest_actionable_proposal = basis_proposals[0] if basis_proposals else None

    if current_profile is None:
        return {
            "metric_basis": metric_basis,
            "status": "missing_profile",
            "summary": summary,
            "current_profile": None,
            "current_metric_profile": None,
            "latest_actionable_proposal": latest_actionable_proposal,
            "supporting_activity_count": 0,
            "supporting_activities": [],
            "proposed_boundary_changes": [],
            "limiting_factors": [],
            "recommendation": "No hay perfil activo para esta base; conviene revisar y fijar zonas antes de usarla como referencia semanal.",
        }

    active_profile = _get_active_zone_profile(
        connection,
        season_id=season_id,
        discipline="cycling",
        metric_basis=metric_basis,
        activity_date=as_of_date,
    )
    if active_profile is None:
        return {
            "metric_basis": metric_basis,
            "status": "missing_profile",
            "summary": summary,
            "current_profile": current_profile,
            "current_metric_profile": current_profile.get("metric_profile"),
            "latest_actionable_proposal": latest_actionable_proposal,
            "supporting_activity_count": 0,
            "supporting_activities": [],
            "proposed_boundary_changes": [],
            "limiting_factors": [],
            "recommendation": "No hay un perfil activo para la fecha de cierre de la semana; conviene revisar vigencia y versionado de zonas.",
        }

    current_boundaries = _get_profile_boundaries(connection, int(active_profile["zone_profile_id"]))
    proposed_boundaries, supporting_rows = _build_refinement_boundary_updates(
        connection,
        zone_profile_id=int(active_profile["zone_profile_id"]),
        metric_basis=metric_basis,
        as_of_date=as_of_date,
        current_boundaries=current_boundaries,
    )
    limiting_factors: list[str] = []
    if proposed_boundaries:
        limiting_factors, _ = _collect_recovery_limiting_factors(
            connection,
            season_id=season_id,
            as_of_date=as_of_date,
            metric_basis=metric_basis,
        )

    if proposed_boundaries:
        status = "update_deferred" if limiting_factors else "update_recommended"
        recommendation = (
            "Las actividades recientes en Z2 apoyan una revision de zonas, pero conviene diferir el cambio hasta que mejore la recuperacion."
            if limiting_factors
            else "Las actividades recientes en Z2 sugieren que la definicion actual puede haberse quedado baja y conviene revisar o actualizar el perfil."
        )
    elif latest_actionable_proposal is not None:
        status = "update_deferred" if latest_actionable_proposal["proposal_status"] == "deferred" else "update_recommended"
        recommendation = (
            latest_actionable_proposal.get("proposal_summary")
            or "Existe una propuesta de refinamiento pendiente para esta base; conviene revisarla en la decision semanal."
        )
    elif summary["misaligned_count"] > 0 and summary["aligned_count"] == 0 and summary["linked_activity_count"] > 0:
        status = "watch"
        recommendation = "La semana no demuestra por si sola que las zonas esten mal, pero deja una senal para vigilar ejecucion, terreno y coherencia del perfil."
    elif summary["planned_session_count"] > 0 and summary["linked_activity_count"] < summary["planned_session_count"]:
        status = "limited_week_evidence"
        recommendation = "La evidencia semanal es parcial; no hay base suficiente para cambiar zonas solo con esta semana."
    else:
        status = "coherent"
        recommendation = "No hay una senal util esta semana para cambiar la definicion de zonas; mantener y seguir observando."

    return {
        "metric_basis": metric_basis,
        "status": status,
        "summary": summary,
        "current_profile": {
            "zone_profile_id": current_profile.get("zone_profile_id"),
            "profile_label": current_profile.get("profile_label"),
            "effective_start_date": current_profile.get("effective_start_date"),
            "z2_upper_bound": _find_zone_boundary_value(current_profile.get("boundaries", []), "Z2", "upper_bound_value"),
            "z3_lower_bound": _find_zone_boundary_value(current_profile.get("boundaries", []), "Z3", "lower_bound_value"),
        },
        "current_metric_profile": current_profile.get("metric_profile"),
        "latest_actionable_proposal": latest_actionable_proposal,
        "supporting_activity_count": len(supporting_rows),
        "supporting_activities": supporting_rows[:3],
        "proposed_boundary_changes": proposed_boundaries,
        "limiting_factors": limiting_factors,
        "recommendation": recommendation,
    }


def _resolve_week_zone_coherence_overall_status(basis_assessments: list[dict[str, Any]]) -> str:
    statuses = {item["status"] for item in basis_assessments}
    if "missing_profile" in statuses:
        return "review_needed"
    if "update_recommended" in statuses:
        return "update_candidate"
    if "update_deferred" in statuses:
        return "defer_update"
    if "watch" in statuses:
        return "monitor"
    if "limited_week_evidence" in statuses:
        return "limited_week_evidence"
    return "coherent"


def _empty_week_zone_summary(metric_basis: str) -> dict[str, Any]:
    return {
        "metric_basis": metric_basis,
        "planned_session_count": 0,
        "linked_activity_count": 0,
        "aligned_count": 0,
        "misaligned_count": 0,
        "limited_count": 0,
        "not_comparable_count": 0,
        "sessions": [],
    }


def _find_zone_boundary_value(boundaries: list[dict[str, Any]], zone_code: str, field_name: str) -> Any:
    for boundary in boundaries:
        if boundary.get("zone_code") == zone_code:
            return boundary.get(field_name)
    return None


def _parse_calculation_notes(calculation_notes: str | None) -> list[str]:
    if calculation_notes is None:
        return []
    try:
        parsed = json.loads(calculation_notes)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _empty_zone_proposal_basis_summary() -> dict[str, dict[str, Any]]:
    return {
        metric_basis: {
            "proposal_count": 0,
            "pending_count": 0,
            "deferred_count": 0,
            "actionable_count": 0,
            "latest_proposal_id": None,
            "latest_proposal_status": None,
        }
        for metric_basis in sorted(SUPPORTED_ZONE_BASES)
    }


def _summarize_zone_proposals_by_basis(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary = _empty_zone_proposal_basis_summary()
    for item in items:
        metric_basis = normalize_zone_basis(item.get("metric_basis"))
        if metric_basis is None:
            continue
        basis_summary = summary[metric_basis]
        basis_summary["proposal_count"] += 1
        if item["proposal_status"] == "pending":
            basis_summary["pending_count"] += 1
        if item["proposal_status"] == "deferred":
            basis_summary["deferred_count"] += 1
        if item["proposal_status"] in {"pending", "deferred"}:
            basis_summary["actionable_count"] += 1
        if basis_summary["latest_proposal_id"] is None:
            basis_summary["latest_proposal_id"] = item["proposal_id"]
            basis_summary["latest_proposal_status"] = item["proposal_status"]
    return summary


def _resolve_zone_proposal_review_state(basis_summary: dict[str, dict[str, Any]]) -> str:
    heart_rate_actionable = basis_summary["heart_rate"]["actionable_count"]
    power_actionable = basis_summary["power"]["actionable_count"]
    if heart_rate_actionable and power_actionable:
        return "mixed_basis"
    if heart_rate_actionable:
        return "heart_rate_only"
    if power_actionable:
        return "power_only"
    return "no_actionable_proposals"


def _parse_json_object(payload: str | None) -> dict[str, Any]:
    if payload is None:
        return {}
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _previous_iso_date(iso_date: str) -> str:
    return (date.fromisoformat(iso_date) - timedelta(days=1)).isoformat()


def _next_iso_date(iso_date: str) -> str:
    return (date.fromisoformat(iso_date) + timedelta(days=1)).isoformat()


def _iso_date_portion(timestamp_or_date: str) -> str:
    return timestamp_or_date[:10]


def _zone_code_from_index(zone_index: int | None) -> str | None:
    if zone_index is None:
        return None
    return f"Z{int(zone_index)}"


def _zone_index_from_code(zone_code: str | None) -> int | None:
    if zone_code is None or not zone_code.startswith("Z"):
        return None
    try:
        return int(zone_code[1:])
    except ValueError:
        return None


def _sum_bucket_seconds(bucket_rows: list[dict[str, Any]], *, min_index: int | None = None, max_index: int | None = None) -> int:
    total = 0
    for bucket in bucket_rows:
        zone_index = _zone_index_from_code(bucket.get("zone_code"))
        if zone_index is None:
            continue
        if min_index is not None and zone_index < min_index:
            continue
        if max_index is not None and zone_index > max_index:
            continue
        total += int(bucket.get("seconds_in_zone") or 0)
    return total


def _resolve_training_zone_from_buckets(
    bucket_rows: list[dict[str, Any]],
    *,
    total_supported_seconds: int,
) -> tuple[str | None, float | None, str | None]:
    if total_supported_seconds <= 0 or not bucket_rows:
        return (None, None, None)

    z1_seconds = _sum_bucket_seconds(bucket_rows, min_index=1, max_index=1)
    z2_seconds = _sum_bucket_seconds(bucket_rows, min_index=2, max_index=2)
    z1_z2_seconds = _sum_bucket_seconds(bucket_rows, min_index=1, max_index=2)
    z2_z3_seconds = _sum_bucket_seconds(bucket_rows, min_index=2, max_index=3)
    z3_plus_seconds = _sum_bucket_seconds(bucket_rows, min_index=3)
    z4_plus_seconds = _sum_bucket_seconds(bucket_rows, min_index=4)
    z5_plus_seconds = _sum_bucket_seconds(bucket_rows, min_index=5)
    z6_plus_seconds = _sum_bucket_seconds(bucket_rows, min_index=6)
    z7_seconds = _sum_bucket_seconds(bucket_rows, min_index=7)
    z1_share = z1_seconds / total_supported_seconds
    z1_z2_share = z1_z2_seconds / total_supported_seconds
    z2_z3_share = z2_z3_seconds / total_supported_seconds

    # Calibrated against recent terrain-shaped cycling history: aerobic rides often
    # accumulate some Z4/Z5 spikes, so higher-zone labels require a more substantial dose.
    if z6_plus_seconds >= 900 or z7_seconds >= 300:
        return ("Z6", round(z6_plus_seconds / total_supported_seconds, 4), "meaningful_z6_plus_dose")
    if z5_plus_seconds >= 1500:
        return ("Z5", round(z5_plus_seconds / total_supported_seconds, 4), "meaningful_z5_plus_dose")
    if z4_plus_seconds >= 2400:
        return ("Z4", round(z4_plus_seconds / total_supported_seconds, 4), "meaningful_z4_plus_dose")
    if z3_plus_seconds >= 3000:
        return ("Z3", round(z3_plus_seconds / total_supported_seconds, 4), "meaningful_z3_plus_dose")
    if z1_z2_share >= 0.78 and z4_plus_seconds < 500 and z5_plus_seconds < 120:
        return ("Z1", round(z1_z2_share, 4), "predominantly_easy_with_low_upper_zone_contamination")
    if z2_z3_share >= 0.45 and z5_plus_seconds < 900 and z4_plus_seconds < 1800:
        return ("Z2", round(z2_z3_share, 4), "sustained_aerobic_useful_work_without_large_high_intensity_dose")

    weighted_zone_score = sum(
        int(bucket["zone_code"][1:]) * int(bucket.get("seconds_in_zone") or 0)
        for bucket in bucket_rows
        if _zone_index_from_code(bucket.get("zone_code")) is not None
    ) / total_supported_seconds
    fallback_zone_index = max(1, min(7, int(weighted_zone_score + 0.5)))
    return (_zone_code_from_index(fallback_zone_index), None, "weighted_zone_centroid_fallback")


def _resolve_session_zone_comparison_status(
    *,
    target_basis: str | None,
    comparison_eligibility: str | None,
    activity_id: int | None,
    calculation_status: str | None,
    target_kind: str | None,
    training_zone_code: str | None,
    target_zone_min_index: int | None,
    target_zone_max_index: int | None,
    any_result_count: int,
) -> str:
    if comparison_eligibility == "not_comparable":
        return "not_comparable"
    if target_basis is None or target_basis == "mixed":
        return "limited"
    if activity_id is None:
        return "not_comparable"
    if target_kind == "multi_segment":
        return "limited"
    if calculation_status != "calculated":
        return "limited" if any_result_count > 0 or activity_id is not None else "not_comparable"
    training_zone_index = _zone_index_from_code(training_zone_code)
    if training_zone_index is None or target_zone_min_index is None or target_zone_max_index is None:
        return "limited"
    if target_zone_min_index <= training_zone_index <= target_zone_max_index:
        return "aligned"
    return "misaligned"


def _merge_refined_boundaries(
    source_boundaries: list[dict[str, Any]],
    proposal_boundaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    proposal_by_zone_index = {
        int(boundary["zone_index"]): boundary
        for boundary in proposal_boundaries
    }
    merged: list[dict[str, Any]] = []
    for source_boundary in source_boundaries:
        proposal_boundary = proposal_by_zone_index.get(int(source_boundary["zone_index"]))
        if proposal_boundary is None:
            merged.append(dict(source_boundary))
            continue
        merged.append(
            {
                **dict(source_boundary),
                "lower_bound_value": proposal_boundary["proposed_lower_bound_value"],
                "upper_bound_value": proposal_boundary["proposed_upper_bound_value"],
                "bound_unit": proposal_boundary.get("bound_unit", source_boundary["bound_unit"]),
            }
        )
    return merged


def _generate_zone_refinement_proposal_for_basis(
    connection: Any,
    *,
    season_id: int,
    discipline: str,
    metric_basis: str,
    as_of_date: str,
) -> int | None:
    active_profile = _get_active_zone_profile(
        connection,
        season_id=season_id,
        discipline=discipline,
        metric_basis=metric_basis,
        activity_date=as_of_date,
    )
    if active_profile is None:
        return None

    current_boundaries = _get_profile_boundaries(connection, int(active_profile["zone_profile_id"]))
    proposed_boundaries, activity_evidence = _build_refinement_boundary_updates(
        connection,
        zone_profile_id=int(active_profile["zone_profile_id"]),
        metric_basis=metric_basis,
        as_of_date=as_of_date,
        current_boundaries=current_boundaries,
    )
    if not proposed_boundaries or len(activity_evidence) < MIN_REFINEMENT_ACTIVITY_COUNT:
        return None

    limiting_factors, daily_metric_evidence = _collect_recovery_limiting_factors(
        connection,
        season_id=season_id,
        as_of_date=as_of_date,
        metric_basis=metric_basis,
    )
    proposal_status = "deferred" if limiting_factors else "pending"
    confidence_level = "low" if limiting_factors else ("high" if len(activity_evidence) >= 3 else "medium")
    proposal_summary = _build_proposal_summary(metric_basis, proposed_boundaries)
    proposal_cursor = connection.execute(
        """
        INSERT INTO zone_refinement_proposals (
            season_id,
            discipline,
            metric_basis,
            source_zone_profile_id,
            proposal_status,
            confidence_level,
            recommendation_kind,
            proposal_summary,
            limiting_factors,
            proposed_effective_start_date
        ) VALUES (?, ?, ?, ?, ?, ?, 'rebalance', ?, ?, ?)
        """,
        (
            season_id,
            discipline,
            metric_basis,
            active_profile["zone_profile_id"],
            proposal_status,
            confidence_level,
            proposal_summary,
            json.dumps(limiting_factors, ensure_ascii=True),
            _next_iso_date(as_of_date),
        ),
    )
    proposal_id = int(proposal_cursor.lastrowid)

    for boundary in proposed_boundaries:
        connection.execute(
            """
            INSERT INTO zone_refinement_proposal_boundaries (
                proposal_id,
                zone_index,
                zone_code,
                proposed_lower_bound_value,
                proposed_upper_bound_value,
                bound_unit,
                delta_vs_current_lower,
                delta_vs_current_upper
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                boundary["zone_index"],
                boundary["zone_code"],
                boundary["proposed_lower_bound_value"],
                boundary["proposed_upper_bound_value"],
                boundary["bound_unit"],
                boundary["delta_vs_current_lower"],
                boundary["delta_vs_current_upper"],
            ),
        )

    for evidence in activity_evidence:
        connection.execute(
            """
            INSERT INTO zone_refinement_evidence (
                proposal_id,
                evidence_type,
                activity_id,
                evidence_date,
                evidence_role,
                metric_basis,
                summary_json
            ) VALUES (?, 'activity', ?, ?, 'supporting', ?, ?)
            """,
            (
                proposal_id,
                evidence["activity_id"],
                evidence["activity_date"],
                metric_basis,
                json.dumps(
                    {
                        "dominant_zone_code": evidence["dominant_zone_code"],
                        "dominant_zone_share": evidence["dominant_zone_share"],
                        "anchor_value": evidence["anchor_value"],
                    },
                    ensure_ascii=True,
                ),
            ),
        )

    for evidence in daily_metric_evidence:
        connection.execute(
            """
            INSERT INTO zone_refinement_evidence (
                proposal_id,
                evidence_type,
                daily_metric_id,
                evidence_date,
                evidence_role,
                metric_basis,
                summary_json
            ) VALUES (?, 'daily_metric', ?, ?, 'limiting', ?, ?)
            """,
            (
                proposal_id,
                evidence["daily_metric_id"],
                evidence["metric_date"],
                metric_basis,
                json.dumps(evidence["summary"], ensure_ascii=True),
            ),
        )

    return proposal_id


def _build_refinement_boundary_updates(
    connection: Any,
    *,
    zone_profile_id: int,
    metric_basis: str,
    as_of_date: str,
    current_boundaries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    z2_boundary = next((boundary for boundary in current_boundaries if boundary["zone_code"] == "Z2"), None)
    z3_boundary = next((boundary for boundary in current_boundaries if boundary["zone_code"] == "Z3"), None)
    if z2_boundary is None or z3_boundary is None or z2_boundary["upper_bound_value"] is None:
        return ([], [])

    lookback_start = (date.fromisoformat(as_of_date) - timedelta(days=REFINEMENT_ACTIVITY_LOOKBACK_DAYS)).isoformat()
    anchor_expression = "ea.avg_hr" if metric_basis == "heart_rate" else "COALESCE(ea.normalized_power, ea.avg_power)"
    activity_rows = connection.execute(
        f"""
        SELECT ea.activity_id,
               ea.activity_date,
               ear.dominant_zone_code,
               ear.dominant_zone_share,
               {anchor_expression} AS anchor_value
        FROM exec_activity_zone_results ear
        JOIN exec_activities ea ON ea.activity_id = ear.activity_id
        WHERE ear.zone_profile_id = ?
          AND ear.metric_basis = ?
          AND ear.calculation_status = 'calculated'
          AND ea.activity_date BETWEEN ? AND ?
        ORDER BY ea.activity_date DESC, ea.activity_id DESC
        """,
        (zone_profile_id, metric_basis, lookback_start, as_of_date),
    ).fetchall()
    supporting_rows = [
        {
            "activity_id": row["activity_id"],
            "activity_date": row["activity_date"],
            "dominant_zone_code": row["dominant_zone_code"],
            "dominant_zone_share": row["dominant_zone_share"],
            "anchor_value": row["anchor_value"],
        }
        for row in activity_rows
        if row["anchor_value"] is not None
        and row["dominant_zone_code"] == "Z2"
        and (row["dominant_zone_share"] or 0) >= 0.5
    ]
    if len(supporting_rows) < MIN_REFINEMENT_ACTIVITY_COUNT:
        return ([], [])

    current_upper = float(z2_boundary["upper_bound_value"])
    proposed_upper = int(round(median([float(row["anchor_value"]) for row in supporting_rows])))
    minimum_delta = MIN_REFINEMENT_DELTA[metric_basis]
    if proposed_upper < current_upper + minimum_delta:
        return ([], [])

    z3_upper = z3_boundary.get("upper_bound_value")
    if z3_upper is not None:
        proposed_upper = min(proposed_upper, int(float(z3_upper)) - 1)
    if proposed_upper < current_upper + minimum_delta:
        return ([], [])

    proposed_z2_upper = float(proposed_upper)
    proposed_z3_lower = float(proposed_upper + 1)
    return (
        [
            {
                "zone_index": z2_boundary["zone_index"],
                "zone_code": z2_boundary["zone_code"],
                "proposed_lower_bound_value": z2_boundary["lower_bound_value"],
                "proposed_upper_bound_value": proposed_z2_upper,
                "bound_unit": z2_boundary["bound_unit"],
                "delta_vs_current_lower": 0,
                "delta_vs_current_upper": round(proposed_z2_upper - float(current_upper), 2),
            },
            {
                "zone_index": z3_boundary["zone_index"],
                "zone_code": z3_boundary["zone_code"],
                "proposed_lower_bound_value": proposed_z3_lower,
                "proposed_upper_bound_value": z3_boundary["upper_bound_value"],
                "bound_unit": z3_boundary["bound_unit"],
                "delta_vs_current_lower": round(proposed_z3_lower - float(z3_boundary["lower_bound_value"]), 2)
                if z3_boundary["lower_bound_value"] is not None
                else None,
                "delta_vs_current_upper": 0,
            },
        ],
        supporting_rows,
    )


def _collect_recovery_limiting_factors(
    connection: Any,
    *,
    season_id: int,
    as_of_date: str,
    metric_basis: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    lookback_start = (date.fromisoformat(as_of_date) - timedelta(days=REFINEMENT_RECOVERY_LOOKBACK_DAYS)).isoformat()
    try:
        rows = connection.execute(
            """
            SELECT daily_metric_id,
                   metric_date,
                   sleep_hours,
                   body_battery,
                   stress_avg,
                   hrv
            FROM exec_daily_metrics
            WHERE season_id = ?
              AND metric_date BETWEEN ? AND ?
            ORDER BY metric_date DESC, daily_metric_id DESC
            """,
            (season_id, lookback_start, as_of_date),
        ).fetchall()
    except sqlite3.OperationalError:
        return ([], [])

    limiting_factors: set[str] = set()
    evidence_rows: list[dict[str, Any]] = []
    for row in rows:
        summary: dict[str, Any] = {}
        if row["sleep_hours"] is not None and float(row["sleep_hours"]) < 6:
            limiting_factors.add("low_sleep_window")
            summary["sleep_hours"] = row["sleep_hours"]
        if row["stress_avg"] is not None and float(row["stress_avg"]) >= 40:
            limiting_factors.add("elevated_stress_window")
            summary["stress_avg"] = row["stress_avg"]
        if row["body_battery"] is not None and float(row["body_battery"]) < 40:
            limiting_factors.add("low_body_battery_window")
            summary["body_battery"] = row["body_battery"]
        if not summary:
            continue
        if row["hrv"] is not None:
            summary["hrv"] = row["hrv"]
        evidence_rows.append(
            {
                "daily_metric_id": row["daily_metric_id"],
                "metric_date": row["metric_date"],
                "summary": summary,
                "metric_basis": metric_basis,
            }
        )
    return (sorted(limiting_factors), evidence_rows)


def _build_proposal_summary(metric_basis: str, proposed_boundaries: list[dict[str, Any]]) -> str:
    z2_boundary = next(boundary for boundary in proposed_boundaries if boundary["zone_code"] == "Z2")
    basis_label = "heart-rate" if metric_basis == "heart_rate" else "power"
    return f"Recent {basis_label} activity evidence suggests lifting the Z2 upper bound to {int(z2_boundary['proposed_upper_bound_value'])}."


def _serialize_zone_metric_profile_row(row: Any) -> dict[str, Any]:
    payload = {
        "zone_metric_profile_id": row["zone_metric_profile_id"],
        "metric_basis": row["metric_basis"],
        "profile_label": row["profile_label"],
        "model_key": row["model_key"],
        "effective_start_date": row["effective_start_date"],
        "effective_end_date": row["effective_end_date"],
        "accepted_at": row["accepted_at"],
        "notes": row["notes"],
        "parameters": {},
    }
    if row["metric_basis"] == "heart_rate":
        payload["parameters"] = {
            "resting_hr": row["resting_hr"],
            "max_hr": row["max_hr"],
        }
    if row["metric_basis"] == "power":
        payload["parameters"] = {
            "ftp": row["ftp"],
        }
    return payload


def _validate_zone_metric_profile_parameters(
    *,
    metric_basis: str,
    model_key: str,
    resting_hr: float | None,
    max_hr: float | None,
    ftp: float | None,
) -> None:
    supported_models = SUPPORTED_ZONE_MODELS.get(metric_basis, set())
    if model_key not in supported_models:
        raise ValueError(f"Modelo no soportado para {metric_basis}: {model_key}.")
    if metric_basis == "heart_rate":
        if resting_hr is None or max_hr is None:
            raise ValueError("El modelo de reserva cardiaca requiere resting_hr y max_hr.")
        if resting_hr <= 0 or max_hr <= 0:
            raise ValueError("resting_hr y max_hr deben ser positivos.")
        if max_hr <= resting_hr:
            raise ValueError("max_hr debe ser mayor que resting_hr.")
        return
    if ftp is None or ftp <= 0:
        raise ValueError("El modelo FTP requiere ftp positivo.")


def _default_metric_profile_label(*, metric_basis: str, model_key: str) -> str:
    if metric_basis == "heart_rate" and model_key == "heart_rate_reserve_5_zone":
        return "cycling hr reserve 5 zones"
    if metric_basis == "power" and model_key == "ftp_coggan_7_zone":
        return "cycling ftp 7 zones"
    return f"cycling {metric_basis} {model_key}"


def derive_zone_boundaries_from_metrics(
    *,
    metric_basis: str,
    model_key: str,
    resting_hr: float | None = None,
    max_hr: float | None = None,
    ftp: float | None = None,
) -> list[dict[str, Any]]:
    _validate_zone_metric_profile_parameters(
        metric_basis=metric_basis,
        model_key=model_key,
        resting_hr=resting_hr,
        max_hr=max_hr,
        ftp=ftp,
    )
    if metric_basis == "heart_rate":
        assert resting_hr is not None
        assert max_hr is not None
        return _derive_heart_rate_reserve_boundaries(resting_hr=resting_hr, max_hr=max_hr)
    assert ftp is not None
    return _derive_ftp_coggan_boundaries(ftp=ftp)


def _derive_heart_rate_reserve_boundaries(*, resting_hr: float, max_hr: float) -> list[dict[str, Any]]:
    reserve = max_hr - resting_hr
    upper_bounds = [round(resting_hr + reserve * percentage) for percentage in (0.60, 0.70, 0.80, 0.90)]
    zone_names = ["Recuperacion", "Aerobica", "Tempo", "Umbral", "VO2 max"]
    lower_bound = round(resting_hr)
    boundaries: list[dict[str, Any]] = []
    for zone_index, zone_name in enumerate(zone_names, start=1):
        upper_bound = None if zone_index == len(zone_names) else upper_bounds[zone_index - 1]
        boundaries.append(
            {
                "zone_index": zone_index,
                "zone_code": f"Z{zone_index}",
                "zone_name": zone_name,
                "lower_bound_value": lower_bound,
                "upper_bound_value": upper_bound,
                "bound_unit": "bpm",
                "target_kind": "closed",
            }
        )
        if upper_bound is not None:
            lower_bound = upper_bound + 1
    return boundaries


def _derive_ftp_coggan_boundaries(*, ftp: float) -> list[dict[str, Any]]:
    upper_bounds = [round(ftp * percentage) for percentage in (0.55, 0.75, 0.90, 1.05, 1.20, 1.50)]
    zone_names = [
        "Recuperacion activa",
        "Resistencia aerobica",
        "Tempo",
        "Umbral",
        "VO2 max",
        "Capacidad anaerobica",
        "Potencia neuromuscular",
    ]
    lower_bound = 0
    boundaries: list[dict[str, Any]] = []
    for zone_index, zone_name in enumerate(zone_names, start=1):
        upper_bound = None if zone_index == len(zone_names) else upper_bounds[zone_index - 1]
        boundaries.append(
            {
                "zone_index": zone_index,
                "zone_code": f"Z{zone_index}",
                "zone_name": zone_name,
                "lower_bound_value": lower_bound,
                "upper_bound_value": upper_bound,
                "bound_unit": "watts",
                "target_kind": "closed",
            }
        )
        if upper_bound is not None:
            lower_bound = upper_bound + 1
    return boundaries


def _get_active_zone_profile(
    connection: Any,
    *,
    season_id: int,
    discipline: str,
    metric_basis: str,
    activity_date: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
                SELECT zone_profile_id,
                             metric_basis,
                             profile_label,
                             source_metric_profile_id,
                             calculation_model_key,
                             effective_start_date,
                             effective_end_date
        FROM zone_profiles
        WHERE season_id = ?
          AND discipline = ?
          AND metric_basis = ?
          AND governance_status = 'accepted'
          AND effective_start_date <= ?
          AND (effective_end_date IS NULL OR effective_end_date = '' OR effective_end_date >= ?)
        ORDER BY effective_start_date DESC, zone_profile_id DESC
        LIMIT 1
        """,
        (season_id, discipline, metric_basis, activity_date, activity_date),
    ).fetchone()
    return dict(row) if row else None


def _get_profile_boundaries(connection: Any, zone_profile_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT zone_index, zone_code, lower_bound_value, upper_bound_value, bound_unit
        FROM zone_profile_boundaries
        WHERE zone_profile_id = ?
        ORDER BY zone_index
        """,
        (zone_profile_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _excluded_sample_indexes_for_metric(evaluation: ActivityQualityEvaluation, metric_name: str) -> set[int]:
    excluded_indexes: set[int] = set()
    for decision in evaluation.decisions:
        if decision.metric_name != metric_name or decision.decision_status != "excluded":
            continue
        excluded_indexes.update(range(decision.start_sample_index, decision.end_sample_index + 1))
    return excluded_indexes


def _accepted_metric_readings(
    activity: NormalizedActivity,
    *,
    metric_basis: str,
    evaluation: ActivityQualityEvaluation,
) -> list[NormalizedMetricReading]:
    metric_name = ZONE_METRIC_STREAMS[metric_basis]
    readings = [reading for reading in activity.metric_readings if reading.metric_name == metric_name]
    if metric_basis != "heart_rate":
        return readings
    excluded_indexes = _excluded_sample_indexes_for_metric(evaluation, metric_name)
    return [reading for reading in readings if reading.sample_index not in excluded_indexes]


def _bucket_for_value(value: float, boundaries: list[dict[str, Any]]) -> dict[str, Any] | None:
    for boundary in boundaries:
        lower_bound = boundary["lower_bound_value"]
        upper_bound = boundary["upper_bound_value"]
        if lower_bound is not None and value < lower_bound:
            continue
        if upper_bound is not None and value > upper_bound:
            continue
        return boundary
    return None


def _estimate_sample_durations(readings: list[NormalizedMetricReading]) -> list[int]:
    if not readings:
        return []
    positive_deltas: list[int] = []
    durations: list[int] = []
    for index, reading in enumerate(readings):
        duration = 0
        if index + 1 < len(readings):
            current_elapsed = reading.elapsed_seconds
            next_elapsed = readings[index + 1].elapsed_seconds
            if current_elapsed is not None and next_elapsed is not None:
                delta = int(round(next_elapsed - current_elapsed))
                if delta > 0:
                    duration = delta
                    positive_deltas.append(delta)
        if duration <= 0:
            if positive_deltas:
                duration = int(round(median(positive_deltas)))
            else:
                duration = 1
        durations.append(max(duration, 1))
    return durations


def _insufficient_sample_reason(metric_basis: str, readings: list[NormalizedMetricReading]) -> str | None:
    minimum_required = MIN_ZONE_SAMPLE_COUNT[metric_basis]
    if len(readings) >= minimum_required:
        return None
    return f"insufficient_{ZONE_METRIC_STREAMS[metric_basis]}_samples"


def persist_activity_zone_results(
    connection: Any,
    *,
    season_id: int,
    activity_row_id: int,
    activity: NormalizedActivity,
    evaluation: ActivityQualityEvaluation,
) -> None:
    normalized_discipline = normalize_zone_discipline(activity.discipline)
    if normalized_discipline is None:
        stale_result_ids = [
            row["activity_zone_result_id"]
            for row in connection.execute(
                "SELECT activity_zone_result_id FROM exec_activity_zone_results WHERE activity_id = ?",
                (activity_row_id,),
            ).fetchall()
        ]
        for stale_result_id in stale_result_ids:
            connection.execute(
                "DELETE FROM exec_activity_zone_buckets WHERE activity_zone_result_id = ?",
                (stale_result_id,),
            )
        connection.execute("DELETE FROM exec_activity_zone_results WHERE activity_id = ?", (activity_row_id,))
        return

    for metric_basis in sorted(SUPPORTED_ZONE_BASES):
        active_profile = _get_active_zone_profile(
            connection,
            season_id=season_id,
            discipline=normalized_discipline,
            metric_basis=metric_basis,
            activity_date=activity.activity_date,
        )
        stale_rows = connection.execute(
            """
            SELECT activity_zone_result_id
            FROM exec_activity_zone_results
            WHERE activity_id = ?
              AND metric_basis = ?
              AND (? IS NULL OR zone_profile_id != ?)
            """,
            (
                activity_row_id,
                metric_basis,
                active_profile["zone_profile_id"] if active_profile is not None else None,
                active_profile["zone_profile_id"] if active_profile is not None else None,
            ),
        ).fetchall()
        for stale_row in stale_rows:
            connection.execute(
                "DELETE FROM exec_activity_zone_buckets WHERE activity_zone_result_id = ?",
                (stale_row["activity_zone_result_id"],),
            )
        connection.execute(
            """
            DELETE FROM exec_activity_zone_results
            WHERE activity_id = ?
              AND metric_basis = ?
              AND (? IS NULL OR zone_profile_id != ?)
            """,
            (
                activity_row_id,
                metric_basis,
                active_profile["zone_profile_id"] if active_profile is not None else None,
                active_profile["zone_profile_id"] if active_profile is not None else None,
            ),
        )
        if active_profile is None:
            continue

        boundaries = _get_profile_boundaries(connection, int(active_profile["zone_profile_id"]))
        readings = _accepted_metric_readings(activity, metric_basis=metric_basis, evaluation=evaluation)
        if not readings:
            calculation_status = "unavailable"
            supported_sample_count = 0
            total_supported_seconds = 0
            dominant_zone_code = None
            dominant_zone_share = None
            calculation_notes = json.dumps([f"missing_{ZONE_METRIC_STREAMS[metric_basis]}_stream"], ensure_ascii=True)
            bucket_rows: list[tuple[int, str, int, float, int]] = []
        else:
            insufficient_sample_reason = _insufficient_sample_reason(metric_basis, readings)
            if insufficient_sample_reason is not None:
                calculation_status = "limited"
                supported_sample_count = len(readings)
                total_supported_seconds = 0
                dominant_zone_code = None
                dominant_zone_share = None
                calculation_notes = json.dumps([insufficient_sample_reason], ensure_ascii=True)
                bucket_rows = []
            else:
                durations = _estimate_sample_durations(readings)
                seconds_by_zone: dict[str, int] = {}
                sample_counts_by_zone: dict[str, int] = {}
                zone_order: dict[str, int] = {}
                for reading, duration in zip(readings, durations, strict=False):
                    boundary = _bucket_for_value(reading.raw_value, boundaries)
                    if boundary is None:
                        continue
                    zone_code = boundary["zone_code"]
                    seconds_by_zone[zone_code] = seconds_by_zone.get(zone_code, 0) + duration
                    sample_counts_by_zone[zone_code] = sample_counts_by_zone.get(zone_code, 0) + 1
                    zone_order[zone_code] = int(boundary["zone_index"])

                total_supported_seconds = sum(seconds_by_zone.values())
                supported_sample_count = len(readings)
                if total_supported_seconds <= 0 or not seconds_by_zone:
                    calculation_status = "limited"
                    dominant_zone_code = None
                    dominant_zone_share = None
                    calculation_notes = json.dumps(["no_bucketed_samples"], ensure_ascii=True)
                    bucket_rows = []
                else:
                    calculation_status = "calculated"
                    dominant_zone_code = max(seconds_by_zone, key=seconds_by_zone.get)
                    dominant_zone_share = round(seconds_by_zone[dominant_zone_code] / total_supported_seconds, 4)
                    calculation_notes = None
                    bucket_rows = []
                    for zone_code, seconds_in_zone in sorted(seconds_by_zone.items(), key=lambda item: zone_order[item[0]]):
                        bucket_rows.append(
                            (
                                zone_order[zone_code],
                                zone_code,
                                seconds_in_zone,
                                round(seconds_in_zone / total_supported_seconds, 4),
                                sample_counts_by_zone[zone_code],
                            )
                        )

        connection.execute(
            """
            INSERT INTO exec_activity_zone_results (
                activity_id, zone_profile_id, metric_basis, calculation_status, quality_status_snapshot,
                supported_sample_count, total_supported_seconds, dominant_zone_code, dominant_zone_share,
                calculation_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_id, metric_basis, zone_profile_id) DO UPDATE SET
                calculation_status = excluded.calculation_status,
                quality_status_snapshot = excluded.quality_status_snapshot,
                supported_sample_count = excluded.supported_sample_count,
                total_supported_seconds = excluded.total_supported_seconds,
                dominant_zone_code = excluded.dominant_zone_code,
                dominant_zone_share = excluded.dominant_zone_share,
                calculation_notes = excluded.calculation_notes,
                calculated_at = CURRENT_TIMESTAMP
            """,
            (
                activity_row_id,
                active_profile["zone_profile_id"],
                metric_basis,
                calculation_status,
                activity.quality_status,
                supported_sample_count,
                total_supported_seconds,
                dominant_zone_code,
                dominant_zone_share,
                calculation_notes,
            ),
        )
        result_row = connection.execute(
            """
            SELECT activity_zone_result_id
            FROM exec_activity_zone_results
            WHERE activity_id = ? AND metric_basis = ? AND zone_profile_id = ?
            """,
            (activity_row_id, metric_basis, active_profile["zone_profile_id"]),
        ).fetchone()
        if result_row is None:
            raise RuntimeError("No se pudo resolver el resultado de zonas persistido.")
        result_id = int(result_row["activity_zone_result_id"])
        connection.execute("DELETE FROM exec_activity_zone_buckets WHERE activity_zone_result_id = ?", (result_id,))
        for zone_index, zone_code, seconds_in_zone, share_in_zone, sample_count in bucket_rows:
            connection.execute(
                """
                INSERT INTO exec_activity_zone_buckets (
                    activity_zone_result_id, zone_index, zone_code, seconds_in_zone, share_in_zone, sample_count
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (result_id, zone_index, zone_code, seconds_in_zone, share_in_zone, sample_count),
            )