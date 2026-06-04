#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from statistics import mean
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = REPO_ROOT / "Sistema" / "training.sqlite"

CYCLING_DISCIPLINES = {
    "cycling",
    "bike",
    "road_biking",
    "gravel_cycling",
    "mountain_biking",
    "virtual_ride",
    "indoor_cycling",
}

RUNNING_DISCIPLINES = {
    "running",
    "trail_running",
    "track_running",
    "treadmill_running",
}

WALKING_DISCIPLINES = {
    "walking",
    "hiking",
    "trail_walking",
    "nordic_walking",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute a compact activity-metric analysis block from stored activity data.")
    parser.add_argument("--activity-id", required=True, type=int, help="Activity id to analyze")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    return parser.parse_args()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def fetch_one(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    return row_to_dict(connection.execute(query, params).fetchone())


def fetch_all(connection: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in connection.execute(query, params).fetchall() if row is not None]


def load_activity_context(connection: sqlite3.Connection, activity_id: int) -> dict[str, Any]:
    activity = fetch_one(
        connection,
        """
        SELECT ea.activity_id, ea.activity_date, ea.started_at, ea.discipline, ea.activity_type,
               ea.duration_seconds, ea.avg_hr, ea.max_hr, ea.avg_power, ea.normalized_power,
               ea.avg_pace_seconds_per_km, ea.training_load, ea.quality_status,
               ea.quality_decision_count, ea.quality_limited_metric_count,
               l.planned_session_id,
               ps.primary_session, ps.objective, ps.duration_min, ps.duration_max,
               ps.intensity_class,
               zt.target_basis, zt.target_kind, zt.source_text
        FROM exec_activities ea
        LEFT JOIN link_plan_execution l ON l.activity_id = ea.activity_id
        LEFT JOIN plan_planned_sessions ps ON ps.planned_session_id = l.planned_session_id
        LEFT JOIN plan_session_zone_targets zt ON zt.planned_session_id = ps.planned_session_id
        WHERE ea.activity_id = ?
        ORDER BY l.link_id DESC
        LIMIT 1
        """,
        (activity_id,),
    )
    if activity is None:
        raise ValueError(f"Activity {activity_id} not found")
    return activity


def load_metric_summaries(connection: sqlite3.Connection, activity_id: int) -> dict[tuple[str, str], dict[str, Any]]:
    rows = fetch_all(
        connection,
        """
        SELECT metric_name, summary_kind, trusted_value, summary_status
        FROM exec_activity_metric_summaries
        WHERE activity_id = ?
        """,
        (activity_id,),
    )
    return {(str(row["metric_name"]), str(row["summary_kind"])): row for row in rows}


def load_metric_readings(connection: sqlite3.Connection, activity_id: int, metric_name: str) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT sample_index, raw_value, elapsed_seconds
        FROM exec_activity_metric_readings
        WHERE activity_id = ? AND metric_name = ?
        ORDER BY sample_index
        """,
        (activity_id, metric_name),
    )


RUNNING_DYNAMICS_METRICS = (
    "cadence_double",
    "run_cadence",
    "ground_contact_time",
    "ground_contact_balance_left",
    "vertical_oscillation",
    "vertical_ratio",
    "stride_length",
    "performance_condition",
)


def get_summary_value(
    summaries: dict[tuple[str, str], dict[str, Any]], metric_name: str, summary_kind: str = "average"
) -> float | None:
    row = summaries.get((metric_name, summary_kind))
    if not row:
        return None
    trusted_value = row.get("trusted_value")
    if trusted_value in (None, 0):
        return None
    normalized_value = float(trusted_value)
    if metric_name == "stride_length" and normalized_value > 10:
        normalized_value /= 100.0
    return normalized_value


def build_running_dynamics_summary(
    activity: dict[str, Any], summaries: dict[tuple[str, str], dict[str, Any]]
) -> dict[str, Any] | None:
    discipline = str(activity.get("discipline") or "").lower()
    if discipline not in RUNNING_DISCIPLINES:
        return None

    values = {metric_name: get_summary_value(summaries, metric_name) for metric_name in RUNNING_DYNAMICS_METRICS}
    available = {metric_name: value for metric_name, value in values.items() if value is not None}
    if not available:
        return None

    cadence_double = values.get("cadence_double")
    run_cadence = values.get("run_cadence")
    total_cadence = cadence_double if cadence_double is not None else (run_cadence * 2 if run_cadence is not None else None)
    ground_contact_time = values.get("ground_contact_time")
    balance_left = values.get("ground_contact_balance_left")
    vertical_ratio = values.get("vertical_ratio")
    stride_length = values.get("stride_length")
    performance_condition = values.get("performance_condition")

    notes: list[str] = []
    flags: list[str] = []

    if total_cadence is not None:
        if total_cadence < 160:
            notes.append(f"Cadence {total_cadence:.1f} spm suggests a relatively slow turnover for running.")
        elif total_cadence <= 180:
            notes.append(f"Cadence {total_cadence:.1f} spm sits in a functional aerobic range.")
        else:
            notes.append(f"Cadence {total_cadence:.1f} spm is high and compatible with quick support.")

    if ground_contact_time is not None:
        if ground_contact_time > 300:
            flags.append("contact_long")
            notes.append(f"Ground contact time {ground_contact_time:.0f} ms looks long and may reflect heavier support.")
        elif ground_contact_time < 250:
            notes.append(f"Ground contact time {ground_contact_time:.0f} ms stays short.")

    if balance_left is not None:
        asymmetry = abs(balance_left - 50)
        if asymmetry > 2:
            flags.append("contact_asymmetry")
            notes.append(f"Ground contact balance shows {asymmetry:.1f}% left-right asymmetry.")
        elif asymmetry <= 1:
            notes.append("Ground contact balance is very even.")

    if vertical_ratio is not None:
        if vertical_ratio > 10:
            flags.append("bounce_high")
            notes.append(f"Vertical ratio {vertical_ratio:.1f}% is relatively high for the forward speed generated.")
        elif vertical_ratio < 8.5:
            notes.append(f"Vertical ratio {vertical_ratio:.1f}% keeps bounce contained.")

    if stride_length is not None:
        notes.append(f"Stride length averaged {stride_length:.2f} m.")

    if performance_condition is not None:
        if performance_condition <= -3:
            flags.append("performance_condition_low")
            notes.append(f"Performance condition {performance_condition:.1f} points to a negative freshness signal.")
        elif performance_condition >= 2:
            notes.append(f"Performance condition {performance_condition:.1f} points to a positive freshness signal.")

    full_block_metrics = (
        "ground_contact_time",
        "ground_contact_balance_left",
        "vertical_oscillation",
        "vertical_ratio",
        "stride_length",
    )
    full_block_available = sum(1 for metric_name in full_block_metrics if values.get(metric_name) is not None)
    status = "partial" if full_block_available < len(full_block_metrics) else "available"
    if status == "partial":
        notes.append("Garmin did not expose the full running dynamics block for this activity.")

    return {
        "status": status,
        "available_metric_count": len(available),
        "metrics": available,
        "flags": flags,
        "notes": notes,
    }


def load_zone_results(connection: sqlite3.Connection, activity_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT metric_basis, calculation_status, dominant_zone_code, dominant_zone_share, total_supported_seconds
        FROM exec_activity_zone_results
        WHERE activity_id = ?
        ORDER BY metric_basis
        """,
        (activity_id,),
    )


def first_second_half_means(values: list[float]) -> tuple[float | None, float | None]:
    if len(values) < 8:
        return None, None
    midpoint = len(values) // 2
    first_half = values[:midpoint]
    second_half = values[midpoint:]
    if not first_half or not second_half:
        return None, None
    return mean(first_half), mean(second_half)


def bucket_mean_values(readings: list[dict[str, Any]], bucket_seconds: int) -> list[float]:
    buckets: dict[int, list[float]] = {}
    for row in readings:
        raw_value = row.get("raw_value")
        if raw_value in (None, 0):
            continue
        elapsed_seconds = row.get("elapsed_seconds")
        sample_index = row.get("sample_index")
        if elapsed_seconds is None:
            if sample_index is None:
                continue
            elapsed_seconds = int(sample_index)
        bucket_index = max(int(float(elapsed_seconds)) // bucket_seconds, 0)
        buckets.setdefault(bucket_index, []).append(float(raw_value))
    return [mean(values) for _, values in sorted(buckets.items()) if values]


def coefficient_of_variation(values: list[float]) -> float | None:
    if len(values) < 4:
        return None
    avg = mean(values)
    if avg == 0:
        return None
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return (variance ** 0.5) / avg


def extract_target_zone(source_text: str | None) -> str | None:
    if not source_text:
        return None
    match = re.search(r"\bZ(\d+)\b", source_text.upper())
    return f"Z{match.group(1)}" if match else None


def format_pace(seconds_per_km: float | None) -> str | None:
    if seconds_per_km is None or seconds_per_km <= 0:
        return None
    total_seconds = int(round(seconds_per_km))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}/km"


def classify_pacing_stability(activity: dict[str, Any], power_readings: list[dict[str, Any]], hr_readings: list[dict[str, Any]]) -> tuple[str, str]:
    discipline = str(activity.get("discipline") or "").lower()
    power_bucket_seconds = 300 if discipline in CYCLING_DISCIPLINES else 180
    hr_bucket_seconds = 300 if discipline in CYCLING_DISCIPLINES else 180

    power_values = bucket_mean_values(power_readings, power_bucket_seconds)
    hr_values = bucket_mean_values(hr_readings, hr_bucket_seconds)
    basis = power_values if len(power_values) >= 6 else hr_values
    cv = coefficient_of_variation(basis)
    if cv is None:
        return "unavailable", "Insufficient samples for stability classification."

    stable_threshold = 0.12
    mild_threshold = 0.2
    if discipline in CYCLING_DISCIPLINES:
        stable_threshold = 0.18
        mild_threshold = 0.3
    elif discipline in RUNNING_DISCIPLINES:
        stable_threshold = 0.1
        mild_threshold = 0.18

    basis_label = "power" if len(power_values) >= 6 else "heart rate"
    bucket_minutes = power_bucket_seconds // 60 if basis_label == "power" else hr_bucket_seconds // 60
    if cv < stable_threshold:
        return "stable", f"{bucket_minutes}-minute {basis_label} CV {cv:.2f} after smoothing the stream."
    if cv < mild_threshold:
        return "mildly_variable", f"{bucket_minutes}-minute {basis_label} CV {cv:.2f} suggests normal variability for the session type."
    return "highly_variable", f"{bucket_minutes}-minute {basis_label} CV {cv:.2f} still suggests materially spiky execution after smoothing."


def classify_duration_vs_plan(activity: dict[str, Any]) -> tuple[str, int | None]:
    duration_seconds = activity.get("duration_seconds")
    duration_min = round(float(duration_seconds) / 60) if duration_seconds not in (None, 0) else None
    min_plan = activity.get("duration_min")
    max_plan = activity.get("duration_max")
    if duration_min is None or (min_plan is None and max_plan is None):
        return "unknown", None
    if max_plan is not None and duration_min > int(max_plan):
        return "slightly_above", int(duration_min - int(max_plan))
    if min_plan is not None and duration_min < int(min_plan):
        return "slightly_below", int(duration_min - int(min_plan))
    return "on_target", 0


def build_analysis(activity: dict[str, Any], summaries: dict[tuple[str, str], dict[str, Any]], hr_readings: list[dict[str, Any]], power_readings: list[dict[str, Any]], zone_results: list[dict[str, Any]]) -> dict[str, Any]:
    discipline = str(activity.get("discipline") or "").lower()
    is_running = discipline in RUNNING_DISCIPLINES
    is_pace_endurance = discipline in RUNNING_DISCIPLINES or discipline in WALKING_DISCIPLINES
    avg_hr = float(activity["avg_hr"]) if activity.get("avg_hr") not in (None, 0) else None
    max_hr = float(activity["max_hr"]) if activity.get("max_hr") not in (None, 0) else None
    avg_power = float(activity["avg_power"]) if activity.get("avg_power") not in (None, 0) else None
    normalized_power = float(activity["normalized_power"]) if activity.get("normalized_power") not in (None, 0) else None
    avg_pace_seconds_per_km = float(activity["avg_pace_seconds_per_km"]) if activity.get("avg_pace_seconds_per_km") not in (None, 0) else None
    avg_pace_formatted = format_pace(avg_pace_seconds_per_km)

    hr_values = [float(row["raw_value"]) for row in hr_readings if row.get("raw_value") not in (None, 0)]
    power_values = [float(row["raw_value"]) for row in power_readings if row.get("raw_value") not in (None, 0)]

    first_hr, second_hr = first_second_half_means(hr_values)
    first_power, second_power = first_second_half_means(power_values)

    hr_drift_percent = None
    hr_power_decoupling_percent = None
    if first_hr and second_hr:
        hr_drift_percent = round(((second_hr - first_hr) / first_hr) * 100, 2)
    if first_hr and second_hr and first_power and second_power and first_power != 0 and second_power != 0:
        first_ratio = first_hr / first_power
        second_ratio = second_hr / second_power
        hr_power_decoupling_percent = round(((second_ratio - first_ratio) / first_ratio) * 100, 2)

    pacing_status, pacing_evidence = classify_pacing_stability(activity, power_readings, hr_readings)
    late_session_fade = "unclear"
    if first_power and second_power:
        late_session_fade = "yes" if second_power < first_power * 0.95 else "no"

    aerobic_status = "unavailable"
    aerobic_notes = "No credible decoupling metric available."
    if hr_power_decoupling_percent is not None:
        absolute_decoupling = abs(hr_power_decoupling_percent)
        if absolute_decoupling < 5:
            aerobic_status = "good"
        elif absolute_decoupling < 8:
            aerobic_status = "borderline"
        else:
            aerobic_status = "poor"
        aerobic_notes = f"HR-power decoupling {hr_power_decoupling_percent:.2f}% based on first-versus-second half averages."
    elif hr_drift_percent is not None:
        absolute_drift = abs(hr_drift_percent)
        if absolute_drift < 5:
            aerobic_status = "good"
        elif absolute_drift < 8:
            aerobic_status = "borderline"
        else:
            aerobic_status = "poor"
        aerobic_notes = f"HR drift {hr_drift_percent:.2f}% based on first-versus-second half averages."

    duration_status, duration_delta = classify_duration_vs_plan(activity)
    execution_vs_plan = duration_status
    target_zone = extract_target_zone(activity.get("source_text"))
    dominant_hr_zone = next((row.get("dominant_zone_code") for row in zone_results if row.get("metric_basis") == "heart_rate"), None)
    dominant_power_zone = next((row.get("dominant_zone_code") for row in zone_results if row.get("metric_basis") == "power"), None)

    zone_execution = "unavailable"
    zone_execution_notes = "No comparable target zone available."
    if target_zone and dominant_hr_zone:
        if dominant_hr_zone == target_zone:
            zone_execution = "aligned"
        elif abs(int(dominant_hr_zone[1:]) - int(target_zone[1:])) == 1:
            zone_execution = "mostly_aligned"
        else:
            zone_execution = "misaligned"
        zone_execution_notes = f"Target zone {target_zone}; dominant HR zone {dominant_hr_zone}."

    intensity_execution = "unknown"
    if zone_execution == "aligned":
        intensity_execution = "controlled"
    elif zone_execution == "mostly_aligned":
        intensity_execution = "variable"
    elif zone_execution == "misaligned":
        intensity_execution = "too_high" if dominant_hr_zone and target_zone and int(dominant_hr_zone[1:]) > int(target_zone[1:]) else "too_low"

    power_hr_relationship = "unavailable"
    relationship_notes = "Power and HR relationship could not be classified confidently."
    if hr_power_decoupling_percent is not None:
        absolute_decoupling = abs(hr_power_decoupling_percent)
        if absolute_decoupling < 5:
            power_hr_relationship = "aligned"
        else:
            power_hr_relationship = "decoupled"
        relationship_notes = f"Based on HR-power decoupling of {hr_power_decoupling_percent:.2f}%."
    elif is_pace_endurance and avg_pace_formatted and hr_drift_percent is not None:
        absolute_drift = abs(hr_drift_percent)
        if absolute_drift < 5:
            power_hr_relationship = "aligned"
        elif hr_drift_percent > 0:
            power_hr_relationship = "hr_high_for_power"
        else:
            power_hr_relationship = "power_high_for_hr"
        relationship_notes = f"Average pace {avg_pace_formatted} with HR drift {hr_drift_percent:.2f}% across the run."

    efficiency_flags: list[str] = []
    if hr_power_decoupling_percent is not None and abs(hr_power_decoupling_percent) >= 8:
        efficiency_flags.append("cardiac_drift")
    if late_session_fade == "yes":
        efficiency_flags.append("late_fade")
    if pacing_status == "highly_variable":
        efficiency_flags.append("power_spiky")
    if aerobic_status == "good":
        efficiency_flags.append("durability_good")
    if dominant_hr_zone and target_zone and int(dominant_hr_zone[1:]) > int(target_zone[1:]):
        efficiency_flags.append("hr_elevated")

    metric_sources = []
    if hr_values:
        metric_sources.append("heart_rate")
    if power_values:
        metric_sources.append("power")
    elif is_running and avg_pace_formatted:
        metric_sources.append("pace")
    if any(key[0] == "respiration_rate" for key in summaries):
        metric_sources.append("respiration_rate")
    if zone_results:
        metric_sources.append("zones")
    running_dynamics = build_running_dynamics_summary(activity, summaries)
    if running_dynamics is not None:
        metric_sources.append("running_dynamics")

    quality_status = str(activity.get("quality_status") or "unavailable")
    quality_notes = []
    if activity.get("quality_decision_count"):
        quality_notes.append(f"{activity['quality_decision_count']} quality decisions recorded.")
    if activity.get("quality_limited_metric_count"):
        quality_notes.append(f"{activity['quality_limited_metric_count']} metrics were limited by quality filtering.")
    if not quality_notes:
        quality_notes.append("Stored quality status indicates clean usable data.")

    analysis_scope = "power_plus_hr" if hr_values and power_values else "hr_only" if hr_values else "summary_only"
    if is_pace_endurance and hr_values and avg_pace_formatted:
        analysis_scope = "pace_plus_hr"

    plan_alignment_notes = f"Planned intensity {activity.get('intensity_class') or 'unknown'}; planned text: {activity.get('primary_session') or 'n/a'}." if activity.get("planned_session_id") else "No linked planned session."
    if is_pace_endurance and avg_pace_formatted:
        if activity.get("planned_session_id"):
            plan_alignment_notes = f"Planned intensity {activity.get('intensity_class') or 'unknown'}; planned text: {activity.get('primary_session') or 'n/a'}; observed average pace {avg_pace_formatted}."
        else:
            plan_alignment_notes = f"No linked planned session. Observed average pace {avg_pace_formatted}."

    return {
        "activity_id": activity["activity_id"],
        "sport": activity.get("discipline"),
        "analysis_scope": analysis_scope,
        "data_quality": {
            "quality_status": quality_status,
            "quality_notes": quality_notes,
            "metric_sources": metric_sources,
        },
        "execution_vs_plan": execution_vs_plan,
        "duration_vs_plan_minutes": duration_delta,
        "intensity_execution": intensity_execution,
        "plan_alignment_notes": plan_alignment_notes,
        "pacing_stability_status": pacing_status,
        "pacing_stability_evidence": pacing_evidence,
        "late_session_fade": late_session_fade,
        "aerobic_control_status": aerobic_status,
        "hr_drift_percent": hr_drift_percent,
        "hr_power_decoupling_percent": hr_power_decoupling_percent,
        "aerobic_control_notes": aerobic_notes,
        "power_hr_relationship": power_hr_relationship,
        "avg_power": avg_power,
        "normalized_power": normalized_power,
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "avg_pace_seconds_per_km": avg_pace_seconds_per_km,
        "avg_pace_formatted": avg_pace_formatted,
        "relationship_notes": relationship_notes,
        "zone_execution": zone_execution,
        "dominant_hr_zone": dominant_hr_zone,
        "dominant_power_zone": dominant_power_zone,
        "zone_execution_notes": zone_execution_notes,
        "running_dynamics": running_dynamics,
        "efficiency_flags": efficiency_flags,
        "metric_verdict": build_metric_verdict(execution_vs_plan, intensity_execution, aerobic_status, pacing_status, late_session_fade),
        "coaching_implication": build_coaching_implication(execution_vs_plan, aerobic_status, efficiency_flags),
    }


def compute_activity_metric_analysis(connection: sqlite3.Connection, activity_id: int) -> dict[str, Any]:
    activity = load_activity_context(connection, activity_id)
    summaries = load_metric_summaries(connection, activity_id)
    hr_readings = load_metric_readings(connection, activity_id, "heart_rate")
    power_readings = load_metric_readings(connection, activity_id, "power")
    zone_results = load_zone_results(connection, activity_id)
    return build_analysis(activity, summaries, hr_readings, power_readings, zone_results)


def build_metric_verdict(execution_vs_plan: str, intensity_execution: str, aerobic_status: str, pacing_status: str, late_session_fade: str) -> str:
    descriptors: list[str] = []
    if intensity_execution != "unknown":
        descriptors.append(f"{intensity_execution.replace('_', ' ')} intensity")
    if aerobic_status != "unavailable":
        descriptors.append(f"{aerobic_status} aerobic control")
    if pacing_status != "unavailable":
        descriptors.append(f"{pacing_status.replace('_', ' ')} pacing")
    if late_session_fade in {"yes", "no"}:
        descriptors.append("late fade" if late_session_fade == "yes" else "no obvious late fade")

    if execution_vs_plan != "unknown":
        sentence = f"Execution was {execution_vs_plan.replace('_', ' ')}"
        if descriptors:
            sentence += " with " + ", ".join(descriptors)
        return sentence + "."

    if descriptors:
        return "Activity metrics show " + ", ".join(descriptors) + "."
    return "Activity metrics were available but inconclusive."


def build_coaching_implication(execution_vs_plan: str, aerobic_status: str, efficiency_flags: list[str]) -> str:
    if aerobic_status == "poor" or "cardiac_drift" in efficiency_flags:
        return "This session should push the day-level assessment toward caution, because the aerobic control cost was high for the intended work."
    if execution_vs_plan == "on_target" and aerobic_status in {"good", "borderline"}:
        return "This supports reading the session as well-executed aerobic work rather than an intensity mistake."
    if execution_vs_plan == "slightly_above":
        return "This supports a reading of good execution with some load creep, especially if the surrounding days were already dense."
    return "This metric block adds context but does not fully overturn the broader day-level assessment on its own."


def main() -> int:
    args = parse_args()
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    analysis = compute_activity_metric_analysis(connection, args.activity_id)
    print(json.dumps(analysis, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())