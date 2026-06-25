#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import sqlite3
from pathlib import Path
from statistics import mean, median
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

PACE_ENDURANCE_DISCIPLINES = RUNNING_DISCIPLINES | WALKING_DISCIPLINES


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


def load_prescription_target(connection: sqlite3.Connection, planned_session_id: int | None) -> dict[str, Any] | None:
    if planned_session_id is None:
        return None
    rows = fetch_all(
        connection,
        """
        SELECT pb.sequence_order,
               pb.block_role,
               pb.block_name,
               pb.duration_min,
               pb.duration_max,
               pb.target_basis,
               pb.target_zone_min_code,
               pb.target_zone_max_code
        FROM plan_session_prescriptions pr
        JOIN plan_prescription_blocks pb ON pb.prescription_id = pr.prescription_id
        WHERE pr.planned_session_id = ?
        ORDER BY pb.relation_group, pb.sequence_order
        """,
        (planned_session_id,),
    )
    if not rows:
        return None

    targeted_rows = [
        row
        for row in rows
        if row.get("target_basis")
        and row.get("target_zone_min_code")
        and row.get("target_zone_max_code")
    ]
    if not targeted_rows:
        return None

    target_basis = str(targeted_rows[0]["target_basis"])
    zone_pairs = [
        (str(row["target_zone_min_code"]), str(row["target_zone_max_code"]))
        for row in targeted_rows
    ]
    unique_zone_pairs = list(dict.fromkeys(zone_pairs))
    target_kind = "single_zone" if len(unique_zone_pairs) == 1 and unique_zone_pairs[0][0] == unique_zone_pairs[0][1] else "multi_segment"

    return {
        "target_basis": target_basis,
        "target_kind": target_kind,
        "target_zone_min_code": unique_zone_pairs[0][0],
        "target_zone_max_code": unique_zone_pairs[0][1],
    }


def load_activity_context(connection: sqlite3.Connection, activity_id: int) -> dict[str, Any]:
    activity = fetch_one(
        connection,
        """
        SELECT ea.activity_id, ea.activity_date, ea.started_at, ea.discipline, ea.activity_type,
               ea.season_id, ea.duration_seconds, ea.distance_meters, ea.ascent_meters, ea.calories,
               ea.avg_hr, ea.max_hr, ea.avg_power, ea.normalized_power,
               ea.avg_pace_seconds_per_km, ea.training_load, ea.quality_status,
               ea.quality_decision_count, ea.quality_limited_metric_count,
               l.planned_session_id,
             ps.duration_min, ps.duration_max,
               ps.intensity_class,
               pr.title AS prescription_title,
               pr.estimated_duration_min,
               pr.estimated_duration_max
        FROM exec_activities ea
        LEFT JOIN link_plan_execution l ON l.activity_id = ea.activity_id
        LEFT JOIN plan_planned_sessions ps ON ps.planned_session_id = l.planned_session_id
        LEFT JOIN plan_session_prescriptions pr ON pr.planned_session_id = ps.planned_session_id
        WHERE ea.activity_id = ?
        ORDER BY l.link_id DESC
        LIMIT 1
        """,
        (activity_id,),
    )
    if activity is None:
        raise ValueError(f"Activity {activity_id} not found")
    prescription_target = load_prescription_target(connection, int(activity["planned_session_id"])) if activity.get("planned_session_id") is not None else None
    if prescription_target is not None:
        activity.update(prescription_target)
        if activity.get("duration_min") is None and activity.get("estimated_duration_min") is not None:
            activity["duration_min"] = activity.get("estimated_duration_min")
        if activity.get("duration_max") is None and activity.get("estimated_duration_max") is not None:
            activity["duration_max"] = activity.get("estimated_duration_max")
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


def build_reading_index(readings: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for row in readings:
        sample_index = row.get("sample_index")
        if sample_index is None:
            continue
        indexed[int(sample_index)] = row
    return indexed


def derive_vertical_speed_index(elevation_readings: list[dict[str, Any]]) -> dict[int, float]:
    vertical_speed: dict[int, float] = {}
    previous_row: dict[str, Any] | None = None
    for row in elevation_readings:
        sample_index = row.get("sample_index")
        raw_value = row.get("raw_value")
        elapsed_seconds = row.get("elapsed_seconds")
        if sample_index is None or raw_value is None:
            previous_row = row
            continue
        if previous_row is None:
            previous_row = row
            continue
        previous_value = previous_row.get("raw_value")
        previous_elapsed = previous_row.get("elapsed_seconds")
        previous_index = previous_row.get("sample_index")
        if previous_value is None or previous_index is None:
            previous_row = row
            continue
        current_elapsed = float(elapsed_seconds if elapsed_seconds is not None else sample_index)
        prior_elapsed = float(previous_elapsed if previous_elapsed is not None else previous_index)
        delta_seconds = current_elapsed - prior_elapsed
        if delta_seconds > 0:
            vertical_speed[int(sample_index)] = (float(raw_value) - float(previous_value)) / delta_seconds
        previous_row = row
    return vertical_speed


def terrain_multiplier_running(grade: float) -> float:
    clipped_grade = max(min(grade, 0.3), -0.3)
    flat_cost = 3.6
    grade_cost = (
        155.4 * clipped_grade**5
        - 30.4 * clipped_grade**4
        - 43.3 * clipped_grade**3
        + 46.3 * clipped_grade**2
        + 19.5 * clipped_grade
        + flat_cost
    )
    if grade_cost <= 0:
        return 1.0
    return grade_cost / flat_cost


def terrain_multiplier_walking(grade: float) -> float:
    import math

    clipped_grade = max(min(grade, 0.5), -0.5)
    flat_speed = 6.0 * math.exp(-3.5 * abs(0.05))
    graded_speed = 6.0 * math.exp(-3.5 * abs(clipped_grade + 0.05))
    if graded_speed <= 0:
        return 1.0
    return flat_speed / graded_speed


def format_seconds_per_km(seconds_per_km: float | None) -> str | None:
    return format_pace(seconds_per_km)


def build_grade_adjusted_pace_summary(
    activity: dict[str, Any],
    speed_readings: list[dict[str, Any]],
    vertical_speed_readings: list[dict[str, Any]],
    elevation_readings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    discipline = str(activity.get("discipline") or "").lower()
    if discipline not in PACE_ENDURANCE_DISCIPLINES:
        return None

    avg_pace_seconds_per_km = float(activity["avg_pace_seconds_per_km"]) if activity.get("avg_pace_seconds_per_km") not in (None, 0) else None
    if avg_pace_seconds_per_km is None:
        return None

    if discipline in WALKING_DISCIPLINES:
        distance_meters = float(activity["distance_meters"]) if activity.get("distance_meters") not in (None, 0) else None
        ascent_meters = float(activity["ascent_meters"]) if activity.get("ascent_meters") not in (None, 0) else None
        if distance_meters is None or ascent_meters is None or distance_meters <= 0 or ascent_meters <= 0:
            return None
        effective_grade = max(min(ascent_meters / distance_meters, 0.25), 0.0)
        multiplier = terrain_multiplier_walking(effective_grade)
        adjusted_pace = avg_pace_seconds_per_km / multiplier if multiplier > 0 else avg_pace_seconds_per_km
        return {
            "model_key": "walking_tobler_adjustment",
            "actual_pace_seconds_per_km": round(avg_pace_seconds_per_km, 2),
            "actual_pace_formatted": format_seconds_per_km(avg_pace_seconds_per_km),
            "grade_adjusted_pace_seconds_per_km": round(adjusted_pace, 2),
            "grade_adjusted_pace_formatted": format_seconds_per_km(adjusted_pace),
            "adjustment_seconds_per_km": round(adjusted_pace - avg_pace_seconds_per_km, 2),
        }

    if len(speed_readings) < 10:
        return None

    vertical_speed_index = {
        int(key): float(value["raw_value"])
        for key, value in build_reading_index(vertical_speed_readings).items()
        if value.get("raw_value") is not None
    }
    if not vertical_speed_index and elevation_readings:
        vertical_speed_index = derive_vertical_speed_index(elevation_readings)

    weighted_actual_speed = 0.0
    weighted_adjusted_speed = 0.0
    total_seconds = 0.0
    actual_samples = [row for row in speed_readings if row.get("raw_value") not in (None, 0)]
    if len(actual_samples) < 10:
        return None

    elapsed_values = []
    for row in actual_samples:
        elapsed_seconds = row.get("elapsed_seconds")
        sample_index = row.get("sample_index")
        elapsed_values.append(float(elapsed_seconds if elapsed_seconds is not None else sample_index))
    actual_values = elapsed_values
    intervals = [
        max(actual_values[index + 1] - actual_values[index], 0.0)
        for index in range(len(actual_values) - 1)
        if actual_values[index + 1] >= actual_values[index]
    ]
    default_interval = median(intervals) if intervals else 1.0

    for index, row in enumerate(actual_samples):
        speed = float(row["raw_value"])
        sample_index = int(row.get("sample_index") or 0)
        interval = default_interval
        if index < len(actual_samples) - 1:
            interval = max(elapsed_values[index + 1] - elapsed_values[index], 0.0) or default_interval
        if speed <= 0.2:
            continue
        vertical_speed = vertical_speed_index.get(sample_index, 0.0)
        grade = max(min(vertical_speed / speed, 0.3), -0.3)
        multiplier = terrain_multiplier_running(grade)
        adjusted_speed = speed * multiplier
        weighted_actual_speed += speed * interval
        weighted_adjusted_speed += adjusted_speed * interval
        total_seconds += interval

    if total_seconds <= 0 or weighted_actual_speed <= 0 or weighted_adjusted_speed <= 0:
        return None

    adjustment_ratio = (weighted_adjusted_speed / total_seconds) / (weighted_actual_speed / total_seconds)
    if adjustment_ratio <= 0:
        return None
    adjusted_pace = avg_pace_seconds_per_km / adjustment_ratio
    return {
        "model_key": "running_grade_cost_model",
        "actual_pace_seconds_per_km": round(avg_pace_seconds_per_km, 2),
        "actual_pace_formatted": format_seconds_per_km(avg_pace_seconds_per_km),
        "grade_adjusted_pace_seconds_per_km": round(adjusted_pace, 2),
        "grade_adjusted_pace_formatted": format_seconds_per_km(adjusted_pace),
        "adjustment_seconds_per_km": round(adjusted_pace - avg_pace_seconds_per_km, 2),
    }


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


def build_performance_condition_signal(
    summaries: dict[tuple[str, str], dict[str, Any]]
) -> dict[str, Any] | None:
    average_value = get_summary_value(summaries, "performance_condition", "average")
    minimum_value = get_summary_value(summaries, "performance_condition", "minimum")
    maximum_value = get_summary_value(summaries, "performance_condition", "maximum")
    if average_value is None and minimum_value is None and maximum_value is None:
        return None

    status = "neutral"
    notes: list[str] = []
    if average_value is not None:
        if average_value >= 2:
            status = "positive"
            notes.append(f"Average performance condition {average_value:.1f} points to a positive in-session freshness signal.")
        elif average_value <= -2:
            status = "negative"
            notes.append(f"Average performance condition {average_value:.1f} points to a negative in-session freshness signal.")
        else:
            notes.append(f"Average performance condition {average_value:.1f} was broadly neutral.")

    if minimum_value is not None and maximum_value is not None and minimum_value <= -3 and maximum_value >= 2:
        status = "mixed"
        notes.append(
            f"The signal ranged from {minimum_value:.1f} to {maximum_value:.1f}, so freshness moved meaningfully during the activity."
        )
    elif maximum_value is not None and average_value is not None and maximum_value - average_value >= 3:
        notes.append(f"Peak performance condition reached {maximum_value:.1f} despite a lower average signal.")
    elif minimum_value is not None and average_value is not None and average_value - minimum_value >= 3:
        notes.append(f"Lowest performance condition reached {minimum_value:.1f} despite a higher average signal.")

    return {
        "status": status,
        "average": round_or_none(average_value, 2),
        "minimum": round_or_none(minimum_value, 2),
        "maximum": round_or_none(maximum_value, 2),
        "notes": notes,
    }


def describe_performance_condition_level(value: float | None) -> str:
    if value is None:
        return "unavailable"
    if value <= -1.5:
        return "negative"
    if value < 0.5:
        return "neutral"
    if value < 1.5:
        return "mildly positive"
    return "clearly positive"


def build_performance_condition_evolution(
    readings: list[dict[str, Any]],
    signal: dict[str, Any] | None,
) -> str | None:
    valid_rows = [row for row in readings if row.get("raw_value") is not None]
    if len(valid_rows) < 6:
        if signal is None:
            return None
        status = signal.get("status") or "neutral"
        average = signal.get("average")
        if average is not None:
            return f"Performance Condition was {status} overall, averaging {average:.1f}."
        return f"Performance Condition was {status} overall."

    elapsed_values = [float(row.get("elapsed_seconds") if row.get("elapsed_seconds") is not None else row.get("sample_index") or 0) for row in valid_rows]
    total_elapsed = max(elapsed_values) if elapsed_values else 0.0
    if total_elapsed <= 0:
        total_elapsed = float(len(valid_rows))

    phase_labels = ("early", "middle", "late")
    phase_values: dict[str, list[float]] = {label: [] for label in phase_labels}
    for row, elapsed_seconds in zip(valid_rows, elapsed_values):
        fraction = elapsed_seconds / total_elapsed if total_elapsed > 0 else 0.0
        if fraction < 1 / 3:
            phase_values["early"].append(float(row["raw_value"]))
        elif fraction < 2 / 3:
            phase_values["middle"].append(float(row["raw_value"]))
        else:
            phase_values["late"].append(float(row["raw_value"]))

    phase_means = {
        label: (round(mean(values), 2) if values else None)
        for label, values in phase_values.items()
    }
    early_mean = phase_means["early"]
    middle_mean = phase_means["middle"]
    late_mean = phase_means["late"]
    maximum = signal.get("maximum") if signal is not None else None
    minimum = signal.get("minimum") if signal is not None else None

    sentences: list[str] = []
    if early_mean is not None and middle_mean is not None and late_mean is not None:
        sentences.append(
            "Performance Condition opened "
            f"{describe_performance_condition_level(early_mean)} in the early phase ({early_mean:.1f}), "
            f"moved to {describe_performance_condition_level(middle_mean)} through the middle phase ({middle_mean:.1f}), "
            f"and finished {describe_performance_condition_level(late_mean)} late ({late_mean:.1f})."
        )

    if early_mean is not None and middle_mean is not None and late_mean is not None:
        if early_mean < 0 and middle_mean >= 1.5 and late_mean >= 0.5:
            sentences.append(
                "This pattern usually means the athlete was not especially sharp at the start, then settled well into the work and held a manageable internal cost without a late collapse."
            )
        elif early_mean >= 1.5 and late_mean < 0.5:
            sentences.append(
                "This pattern points to a strong start that faded back toward neutral late, which is more compatible with accumulating internal cost than with durable freshness."
            )
        elif middle_mean >= 1.5 and late_mean >= 1.0:
            sentences.append(
                "This pattern supports reading the session as internally manageable once underway, with freshness staying positive through most of the useful work."
            )
        elif late_mean < 0:
            sentences.append(
                "This pattern is more cautionary because the signal faded into negative territory late in the activity."
            )
        else:
            sentences.append(
                "This pattern looks mostly neutral, so Performance Condition adds context but does not materially change the broader execution read."
            )

    if minimum is not None and maximum is not None and maximum - minimum >= 4:
        sentences.append(
            f"The full range from {minimum:.1f} to {maximum:.1f} was wide enough that the signal should be read as a trajectory, not as one fixed readiness score."
        )

    return " ".join(sentences) if sentences else None


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
        SELECT activity_zone_result_id, metric_basis, calculation_status, dominant_zone_code, dominant_zone_share, total_supported_seconds
        FROM exec_activity_zone_results
        WHERE activity_id = ?
        ORDER BY metric_basis
        """,
        (activity_id,),
    )


def load_zone_buckets(connection: sqlite3.Connection, activity_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        connection,
        """
        SELECT azr.metric_basis, azb.zone_code, azb.zone_index, azb.seconds_in_zone, azb.share_in_zone
        FROM exec_activity_zone_results azr
        JOIN exec_activity_zone_buckets azb ON azb.activity_zone_result_id = azr.activity_zone_result_id
        WHERE azr.activity_id = ?
        ORDER BY azr.metric_basis, azb.zone_index
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


def extract_target_zone(activity: dict[str, Any]) -> str | None:
    zone_min = activity.get("target_zone_min_code")
    zone_max = activity.get("target_zone_max_code")
    if not zone_min:
        return None
    return str(zone_min if zone_min == zone_max or zone_max in (None, "") else zone_min)


def format_planned_target(activity: dict[str, Any]) -> str | None:
    zone_min = activity.get("target_zone_min_code")
    zone_max = activity.get("target_zone_max_code")
    duration_min = activity.get("duration_min")
    duration_max = activity.get("duration_max")
    parts: list[str] = []

    if activity.get("target_basis"):
        parts.append(f"base {activity['target_basis']}")
    if zone_min:
        zone_label = str(zone_min) if zone_min == zone_max or zone_max in (None, "") else f"{zone_min}-{zone_max}"
        parts.append(f"zona {zone_label}")
    if duration_min is not None and duration_max is not None:
        duration_label = f"{duration_min}-{duration_max} min" if duration_min != duration_max else f"{duration_min} min"
        parts.append(f"duracion {duration_label}")
    elif duration_min is not None:
        parts.append(f"duracion {duration_min} min")

    return "; ".join(parts) or None


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


def round_or_none(value: float | int | None, digits: int = 1) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def build_segment_analysis(connection: sqlite3.Connection, activity: dict[str, Any]) -> dict[str, Any] | None:
    efforts = fetch_all(
        connection,
        """
        SELECT se.segment_effort_id,
               se.segment_id,
               se.activity_id,
               se.activity_date,
               se.elapsed_time_seconds,
               se.avg_power,
               se.avg_heart_rate,
               s.segment_name,
               s.discipline,
               s.distance_meters,
               s.ascent_meters,
               s.average_grade_percent
        FROM exec_segment_efforts se
        JOIN exec_segments s ON s.segment_id = se.segment_id
        WHERE se.activity_id = ?
        ORDER BY se.started_at, se.segment_effort_id
        """,
        (activity["activity_id"],),
    )
    if not efforts:
        return None

    segment_items: list[dict[str, Any]] = []
    for effort in efforts:
        history = fetch_all(
            connection,
            """
            SELECT segment_effort_id,
                   activity_id,
                   activity_date,
                   elapsed_time_seconds,
                   avg_power,
                   avg_heart_rate
            FROM exec_segment_efforts
            WHERE segment_id = ?
              AND activity_id != ?
              AND elapsed_time_seconds IS NOT NULL
              AND (
                    activity_date < ?
                 OR (activity_date = ? AND segment_effort_id < ?)
              )
            ORDER BY activity_date DESC, segment_effort_id DESC
            LIMIT 5
            """,
            (
                effort["segment_id"],
                activity["activity_id"],
                activity["activity_date"],
                activity["activity_date"],
                effort["segment_effort_id"],
            ),
        )
        comparable_history = [row for row in history if row.get("elapsed_time_seconds") is not None]
        latest_previous = comparable_history[0] if comparable_history else None
        best_previous = min(comparable_history, key=lambda row: float(row["elapsed_time_seconds"])) if comparable_history else None

        elapsed_time_seconds = effort.get("elapsed_time_seconds")
        delta_vs_previous = None
        delta_vs_best = None
        trend_status = "first_recorded_effort"
        if elapsed_time_seconds is not None and latest_previous and latest_previous.get("elapsed_time_seconds") is not None:
            delta_vs_previous = int(float(elapsed_time_seconds) - float(latest_previous["elapsed_time_seconds"]))
            if delta_vs_previous < 0:
                trend_status = "improved_vs_previous"
            elif delta_vs_previous > 0:
                trend_status = "slower_vs_previous"
            else:
                trend_status = "matched_previous"
        if elapsed_time_seconds is not None and best_previous and best_previous.get("elapsed_time_seconds") is not None:
            delta_vs_best = int(float(elapsed_time_seconds) - float(best_previous["elapsed_time_seconds"]))

        segment_items.append(
            {
                "segment_id": effort["segment_id"],
                "segment_name": effort.get("segment_name") or f"Segment {effort['segment_id']}",
                "discipline": effort.get("discipline"),
                "distance_meters": round_or_none(effort.get("distance_meters"), 0),
                "ascent_meters": round_or_none(effort.get("ascent_meters"), 0),
                "average_grade_percent": round_or_none(effort.get("average_grade_percent"), 1),
                "elapsed_time_seconds": elapsed_time_seconds,
                "avg_power": round_or_none(effort.get("avg_power"), 1),
                "avg_heart_rate": round_or_none(effort.get("avg_heart_rate"), 1),
                "history_sample_count": len(comparable_history),
                "delta_vs_previous_seconds": delta_vs_previous,
                "delta_vs_best_seconds": delta_vs_best,
                "trend_status": trend_status,
            }
        )

    comparable_count = sum(1 for item in segment_items if item["history_sample_count"] > 0)
    return {
        "segment_count": len(segment_items),
        "comparable_segment_count": comparable_count,
        "highlights": segment_items,
    }


def load_recent_comparable_activities(connection: sqlite3.Connection, activity: dict[str, Any]) -> list[dict[str, Any]]:
    discipline = activity.get("discipline")
    season_id = activity.get("season_id")
    activity_date = activity.get("activity_date")
    if discipline is None or season_id is None or activity_date is None:
        return []

    current_duration_seconds = float(activity.get("duration_seconds") or 0)
    lower_bound = int(max(current_duration_seconds * 0.6, current_duration_seconds - 45 * 60)) if current_duration_seconds else 0
    upper_bound = int(max(current_duration_seconds * 1.4, current_duration_seconds + 45 * 60)) if current_duration_seconds else 24 * 60 * 60
    lookback_start = (date.fromisoformat(str(activity_date)) - timedelta(days=42)).isoformat()

    return fetch_all(
        connection,
        """
        SELECT ea.activity_id,
               ea.activity_date,
               ea.discipline,
               ea.duration_seconds,
               ea.distance_meters,
               ea.ascent_meters,
               ea.avg_hr,
               ea.avg_power,
               ea.normalized_power,
               ea.avg_pace_seconds_per_km,
               ea.training_load,
               (
                   SELECT ms.trusted_value
                   FROM exec_activity_metric_summaries ms
                   WHERE ms.activity_id = ea.activity_id
                     AND ms.metric_name = 'respiration_rate'
                     AND ms.summary_kind = 'average'
                   LIMIT 1
               ) AS avg_respiration_rate
        FROM exec_activities ea
        WHERE ea.season_id = ?
          AND ea.discipline = ?
          AND ea.activity_id != ?
          AND ea.activity_date >= ?
          AND ea.activity_date <= ?
          AND ea.duration_seconds BETWEEN ? AND ?
        ORDER BY ea.activity_date DESC, ea.started_at DESC, ea.activity_id DESC
        LIMIT 5
        """,
        (season_id, discipline, activity["activity_id"], lookback_start, activity_date, lower_bound, upper_bound),
    )


def summarize_comparison(current_value: float | int | None, recent_values: list[float], digits: int = 1) -> dict[str, Any] | None:
    if current_value is None or not recent_values:
        return None
    recent_average = mean(recent_values)
    delta = float(current_value) - recent_average
    percent_delta = None if recent_average == 0 else round((delta / recent_average) * 100, 1)
    return {
        "current": round_or_none(float(current_value), digits),
        "recent_average": round_or_none(recent_average, digits),
        "delta": round_or_none(delta, digits),
        "percent_delta": percent_delta,
    }


def build_recent_comparison(activity: dict[str, Any], recent_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not recent_rows:
        return None

    comparison: dict[str, Any] = {
        "matching_basis": "same_discipline_recent_duration_band",
        "sample_count": len(recent_rows),
        "window_start_date": recent_rows[-1].get("activity_date"),
        "window_end_date": recent_rows[0].get("activity_date"),
        "similar_activities": [],
        "current_vs_recent": {},
    }

    metric_names = (
        "duration_seconds",
        "avg_hr",
        "avg_power",
        "normalized_power",
        "avg_pace_seconds_per_km",
        "training_load",
    )
    for metric_name in metric_names:
        comparable_values = [float(row[metric_name]) for row in recent_rows if row.get(metric_name) not in (None, 0)]
        current_value = activity.get(metric_name)
        summary = summarize_comparison(current_value, comparable_values)
        if summary is not None:
            comparison["current_vs_recent"][metric_name] = summary

    for row in recent_rows[:3]:
        comparison["similar_activities"].append(
            {
                "activity_id": row["activity_id"],
                "activity_date": row.get("activity_date"),
                "duration_minutes": round_or_none((row.get("duration_seconds") or 0) / 60, 1),
                "avg_hr": round_or_none(row.get("avg_hr"), 1),
                "avg_power": round_or_none(row.get("avg_power"), 1),
                "normalized_power": round_or_none(row.get("normalized_power"), 1),
                "training_load": round_or_none(row.get("training_load"), 1),
            }
        )

    return comparison


def estimate_low_output_share(readings: list[dict[str, Any]], threshold: float) -> tuple[float | None, float | None]:
    valid_readings = [row for row in readings if row.get("raw_value") is not None]
    if len(valid_readings) < 10:
        return None, None

    elapsed_values: list[float] = []
    for row in valid_readings:
        elapsed_seconds = row.get("elapsed_seconds")
        sample_index = row.get("sample_index")
        if elapsed_seconds is None and sample_index is None:
            elapsed_values.append(float(len(elapsed_values)))
        else:
            elapsed_values.append(float(elapsed_seconds if elapsed_seconds is not None else sample_index))

    intervals = [
        max(elapsed_values[index + 1] - elapsed_values[index], 0.0)
        for index in range(len(elapsed_values) - 1)
        if elapsed_values[index + 1] >= elapsed_values[index]
    ]
    default_interval = median(intervals) if intervals else 1.0

    total_seconds = 0.0
    low_output_seconds = 0.0
    for index, row in enumerate(valid_readings):
        interval = default_interval
        if index < len(valid_readings) - 1:
            interval = max(elapsed_values[index + 1] - elapsed_values[index], 0.0) or default_interval
        total_seconds += interval
        if float(row["raw_value"]) <= threshold:
            low_output_seconds += interval

    if total_seconds <= 0:
        return None, None
    return low_output_seconds, low_output_seconds / total_seconds


def build_activity_efficiency(
    activity: dict[str, Any],
    summaries: dict[tuple[str, str], dict[str, Any]],
    power_readings: list[dict[str, Any]],
    zone_buckets: list[dict[str, Any]],
    recent_rows: list[dict[str, Any]],
    grade_adjusted_pace: dict[str, Any] | None,
) -> dict[str, Any] | None:
    avg_hr = float(activity["avg_hr"]) if activity.get("avg_hr") not in (None, 0) else None
    avg_power = float(activity["avg_power"]) if activity.get("avg_power") not in (None, 0) else None
    normalized_power = float(activity["normalized_power"]) if activity.get("normalized_power") not in (None, 0) else None
    duration_seconds = float(activity.get("duration_seconds") or 0)
    training_load = float(activity["training_load"]) if activity.get("training_load") not in (None, 0) else None
    ascent_meters = float(activity["ascent_meters"]) if activity.get("ascent_meters") not in (None, 0) else None
    avg_respiration_rate = get_summary_value(summaries, "respiration_rate")
    target_zone = extract_target_zone(activity)
    target_basis = activity.get("target_basis")
    avg_pace_seconds_per_km = float(activity["avg_pace_seconds_per_km"]) if activity.get("avg_pace_seconds_per_km") not in (None, 0) else None
    discipline = str(activity.get("discipline") or "").lower()

    efficiency: dict[str, Any] = {}

    efficiency_factor_value = None
    efficiency_factor_basis = None
    if normalized_power is not None and avg_hr is not None and avg_hr > 0:
        efficiency_factor_value = normalized_power / avg_hr
        efficiency_factor_basis = "normalized_power_per_avg_hr"
    elif avg_power is not None and avg_hr is not None and avg_hr > 0:
        efficiency_factor_value = avg_power / avg_hr
        efficiency_factor_basis = "avg_power_per_avg_hr"
    elif avg_pace_seconds_per_km is not None and avg_hr is not None and avg_hr > 0:
        effective_pace = grade_adjusted_pace.get("grade_adjusted_pace_seconds_per_km") if grade_adjusted_pace else avg_pace_seconds_per_km
        if effective_pace not in (None, 0):
            effective_speed = 1000.0 / float(effective_pace)
            efficiency_factor_value = effective_speed / avg_hr
            efficiency_factor_basis = "grade_adjusted_speed_per_avg_hr" if grade_adjusted_pace else "speed_per_avg_hr"

    if efficiency_factor_value is not None and efficiency_factor_basis is not None:
        recent_efficiency_values: list[float] = []
        for row in recent_rows:
            row_avg_hr = row.get("avg_hr")
            if row_avg_hr in (None, 0):
                continue
            if efficiency_factor_basis == "normalized_power_per_avg_hr" and row.get("normalized_power") not in (None, 0):
                recent_efficiency_values.append(float(row["normalized_power"]) / float(row_avg_hr))
            elif efficiency_factor_basis == "avg_power_per_avg_hr" and row.get("avg_power") not in (None, 0):
                recent_efficiency_values.append(float(row["avg_power"]) / float(row_avg_hr))
        comparison = summarize_comparison(efficiency_factor_value, recent_efficiency_values, digits=3)
        efficiency["efficiency_factor"] = {
            "basis": efficiency_factor_basis,
            **(comparison or {"current": round_or_none(efficiency_factor_value, 3)}),
        }

    if normalized_power is not None and avg_power is not None and avg_power > 0:
        variability_index = normalized_power / avg_power
        recent_variability_values = [
            float(row["normalized_power"]) / float(row["avg_power"])
            for row in recent_rows
            if row.get("normalized_power") not in (None, 0) and row.get("avg_power") not in (None, 0)
        ]
        comparison = summarize_comparison(variability_index, recent_variability_values, digits=3)
        status = "smooth" if variability_index <= 1.08 else "moderately_variable" if variability_index <= 1.15 else "spiky"
        efficiency["variability_index"] = {
            "status": status,
            **(comparison or {"current": round_or_none(variability_index, 3)}),
        }

    if grade_adjusted_pace is not None:
        efficiency["grade_adjusted_pace"] = grade_adjusted_pace

    zone_basis = target_basis if target_basis else ("heart_rate" if any(row.get("metric_basis") == "heart_rate" for row in zone_buckets) else None)
    matching_zone_rows = [row for row in zone_buckets if row.get("metric_basis") == zone_basis] if zone_basis else []
    if target_zone and matching_zone_rows:
        target_index = int(target_zone[1:])
        total_seconds = sum(int(row.get("seconds_in_zone") or 0) for row in matching_zone_rows)
        if total_seconds > 0:
            in_target_seconds = sum(int(row.get("seconds_in_zone") or 0) for row in matching_zone_rows if row.get("zone_code") == target_zone)
            above_target_seconds = sum(int(row.get("seconds_in_zone") or 0) for row in matching_zone_rows if int(str(row.get("zone_code") or "Z0")[1:]) > target_index)
            below_target_seconds = sum(int(row.get("seconds_in_zone") or 0) for row in matching_zone_rows if int(str(row.get("zone_code") or "Z0")[1:]) < target_index)
            in_target_share = in_target_seconds / total_seconds
            above_target_share = above_target_seconds / total_seconds
            below_target_share = below_target_seconds / total_seconds
            status = "tight" if in_target_share >= 0.75 and above_target_share <= 0.1 else "acceptable" if in_target_share >= 0.6 and above_target_share <= 0.2 else "loose"
            efficiency["target_zone_compliance"] = {
                "metric_basis": zone_basis,
                "target_zone": target_zone,
                "time_in_target_seconds": in_target_seconds,
                "time_in_target_share": round(in_target_share, 4),
                "time_above_target_seconds": above_target_seconds,
                "time_above_target_share": round(above_target_share, 4),
                "time_below_target_seconds": below_target_seconds,
                "time_below_target_share": round(below_target_share, 4),
                "status": status,
            }

    if training_load is not None and duration_seconds > 0:
        load_density = training_load / (duration_seconds / 3600.0)
        recent_density_values = [
            float(row["training_load"]) / (float(row["duration_seconds"]) / 3600.0)
            for row in recent_rows
            if row.get("training_load") not in (None, 0) and row.get("duration_seconds") not in (None, 0)
        ]
        comparison = summarize_comparison(load_density, recent_density_values, digits=1)
        efficiency["load_density"] = {
            "basis": "garmin_training_load_per_hour",
            **(comparison or {"current": round_or_none(load_density, 1)}),
        }

    low_output_seconds, low_output_share = estimate_low_output_share(power_readings, threshold=5.0)
    if low_output_share is not None:
        status = "minimal" if low_output_share <= 0.1 else "moderate" if low_output_share <= 0.2 else "high"
        efficiency["coasting_or_low_output_share"] = {
            "threshold_watts": 5.0,
            "low_output_seconds": round_or_none(low_output_seconds, 1),
            "share": round(low_output_share, 4),
            "status": status,
        }

    if ascent_meters is not None and ascent_meters >= 150 and duration_seconds > 0:
        vertical_rate = ascent_meters / (duration_seconds / 3600.0)
        recent_vertical_rates = [
            float(row["ascent_meters"]) / (float(row["duration_seconds"]) / 3600.0)
            for row in recent_rows
            if row.get("ascent_meters") not in (None, 0) and row.get("duration_seconds") not in (None, 0)
        ]
        climbing_efficiency: dict[str, Any] = {
            "ascent_meters": round_or_none(ascent_meters, 1),
            "vertical_rate_m_per_hour": summarize_comparison(vertical_rate, recent_vertical_rates, digits=1) or {"current": round_or_none(vertical_rate, 1)},
        }
        distance_meters = float(activity["distance_meters"]) if activity.get("distance_meters") not in (None, 0) else None
        if distance_meters is not None and distance_meters > 0:
            ascent_per_km = ascent_meters / (distance_meters / 1000.0)
            recent_ascent_per_km = [
                float(row["ascent_meters"]) / (float(row["distance_meters"]) / 1000.0)
                for row in recent_rows
                if row.get("ascent_meters") not in (None, 0) and row.get("distance_meters") not in (None, 0)
            ]
            climbing_efficiency["ascent_per_km"] = summarize_comparison(ascent_per_km, recent_ascent_per_km, digits=1) or {"current": round_or_none(ascent_per_km, 1)}
        if avg_power is not None and avg_power > 0:
            energy_kj = avg_power * duration_seconds / 1000.0
            vertical_gain_per_kj = ascent_meters / energy_kj if energy_kj > 0 else None
            recent_vertical_gain_values = [
                float(row["ascent_meters"]) / ((float(row["avg_power"]) * float(row["duration_seconds"])) / 1000.0)
                for row in recent_rows
                if row.get("ascent_meters") not in (None, 0) and row.get("avg_power") not in (None, 0) and row.get("duration_seconds") not in (None, 0)
            ]
            climbing_efficiency["vertical_gain_per_kj"] = summarize_comparison(vertical_gain_per_kj, recent_vertical_gain_values, digits=3) or {"current": round_or_none(vertical_gain_per_kj, 3)}
        efficiency["climbing_efficiency"] = climbing_efficiency

    if avg_respiration_rate is not None and avg_respiration_rate > 0:
        respiration_relationship: dict[str, Any] = {
            "avg_respiration_rate": round_or_none(avg_respiration_rate, 1),
        }
        if avg_power is not None and avg_power > 0:
            breaths_per_100w = avg_respiration_rate / (avg_power / 100.0)
            recent_breaths_per_100w = [
                float(row["avg_respiration_rate"]) / (float(row["avg_power"]) / 100.0)
                for row in recent_rows
                if row.get("avg_respiration_rate") not in (None, 0) and row.get("avg_power") not in (None, 0)
            ]
            respiration_relationship["breaths_per_100w"] = summarize_comparison(breaths_per_100w, recent_breaths_per_100w, digits=2) or {
                "current": round_or_none(breaths_per_100w, 2)
            }
        elif avg_pace_seconds_per_km is not None and avg_pace_seconds_per_km > 0:
            breaths_per_km = avg_respiration_rate * (avg_pace_seconds_per_km / 60.0)
            recent_breaths_per_km = [
                float(row["avg_respiration_rate"]) * (float(row["avg_pace_seconds_per_km"]) / 60.0)
                for row in recent_rows
                if row.get("avg_respiration_rate") not in (None, 0) and row.get("avg_pace_seconds_per_km") not in (None, 0)
            ]
            respiration_relationship["breaths_per_km"] = summarize_comparison(breaths_per_km, recent_breaths_per_km, digits=1) or {
                "current": round_or_none(breaths_per_km, 1)
            }
        if avg_hr is not None and avg_hr > 0:
            breaths_per_beat = avg_respiration_rate / avg_hr
            recent_breaths_per_beat = [
                float(row["avg_respiration_rate"]) / float(row["avg_hr"])
                for row in recent_rows
                if row.get("avg_respiration_rate") not in (None, 0) and row.get("avg_hr") not in (None, 0)
            ]
            respiration_relationship["breaths_per_beat"] = summarize_comparison(breaths_per_beat, recent_breaths_per_beat, digits=3) or {
                "current": round_or_none(breaths_per_beat, 3)
            }
        efficiency["respiration_relationship"] = respiration_relationship

    return efficiency or None


def build_analysis(
    connection: sqlite3.Connection,
    activity: dict[str, Any],
    summaries: dict[tuple[str, str], dict[str, Any]],
    hr_readings: list[dict[str, Any]],
    power_readings: list[dict[str, Any]],
    performance_condition_readings: list[dict[str, Any]],
    speed_readings: list[dict[str, Any]],
    vertical_speed_readings: list[dict[str, Any]],
    elevation_readings: list[dict[str, Any]],
    zone_results: list[dict[str, Any]],
    zone_buckets: list[dict[str, Any]],
) -> dict[str, Any]:
    discipline = str(activity.get("discipline") or "").lower()
    is_running = discipline in RUNNING_DISCIPLINES
    is_walking_like = discipline in WALKING_DISCIPLINES
    is_pace_endurance = discipline in PACE_ENDURANCE_DISCIPLINES
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
    grade_adjusted_pace = build_grade_adjusted_pace_summary(activity, speed_readings, vertical_speed_readings, elevation_readings)
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
        if is_pace_endurance and hr_drift_percent < -5:
            aerobic_status = "good"
            if is_walking_like:
                aerobic_notes = f"HR drift {hr_drift_percent:.2f}% with pace-endurance terrain usually reflects easing terrain or deliberate containment rather than aerobic breakdown."
            else:
                aerobic_notes = f"HR drift {hr_drift_percent:.2f}% suggests the session stayed contained or terrain softened late rather than showing aerobic breakdown."
        else:
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
    target_zone = extract_target_zone(activity)
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
        if absolute_drift < 5 or hr_drift_percent < -5:
            power_hr_relationship = "aligned"
        elif hr_drift_percent > 0:
            power_hr_relationship = "hr_high_for_power"
        else:
            power_hr_relationship = "aligned"
        if is_walking_like and hr_drift_percent < -5:
            if grade_adjusted_pace is not None:
                relationship_notes = f"Average pace {avg_pace_formatted}; grade-adjusted pace {grade_adjusted_pace['grade_adjusted_pace_formatted']}; HR drift {hr_drift_percent:.2f}%. In a walking-like session this usually reflects easing terrain or controlled containment."
            else:
                relationship_notes = f"Average pace {avg_pace_formatted} with HR drift {hr_drift_percent:.2f}% for a walking-like session usually reflects easing terrain or controlled containment."
        elif grade_adjusted_pace is not None:
            relationship_notes = f"Average pace {avg_pace_formatted}; grade-adjusted pace {grade_adjusted_pace['grade_adjusted_pace_formatted']}; HR drift {hr_drift_percent:.2f}%."
        else:
            relationship_notes = f"Average pace {avg_pace_formatted} with HR drift {hr_drift_percent:.2f}% across the pace-endurance session."

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
    elif is_pace_endurance and avg_pace_formatted:
        metric_sources.append("pace")
    if any(key[0] == "respiration_rate" for key in summaries):
        metric_sources.append("respiration_rate")
    if zone_results:
        metric_sources.append("zones")
    running_dynamics = build_running_dynamics_summary(activity, summaries)
    performance_condition_signal = build_performance_condition_signal(summaries)
    performance_condition_evolution = build_performance_condition_evolution(
        performance_condition_readings,
        performance_condition_signal,
    )
    if performance_condition_signal is not None or performance_condition_evolution is not None:
        metric_sources.append("performance_condition")
    if running_dynamics is not None:
        metric_sources.append("running_dynamics")

    segment_analysis = build_segment_analysis(connection, activity)
    if segment_analysis is not None:
        metric_sources.append("segments")
    recent_rows = load_recent_comparable_activities(connection, activity)
    recent_comparison = build_recent_comparison(activity, recent_rows)
    activity_efficiency = build_activity_efficiency(activity, summaries, power_readings, zone_buckets, recent_rows, grade_adjusted_pace)

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

    planned_target = format_planned_target(activity)
    plan_alignment_notes = f"Planned intensity {activity.get('intensity_class') or 'unknown'}; structured target: {planned_target or 'n/a'}." if activity.get("planned_session_id") else "No linked planned session."
    if is_pace_endurance and avg_pace_formatted:
        if activity.get("planned_session_id"):
            plan_alignment_notes = f"Planned intensity {activity.get('intensity_class') or 'unknown'}; structured target: {planned_target or 'n/a'}; observed average pace {avg_pace_formatted}."
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
        "grade_adjusted_pace": grade_adjusted_pace,
        "relationship_notes": relationship_notes,
        "zone_execution": zone_execution,
        "dominant_hr_zone": dominant_hr_zone,
        "dominant_power_zone": dominant_power_zone,
        "zone_execution_notes": zone_execution_notes,
        "performance_condition_signal": performance_condition_signal,
        "performance_condition_evolution": performance_condition_evolution,
        "running_dynamics": running_dynamics,
        "efficiency_flags": efficiency_flags,
        "activity_efficiency": activity_efficiency,
        "segment_analysis": segment_analysis,
        "recent_comparison": recent_comparison,
        "metric_verdict": build_metric_verdict(execution_vs_plan, intensity_execution, aerobic_status, pacing_status, late_session_fade),
        "coaching_implication": build_coaching_implication(execution_vs_plan, aerobic_status, efficiency_flags),
    }


def compute_activity_metric_analysis(connection: sqlite3.Connection, activity_id: int) -> dict[str, Any]:
    activity = load_activity_context(connection, activity_id)
    summaries = load_metric_summaries(connection, activity_id)
    hr_readings = load_metric_readings(connection, activity_id, "heart_rate")
    power_readings = load_metric_readings(connection, activity_id, "power")
    performance_condition_readings = load_metric_readings(connection, activity_id, "performance_condition")
    speed_readings = load_metric_readings(connection, activity_id, "speed")
    vertical_speed_readings = load_metric_readings(connection, activity_id, "vertical_speed")
    elevation_readings = load_metric_readings(connection, activity_id, "elevation")
    zone_results = load_zone_results(connection, activity_id)
    zone_buckets = load_zone_buckets(connection, activity_id)
    return build_analysis(connection, activity, summaries, hr_readings, power_readings, performance_condition_readings, speed_readings, vertical_speed_readings, elevation_readings, zone_results, zone_buckets)


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