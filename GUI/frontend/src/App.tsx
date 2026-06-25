import { useEffect, useRef, useState, type ChangeEvent } from "react";
import ReactMarkdown from "react-markdown";

type Season = {
  season_id: number;
  season_code: string;
  season_name: string;
  start_date: string;
  end_date: string;
  status: string;
};

type Block = {
  block_id: number;
  block_code: string;
  block_name: string;
  phase_name: string;
  sequence_order: number;
  start_date: string | null;
  end_date: string | null;
  objective_primary: string;
};

type Week = {
  week_id: number;
  week_code: string;
  sequence_in_block: number;
  start_date: string;
  end_date: string;
  week_role: string;
  objective_primary: string;
  target_volume_hours_min: number | null;
  target_volume_hours_max: number | null;
};

type Session = {
  planned_session_id: number;
  session_date: string;
  day_name: string;
  planned_role: string | null;
  prescription_type?: string | null;
  planned_type: string;
  objective: string;
  primary_session: string;
  complementary_session: string | null;
  planned_support_routine?: string | null;
  intensity_class: string | null;
  duration_min: number | null;
  duration_max: number | null;
  is_key_session: number;
  planned_prescription?: PlannedPrescription | null;
  planned_activity_groups?: PlannedActivityGroup[];
  planned_zone_target?: PlannedZoneTarget | null;
};

type PlannedPrescriptionExerciseOption = {
  exercise_option_id: number;
  sequence_order: number;
  option_name: string;
  equipment: string | null;
  condition_notes: string | null;
};

type PlannedPrescriptionExercise = {
  prescription_exercise_id: number;
  sequence_order: number;
  exercise_name: string;
  movement_pattern: string | null;
  equipment: string | null;
  unilateral_mode: string;
  sets_count: number | null;
  reps_min: number | null;
  reps_max: number | null;
  hold_seconds_min: number | null;
  hold_seconds_max: number | null;
  distance_meters: number | null;
  target_rpe_min: number | null;
  target_rpe_max: number | null;
  target_rir_min: number | null;
  target_rir_max: number | null;
  tempo: string | null;
  load_guidance: string | null;
  optional_flag: number;
  substitution_group: string | null;
  notes: string | null;
  options: PlannedPrescriptionExerciseOption[];
};

type PlannedPrescriptionBlock = {
  prescription_block_id: number;
  sequence_order: number;
  block_role: "primary" | "support" | string;
  relation_group: number;
  relation_mode: "one_of" | "all_of" | string;
  is_optional: number;
  block_type: string;
  block_name: string | null;
  objective: string | null;
  rounds: number | null;
  rest_seconds: number | null;
  discipline_family: string | null;
  duration_min: number | null;
  duration_max: number | null;
  target_basis: string | null;
  target_zone_min_code: string | null;
  target_zone_max_code: string | null;
  condition_key: string | null;
  condition_value: string | null;
  notes: string | null;
  exercises: PlannedPrescriptionExercise[];
};

type PlannedPrescription = {
  prescription_id: number;
  planned_session_id: number;
  prescription_type: string;
  discipline_family: string | null;
  title: string | null;
  focus_primary: string | null;
  focus_secondary: string | null;
  estimated_duration_min: number | null;
  estimated_duration_max: number | null;
  target_rpe_min: number | null;
  target_rpe_max: number | null;
  warmup_notes: string | null;
  cooldown_notes: string | null;
  execution_notes: string | null;
  adaptation_notes: string | null;
  source_kind: string;
  structure_version: string;
  source_markdown_path: string | null;
  blocks: PlannedPrescriptionBlock[];
};

type PlannedActivityItem = {
  activity_item_id: number;
  sequence_order: number;
  item_type: string;
  discipline_family: string | null;
  display_label: string | null;
  duration_min: number | null;
  duration_max: number | null;
  target_basis: string | null;
  target_zone_min_code: string | null;
  target_zone_max_code: string | null;
  condition_key: string | null;
  condition_value: string | null;
  notes: string | null;
};

type PlannedActivityGroup = {
  activity_group_id: number;
  planned_session_id: number;
  group_role: "primary" | "support" | string;
  relation_group: number;
  relation_mode: "one_of" | "all_of" | string;
  is_optional: number;
  summary_label: string | null;
  notes: string | null;
  items: PlannedActivityItem[];
};

type PlannedZoneTargetSegment = {
  sequence_order: number;
  segment_label: string | null;
  target_zone_min_code: string | null;
  target_zone_max_code: string | null;
  target_duration_seconds_min: number | null;
  target_duration_seconds_max: number | null;
  notes: string | null;
};

type PlannedZoneTarget = {
  planned_zone_target_id: number;
  planned_session_id: number;
  target_basis: "heart_rate" | "power" | string | null;
  target_kind: string;
  source_kind: string;
  source_text: string | null;
  comparison_eligibility: string;
  segments: PlannedZoneTargetSegment[];
};

type ZoneComparisonItem = {
  planned_session_id: number;
  session_date: string;
  metric_basis: "heart_rate" | "power" | string | null;
  target_kind: string | null;
  comparison_eligibility: string | null;
  target_zone_min_code: string | null;
  target_zone_max_code: string | null;
  activity_id: number | null;
  calculation_status: string | null;
  dominant_zone_code: string | null;
  dominant_zone_share: number | null;
  comparison_status: string;
};

type PlanVsRealRow = {
  planned_session_id: number;
  session_date: string;
  day_name: string;
  planned_role: string | null;
  prescription_type?: string | null;
  planned_type: string;
  planned_objective: string;
  planned_session: string;
  planned_support_routine?: string | null;
  duration_min: number | null;
  duration_max: number | null;
  is_key_session: number;
  activity_id: number | null;
  actual_activity_type: string | null;
  actual_link_type: string | null;
  actual_source_system: string | null;
  actual_discipline: string | null;
  compatible_garmin_count: number;
  actual_duration_min: number | null;
  perceived_exertion: number | null;
  daily_review_id: number | null;
  compliance_status: string;
  actual_summary: string | null;
  general_feeling: string | null;
  next_day_decision: string | null;
  daily_assessment_available?: boolean;
  daily_assessment_url?: string | null;
  planned_prescription?: PlannedPrescription | null;
  planned_activity_groups?: PlannedActivityGroup[];
  activities?: PlanVsRealActivity[];
  optional_daily_activities?: OptionalDailyActivity[];
  other_daily_activities?: DailyUnlinkedActivity[];
  zone_comparison?: ZoneComparisonItem[];
};

type DailyAssessmentView = {
  dailyReviewId: number;
  sessionDate: string;
  plannedSession: string;
  markdown: string;
};

type WeekZoneComparisonSummaryItem = {
  metric_basis: "heart_rate" | "power" | string;
  planned_session_count: number;
  linked_activity_count: number;
  aligned_count: number;
  misaligned_count: number;
  limited_count: number;
  not_comparable_count: number;
  sessions: Array<{
    planned_session_id: number;
    comparison_status: string;
    dominant_zone_code: string | null;
  }>;
};

type WeekZoneComparisonSummary = {
  items: WeekZoneComparisonSummaryItem[];
};

type PlanVsRealActivity = {
  activity_id: number;
  actual_activity_type: string | null;
  actual_link_type: string | null;
  actual_source_system: string | null;
  actual_discipline: string | null;
  compatible_garmin_count: number;
  actual_duration_min: number | null;
  perceived_exertion: number | null;
};

type OptionalDailyActivity = PlanVsRealActivity & {
  started_at?: string | null;
};

type DailyUnlinkedActivity = PlanVsRealActivity & {
  started_at?: string | null;
};

type WeeklyReview = {
  week_id: number;
  week_code: string;
  review_status: string;
  closed_at: string | null;
  adherence_rate?: number;
  traceability_rate?: number;
  actual_minutes?: number;
  planned_reference_minutes?: number;
  volume_delta_minutes?: number;
  risk_level: string | null;
  recommendation_text: string | null;
  summary_text: string | null;
  weekly_assessment_available?: boolean;
  weekly_assessment_url?: string | null;
  zone_comparison_summary?: WeekZoneComparisonSummary;
};

type BlockReview = {
  block_id: number;
  season_id: number;
  block_code: string;
  block_name?: string | null;
  review_status: string;
  closed_at: string | null;
  weeks_in_block?: number | null;
  adherence_rate?: number | null;
  traceability_rate?: number | null;
  actual_minutes?: number | null;
  planned_reference_minutes?: number | null;
  volume_delta_minutes?: number | null;
  risk_level: string | null;
  recommendation_text: string | null;
  summary_text: string | null;
  block_assessment_available: boolean;
  block_assessment_url: string | null;
};

type WeightReview = {
  season_id: number;
  weight_review_id: number | null;
  review_date: string | null;
  classification: string | null;
  recommendation_text: string | null;
  summary_text: string | null;
  latest_weight_kg?: number | null;
  latest_7d_avg_kg?: number | null;
  delta_7d_avg_kg?: number | null;
  latest_14d_avg_kg?: number | null;
  delta_14d_avg_kg?: number | null;
  volatility_7d_kg?: number | null;
  gap_to_target_kg?: number | null;
  weight_assessment_available: boolean;
  weight_assessment_url: string | null;
};

type ZoneProposalItem = {
  proposal_id: number;
  discipline: string;
  metric_basis: "heart_rate" | "power" | string;
  proposal_status: string;
  confidence_level: string;
  recommendation_kind: string;
  proposal_summary: string;
  limiting_factors: string[];
  source_zone_profile_id: number | null;
  proposed_effective_start_date: string | null;
  created_at: string | null;
};

type ZoneProposalListResponse = {
  season_id?: number;
  discipline?: string;
  review_state?: string;
  basis_summary?: Record<string, unknown>;
  items: ZoneProposalItem[];
};

type ZoneProfileBoundary = {
  zone_index: number;
  zone_code: string;
  zone_name: string | null;
  lower_bound_value: number | null;
  upper_bound_value: number | null;
  bound_unit: string;
  target_kind: string;
};

type CurrentZoneProfile = {
  zone_profile_id: number;
  metric_basis: "heart_rate" | "power" | string;
  profile_label: string | null;
  source_metric_profile_id?: number | null;
  calculation_model_key?: string | null;
  governance_status: string;
  effective_start_date: string;
  effective_end_date: string | null;
  accepted_at: string | null;
  metric_profile?: ZoneMetricProfile | null;
  boundaries: ZoneProfileBoundary[];
};

type ZoneMetricProfile = {
  zone_metric_profile_id: number;
  metric_basis: "heart_rate" | "power" | string;
  profile_label: string | null;
  model_key: string;
  effective_start_date: string;
  effective_end_date: string | null;
  accepted_at: string | null;
  notes: string | null;
  parameters: {
    resting_hr?: number | null;
    max_hr?: number | null;
    ftp?: number | null;
  };
};

type PhysiologicalAnchorsFormState = {
  effective_start_date: string;
  resting_hr: string;
  max_hr: string;
  ftp: string;
  notes: string;
};

type CurrentZoneProfilesResponse = {
  season_id: number;
  discipline: string;
  profiles: Partial<Record<"heart_rate" | "power", CurrentZoneProfile>> & Record<string, CurrentZoneProfile | undefined>;
};

const SEGMENT_HISTORY_LIMIT_OPTIONS = [5, 10, 20, 30, 50] as const;
const SEGMENT_DAY_OCCURRENCE_COLORS = ["#0f766e", "#b45309", "#2563eb", "#9333ea", "#dc2626"] as const;

type DailyMetricDetail = {
  daily_metric_id: number;
  season_id: number;
  metric_date: string;
  source_system: string;
  load_model?: {
    daily_training_load: number;
    atl: number;
    ctl: number;
    tsb: number;
    atl_time_constant_days: number;
    ctl_time_constant_days: number;
    trend: Array<{
      metric_date: string;
      daily_training_load: number;
      atl: number;
      ctl: number;
      tsb: number;
    }>;
  } | null;
  weight_trend?: WeightTrendEntry[];
  weight_measurements?: WeightMeasurementEntry[];
  weight_measured_at: string | null;
  weight_measurement_source: string | null;
  weight_kg: number | null;
  body_fat_pct: number | null;
  body_water_pct: number | null;
  bone_mass_kg: number | null;
  muscle_mass_kg: number | null;
  bmi: number | null;
  visceral_fat: number | null;
  metabolic_age: number | null;
  physique_rating: number | null;
  sleep_hours: number | null;
  sleep_quality: string | null;
  resting_hr: number | null;
  vo2max_cycling: number | null;
  vo2max_running: number | null;
  lactate_threshold_hr: number | null;
  hrv: number | null;
  body_battery: number | null;
  total_steps: number | null;
  total_distance_m: number | null;
  step_goal: number | null;
  stress_avg: number | null;
  stress_max: number | null;
  spo2_avg: number | null;
  spo2_sleep_avg: number | null;
  spo2_7d_avg: number | null;
  spo2_lowest: number | null;
  subjective_energy: number | null;
  subjective_fatigue: number | null;
  soreness: string | null;
  notes: string | null;
};

type WeightTrendEntry = {
  metric_date: string;
  weight_kg: number;
  weight_measured_at: string | null;
  weight_measurement_source: string | null;
};

type WeightMeasurementEntry = {
  metric_date: string;
  measured_at: string | null;
  weight_kg: number;
  measurement_source: string | null;
};

type ActivityMetricAnalysisPerformanceConditionSignal = {
  status: string;
  average: number | null;
  minimum: number | null;
  maximum: number | null;
  notes: string[];
};

type ActivityMetricAnalysis = {
  performance_condition_signal: ActivityMetricAnalysisPerformanceConditionSignal | null;
  performance_condition_evolution: string | null;
};

type ActivityWeatherSample = {
  route_point_index: number;
  sampled_at: string;
  weather_hour: string;
  elapsed_seconds: number | null;
  distance_meters: number | null;
  latitude_degrees: number;
  longitude_degrees: number;
  temperature_2m: number | null;
  apparent_temperature: number | null;
  precipitation: number | null;
  rain: number | null;
  snowfall: number | null;
  weather_code: number | null;
  cloud_cover: number | null;
  wind_speed_10m: number | null;
  wind_gusts_10m: number | null;
  wind_direction_10m: number | null;
  shortwave_radiation: number | null;
};

type ActivityWeatherSummary = {
  temperature_mean: number | null;
  temperature_min: number | null;
  temperature_max: number | null;
  apparent_temperature_mean: number | null;
  precipitation_sum_est: number | null;
  rain_sum_est: number | null;
  snowfall_sum_est: number | null;
  cloud_cover_mean: number | null;
  wind_speed_mean: number | null;
  wind_speed_max: number | null;
  wind_gusts_max: number | null;
  shortwave_radiation_mean: number | null;
  dominant_weather_code: number | null;
  sample_count: number;
};

type ActivityWeatherDetail = {
  weather_enrichment_run_id: number;
  activity_id: number;
  provider_key: string;
  provider_version: string;
  provider_model: string | null;
  sample_strategy: string;
  requested_at: string;
  status: string;
  point_count: number;
  sample_count: number;
  notes: string | null;
  metadata: {
    sampling_interval_seconds?: number;
    sampling_distance_meters?: number;
    provider_model?: string;
    queries?: Array<{
      route_point_index: number;
      weather_hour: string;
      latitude: number;
      longitude: number;
      timezone?: string;
      elevation?: number;
    }>;
  };
  summary: ActivityWeatherSummary | null;
  samples: ActivityWeatherSample[];
};

type ActivityDetail = {
  activity_id: number;
  season_id: number;
  source_system: string;
  external_activity_id: string | null;
  activity_date: string;
  started_at: string | null;
  discipline: string | null;
  activity_type: string | null;
  duration_seconds: number | null;
  distance_meters: number | null;
  ascent_meters: number | null;
  calories: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_respiration_rate: number | null;
  max_respiration_rate: number | null;
  avg_power: number | null;
  normalized_power: number | null;
  training_load: number | null;
  calculated_training_load: number;
  calculated_training_load_source: string;
  avg_pace_seconds_per_km: number | null;
  perceived_exertion: number | null;
  subjective_feeling: string | null;
  power_sensor_profile: string | null;
  power_sensor_manufacturer: string | null;
  power_sensor_label: string | null;
  power_sensor_metadata_json: string | null;
  stress_avg: number | null;
  stress_max: number | null;
  spo2_sleep_avg: number | null;
  spo2_avg: number | null;
  spo2_7d_avg: number | null;
  spo2_lowest: number | null;
  source_file: string | null;
  raw_payload_path: string | null;
  notes: string | null;
  quality_status: string | null;
  quality_checked_at: string | null;
  quality_rule_version: string | null;
  quality_decision_count: number | null;
  quality_limited_metric_count: number | null;
  planned_session_id: number | null;
  compliance_status: string | null;
  rationale: string | null;
  actual_summary: string | null;
  general_feeling: string | null;
  next_day_decision: string | null;
  activity_metric_analysis?: ActivityMetricAnalysis | null;
  weather?: ActivityWeatherDetail | null;
};

type ActivityZoneSummaryBasis = {
  calculation_status: string;
  dominant_zone_code: string | null;
  dominant_zone_share: number | null;
  zone_profile_id: number;
  limiting_reasons?: string[];
};

type ActivityZoneSummary = Partial<Record<"heart_rate" | "power", ActivityZoneSummaryBasis>>;

function getTodayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function addDaysToIsoDate(date: string, days: number) {
  const nextDate = new Date(`${date}T00:00:00Z`);
  nextDate.setUTCDate(nextDate.getUTCDate() + days);
  return nextDate.toISOString().slice(0, 10);
}

function hasBodyCompositionMetrics(metric: DailyMetricDetail) {
  return [
    metric.body_fat_pct,
    metric.body_water_pct,
    metric.bone_mass_kg,
    metric.muscle_mass_kg,
    metric.bmi,
    metric.visceral_fat,
    metric.metabolic_age,
    metric.physique_rating,
  ].some((value) => value != null);
}

function getSeasonImportDateRange(season: Season, activities: ActivityListItem[] = []): Pick<GarminImportFormState, "date_from" | "date_to"> {
  const today = getTodayIsoDate();
  const dateTo = season.end_date < today ? season.end_date : today;
  const latestImportedActivityDate = activities[0]?.activity_date ?? null;
  const fallbackDateFrom = addDaysToIsoDate(dateTo, -1);
  const overlapDateFrom = latestImportedActivityDate ? addDaysToIsoDate(latestImportedActivityDate, -1) : null;
  const unclampedDateFrom = overlapDateFrom ?? fallbackDateFrom;
  const dateFrom = unclampedDateFrom < season.start_date ? season.start_date : unclampedDateFrom;

  return {
    date_from: dateFrom > dateTo ? dateTo : dateFrom,
    date_to: dateTo,
  };
}

function isDateWithinRange(date: string, startDate: string | null, endDate: string | null) {
  if (!startDate || !endDate) {
    return false;
  }
  return startDate <= date && date <= endDate;
}

function pickPreferredBlock(blocks: Block[], referenceDate: string) {
  return (
    blocks.find((block) => isDateWithinRange(referenceDate, block.start_date, block.end_date)) ??
    blocks[0] ??
    null
  );
}

function pickPreferredWeek(weeks: Week[], referenceDate: string) {
  return (
    weeks.find((week) => isDateWithinRange(referenceDate, week.start_date, week.end_date)) ??
    weeks.find((week) => week.start_date >= referenceDate) ??
    weeks[0] ??
    null
  );
}

type ActivityListItem = {
  activity_id: number;
  season_id: number;
  source_system: string;
  external_activity_id: string | null;
  activity_date: string;
  started_at: string | null;
  discipline: string | null;
  activity_type: string | null;
  duration_seconds: number | null;
  distance_meters: number | null;
  ascent_meters: number | null;
  calories: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_power: number | null;
  normalized_power: number | null;
  training_load: number | null;
  calculated_training_load: number;
  calculated_training_load_source: string;
  avg_pace_seconds_per_km: number | null;
  perceived_exertion: number | null;
  subjective_feeling: string | null;
  power_sensor_profile: string | null;
  power_sensor_manufacturer: string | null;
  power_sensor_label: string | null;
  power_sensor_metadata_json: string | null;
  raw_payload_path: string | null;
  notes: string | null;
  quality_status: string | null;
  quality_checked_at: string | null;
  quality_rule_version: string | null;
  quality_decision_count: number | null;
  quality_limited_metric_count: number | null;
  planned_session_id: number | null;
  compliance_status: string | null;
  rationale: string | null;
  actual_summary: string | null;
  general_feeling: string | null;
  next_day_decision: string | null;
  zone_summary?: ActivityZoneSummary;
};

type ActivityQualitySummaryImpact = {
  summary_kind: string;
  source_value: number | null;
  trusted_value: number | null;
  changed_by_filter: boolean;
  summary_status: string;
};

type ActivityQualityDecision = {
  quality_decision_id: number;
  decision_status: string;
  start_sample_index: number;
  end_sample_index: number;
  reason_code: string;
  rule_key: string;
  threshold_low: number | null;
  threshold_high: number | null;
  impacted_summary_kinds: string[];
};

type ActivityQualityMetric = {
  metric_name: string;
  metric_status: string;
  evaluated_reading_count: number;
  accepted_reading_count: number;
  excluded_reading_count: number;
  summary_impacts: ActivityQualitySummaryImpact[];
  decisions: ActivityQualityDecision[];
};

type ActivityQualityDetail = {
  activity: {
    activity_id: number;
    external_activity_id: string | null;
    activity_date: string;
    quality_status: string | null;
    quality_checked_at: string | null;
    quality_rule_version: string | null;
    source_reading_fingerprint: string | null;
  };
  metrics: ActivityQualityMetric[];
};

type RunningDynamicsHistoryItem = {
  activity_id: number;
  activity_date: string;
  started_at: string | null;
  discipline: string | null;
  activity_type: string | null;
  duration_seconds: number | null;
  avg_pace_seconds_per_km: number | null;
  avg_hr: number | null;
  metrics: Record<string, number>;
};

type RunningDynamicsHistoryResponse = {
  activity_id: number;
  discipline: string | null;
  compared_activity_count: number;
  baseline_metrics: Record<string, number>;
  history: RunningDynamicsHistoryItem[];
};

type ActivityQualityReplayResponse = {
  activity_id: number;
  quality_status: string | null;
  quality_rule_version: string | null;
  source_reading_fingerprint: string;
  result: "created_new_run" | "reused_existing_run";
};

type GarminImportFormState = {
  date_from: string;
  date_to: string;
  include_daily_metrics: boolean;
};

type GarminImportPreview = {
  request: {
    season_id: number;
    date_from: string;
    date_to: string;
    include_daily_metrics: boolean;
  };
  source_system: string;
  source_label: string;
  notes: string[];
  activities_detected: number;
  daily_metrics_detected: number;
  ready: boolean;
};

type GarminConnectStatus = {
  configured: boolean;
  auth_mode: string;
  tokenstore_path: string | null;
  tokenstore_available: boolean;
  credentials_available: boolean;
  detail: string;
};

type ImportJob = {
  import_job_id: number;
  season_id: number;
  source_system: string;
  import_type: string;
  source_path: string | null;
  imported_at: string;
  finished_at: string | null;
  rows_detected: number;
  rows_loaded: number;
  status: string;
  failure_stage: string | null;
  failure_class: string | null;
  retry_suitability: string | null;
  partial_completion: boolean;
  operator_detail: string | null;
  request_scope?: {
    season_id: number;
    date_from: string | null;
    date_to: string | null;
    include_daily_metrics: boolean;
  };
  notes: string[];
  breakdown: {
    activity_rows_detected: number;
    activity_rows_inserted: number;
    activity_rows_updated: number;
    activity_rows_skipped: number;
    daily_metric_rows_detected: number;
    daily_metric_rows_inserted: number;
    daily_metric_rows_updated: number;
    daily_metric_rows_skipped: number;
    segment_activities_checked: number;
    segment_activities_with_data: number;
    segment_efforts_detected: number;
    segment_efforts_inserted: number;
    segment_efforts_updated: number;
    segment_efforts_skipped: number;
    quality_activities_checked: number;
    quality_activities_filtered: number;
    quality_runs_created: number;
    quality_runs_reused: number;
    quality_decisions_recorded: number;
    quality_limited_metrics: number;
  };
  has_breakdown_details: boolean;
};

type SegmentListItem = {
  segment_id: number;
  source_system: string;
  external_segment_id: string;
  segment_name: string | null;
  discipline: string | null;
  effort_count: number;
  comparable_effort_count: number;
  first_activity_date: string | null;
  last_activity_date: string | null;
  best_elapsed_time_seconds: number | null;
  latest_elapsed_time_seconds: number | null;
  missing_metric_counts: {
    avg_power: number;
    avg_cadence: number;
    avg_heart_rate: number;
  };
};

type SegmentHistoryEffort = {
  segment_effort_id: number;
  activity_id: number;
  external_activity_id: string | null;
  activity_date: string;
  started_at: string | null;
  elapsed_time_seconds: number | null;
  avg_power: number | null;
  avg_cadence: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  avg_respiration_rate: number | null;
  missing_metrics: string[];
  is_best_effort: boolean;
  is_latest_effort: boolean;
  delta_vs_best_seconds: number | null;
  delta_vs_previous_seconds: number | null;
};

type SegmentHistoryResponse = {
  segment: {
    segment_id: number;
    external_segment_id: string;
    segment_name: string | null;
    discipline: string | null;
    distance_meters: number | null;
    ascent_meters: number | null;
    average_grade_percent: number | null;
  };
  summary: {
    effort_count: number;
    comparable_effort_count: number;
    membership_only_count: number;
    best_effort_id: number | null;
    latest_effort_id: number | null;
    trend_status: string;
    recent_window_size: number;
    available_metric_names: string[];
    missing_metric_names: string[];
  };
  efforts: SegmentHistoryEffort[];
};

type SegmentChartMetricKey = "elapsed_time_seconds" | "avg_power" | "avg_cadence" | "avg_heart_rate" | "max_heart_rate" | "avg_respiration_rate";

type GarminImportRunResponse = {
  status: string;
  counts: {
    activities_detected: number;
    daily_metrics_detected: number;
    segment_activities_checked: number;
    segment_activities_with_data: number;
    segment_efforts_detected: number;
    segment_efforts_loaded: number;
    quality_activities_checked: number;
    quality_activities_with_exclusions: number;
    quality_decisions_recorded: number;
    quality_limited_metrics: number;
    quality_runs_created: number;
    quality_runs_reused: number;
  };
  metadata: {
    notes: string[];
    segment_summary?: {
      activities_with_segment_data: number;
      activities_without_segment_data: number;
    };
    quality_summary?: {
      clean_activities: number;
      filtered_activities: number;
      limited_activities: number;
      rule_version: string | null;
    };
  };
  import_job: {
    import_job_id: number;
    status: string;
    rows_detected: number;
    rows_loaded: number;
    finished_at: string | null;
    failure_stage: string | null;
    failure_class: string | null;
    retry_suitability: string | null;
    partial_completion: boolean;
    operator_detail: string | null;
    request_scope: ImportJob["request_scope"];
    notes: string[];
    breakdown: ImportJob["breakdown"];
    has_breakdown_details: boolean;
  };
};

if (false) {
  const activityQualityDetailTypeCheck = {
    activity: {
      activity_id: 1,
      external_activity_id: "123",
      activity_date: "2026-05-19",
      quality_status: "filtered",
      quality_checked_at: "2026-05-27T18:34:12Z",
      quality_rule_version: "bad_reading_filter/v1",
      source_reading_fingerprint: "abc123",
    },
    metrics: [
      {
        metric_name: "heart_rate",
        metric_status: "filtered",
        evaluated_reading_count: 3,
        accepted_reading_count: 2,
        excluded_reading_count: 1,
        summary_impacts: [
          {
            summary_kind: "average",
            source_value: 181,
            trusted_value: 151,
            changed_by_filter: true,
            summary_status: "filtered",
          },
        ],
        decisions: [
          {
            quality_decision_id: 1,
            decision_status: "excluded",
            start_sample_index: 1,
            end_sample_index: 1,
            reason_code: "hr_above_hard_cap",
            rule_key: "hr_absolute_ceiling",
            threshold_low: null,
            threshold_high: 235,
            impacted_summary_kinds: ["average", "maximum"],
          },
        ],
      },
    ],
  } satisfies ActivityQualityDetail;

  const activityListItemTypeCheck = {
    activity_id: 1,
    season_id: 2026,
    source_system: "garmin",
    external_activity_id: "123",
    activity_date: "2026-05-19",
    started_at: "2026-05-19T08:00:00",
    discipline: "road_biking",
    activity_type: "Salida larga",
    duration_seconds: 3600,
    distance_meters: 25000,
    ascent_meters: 500,
    calories: 700,
    avg_hr: 151,
    max_hr: 178,
    avg_power: 250,
    normalized_power: 265,
    training_load: 90,
    calculated_training_load: 95,
    calculated_training_load_source: "power_tss",
    avg_pace_seconds_per_km: null,
    perceived_exertion: 7,
    subjective_feeling: null,
    power_sensor_profile: "pedal_power_meter",
    power_sensor_manufacturer: "GARMIN",
    power_sensor_label: "GARMIN 006-B2787-00 fit:2787 serial:3996467079",
    power_sensor_metadata_json: '{"antplusDeviceType":"BIKE_POWER","fitProductNumber":2787,"manufacturer":"GARMIN"}',
    raw_payload_path: "/tmp/123.tcx",
    notes: null,
    quality_status: "filtered",
    quality_checked_at: "2026-05-27T18:34:12Z",
    quality_rule_version: "bad_reading_filter/v1",
    quality_decision_count: 1,
    quality_limited_metric_count: 0,
    planned_session_id: null,
    compliance_status: null,
    rationale: null,
    actual_summary: null,
    general_feeling: null,
    next_day_decision: null,
  } satisfies ActivityListItem;

  const importRunResponseTypeCheck = {
    status: "ok",
    counts: {
      activities_detected: 1,
      daily_metrics_detected: 0,
      segment_activities_checked: 1,
      segment_activities_with_data: 0,
      segment_efforts_detected: 0,
      segment_efforts_loaded: 0,
      quality_activities_checked: 1,
      quality_activities_with_exclusions: 1,
      quality_decisions_recorded: 1,
      quality_limited_metrics: 0,
      quality_runs_created: 1,
      quality_runs_reused: 0,
    },
    metadata: {
      notes: ["Importacion Garmin completada."],
      segment_summary: {
        activities_with_segment_data: 0,
        activities_without_segment_data: 1,
      },
      quality_summary: {
        clean_activities: 0,
        filtered_activities: 1,
        limited_activities: 0,
        rule_version: "bad_reading_filter/v1",
      },
    },
    import_job: {
      import_job_id: 1,
      status: "completed",
      rows_detected: 1,
      rows_loaded: 1,
      finished_at: null,
      failure_stage: null,
      failure_class: null,
      retry_suitability: "safe_to_retry",
      partial_completion: false,
      operator_detail: null,
      request_scope: {
        season_id: 2026,
        date_from: "2026-05-19",
        date_to: "2026-05-19",
        include_daily_metrics: false,
      },
      notes: ["Importacion Garmin completada."],
      breakdown: {
        activity_rows_detected: 1,
        activity_rows_inserted: 1,
        activity_rows_updated: 0,
        activity_rows_skipped: 0,
        daily_metric_rows_detected: 0,
        daily_metric_rows_inserted: 0,
        daily_metric_rows_updated: 0,
        daily_metric_rows_skipped: 0,
        segment_activities_checked: 1,
        segment_activities_with_data: 0,
        segment_efforts_detected: 0,
        segment_efforts_inserted: 0,
        segment_efforts_updated: 0,
        segment_efforts_skipped: 0,
        quality_activities_checked: 1,
        quality_activities_filtered: 1,
        quality_runs_created: 1,
        quality_runs_reused: 0,
        quality_decisions_recorded: 1,
        quality_limited_metrics: 0,
      },
      has_breakdown_details: true,
    },
  } satisfies GarminImportRunResponse;

  void activityQualityDetailTypeCheck;
  void activityListItemTypeCheck;
  void importRunResponseTypeCheck;
}

function formatRetrySuitabilityLabel(retrySuitability: string | null): string {
  if (retrySuitability === "safe_to_retry") {
    return "Reintento seguro";
  }
  if (retrySuitability === "inspect_before_retry") {
    return "Inspeccionar antes de reintentar";
  }
  return "Sin clasificar";
}

function formatFailureStageLabel(failureStage: string | null): string {
  if (failureStage === "configuration") {
    return "Configuracion";
  }
  if (failureStage === "fetch") {
    return "Fetch";
  }
  if (failureStage === "normalize") {
    return "Normalizacion";
  }
  if (failureStage === "persist") {
    return "Persistencia";
  }
  return "Sin etapa";
}

function formatFailureClassLabel(failureClass: string | null): string {
  if (failureClass === "configuration_authentication") {
    return "Configuracion o autenticacion";
  }
  if (failureClass === "transport_rate_limit") {
    return "Transporte o rate limit";
  }
  if (failureClass === "source_data_normalization") {
    return "Datos origen o normalizacion";
  }
  if (failureClass === "persistence_transaction") {
    return "Persistencia o transaccion";
  }
  return "Sin clasificar";
}

function getImportJobScope(job: ImportJob) {
  return job.request_scope ?? {
    season_id: job.season_id,
    date_from: job.source_path?.split(":")[0] ?? null,
    date_to: job.source_path?.split(":")[1] ?? null,
    include_daily_metrics: false,
  };
}

const emptyGarminImportForm = (): GarminImportFormState => ({
  date_from: addDaysToIsoDate(getTodayIsoDate(), -1),
  date_to: getTodayIsoDate(),
  include_daily_metrics: true,
});

const emptyPhysiologicalAnchorsForm = (): PhysiologicalAnchorsFormState => ({
  effective_start_date: getTodayIsoDate(),
  resting_hr: "",
  max_hr: "",
  ftp: "",
  notes: "",
});

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Error ${response.status} cargando ${path}`);
  }
  return response.json() as Promise<T>;
}

async function fetchText(path: string): Promise<string> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, `Error ${response.status} cargando ${path}`));
  }
  return response.text();
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, `Error ${response.status} guardando ${path}`));
  }
  return response.json() as Promise<T>;
}

async function getApiErrorMessage(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail.trim() !== "") {
      return payload.detail;
    }
  } catch {
    // Ignore invalid JSON error bodies and fall back to a generic message.
  }
  return fallbackMessage;
}

function formatGarminRequestError(message: string): string {
  if (message.includes("Garmin Connect no esta configurado")) {
    return `${message} Arranca el backend con GARMIN_CONNECT_SESSION_PATH o con GARMIN_CONNECT_USERNAME/GARMIN_CONNECT_PASSWORD. Si quieres un arranque preparado, usa GUI/dev-with-garmin.sh.`;
  }
  if (message.includes("GARMIN_CONNECT_MFA_CODE")) {
    return `${message} Exporta GARMIN_CONNECT_MFA_CODE antes de arrancar el backend.`;
  }
  return message;
}

function toGarminAuthModeLabel(status: GarminConnectStatus): string {
  if (!status.configured) {
    return "Sin configurar";
  }
  if (status.auth_mode === "tokenstore") {
    return "Configurado · tokenstore";
  }
  if (status.auth_mode === "credentials") {
    return "Configurado · credenciales";
  }
  return "Configurado";
}

function isNotFoundError(error: unknown) {
  return error instanceof Error && error.message.startsWith("Error 404 ");
}

function formatSecondsLabel(value: number | null) {
  if (value == null) {
    return "Sin dato";
  }
  const minutes = Math.floor(value / 60);
  const seconds = Math.abs(value % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function formatTrendLabel(value: string) {
  if (value === "improving") {
    return "Mejorando";
  }
  if (value === "declining") {
    return "Cayendo";
  }
  if (value === "stable") {
    return "Estable";
  }
  return "Datos insuficientes";
}

function formatDeltaLabel(value: number | null) {
  if (value == null) {
    return "Sin referencia";
  }
  if (value === 0) {
    return "Igual";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value}s`;
}

function formatSegmentCoverageLabel(effortCount: number, comparableEffortCount: number) {
  if (effortCount === 0) {
    return "Sin registros";
  }
  if (comparableEffortCount === 0) {
    return `${effortCount} presencias`;
  }
  if (comparableEffortCount === effortCount) {
    return `${effortCount} esfuerzos`;
  }
  return `${comparableEffortCount}/${effortCount} con tiempo`;
}

function formatMetricValueLabel(metric: SegmentChartMetricKey, value: number) {
  if (metric === "elapsed_time_seconds") {
    return formatSecondsLabel(Math.round(value));
  }
  if (metric === "avg_power") {
    return `${Math.round(value)} W`;
  }
  if (metric === "avg_cadence") {
    return `${Math.round(value)} rpm`;
  }
  if (metric === "avg_respiration_rate") {
    return `${Math.round(value)} rpm resp`;
  }
  return `${Math.round(value)} ppm`;
}

function formatMetricAxisLabel(metric: SegmentChartMetricKey) {
  if (metric === "elapsed_time_seconds") {
    return "Tiempo";
  }
  if (metric === "avg_power") {
    return "Potencia";
  }
  if (metric === "avg_cadence") {
    return "Cadencia";
  }
  if (metric === "avg_respiration_rate") {
    return "Resp media";
  }
  if (metric === "avg_heart_rate") {
    return "FC media";
  }
  return "FC max";
}

function getSegmentEffortMoment(effort: SegmentHistoryEffort) {
  return Date.parse(effort.started_at ?? `${effort.activity_date}T00:00:00`);
}

function formatSegmentChartDateLabel(value: number) {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return new Date(value).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
  });
}

function formatSegmentChartDateParts(activityDate: string) {
  const [year = "", month = "", day = ""] = activityDate.split("-");
  if (!year || !month || !day) {
    return { day: activityDate, month: "" };
  }
  return { day, month };
}

function renderSegmentEvolutionChart(history: SegmentHistoryResponse) {
  const metricCandidates = [
    "elapsed_time_seconds",
    "avg_power",
    "avg_cadence",
    "avg_heart_rate",
    "max_heart_rate",
    "avg_respiration_rate",
  ] as const satisfies readonly SegmentChartMetricKey[];
  const chartMetrics = metricCandidates.filter((metric) => history.efforts.some((effort) => effort[metric] != null));

  if (chartMetrics.length === 0) {
    return null;
  }

  const width = 760;
  const leftGutter = 92;
  const rightGutter = 18;
  const topGutter = 18;
  const rowHeight = 78;
  const rowGap = 18;
  const chartHeight = topGutter + chartMetrics.length * rowHeight + (chartMetrics.length - 1) * rowGap + 72;
  const plotWidth = width - leftGutter - rightGutter;
  const chartStartY = topGutter;
  const timestamps = history.efforts.map(getSegmentEffortMoment);
  const minTimestamp = Math.min(...timestamps);
  const maxTimestamp = Math.max(...timestamps);
  const timestampSpan = Math.max(maxTimestamp - minTimestamp, 1);
  const effortsByDate = new Map<string, SegmentHistoryEffort[]>();

  history.efforts.forEach((effort) => {
    const items = effortsByDate.get(effort.activity_date) ?? [];
    items.push(effort);
    effortsByDate.set(effort.activity_date, items);
  });

  const effortStyleById = new Map<number, { dayOccurrenceIndex: number; sameDayOccurrenceCount: number; color: string }>();
  effortsByDate.forEach((efforts) => {
    efforts.forEach((effort, index) => {
      effortStyleById.set(effort.segment_effort_id, {
        dayOccurrenceIndex: index,
        sameDayOccurrenceCount: efforts.length,
        color: SEGMENT_DAY_OCCURRENCE_COLORS[index % SEGMENT_DAY_OCCURRENCE_COLORS.length],
      });
    });
  });
  const hasSameDayDuplicates = Array.from(effortsByDate.values()).some((efforts) => efforts.length > 1);
  const dateTicks = Array.from(effortsByDate.entries()).map(([activityDate, efforts]) => {
    const meanTimestamp = efforts.reduce((sum, effort) => sum + getSegmentEffortMoment(effort), 0) / efforts.length;
    const x = leftGutter + ((meanTimestamp - minTimestamp) / timestampSpan) * plotWidth;
    return {
      activityDate,
      x,
    };
  });

  return (
    <section className="segment-chart-card panel-subcard">
      <div className="segment-chart-head">
        <div>
          <strong>Evolucion del segmento</strong>
          <p className="segment-missing-copy">
            Fecha en eje X y una escala propia por metrica para no mezclar unidades.
            {hasSameDayDuplicates ? " Si hay varias ocurrencias el mismo dia, el color identifica el orden de cada intento dentro de ese dia." : ""}
          </p>
        </div>
      </div>
      <svg className="segment-evolution-chart" viewBox={`0 0 ${width} ${chartHeight}`} role="img" aria-label="Grafico de evolucion del segmento">
        {chartMetrics.map((metric, metricIndex) => {
          const rowTop = chartStartY + metricIndex * (rowHeight + rowGap);
          const rowBottom = rowTop + rowHeight;
          const rowMid = rowTop + rowHeight / 2;
          const values = history.efforts.flatMap((effort) => {
            const value = effort[metric];
            return value == null ? [] : [value];
          });
          const minValue = Math.min(...values);
          const maxValue = Math.max(...values);
          const valueSpan = Math.max(maxValue - minValue, 1);
          const points = history.efforts.flatMap((effort) => {
            const value = effort[metric];
            if (value == null) {
              return [];
            }
            const timestamp = getSegmentEffortMoment(effort);
            const x = leftGutter + ((timestamp - minTimestamp) / timestampSpan) * plotWidth;
            const y = rowBottom - ((value - minValue) / valueSpan) * (rowHeight - 16) - 8;
            return [{ effort, value, x, y }];
          });

          return (
            <g key={metric}>
              <line x1={leftGutter} y1={rowBottom} x2={width - rightGutter} y2={rowBottom} className="segment-chart-axis" />
              <line x1={leftGutter} y1={rowTop} x2={leftGutter} y2={rowBottom} className="segment-chart-axis" />
              <text x={12} y={rowTop + 16} className="segment-chart-label">{formatMetricAxisLabel(metric)}</text>
              <text x={12} y={rowMid + 18} className="segment-chart-range">{formatMetricValueLabel(metric, maxValue)}</text>
              <text x={12} y={rowBottom - 4} className="segment-chart-range">{formatMetricValueLabel(metric, minValue)}</text>
              {points.map((point) => (
                <circle
                  key={point.effort.segment_effort_id}
                  cx={point.x}
                  cy={point.y}
                  r={4.5}
                  className="segment-chart-dot"
                  style={{ fill: effortStyleById.get(point.effort.segment_effort_id)?.color }}
                >
                  <title>{`${point.effort.activity_date}${point.effort.started_at ? ` ${toDateTimeLabel(point.effort.started_at)}` : ""}${(effortStyleById.get(point.effort.segment_effort_id)?.sameDayOccurrenceCount ?? 0) > 1 ? ` · intento ${(effortStyleById.get(point.effort.segment_effort_id)?.dayOccurrenceIndex ?? 0) + 1}/${effortStyleById.get(point.effort.segment_effort_id)?.sameDayOccurrenceCount}` : ""} · ${formatMetricAxisLabel(metric)}: ${formatMetricValueLabel(metric, point.value)}`}</title>
                </circle>
              ))}
            </g>
          );
        })}

        {dateTicks.map((tick) => (
          <g key={tick.activityDate} transform={`translate(${tick.x.toFixed(1)}, ${chartHeight - 28})`}>
            <line x1={0} y1={-10} x2={0} y2={-2} className="segment-chart-axis" />
            <text textAnchor="middle" className="segment-chart-date">
              <tspan x={0} dy={0}>{formatSegmentChartDateParts(tick.activityDate).day}</tspan>
              <tspan x={0} dy={11}>{formatSegmentChartDateParts(tick.activityDate).month}</tspan>
            </text>
          </g>
        ))}
      </svg>
    </section>
  );
}

function renderLoadModelChart(
  loadModel: NonNullable<DailyMetricDetail["load_model"]>,
  className = "load-chart-card panel-subcard",
) {
  const history = loadModel.trend;
  if (!history.length) {
    return null;
  }

  const width = 1200;
  const height = 360;
  const leftGutter = 56;
  const rightGutter = 24;
  const topGutter = 26;
  const bottomGutter = 52;
  const plotWidth = width - leftGutter - rightGutter;
  const plotHeight = height - topGutter - bottomGutter;
  const minTsb = Math.min(...history.map((entry) => entry.tsb), 0);
  const maxPositive = Math.max(...history.map((entry) => Math.max(entry.daily_training_load, entry.atl, entry.ctl, entry.tsb)), 1);
  const totalRange = Math.max(maxPositive - minTsb, 1);
  const zeroY = topGutter + ((maxPositive - 0) / totalRange) * plotHeight;
  const stepX = history.length > 1 ? plotWidth / (history.length - 1) : 0;

  const toY = (value: number) => topGutter + ((maxPositive - value) / totalRange) * plotHeight;
  const toX = (index: number) => leftGutter + index * stepX;
  const toPath = (values: number[]) => values.map((value, index) => `${index === 0 ? "M" : "L"}${toX(index).toFixed(1)},${toY(value).toFixed(1)}`).join(" ");

  const atlPath = toPath(history.map((entry) => entry.atl));
  const ctlPath = toPath(history.map((entry) => entry.ctl));
  const tsbPath = toPath(history.map((entry) => entry.tsb));
  const tickValues = [maxPositive, (maxPositive + minTsb) / 2, minTsb].filter((value, index, values) => values.findIndex((candidate) => Math.abs(candidate - value) < 0.01) === index);

  return (
    <section className={className}>
      <div className="load-chart-head">
        <div>
          <strong>Tendencia ATL / CTL / TSB</strong>
          <p className="segment-missing-copy">Carga diaria en barras y ATL, CTL, TSB en lineas sobre los ultimos {history.length} dias.</p>
        </div>
        <div className="load-chart-legend" aria-label="Leyenda del grafico de carga">
          <span><i className="load-chart-swatch load-chart-swatch-load" />Carga</span>
          <span><i className="load-chart-swatch load-chart-swatch-atl" />ATL</span>
          <span><i className="load-chart-swatch load-chart-swatch-ctl" />CTL</span>
          <span><i className="load-chart-swatch load-chart-swatch-tsb" />TSB</span>
        </div>
      </div>
      <svg className="load-model-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Grafico de carga con ATL, CTL y TSB">
        {tickValues.map((tick) => (
          <g key={tick}>
            <line x1={leftGutter} y1={toY(tick)} x2={width - rightGutter} y2={toY(tick)} className="load-chart-grid" />
            <text x={12} y={toY(tick) + 4} className="load-chart-axis-label">{toMetricLabel(tick)}</text>
          </g>
        ))}
        <line x1={leftGutter} y1={zeroY} x2={width - rightGutter} y2={zeroY} className="load-chart-zero" />
        {history.map((entry, index) => {
          const x = toX(index);
          const barWidth = Math.max(plotWidth / Math.max(history.length * 2, 12), 8);
          const barTop = toY(entry.daily_training_load);
          const barHeight = Math.max(zeroY - barTop, 0);
          return (
            <g key={entry.metric_date}>
              <rect x={x - barWidth / 2} y={barTop} width={barWidth} height={barHeight} className="load-chart-bar">
                <title>{`${entry.metric_date} · Carga ${toMetricLabel(entry.daily_training_load)}`}</title>
              </rect>
              {index === 0 || index === history.length - 1 || index % Math.max(Math.floor(history.length / 4), 1) === 0 ? (
                <text x={x} y={height - 14} textAnchor="middle" className="load-chart-date-label">{entry.metric_date.slice(5)}</text>
              ) : null}
            </g>
          );
        })}
        <path d={atlPath} className="load-chart-line load-chart-line-atl" />
        <path d={ctlPath} className="load-chart-line load-chart-line-ctl" />
        <path d={tsbPath} className="load-chart-line load-chart-line-tsb" />
        {history.map((entry, index) => (
          <g key={`${entry.metric_date}-dots`}>
            <circle cx={toX(index)} cy={toY(entry.atl)} r={3.5} className="load-chart-dot load-chart-dot-atl">
              <title>{`${entry.metric_date} · ATL ${toMetricLabel(entry.atl)}`}</title>
            </circle>
            <circle cx={toX(index)} cy={toY(entry.ctl)} r={3.5} className="load-chart-dot load-chart-dot-ctl">
              <title>{`${entry.metric_date} · CTL ${toMetricLabel(entry.ctl)}`}</title>
            </circle>
            <circle cx={toX(index)} cy={toY(entry.tsb)} r={3.5} className="load-chart-dot load-chart-dot-tsb">
              <title>{`${entry.metric_date} · TSB ${toMetricLabel(entry.tsb)}`}</title>
            </circle>
          </g>
        ))}
      </svg>
    </section>
  );
}

function formatWeightMeasurementSourceLabel(source: string | null) {
  if (source === "first_daily_measurement") {
    return "lectura usada del dia";
  }
  if (source === "timestamped_measurement") {
    return "lectura con hora";
  }
  if (source === "daily_aggregate") {
    return "agregado diario";
  }
  return source ?? "sin origen";
}

function renderWeightTrendChart(
  weightTrend: WeightTrendEntry[],
  weightMeasurements: WeightMeasurementEntry[],
  className = "weight-chart-card panel-subcard",
) {
  if (!weightTrend.length) {
    return null;
  }

  const width = 1200;
  const height = 280;
  const leftGutter = 56;
  const rightGutter = 24;
  const topGutter = 26;
  const bottomGutter = 52;
  const plotWidth = width - leftGutter - rightGutter;
  const plotHeight = height - topGutter - bottomGutter;
  const maxWeight = Math.max(...weightTrend.map((entry) => entry.weight_kg));
  const paddedMin = 82;
  const paddedMax = maxWeight + 0.4;
  const weightRange = Math.max(paddedMax - paddedMin, 0.8);
  const stepX = weightTrend.length > 1 ? plotWidth / (weightTrend.length - 1) : 0;

  const toX = (index: number) => leftGutter + index * stepX;
  const toY = (value: number) => topGutter + ((paddedMax - value) / weightRange) * plotHeight;
  const path = weightTrend
    .map((entry, index) => `${index === 0 ? "M" : "L"}${toX(index).toFixed(1)},${toY(entry.weight_kg).toFixed(1)}`)
    .join(" ");
  const tickValues = [paddedMax, (paddedMax + paddedMin) / 2, paddedMin].filter(
    (value, index, values) => values.findIndex((candidate) => Math.abs(candidate - value) < 0.01) === index,
  );
  const selectedByDate = new Map(weightTrend.map((entry) => [entry.metric_date, `${entry.weight_measured_at ?? ""}|${entry.weight_kg}`]));
  const extraMeasurements = weightMeasurements.filter((measurement) => {
    const selectedKey = selectedByDate.get(measurement.metric_date);
    const measurementKey = `${measurement.measured_at ?? ""}|${measurement.weight_kg}`;
    return selectedKey !== measurementKey;
  });
  const indexByDate = new Map(weightTrend.map((entry, index) => [entry.metric_date, index]));

  return (
    <section className={className}>
      <div className="load-chart-head">
        <div>
          <strong>Tendencia de peso</strong>
          <p className="segment-missing-copy">Serie diaria usando la primera lectura del dia cuando existe hora de medicion, con puntos adicionales para el resto de pesajes del mismo dia sin unirlos con lineas.</p>
        </div>
        <div className="load-chart-legend" aria-label="Leyenda del grafico de peso">
          <span><i className="load-chart-swatch weight-chart-swatch-line" />Peso</span>
          <span><i className="load-chart-swatch weight-chart-swatch-primary" />Lectura usada</span>
          <span><i className="load-chart-swatch weight-chart-swatch-extra" />Otras medidas del dia</span>
        </div>
      </div>
      <svg className="load-model-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Grafico de tendencia de peso con primera lectura diaria y medidas adicionales">
        {tickValues.map((tick) => (
          <g key={tick}>
            <line x1={leftGutter} y1={toY(tick)} x2={width - rightGutter} y2={toY(tick)} className="load-chart-grid" />
            <text x={12} y={toY(tick) + 4} className="load-chart-axis-label">{toMetricLabel(tick, " kg")}</text>
          </g>
        ))}
        <path d={path} className="weight-chart-line" />
        {extraMeasurements.map((entry, index) => {
          const dayIndex = indexByDate.get(entry.metric_date);
          if (dayIndex == null) {
            return null;
          }
          return (
            <circle
              key={`${entry.metric_date}-${entry.measured_at ?? index}-${entry.weight_kg}`}
              cx={toX(dayIndex)}
              cy={toY(entry.weight_kg)}
              r={3.6}
              className="weight-chart-dot weight-chart-dot-extra"
            >
              <title>{`${entry.metric_date} · ${toMetricLabel(entry.weight_kg, " kg")} · medida adicional${entry.measured_at ? ` · ${toDateTimeLabel(entry.measured_at)}` : ""}`}</title>
            </circle>
          );
        })}
        {weightTrend.map((entry, index) => {
          return (
            <g key={entry.metric_date}>
              <circle
                cx={toX(index)}
                cy={toY(entry.weight_kg)}
                r={4.2}
                className="weight-chart-dot weight-chart-dot-primary"
              >
                <title>{`${entry.metric_date} · ${toMetricLabel(entry.weight_kg, " kg")} · ${formatWeightMeasurementSourceLabel(entry.weight_measurement_source)}${entry.weight_measured_at ? ` · ${toDateTimeLabel(entry.weight_measured_at)}` : ""}`}</title>
              </circle>
              {index === 0 || index === weightTrend.length - 1 || index % Math.max(Math.floor(weightTrend.length / 4), 1) === 0 ? (
                <text x={toX(index)} y={height - 14} textAnchor="middle" className="load-chart-date-label">{entry.metric_date.slice(5)}</text>
              ) : null}
            </g>
          );
        })}
      </svg>
    </section>
  );
}

function toDurationLabel(min: number | null, max: number | null) {
  if (min == null) {
    return "-";
  }
  if (max != null && max !== min) {
    return `${min} - ${max} min`;
  }
  return `${min} min`;
}

function toDurationFragment(min: number | null, max: number | null) {
  if (min == null) {
    return null;
  }
  if (max != null && max !== min) {
    return `${min}-${max} min`;
  }
  return `${min} min`;
}

function toBadgeClass(status: string) {
  return `badge badge-${status}`;
}

function formatPerformanceConditionStatus(status: string | null | undefined) {
  switch (status) {
    case "positive":
      return "Positiva";
    case "negative":
      return "Negativa";
    case "mixed":
      return "Mixta";
    case "neutral":
      return "Neutra";
    default:
      return "Sin clasificar";
  }
}

function toHoursLabel(totalMinutes: number) {
  const totalHours = totalMinutes / 60;
  return Number.isInteger(totalHours) ? `${totalHours} h` : `${totalHours.toFixed(1)} h`;
}

function toPercentLabel(value: number) {
  return `${Math.round(value)}%`;
}

function toDateTimeLabel(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("es-ES", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toMetricLabel(value: number | null, suffix = "") {
  if (value == null) {
    return "-";
  }
  return `${Number.isInteger(value) ? value : value.toFixed(1)}${suffix}`;
}

function toCompactDateTimeLabel(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
  });
}

function toWeatherSampleDateTimeLabel(activityStartedAt: string | null, elapsedSeconds: number | null, fallbackValue: string | null) {
  if (activityStartedAt && elapsedSeconds != null) {
    const normalizedStart = activityStartedAt.includes("T") ? activityStartedAt : activityStartedAt.replace(" ", "T");
    const start = new Date(normalizedStart);
    if (!Number.isNaN(start.getTime())) {
      return new Date(start.getTime() + elapsedSeconds * 1000).toLocaleString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
      });
    }
  }
  return toCompactDateTimeLabel(fallbackValue);
}

function toElapsedTimeLabel(totalSeconds: number | null) {
  if (totalSeconds == null) {
    return "-";
  }
  const rounded = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  }
  return `${minutes} min`;
}

function toCardinalWindLabel(direction: number | null) {
  if (direction == null) {
    return "-";
  }
  const sectors = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
  const normalized = ((direction % 360) + 360) % 360;
  const index = Math.round(normalized / 45) % sectors.length;
  return `${sectors[index]} · ${Math.round(normalized)}°`;
}

function toWeatherCodeLabel(code: number | null) {
  if (code == null) {
    return "Sin clasificar";
  }
  const labels: Record<number, string> = {
    0: "Despejado",
    1: "Poco nuboso",
    2: "Intervalos",
    3: "Cubierto",
    45: "Niebla",
    48: "Niebla helada",
    51: "Llovizna ligera",
    53: "Llovizna",
    55: "Llovizna intensa",
    61: "Lluvia ligera",
    63: "Lluvia",
    65: "Lluvia intensa",
    71: "Nieve ligera",
    73: "Nieve",
    75: "Nieve intensa",
    77: "Granizo de nieve",
    80: "Chubascos ligeros",
    81: "Chubascos",
    82: "Chubascos intensos",
    85: "Nevadas ligeras",
    86: "Nevadas intensas",
    95: "Tormenta",
    96: "Tormenta con granizo",
    99: "Tormenta severa",
  };
  return labels[code] ?? `Codigo ${code}`;
}

function toTemperatureBandLabel(summary: ActivityWeatherSummary | null) {
  if (!summary || summary.temperature_min == null || summary.temperature_max == null) {
    return "-";
  }
  return `${toMetricLabel(summary.temperature_min, " °C")} / ${toMetricLabel(summary.temperature_max, " °C")}`;
}

function getOptionalDailyActivities(row: PlanVsRealRow): OptionalDailyActivity[] {
  return (row.optional_daily_activities ?? []).filter((activity) => activity.actual_discipline !== "yoga");
}

function getSupportDailyActivities(row: PlanVsRealRow): OptionalDailyActivity[] {
  return (row.optional_daily_activities ?? []).filter((activity) => activity.actual_discipline === "yoga");
}

function getOptionalDailyLoadMinutes(row: PlanVsRealRow) {
  return Math.round(getOptionalDailyActivities(row).reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
}

function getSupportDailyLoadMinutes(row: PlanVsRealRow) {
  return Math.round(getSupportDailyActivities(row).reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
}

function getOtherDailyLoadMinutes(row: PlanVsRealRow) {
  return Math.round((row.other_daily_activities ?? []).reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
}

function getDailyTotalLoadMinutes(row: PlanVsRealRow) {
  return Math.round((row.actual_duration_min ?? 0) + getOptionalDailyLoadMinutes(row) + getSupportDailyLoadMinutes(row) + getOtherDailyLoadMinutes(row));
}

function isManualSource(sourceSystem: string) {
  return sourceSystem.startsWith("manual");
}

function toDisciplineLabel(discipline: string | null) {
  if (!discipline) {
    return "Sin disciplina";
  }
  const labels: Record<string, string> = {
    bicicleta: "Ciclismo",
    caminar: "Caminar",
    fuerza: "Fuerza",
    hiking: "Senderismo",
    indoor_cycling: "Ciclismo en sala",
    paseo: "Caminar",
    road_biking: "Ciclismo en ruta",
    running: "Carrera",
    senderismo: "Senderismo",
    strength_training: "Fuerza",
    trail_running: "Trail running",
    walking: "Caminar",
    yoga: "Yoga",
  };
  return labels[discipline] ?? discipline;
}

function toPlannedFamilyLabel(discipline: string | null, itemType: string, fallbackLabel: string | null) {
  if (itemType === "rest") {
    return fallbackLabel ?? "Descanso activo";
  }
  const labels: Record<string, string> = {
    cycling: "Bicicleta",
    running: "Carrera",
    strength_training: "Fuerza",
    walking: "Paseo",
    yoga: "Movilidad",
  };
  return fallbackLabel && fallbackLabel.trim().length > 0 && itemType !== "endurance"
    ? fallbackLabel
    : labels[discipline ?? ""] ?? fallbackLabel ?? "Actividad";
}

function formatPlannedActivityItem(item: PlannedActivityItem) {
  const rawLabel = item.display_label?.trim() ?? null;
  if (rawLabel && /\bmin\b/i.test(rawLabel)) {
    return rawLabel;
  }

  const baseLabel = toPlannedFamilyLabel(item.discipline_family, item.item_type, rawLabel);
  const zoneLabel = item.target_zone_min_code
    ? item.target_zone_max_code && item.target_zone_max_code !== item.target_zone_min_code
      ? `${item.target_zone_min_code}-${item.target_zone_max_code}`
      : item.target_zone_min_code
    : null;
  const durationLabel = toDurationFragment(item.duration_min, item.duration_max);
  return [baseLabel, zoneLabel, durationLabel].filter(Boolean).join(" ");
}

function formatPlannedActivityGroups(groups: PlannedActivityGroup[] | undefined, role?: "primary" | "support") {
  const scopedGroups = (groups ?? []).filter((group) => (role ? group.group_role === role : true));
  if (scopedGroups.length === 0) {
    return null;
  }
  return scopedGroups
    .map((group) => group.items.map((item) => formatPlannedActivityItem(item)).join(group.relation_mode === "all_of" ? " + " : " o "))
    .join(" + ");
}

function formatPlannedPrescriptionBlock(block: PlannedPrescriptionBlock) {
  const label = block.block_name ?? block.block_type;
  const zoneLabel = block.target_zone_min_code
    ? block.target_zone_max_code && block.target_zone_max_code !== block.target_zone_min_code
      ? `${block.target_zone_min_code}-${block.target_zone_max_code}`
      : block.target_zone_min_code
    : null;
  const durationLabel = toDurationFragment(block.duration_min, block.duration_max);
  const roundsLabel = block.rounds && block.rounds > 1 ? `${block.rounds} rep` : null;
  return [label, zoneLabel, durationLabel, roundsLabel].filter(Boolean).join(" ");
}

function formatPlannedPrescriptionBlocks(prescription: PlannedPrescription | null | undefined, role?: "primary" | "support") {
  const scopedBlocks = (prescription?.blocks ?? []).filter((block) => (role ? block.block_role === role : true));
  if (scopedBlocks.length === 0) {
    return null;
  }
  const groups = new Map<number, PlannedPrescriptionBlock[]>();
  for (const block of scopedBlocks) {
    const existing = groups.get(block.relation_group) ?? [];
    existing.push(block);
    groups.set(block.relation_group, existing);
  }
  return Array.from(groups.entries())
    .sort((left, right) => left[0] - right[0])
    .map(([, blocks]) => blocks.map((block) => formatPlannedPrescriptionBlock(block)).join(blocks[0]?.relation_mode === "one_of" ? " o " : " + "))
    .join(" + ");
}

function toStructuredLabel(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return value
    .split(/[-_]+/)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
}

function getPrescriptionBlockGroups(prescription: PlannedPrescription | null | undefined, role: "primary" | "support") {
  const groups = new Map<number, PlannedPrescriptionBlock[]>();
  for (const block of prescription?.blocks ?? []) {
    if (block.block_role !== role) {
      continue;
    }
    const existing = groups.get(block.relation_group) ?? [];
    existing.push(block);
    groups.set(block.relation_group, existing);
  }
  return Array.from(groups.entries())
    .sort((left, right) => left[0] - right[0])
    .map(([, blocks]) => blocks.sort((left, right) => left.sequence_order - right.sequence_order));
}

function formatPrescriptionConditionLabel(block: PlannedPrescriptionBlock) {
  if (!block.condition_key || !block.condition_value) {
    return null;
  }
  return `${toStructuredLabel(block.condition_key)}: ${block.condition_value}`;
}

function formatExercisePrescriptionMeta(exercise: PlannedPrescriptionExercise) {
  const fragments: string[] = [];
  if (exercise.sets_count != null) {
    fragments.push(`${exercise.sets_count} series`);
  }
  if (exercise.reps_min != null || exercise.reps_max != null) {
    const repsLabel = exercise.reps_min != null && exercise.reps_max != null && exercise.reps_min !== exercise.reps_max
      ? `${exercise.reps_min}-${exercise.reps_max} rep`
      : `${exercise.reps_min ?? exercise.reps_max} rep`;
    fragments.push(repsLabel);
  }
  if (exercise.hold_seconds_min != null || exercise.hold_seconds_max != null) {
    const holdLabel = exercise.hold_seconds_min != null && exercise.hold_seconds_max != null && exercise.hold_seconds_min !== exercise.hold_seconds_max
      ? `${formatSecondsLabel(exercise.hold_seconds_min)}-${formatSecondsLabel(exercise.hold_seconds_max)}`
      : formatSecondsLabel(exercise.hold_seconds_min ?? exercise.hold_seconds_max);
    fragments.push(`isometria ${holdLabel}`);
  }
  if (exercise.distance_meters != null) {
    fragments.push(`${exercise.distance_meters} m`);
  }
  if (exercise.target_rpe_min != null || exercise.target_rpe_max != null) {
    const rpeLabel = exercise.target_rpe_min != null && exercise.target_rpe_max != null && exercise.target_rpe_min !== exercise.target_rpe_max
      ? `${exercise.target_rpe_min}-${exercise.target_rpe_max}`
      : `${exercise.target_rpe_min ?? exercise.target_rpe_max}`;
    fragments.push(`RPE ${rpeLabel}`);
  }
  if (exercise.target_rir_min != null || exercise.target_rir_max != null) {
    const rirLabel = exercise.target_rir_min != null && exercise.target_rir_max != null && exercise.target_rir_min !== exercise.target_rir_max
      ? `${exercise.target_rir_min}-${exercise.target_rir_max}`
      : `${exercise.target_rir_min ?? exercise.target_rir_max}`;
    fragments.push(`RIR ${rirLabel}`);
  }
  if (exercise.tempo) {
    fragments.push(`Tempo ${exercise.tempo}`);
  }
  if (exercise.load_guidance) {
    fragments.push(exercise.load_guidance);
  }
  if (exercise.equipment) {
    fragments.push(`Equipo: ${exercise.equipment}`);
  }
  return fragments;
}

function renderPrescriptionRoleSection(prescription: PlannedPrescription, role: "primary" | "support") {
  const blockGroups = getPrescriptionBlockGroups(prescription, role);
  if (blockGroups.length === 0) {
    return null;
  }
  const title = role === "primary" ? "Bloques principales" : "Bloques complementarios";
  return (
    <section className="session-role-section">
      <div className="session-role-section-head">
        <h4>{title}</h4>
        <small>{blockGroups.length} grupo{blockGroups.length === 1 ? "" : "s"}</small>
      </div>
      {blockGroups.map((blocks) => (
        <div key={`${role}-${blocks[0].relation_group}`} className="session-block-group">
          <div className="session-block-group-head">
            <strong>Grupo {blocks[0].relation_group}</strong>
            <small>
              {blocks[0].relation_mode === "one_of" ? "Elegir una opcion" : "Completar todo el grupo"}
              {blocks[0].is_optional ? " · Opcional" : ""}
            </small>
          </div>
          <div className="prescription-block-list">
            {blocks.map((block) => {
              const conditionLabel = formatPrescriptionConditionLabel(block);
              return (
                <article key={block.prescription_block_id} className="prescription-block-card">
                  <div className="session-block-card-head">
                    <div>
                      <strong>{block.block_name ?? toStructuredLabel(block.block_type)}</strong>
                      {block.objective ? <p>{block.objective}</p> : null}
                    </div>
                    <div className="session-block-badges">
                      {block.target_zone_min_code ? (
                        <span className="zone-pill zone-pill-target">
                          {block.target_zone_max_code && block.target_zone_max_code !== block.target_zone_min_code
                            ? `${block.target_zone_min_code}-${block.target_zone_max_code}`
                            : block.target_zone_min_code}
                        </span>
                      ) : null}
                      {block.block_type ? <span className="zone-pill">{toStructuredLabel(block.block_type)}</span> : null}
                    </div>
                  </div>
                  <div className="session-block-meta">
                    <span>Duracion {toDurationLabel(block.duration_min, block.duration_max)}</span>
                    {block.discipline_family ? <span>{toStructuredLabel(block.discipline_family)}</span> : null}
                    {block.target_basis ? <span>Base {toStructuredLabel(block.target_basis)}</span> : null}
                    {block.rounds ? <span>{block.rounds} repeticiones</span> : null}
                    {block.rest_seconds ? <span>Pausa {formatSecondsLabel(block.rest_seconds)}</span> : null}
                    {conditionLabel ? <span>{conditionLabel}</span> : null}
                  </div>
                  {block.notes ? <p>{block.notes}</p> : null}
                  {block.exercises.length > 0 ? (
                    <div className="prescription-exercise-list">
                      {block.exercises.map((exercise) => {
                        const exerciseMeta = formatExercisePrescriptionMeta(exercise);
                        return (
                          <div key={exercise.prescription_exercise_id} className="prescription-exercise-item">
                            <strong>{exercise.exercise_name}</strong>
                            {exerciseMeta.length > 0 ? (
                              <div className="session-exercise-meta">
                                {exerciseMeta.map((item) => (
                                  <span key={`${exercise.prescription_exercise_id}-${item}`}>{item}</span>
                                ))}
                              </div>
                            ) : null}
                            {exercise.notes ? <p>{exercise.notes}</p> : null}
                            {exercise.options.length > 0 ? (
                              <div className="prescription-option-list">
                                {exercise.options.map((option) => (
                                  <small key={option.exercise_option_id}>
                                    Alternativa: {option.option_name}
                                    {option.equipment ? ` · ${option.equipment}` : ""}
                                    {option.condition_notes ? ` · ${option.condition_notes}` : ""}
                                  </small>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}

function getSessionPrimaryText(session: Session) {
  return formatPlannedPrescriptionBlocks(session.planned_prescription, "primary") ?? formatPlannedActivityGroups(session.planned_activity_groups, "primary") ?? session.primary_session;
}

function getSessionSupportText(session: Session) {
  return formatPlannedPrescriptionBlocks(session.planned_prescription, "support") ?? formatPlannedActivityGroups(session.planned_activity_groups, "support") ?? session.complementary_session ?? "-";
}

function getPlanVsRealPlannedText(row: PlanVsRealRow) {
  return formatPlannedPrescriptionBlocks(row.planned_prescription) ?? formatPlannedActivityGroups(row.planned_activity_groups) ?? row.planned_session;
}

function toPlannedRoleLabel(plannedRole: string | null) {
  if (!plannedRole) {
    return "-";
  }

  const labels: Record<string, string> = {
    activacion: "Activacion",
    "activacion-neuromuscular": "Activacion neuromuscular",
    complementaria: "Complementaria",
    fuerza: "Fuerza",
    "desarrollo-de-fuerza": "Desarrollo de fuerza",
    "potencia-aerobica": "Potencia aerobica",
    recuperacion: "Recuperacion",
    "resistencia-aerobica-extensiva": "Resistencia aerobica extensiva",
    "resistencia-aerobica-principal": "Resistencia aerobica principal",
    "resistencia-aerobica-secundaria": "Resistencia aerobica secundaria",
    "resistencia-aerobica-suave": "Resistencia aerobica suave",
    "referencia-aerobica": "Referencia aerobica",
    "salida-larga": "Salida larga",
  };
  return labels[plannedRole] ?? plannedRole;
}

function toSourceLabel(sourceSystem: string) {
  if (sourceSystem === "garmin") {
    return "Garmin Connect";
  }
  if (isManualSource(sourceSystem)) {
    return "Registro manual";
  }
  return sourceSystem;
}

function toSourceChipClass(sourceSystem: string) {
  if (sourceSystem === "garmin") {
    return "source-chip source-chip-garmin";
  }
  if (isManualSource(sourceSystem)) {
    return "source-chip source-chip-manual";
  }
  return "source-chip";
}

function toActivityTypeLabel(activityType: string | null, sourceSystem: string) {
  if (!activityType) {
    return "Sin tipo";
  }
  if (!isManualSource(sourceSystem)) {
    return activityType;
  }
  return activityType
    .split(/[-_]+/)
    .map((chunk) => (chunk.toLowerCase() === "z2" ? "Z2" : `${chunk.charAt(0).toUpperCase()}${chunk.slice(1)}`))
    .join(" ");
}

function getPlanVsRealActivities(row: PlanVsRealRow): PlanVsRealActivity[] {
  if (row.activities && row.activities.length > 0) {
    return row.activities;
  }

  if (!row.activity_id) {
    return [];
  }

  return [
    {
      activity_id: row.activity_id,
      actual_activity_type: row.actual_activity_type,
      actual_link_type: row.actual_link_type,
      actual_source_system: row.actual_source_system,
      actual_discipline: row.actual_discipline,
      compatible_garmin_count: row.compatible_garmin_count,
      actual_duration_min: row.actual_duration_min,
      perceived_exertion: row.perceived_exertion,
    },
  ];
}

function toPlanVsRealActivityLabel(activity: PlanVsRealActivity) {
  if (!activity.actual_activity_type) {
    return "Sin actividad";
  }
  return toActivityTypeLabel(activity.actual_activity_type, activity.actual_source_system ?? "");
}

function toPlanVsRealMetaLabel(activity: PlanVsRealActivity) {
  const parts = [
    activity.actual_source_system ? toSourceLabel(activity.actual_source_system) : null,
    activity.actual_discipline ? toDisciplineLabel(activity.actual_discipline) : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function toPlanVsRealResolutionLabel(activity: PlanVsRealActivity) {
  if (activity.actual_link_type === "garmin_auto") {
    return "Garmin autoenlazado";
  }
  if ((activity.actual_source_system ?? "").startsWith("manual") && activity.compatible_garmin_count > 0) {
    return activity.compatible_garmin_count === 1
      ? "Garmin disponible sin emparejar"
      : `Garmin disponible sin emparejar (${activity.compatible_garmin_count})`;
  }
  return null;
}

function getOtherDailyActivities(row: PlanVsRealRow): DailyUnlinkedActivity[] {
  return row.other_daily_activities ?? [];
}

function toOptionalDailyLabel(activity: OptionalDailyActivity) {
  if (activity.actual_discipline === "strength_training") {
    return "Fuerza opcional";
  }
  return "Opcional del dia";
}

function toSupportDailyLabel(activity: OptionalDailyActivity) {
  if (activity.actual_discipline === "yoga") {
    return "Flexibilidad de soporte";
  }
  return "Soporte del dia";
}

function toOptionalDailyMetaLabel(activity: OptionalDailyActivity) {
  const parts = [
    activity.started_at ? toDateTimeLabel(activity.started_at) : null,
    activity.actual_source_system ? toSourceLabel(activity.actual_source_system) : null,
    activity.actual_discipline ? toDisciplineLabel(activity.actual_discipline) : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function toOtherDailyLabel(activity: DailyUnlinkedActivity) {
  if (activity.actual_discipline === "road_biking" || activity.actual_discipline === "indoor_cycling") {
    return "Actividad aeróbica adicional";
  }
  if (activity.actual_discipline === "hiking" || activity.actual_discipline === "walking") {
    return "Actividad adicional de campo";
  }
  return "Otra actividad del dia";
}

function toOtherDailyMetaLabel(activity: DailyUnlinkedActivity) {
  const parts = [
    activity.started_at ? toDateTimeLabel(activity.started_at) : null,
    activity.actual_source_system ? toSourceLabel(activity.actual_source_system) : null,
    activity.actual_discipline ? toDisciplineLabel(activity.actual_discipline) : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function toPowerLabel(value: number | null) {
  return value == null ? "-" : `${Math.round(value)} W`;
}

function toPaceLabel(secondsPerKm: number | null) {
  if (secondsPerKm == null) {
    return "-";
  }
  const totalSeconds = Math.round(secondsPerKm);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")} /km`;
}

function toPowerSummary(activity: ActivityDetail) {
  const parts: string[] = [];
  if (activity.avg_power != null) {
    parts.push(`${toPowerLabel(activity.avg_power)} media`);
  }
  if (activity.normalized_power != null) {
    parts.push(`${toPowerLabel(activity.normalized_power)} NP`);
  }
  return parts.length > 0 ? parts.join(" · ") : "-";
}

function toPowerSensorProfileLabel(profile: string | null) {
  if (!profile) {
    return "-";
  }
  if (profile === "pedal_power_meter") {
    return "Potenciometro de pedal";
  }
  if (profile === "non_pedal_bike_power_meter") {
    return "Potenciometro no pedal";
  }
  return profile.replace(/_/g, " ");
}

function toTrainingLoadHeading(_activity: Pick<ActivityDetail, "source_system" | "calculated_training_load_source">) {
  return "Carga usada en modelo";
}

function toTrainingLoadSourceLabel(source: string | null | undefined) {
  if (source === "power_tss") {
    return "Fuente: Power TSS";
  }
  if (source === "hr_trimp") {
    return "Fuente: HR TRIMP";
  }
  if (source === "respiration_rate_heuristic") {
    return "Fuente: heuristica por respiracion";
  }
  if (source === "strength_duration_heuristic") {
    return "Fuente: heuristica por duracion de fuerza";
  }
  if (source === "mobility_duration_heuristic") {
    return "Fuente: heuristica por duracion de movilidad";
  }
  if (source === "garmin_training_load") {
    return "Fuente: fallback Garmin";
  }
  if (source === "no_load_signal") {
    return "Fuente: sin senal util de carga";
  }
  return "Fuente: calculo interno";
}

function isPaceDiscipline(discipline: string | null) {
  return discipline != null && ["running", "trail_running", "treadmill_running", "walking", "hiking", "trail_walking", "nordic_walking"].includes(discipline);
}

const RUNNING_DYNAMICS_METRIC_ORDER = [
  "cadence_double",
  "run_cadence",
  "ground_contact_time",
  "ground_contact_balance_left",
  "vertical_oscillation",
  "vertical_ratio",
  "stride_length",
  "performance_condition",
  "speed",
  "vertical_speed",
  "air_temperature",
] as const;

function isRunningDiscipline(discipline: string | null) {
  return discipline != null && ["running", "trail_running", "treadmill_running"].includes(discipline);
}

function isRunningDynamicsMetric(metricName: string) {
  return RUNNING_DYNAMICS_METRIC_ORDER.includes(metricName as (typeof RUNNING_DYNAMICS_METRIC_ORDER)[number]);
}

function normalizeRunningDynamicsMetricValue(metricName: string, value: number | null) {
  if (value == null) {
    return null;
  }
  if (metricName === "stride_length" && value > 10) {
    return value / 100;
  }
  return value;
}

function getQualitySummaryValue(metric: ActivityQualityMetric, summaryKind = "average") {
  const summary = metric.summary_impacts.find((item) => item.summary_kind === summaryKind);
  return normalizeRunningDynamicsMetricValue(metric.metric_name, summary?.trusted_value ?? null);
}

function getRunningDynamicsBaselineValue(history: RunningDynamicsHistoryResponse | null, metricName: string) {
  return normalizeRunningDynamicsMetricValue(metricName, history?.baseline_metrics[metricName] ?? null);
}

function getRunningDynamicsMetrics(detail: ActivityQualityDetail | null) {
  if (!detail) {
    return [];
  }
  const metrics = detail.metrics.filter((metric) => isRunningDynamicsMetric(metric.metric_name));
  metrics.sort((left, right) => {
    const leftIndex = RUNNING_DYNAMICS_METRIC_ORDER.indexOf(left.metric_name as (typeof RUNNING_DYNAMICS_METRIC_ORDER)[number]);
    const rightIndex = RUNNING_DYNAMICS_METRIC_ORDER.indexOf(right.metric_name as (typeof RUNNING_DYNAMICS_METRIC_ORDER)[number]);
    return leftIndex - rightIndex;
  });
  return metrics;
}

function buildRunningDynamicsInsights(activity: ActivityDetail, detail: ActivityQualityDetail | null) {
  const metrics = getRunningDynamicsMetrics(detail);
  if (metrics.length === 0) {
    return [];
  }

  const metricMap = new Map(metrics.map((metric) => [metric.metric_name, metric]));
  const average = (metricName: string) => {
    const metric = metricMap.get(metricName);
    return metric ? getQualitySummaryValue(metric) : null;
  };

  const insights: string[] = [];
  const cadenceDouble = average("cadence_double");
  const runCadence = average("run_cadence");
  const totalCadence = cadenceDouble ?? (runCadence != null ? runCadence * 2 : null);
  if (totalCadence != null) {
    if (isRunningDiscipline(activity.discipline)) {
      if (totalCadence < 160) {
        insights.push(`Cadencia total ${toMetricLabel(totalCadence, " spm")}: apoyo relativamente pausado para carrera.`);
      } else if (totalCadence <= 180) {
        insights.push(`Cadencia total ${toMetricLabel(totalCadence, " spm")}: rango funcional y estable para carrera aeróbica.`);
      } else {
        insights.push(`Cadencia total ${toMetricLabel(totalCadence, " spm")}: frecuencia alta, compatible con apoyo rápido.`);
      }
    } else if (totalCadence < 110) {
      insights.push(`Cadencia total ${toMetricLabel(totalCadence, " spm")}: caminata relajada, más de paseo que de activación viva.`);
    } else if (totalCadence <= 130) {
      insights.push(`Cadencia total ${toMetricLabel(totalCadence, " spm")}: caminata ágil y útil como locomoción aeróbica suave.`);
    } else {
      insights.push(`Cadencia total ${toMetricLabel(totalCadence, " spm")}: caminata muy viva, cercana a marcha rápida.`);
    }
  }

  const groundContactTime = average("ground_contact_time");
  if (groundContactTime != null) {
    if (groundContactTime < 250) {
      insights.push(`Tiempo de contacto ${toMetricLabel(groundContactTime, " ms")}: apoyo breve.`);
    } else if (groundContactTime <= 300) {
      insights.push(`Tiempo de contacto ${toMetricLabel(groundContactTime, " ms")}: apoyo intermedio, sin señal clara de pesadez.`);
    } else {
      insights.push(`Tiempo de contacto ${toMetricLabel(groundContactTime, " ms")}: apoyo largo, compatible con fatiga o gesto pesado.`);
    }
  }

  const balanceLeft = average("ground_contact_balance_left");
  if (balanceLeft != null) {
    const asymmetry = Math.abs(balanceLeft - 50);
    if (asymmetry <= 1) {
      insights.push(`Balance de contacto ${toMetricLabel(balanceLeft, "% izq")}: reparto muy equilibrado.`);
    } else if (asymmetry <= 2) {
      insights.push(`Balance de contacto ${toMetricLabel(balanceLeft, "% izq")}: ligera asimetría, vigilable pero no alarmante.`);
    } else {
      insights.push(`Balance de contacto ${toMetricLabel(balanceLeft, "% izq")}: asimetría visible que conviene seguir.`);
    }
  }

  const verticalRatio = average("vertical_ratio");
  if (verticalRatio != null) {
    if (verticalRatio < 8.5) {
      insights.push(`Ratio vertical ${toMetricLabel(verticalRatio, "%")}: rebote contenido para la velocidad observada.`);
    } else if (verticalRatio <= 10) {
      insights.push(`Ratio vertical ${toMetricLabel(verticalRatio, "%")}: economía media, sin penalización clara.`);
    } else {
      insights.push(`Ratio vertical ${toMetricLabel(verticalRatio, "%")}: rebote relativamente alto para el avance generado.`);
    }
  }

  const performanceCondition = average("performance_condition");
  if (performanceCondition != null) {
    if (performanceCondition >= 2) {
      insights.push(`Performance condition ${toMetricLabel(performanceCondition)}: señal positiva de frescura.`);
    } else if (performanceCondition <= -3) {
      insights.push(`Performance condition ${toMetricLabel(performanceCondition)}: señal negativa, compatible con fatiga o mal día.`);
    }
  }

  if (insights.length === 0) {
    insights.push("Garmin ha entregado métricas de dinámica, pero en esta actividad solo aportan contexto descriptivo y no una señal técnica fuerte.");
  }

  const missingFullDynamics = [
    "ground_contact_time",
    "ground_contact_balance_left",
    "vertical_oscillation",
    "vertical_ratio",
    "stride_length",
  ].every((metricName) => average(metricName) == null);
  if (missingFullDynamics) {
    insights.push("En esta actividad Garmin no expone el bloque completo de running dynamics; aquí solo se muestran las señales parciales realmente disponibles.");
  }

  return insights;
}

function buildRunningDynamicsHistoryInsights(detail: ActivityQualityDetail | null, history: RunningDynamicsHistoryResponse | null) {
  if (!detail || !history || history.compared_activity_count === 0) {
    return [];
  }

  const metricMap = new Map(getRunningDynamicsMetrics(detail).map((metric) => [metric.metric_name, metric]));
  const current = (metricName: string) => {
    const metric = metricMap.get(metricName);
    return metric ? getQualitySummaryValue(metric) : null;
  };
  const baseline = (metricName: string) => getRunningDynamicsBaselineValue(history, metricName);

  const insights: string[] = [];

  const cadenceDelta = (current("cadence_double") ?? 0) - (baseline("cadence_double") ?? 0);
  if (current("cadence_double") != null && baseline("cadence_double") != null && Math.abs(cadenceDelta) >= 4) {
    insights.push(
      cadenceDelta > 0
        ? `Cadencia total ${formatQualityMetricValue("cadence_double", Math.abs(cadenceDelta))} por encima de tu base reciente.`
        : `Cadencia total ${formatQualityMetricValue("cadence_double", Math.abs(cadenceDelta))} por debajo de tu base reciente.`,
    );
  }

  const contactDelta = (current("ground_contact_time") ?? 0) - (baseline("ground_contact_time") ?? 0);
  if (current("ground_contact_time") != null && baseline("ground_contact_time") != null && Math.abs(contactDelta) >= 10) {
    insights.push(
      contactDelta > 0
        ? `Tiempo de contacto ${formatQualityMetricValue("ground_contact_time", Math.abs(contactDelta))} por encima de tu base reciente.`
        : `Tiempo de contacto ${formatQualityMetricValue("ground_contact_time", Math.abs(contactDelta))} por debajo de tu base reciente.`,
    );
  }

  const verticalRatioDelta = (current("vertical_ratio") ?? 0) - (baseline("vertical_ratio") ?? 0);
  if (current("vertical_ratio") != null && baseline("vertical_ratio") != null && Math.abs(verticalRatioDelta) >= 0.5) {
    insights.push(
      verticalRatioDelta > 0
        ? `Ratio vertical ${formatQualityMetricValue("vertical_ratio", Math.abs(verticalRatioDelta))} por encima de tu base reciente.`
        : `Ratio vertical ${formatQualityMetricValue("vertical_ratio", Math.abs(verticalRatioDelta))} por debajo de tu base reciente.`,
    );
  }

  const strideDelta = (current("stride_length") ?? 0) - (baseline("stride_length") ?? 0);
  if (current("stride_length") != null && baseline("stride_length") != null && Math.abs(strideDelta) >= 0.05) {
    insights.push(
      strideDelta > 0
        ? `Longitud de zancada ${formatQualityMetricValue("stride_length", Math.abs(strideDelta))} por encima de tu base reciente.`
        : `Longitud de zancada ${formatQualityMetricValue("stride_length", Math.abs(strideDelta))} por debajo de tu base reciente.`,
    );
  }

  return insights.slice(0, 3);
}

function isDistanceRelevant(activity: ActivityDetail) {
  return activity.distance_meters != null && activity.distance_meters > 0;
}

function isAscentRelevant(activity: ActivityDetail) {
  return activity.ascent_meters != null && activity.ascent_meters > 0;
}

function isPowerRelevant(activity: ActivityDetail) {
  return activity.avg_power != null || activity.normalized_power != null;
}

function isHeartRateRelevant(activity: ActivityDetail) {
  return activity.avg_hr != null || activity.max_hr != null;
}

function isDistanceRelevantInList(activity: ActivityListItem) {
  return activity.distance_meters != null && activity.distance_meters > 0;
}

function isPowerRelevantInList(activity: ActivityListItem) {
  return activity.avg_power != null || activity.normalized_power != null;
}

function isHeartRateRelevantInList(activity: ActivityListItem) {
  return activity.avg_hr != null || activity.max_hr != null;
}

function formatQualityStatusLabel(status: string | null) {
  if (status === "clean") {
    return "calidad limpia";
  }
  if (status === "filtered") {
    return "filtrada";
  }
  if (status === "limited") {
    return "limitada";
  }
  if (status === "not_checked") {
    return "sin revisar";
  }
  return "sin revisar";
}

function toQualityBadgeClass(status: string | null) {
  if (status === "clean") {
    return "badge badge-completed";
  }
  if (status === "filtered") {
    return "badge badge-partial";
  }
  if (status === "limited") {
    return "badge badge-failed";
  }
  return "badge badge-pending";
}

function formatMetricNameLabel(metricName: string) {
  if (metricName === "heart_rate") {
    return "Frecuencia cardiaca";
  }
  if (metricName === "respiration_rate") {
    return "Respiracion";
  }
  if (metricName === "power") {
    return "Potencia";
  }
  if (metricName === "bike_cadence") {
    return "Cadencia";
  }
  if (metricName === "run_cadence") {
    return "Cadencia carrera";
  }
  if (metricName === "cadence_double") {
    return "Cadencia total";
  }
  if (metricName === "cadence_fractional") {
    return "Cadencia fraccional";
  }
  if (metricName === "vertical_ratio") {
    return "Ratio vertical";
  }
  if (metricName === "ground_contact_time") {
    return "Tiempo de contacto";
  }
  if (metricName === "ground_contact_balance_left") {
    return "Balance contacto izq";
  }
  if (metricName === "vertical_oscillation") {
    return "Oscilacion vertical";
  }
  if (metricName === "stride_length") {
    return "Longitud de zancada";
  }
  if (metricName === "performance_condition") {
    return "Performance condition";
  }
  if (metricName === "air_temperature") {
    return "Temperatura";
  }
  if (metricName === "speed") {
    return "Velocidad";
  }
  if (metricName === "elevation") {
    return "Altitud";
  }
  if (metricName === "vertical_speed") {
    return "Velocidad vertical";
  }
  return metricName;
}

function formatQualitySummaryKindLabel(summaryKind: string) {
  if (summaryKind === "average") {
    return "Media";
  }
  if (summaryKind === "maximum") {
    return "Maximo";
  }
  return summaryKind;
}

function formatZoneBasisShortLabel(metricBasis: "heart_rate" | "power") {
  if (metricBasis === "heart_rate") {
    return "FC";
  }
  return "Pot";
}

function formatZoneBasisLabel(metricBasis: string | null | undefined) {
  if (metricBasis === "heart_rate") {
    return "FC";
  }
  if (metricBasis === "power") {
    return "Potencia";
  }
  return metricBasis ?? "Sin base";
}

function formatPlannedZoneTargetLabel(target: PlannedZoneTarget | null | undefined) {
  if (!target) {
    return null;
  }
  const segments = target.segments.map((segment) => {
    const minCode = segment.target_zone_min_code;
    const maxCode = segment.target_zone_max_code;
    if (!minCode && !maxCode) {
      return null;
    }
    if (minCode && maxCode && minCode !== maxCode) {
      return `${minCode}-${maxCode}`;
    }
    return minCode ?? maxCode;
  }).filter(Boolean);
  if (segments.length === 0) {
    return null;
  }
  return `${formatZoneBasisLabel(target.target_basis)} · ${segments.join(" → ")}`;
}

function formatZoneComparisonStatusLabel(status: string) {
  if (status === "aligned") {
    return "alineada";
  }
  if (status === "misaligned") {
    return "desalineada";
  }
  if (status === "limited") {
    return "limitada";
  }
  if (status === "not_comparable") {
    return "no comparable";
  }
  return status;
}

function formatZoneBoundaryLabel(boundary: ZoneProfileBoundary) {
  const zoneLabel = boundary.zone_name && boundary.zone_name !== boundary.zone_code
    ? `${boundary.zone_code} ${boundary.zone_name}`
    : boundary.zone_code;
  const lower = boundary.lower_bound_value != null ? Math.round(boundary.lower_bound_value) : null;
  const upper = boundary.upper_bound_value != null ? Math.round(boundary.upper_bound_value) : null;
  if (lower != null && upper != null) {
    return `${zoneLabel}: ${lower}-${upper} ${boundary.bound_unit}`;
  }
  if (lower != null) {
    return `${zoneLabel}: >= ${lower} ${boundary.bound_unit}`;
  }
  if (upper != null) {
    return `${zoneLabel}: <= ${upper} ${boundary.bound_unit}`;
  }
  return zoneLabel;
}

function formatQualityMetricValue(metricName: string, value: number | null) {
  const normalizedValue = normalizeRunningDynamicsMetricValue(metricName, value);
  if (metricName === "heart_rate") {
    return toMetricLabel(normalizedValue, " bpm");
  }
  if (metricName === "respiration_rate") {
    return toMetricLabel(normalizedValue, " rpm resp");
  }
  if (metricName === "power") {
    return toMetricLabel(normalizedValue, " W");
  }
  if (metricName === "bike_cadence") {
    return toMetricLabel(normalizedValue, " rpm");
  }
  if (metricName === "run_cadence") {
    return toMetricLabel(normalizedValue, " rpm");
  }
  if (metricName === "cadence_double") {
    return toMetricLabel(normalizedValue, " spm");
  }
  if (metricName === "cadence_fractional") {
    return toMetricLabel(normalizedValue);
  }
  if (metricName === "vertical_ratio") {
    return toMetricLabel(normalizedValue, "%");
  }
  if (metricName === "ground_contact_time") {
    return toMetricLabel(normalizedValue, " ms");
  }
  if (metricName === "ground_contact_balance_left") {
    return toMetricLabel(normalizedValue, "% izq");
  }
  if (metricName === "vertical_oscillation") {
    return toMetricLabel(normalizedValue, " cm");
  }
  if (metricName === "stride_length") {
    return toMetricLabel(normalizedValue, " m");
  }
  if (metricName === "air_temperature") {
    return toMetricLabel(normalizedValue, " C");
  }
  if (metricName === "speed" || metricName === "vertical_speed") {
    return toMetricLabel(normalizedValue, " m/s");
  }
  return toMetricLabel(normalizedValue);
}

function formatMetricProfileModelLabel(modelKey: string | null | undefined) {
  if (modelKey === "heart_rate_reserve_5_zone") {
    return "FC por reserva cardiaca";
  }
  if (modelKey === "ftp_coggan_7_zone") {
    return "Potencia por FTP";
  }
  return modelKey ?? "modelo no definido";
}

function toPhysiologicalAnchorsFormState(currentProfiles: CurrentZoneProfilesResponse | null, fallbackDate: string) {
  const heartRateProfile = currentProfiles?.profiles.heart_rate?.metric_profile;
  const powerProfile = currentProfiles?.profiles.power?.metric_profile;
  return {
    effective_start_date: fallbackDate,
    resting_hr: heartRateProfile?.parameters.resting_hr != null ? String(Math.round(heartRateProfile.parameters.resting_hr)) : "",
    max_hr: heartRateProfile?.parameters.max_hr != null ? String(Math.round(heartRateProfile.parameters.max_hr)) : "",
    ftp: powerProfile?.parameters.ftp != null ? String(Math.round(powerProfile.parameters.ftp)) : "",
    notes: "",
  };
}

function formatActivityZoneSummaryLabel(zoneSummary: ActivityZoneSummary | null | undefined) {
  if (!zoneSummary) {
    return null;
  }

  const orderedBases: Array<"heart_rate" | "power"> = ["heart_rate", "power"];
  const parts = orderedBases.flatMap((metricBasis) => {
    const summary = zoneSummary[metricBasis];
    if (!summary) {
      return [];
    }

    const basisLabel = formatZoneBasisShortLabel(metricBasis);
    if (summary.calculation_status === "calculated") {
      const zoneCode = summary.dominant_zone_code ?? "sin zona";
      const shareLabel = summary.dominant_zone_share != null ? ` ${toPercentLabel(summary.dominant_zone_share)}` : "";
      return [`${basisLabel} ${zoneCode}${shareLabel}`];
    }
    if (summary.calculation_status === "limited") {
      return [`${basisLabel} limitada`];
    }
    if (summary.calculation_status === "unavailable") {
      return [`${basisLabel} sin datos`];
    }
    return [`${basisLabel} ${summary.calculation_status}`];
  });

  if (parts.length === 0) {
    return null;
  }
  return `Zonas: ${parts.join(" · ")}`;
}

function formatQualityDecisionReason(reasonCode: string) {
  if (reasonCode === "hr_above_hard_cap") {
    return "FC por encima del techo duro";
  }
  return reasonCode;
}

function formatQualitySampleRange(startSampleIndex: number, endSampleIndex: number) {
  const start = startSampleIndex + 1;
  const end = endSampleIndex + 1;
  if (start === end) {
    return `muestra ${start}`;
  }
  return `muestras ${start}-${end}`;
}

function formatActivityQualityCompact(activity: Pick<ActivityListItem, "quality_decision_count" | "quality_limited_metric_count" | "quality_checked_at">) {
  const parts: string[] = [];
  if ((activity.quality_decision_count ?? 0) > 0) {
    parts.push(`${activity.quality_decision_count} decisiones`);
  }
  if ((activity.quality_limited_metric_count ?? 0) > 0) {
    parts.push(`${activity.quality_limited_metric_count} metricas limitadas`);
  }
  if (activity.quality_checked_at) {
    parts.push(`rev. ${toDateTimeLabel(activity.quality_checked_at)}`);
  }
  return parts.join(" · ") || "Sin detalle adicional";
}

function toHumanLabel(value: string | null | undefined) {
  if (!value) {
    return "Sin dato";
  }
  return value
    .split(/[_-]+/)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
}

function toCadenceLabel(value: string) {
  if (value === "daily") {
    return "Diaria";
  }
  if (value === "weekly") {
    return "Semanal";
  }
  if (value === "block") {
    return "Bloque";
  }
  if (value === "season") {
    return "Temporada";
  }
  return toHumanLabel(value);
}

function toReviewStatusLabel(value: string) {
  if (value === "no_new_data") {
    return "sin datos nuevos";
  }
  if (value === "partial_context") {
    return "contexto parcial";
  }
  return value.replace(/_/g, " ");
}

function toReviewBadgeClass(value: string) {
  if (["completed", "accepted"].includes(value)) {
    return "badge badge-completed";
  }
  if (["partial_context", "superseded"].includes(value)) {
    return "badge badge-partial";
  }
  if (["failed", "rejected", "critical"].includes(value)) {
    return "badge badge-failed";
  }
  if (["warning", "watch"].includes(value)) {
    return "badge badge-partial";
  }
  return "badge badge-pending";
}

function toConfidenceLabel(value: string | null | undefined) {
  if (value === "high") {
    return "Confianza alta";
  }
  if (value === "medium") {
    return "Confianza media";
  }
  if (value === "limited") {
    return "Confianza limitada";
  }
  return "Sin confianza";
}

export default function App() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [weeks, setWeeks] = useState<Week[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [planVsRealRows, setPlanVsRealRows] = useState<PlanVsRealRow[]>([]);
  const [selectedPlannedSessionId, setSelectedPlannedSessionId] = useState<number | null>(null);
  const [selectedPlannedSessionPrescription, setSelectedPlannedSessionPrescription] = useState<PlannedPrescription | null>(null);

  const [selectedSeason, setSelectedSeason] = useState<Season | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<Block | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<Week | null>(null);
  const [blockReview, setBlockReview] = useState<BlockReview | null>(null);
  const [weeklyReview, setWeeklyReview] = useState<WeeklyReview | null>(null);
  const [weightReview, setWeightReview] = useState<WeightReview | null>(null);
  const [selectedActivity, setSelectedActivity] = useState<ActivityDetail | null>(null);
  const [selectedActivityQuality, setSelectedActivityQuality] = useState<ActivityQualityDetail | null>(null);
  const [selectedActivityRunningDynamicsHistory, setSelectedActivityRunningDynamicsHistory] = useState<RunningDynamicsHistoryResponse | null>(null);
  const [seasonActivities, setSeasonActivities] = useState<ActivityListItem[]>([]);
  const [zoneProposals, setZoneProposals] = useState<ZoneProposalItem[]>([]);
  const [currentZoneProfiles, setCurrentZoneProfiles] = useState<CurrentZoneProfilesResponse | null>(null);
  const [physiologicalAnchorsForm, setPhysiologicalAnchorsForm] = useState<PhysiologicalAnchorsFormState>(emptyPhysiologicalAnchorsForm);
  const [selectedDailyMetric, setSelectedDailyMetric] = useState<DailyMetricDetail | null>(null);
  const [selectedDailyMetricDate, setSelectedDailyMetricDate] = useState<string | null>(null);
  const [selectedDailyAssessment, setSelectedDailyAssessment] = useState<DailyAssessmentView | null>(null);
  const [selectedBlockAssessmentMarkdown, setSelectedBlockAssessmentMarkdown] = useState<string | null>(null);
  const [selectedWeeklyAssessmentMarkdown, setSelectedWeeklyAssessmentMarkdown] = useState<string | null>(null);
  const [selectedWeightAssessmentMarkdown, setSelectedWeightAssessmentMarkdown] = useState<string | null>(null);
  const [submissionMessage, setSubmissionMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importJobs, setImportJobs] = useState<ImportJob[]>([]);
  const [garminStatus, setGarminStatus] = useState<GarminConnectStatus | null>(null);
  const [importForm, setImportForm] = useState<GarminImportFormState>(emptyGarminImportForm);
  const [importPreview, setImportPreview] = useState<GarminImportPreview | null>(null);
  const [segments, setSegments] = useState<SegmentListItem[]>([]);
  const [segmentHistoryLimit, setSegmentHistoryLimit] = useState<number>(20);
  const [selectedSegmentId, setSelectedSegmentId] = useState<number | null>(null);
  const [selectedSegmentHistory, setSelectedSegmentHistory] = useState<SegmentHistoryResponse | null>(null);
  const [importing, setImporting] = useState(false);
  const [previewingImport, setPreviewingImport] = useState(false);
  const [loadingSegments, setLoadingSegments] = useState(false);
  const [loadingSegmentHistory, setLoadingSegmentHistory] = useState(false);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [loadingActivityQuality, setLoadingActivityQuality] = useState(false);
  const [loadingSeasonActivities, setLoadingSeasonActivities] = useState(false);
  const [loadingDailyMetric, setLoadingDailyMetric] = useState(false);
  const [loadingDailyAssessment, setLoadingDailyAssessment] = useState(false);
  const [loadingBlockAssessment, setLoadingBlockAssessment] = useState(false);
  const [loadingWeeklyAssessment, setLoadingWeeklyAssessment] = useState(false);
  const [loadingWeightAssessment, setLoadingWeightAssessment] = useState(false);
  const [loadingActivityWeather, setLoadingActivityWeather] = useState(false);
  const [loadingSelectedPlannedSessionPrescription, setLoadingSelectedPlannedSessionPrescription] = useState(false);
  const [loading, setLoading] = useState(false);
  const [savingWeeklyReview, setSavingWeeklyReview] = useState(false);
  const [replayingActivityQuality, setReplayingActivityQuality] = useState(false);
  const [savingPhysiologicalAnchors, setSavingPhysiologicalAnchors] = useState(false);

  useEffect(() => {
    void loadSeasons();
    void loadImportJobs();
    void loadGarminStatus();
  }, []);

  const sessionDetailRef = useRef<HTMLDivElement | null>(null);
  const selectedPlannedSession = sessions.find((session) => session.planned_session_id === selectedPlannedSessionId) ?? null;
  const selectedPlanVsRealRow = planVsRealRows.find((row) => row.planned_session_id === selectedPlannedSessionId) ?? null;
  const selectedPlannedSessionActivities = selectedPlanVsRealRow ? getPlanVsRealActivities(selectedPlanVsRealRow) : [];
  const selectedLinkedActivity = selectedPlannedSessionActivities.length === 1 ? selectedPlannedSessionActivities[0] : null;

  useEffect(() => {
    if (selectedPlannedSessionId == null) {
      setSelectedPlannedSessionPrescription(null);
      setLoadingSelectedPlannedSessionPrescription(false);
      return;
    }
    const session = sessions.find((item) => item.planned_session_id === selectedPlannedSessionId);
    if (!session) {
      setSelectedPlannedSessionPrescription(null);
      setLoadingSelectedPlannedSessionPrescription(false);
      return;
    }

    let cancelled = false;
    setSelectedPlannedSessionPrescription(session.planned_prescription ?? null);
    setLoadingSelectedPlannedSessionPrescription(true);

    void fetchJson<PlannedPrescription>(`/api/planned-sessions/${selectedPlannedSessionId}/prescription`)
      .then((payload) => {
        if (!cancelled) {
          setSelectedPlannedSessionPrescription(payload);
        }
      })
      .catch((requestError) => {
        if (cancelled) {
          return;
        }
        if (isNotFoundError(requestError)) {
          setSelectedPlannedSessionPrescription(session.planned_prescription ?? null);
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Error desconocido");
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingSelectedPlannedSessionPrescription(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedPlannedSessionId, sessions]);

  useEffect(() => {
    if (!selectedSeason || !selectedDailyMetricDate) {
      setSelectedDailyMetric(null);
      return;
    }
    void loadDailyMetric(selectedSeason.season_id, selectedDailyMetricDate);
  }, [selectedSeason, selectedDailyMetricDate]);

  async function loadGarminStatus() {
    try {
      const data = await fetchJson<GarminConnectStatus>("/api/imports/garmin-connect/status");
      setGarminStatus(data);
    } catch {
      setGarminStatus(null);
    }
  }

  async function loadImportJobs() {
    try {
      const data = await fetchJson<ImportJob[]>("/api/import-jobs");
      setImportJobs(data);
    } catch {
      setImportJobs([]);
    }
  }

  async function loadZoneProposals(seasonId: number) {
    try {
      const payload = await fetchJson<ZoneProposalListResponse>(`/api/seasons/${seasonId}/zone-proposals?discipline=cycling`);
      setZoneProposals(payload.items);
    } catch (requestError) {
      if (isNotFoundError(requestError)) {
        setZoneProposals([]);
        return;
      }
      throw requestError;
    }
  }

  async function loadCurrentZoneProfiles(seasonId: number) {
    try {
      const payload = await fetchJson<CurrentZoneProfilesResponse>(`/api/seasons/${seasonId}/zone-profiles/current?discipline=cycling`);
      setCurrentZoneProfiles(payload);
      setPhysiologicalAnchorsForm((current) => {
        const next = toPhysiologicalAnchorsFormState(payload, current.effective_start_date || getTodayIsoDate());
        return {
          ...next,
          effective_start_date: current.effective_start_date || next.effective_start_date,
          notes: current.notes,
        };
      });
    } catch (requestError) {
      if (isNotFoundError(requestError)) {
        setCurrentZoneProfiles({ season_id: seasonId, discipline: "cycling", profiles: {} });
        setPhysiologicalAnchorsForm((current) => ({
          ...emptyPhysiologicalAnchorsForm(),
          effective_start_date: current.effective_start_date || getTodayIsoDate(),
          notes: current.notes,
        }));
        return;
      }
      throw requestError;
    }
  }

  async function loadSeasons() {
    try {
      setLoading(true);
      setError(null);
      setInfoMessage(null);
      const data = await fetchJson<Season[]>("/api/seasons");
      setSeasons(data);
      if (data[0]) {
        void handleSeasonSelect(data[0]);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  async function loadDailyMetric(seasonId: number, metricDate: string) {
    try {
      setLoadingDailyMetric(true);
      const data = await fetchJson<DailyMetricDetail>(`/api/seasons/${seasonId}/daily-metrics/${metricDate}`);
      setSelectedDailyMetric(data);
    } catch (requestError) {
      if (isNotFoundError(requestError)) {
        setSelectedDailyMetric(null);
        return;
      }
      throw requestError;
    } finally {
      setLoadingDailyMetric(false);
    }
  }

  async function loadSeasonActivities(seasonId: number) {
    try {
      setLoadingSeasonActivities(true);
      const data = await fetchJson<ActivityListItem[]>(`/api/seasons/${seasonId}/activities`);
      setSeasonActivities(data);
      return data;
    } catch (requestError) {
      if (isNotFoundError(requestError)) {
        setSeasonActivities([]);
        return [];
      }
      throw requestError;
    } finally {
      setLoadingSeasonActivities(false);
    }
  }

  async function loadSegmentHistory(segmentId: number, historyLimit: number = segmentHistoryLimit) {
    try {
      setLoadingSegmentHistory(true);
      const data = await fetchJson<SegmentHistoryResponse>(`/api/segments/${segmentId}/history?limit=${historyLimit}`);
      setSelectedSegmentId(segmentId);
      setSelectedSegmentHistory(data);
    } catch (requestError) {
      if (isNotFoundError(requestError)) {
        setSelectedSegmentHistory(null);
        return;
      }
      throw requestError;
    } finally {
      setLoadingSegmentHistory(false);
    }
  }

  async function handleSegmentHistoryLimitChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextLimit = Number(event.target.value);
    setSegmentHistoryLimit(nextLimit);
    if (selectedSegmentId != null) {
      await loadSegmentHistory(selectedSegmentId, nextLimit);
    }
  }

  async function loadSegments(seasonId: number, preferredSegmentId?: number | null) {
    try {
      setLoadingSegments(true);
      const data = await fetchJson<{ items: SegmentListItem[] }>(`/api/segments?season_id=${seasonId}&limit=24`);
      setSegments(data.items);
      const nextSegmentId =
        preferredSegmentId ??
        (selectedSegmentId != null && data.items.some((segment) => segment.segment_id === selectedSegmentId)
          ? selectedSegmentId
          : data.items[0]?.segment_id ?? null);

      if (nextSegmentId != null) {
        await loadSegmentHistory(nextSegmentId);
      } else {
        setSelectedSegmentId(null);
        setSelectedSegmentHistory(null);
      }
    } catch (requestError) {
      setSegments([]);
      setSelectedSegmentId(null);
      setSelectedSegmentHistory(null);
      if (!isNotFoundError(requestError)) {
        throw requestError;
      }
    } finally {
      setLoadingSegments(false);
    }
  }

  async function handleSeasonSelect(season: Season) {
    try {
      setLoading(true);
      setError(null);
      setInfoMessage(null);
      setSubmissionMessage(null);
      setSelectedSeason(season);
      setSelectedBlock(null);
      setSelectedWeek(null);
      setBlockReview(null);
      setWeeklyReview(null);
      setWeightReview(null);
      setSelectedActivity(null);
      setSelectedActivityQuality(null);
      setSelectedActivityRunningDynamicsHistory(null);
      setSelectedDailyAssessment(null);
      setSelectedBlockAssessmentMarkdown(null);
      setSelectedWeeklyAssessmentMarkdown(null);
      setSelectedWeightAssessmentMarkdown(null);
      setSelectedDailyMetric(null);
      setSelectedDailyMetricDate(null);
      setZoneProposals([]);
      setCurrentZoneProfiles(null);
      setPhysiologicalAnchorsForm(emptyPhysiologicalAnchorsForm);
      setSegments([]);
      setSelectedSegmentId(null);
      setSelectedSegmentHistory(null);
      setSeasonActivities([]);
      setWeeks([]);
      setSessions([]);
      setPlanVsRealRows([]);
      const [data, activities] = await Promise.all([
        fetchJson<Block[]>(`/api/seasons/${season.season_id}/blocks`),
        loadSeasonActivities(season.season_id),
        loadSegments(season.season_id),
        loadZoneProposals(season.season_id),
        loadCurrentZoneProfiles(season.season_id),
        loadWeightReview(season.season_id),
      ]);
      setBlocks(data);
      setImportForm((current) => ({
        ...current,
        ...getSeasonImportDateRange(season, activities),
      }));
      const preferredBlock = pickPreferredBlock(data, getTodayIsoDate());
      if (preferredBlock) {
        await handleBlockSelect(preferredBlock);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  function handlePhysiologicalAnchorsInputChange(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value } = event.target;
    setPhysiologicalAnchorsForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  async function savePhysiologicalAnchorsVersion() {
    if (!selectedSeason) {
      setError("Selecciona una temporada antes de crear una nueva version de anclas fisiologicas.");
      return;
    }

    const restingHr = Number(physiologicalAnchorsForm.resting_hr);
    const maxHr = Number(physiologicalAnchorsForm.max_hr);
    const ftp = Number(physiologicalAnchorsForm.ftp);
    if (!Number.isFinite(restingHr) || !Number.isFinite(maxHr) || !Number.isFinite(ftp)) {
      setError("Introduce HRmin, HRmax y FTP validos para crear la nueva version.");
      return;
    }

    try {
      setSavingPhysiologicalAnchors(true);
      setError(null);
      setSubmissionMessage(null);
      const effectiveStartDate = physiologicalAnchorsForm.effective_start_date || getTodayIsoDate();
      const notes = physiologicalAnchorsForm.notes.trim() || null;
      await Promise.all([
        postJson(`/api/seasons/${selectedSeason.season_id}/zone-metric-profiles/accept`, {
          discipline: "cycling",
          metric_basis: "heart_rate",
          model_key: "heart_rate_reserve_5_zone",
          effective_start_date: effectiveStartDate,
          profile_label: `cycling hr reserve 5 zones ${effectiveStartDate}`,
          resting_hr: restingHr,
          max_hr: maxHr,
          notes,
        }),
        postJson(`/api/seasons/${selectedSeason.season_id}/zone-metric-profiles/accept`, {
          discipline: "cycling",
          metric_basis: "power",
          model_key: "ftp_coggan_7_zone",
          effective_start_date: effectiveStartDate,
          profile_label: `cycling ftp 7 zones ${effectiveStartDate}`,
          ftp,
          notes,
        }),
      ]);
      await loadCurrentZoneProfiles(selectedSeason.season_id);
      setSubmissionMessage(`Nueva version de anclas fisiologicas creada con fecha efectiva ${effectiveStartDate}.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setSavingPhysiologicalAnchors(false);
    }
  }

  async function handleBlockSelect(block: Block) {
    try {
      setLoading(true);
      setError(null);
      setInfoMessage(null);
      setSubmissionMessage(null);
      setSelectedBlock(block);
      setSelectedWeek(null);
      setBlockReview(null);
      setWeeklyReview(null);
      setSelectedActivity(null);
      setSelectedActivityQuality(null);
      setSelectedActivityRunningDynamicsHistory(null);
      setSelectedDailyAssessment(null);
      setSelectedBlockAssessmentMarkdown(null);
      setSelectedWeeklyAssessmentMarkdown(null);
      setSelectedWeightAssessmentMarkdown(null);
      setWeeks([]);
      setSessions([]);
      setPlanVsRealRows([]);
      const [data, review] = await Promise.all([
        fetchJson<Week[]>(`/api/blocks/${block.block_id}/weeks`),
        fetchJson<BlockReview>(`/api/blocks/${block.block_id}/review`),
      ]);
      setWeeks(data);
      setBlockReview(review);
      const preferredWeek = pickPreferredWeek(data, getTodayIsoDate());
      if (preferredWeek) {
        await handleWeekSelect(preferredWeek);
      }
    } catch (requestError) {
      if (isNotFoundError(requestError)) {
        setError(null);
        setInfoMessage(`El bloque ${block.block_code} aun no tiene semanas cargadas en SQLite.`);
        return;
      }
      setError(requestError instanceof Error ? requestError.message : 'Error desconocido');
    } finally {
      setLoading(false);
    }
  }

  async function handleWeekSelect(week: Week) {
    try {
      setLoading(true);
      setError(null);
      setInfoMessage(null);
      setSubmissionMessage(null);
      setSelectedWeek(week);
      setSelectedPlannedSessionId(null);
      setSelectedPlannedSessionPrescription(null);
      setSelectedActivity(null);
      setSelectedActivityQuality(null);
      setSelectedActivityRunningDynamicsHistory(null);
      setSelectedDailyAssessment(null);
      setSelectedWeeklyAssessmentMarkdown(null);
      setSelectedWeightAssessmentMarkdown(null);
      const [sessionData, comparisonData, reviewData] = await Promise.all([
        fetchJson<Session[]>(`/api/weeks/${week.week_id}/sessions`),
        fetchJson<PlanVsRealRow[]>(`/api/weeks/${week.week_id}/plan-vs-real`),
        fetchJson<WeeklyReview>(`/api/weeks/${week.week_id}/review`),
      ]);
      setSessions(sessionData);
      const preferredSession = sessionData.find((session) => session.session_date === getTodayIsoDate())
        ?? sessionData.find((session) => session.is_key_session === 1)
        ?? sessionData[0]
        ?? null;
      setSelectedPlannedSessionId(preferredSession?.planned_session_id ?? null);
      setSelectedPlannedSessionPrescription(preferredSession?.planned_prescription ?? null);
      setPlanVsRealRows(comparisonData);
      setWeeklyReview(reviewData);
      const availableDates = Array.from(new Set([...sessionData.map((session) => session.session_date), ...comparisonData.map((row) => row.session_date)])).sort();
      const defaultMetricDate = availableDates.find((date) => date === getTodayIsoDate()) ?? availableDates[0] ?? week.start_date;
      setSelectedDailyMetricDate(defaultMetricDate);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  function focusPlannedSessionDetail(plannedSessionId: number) {
    setSelectedPlannedSessionId(plannedSessionId);
    requestAnimationFrame(() => {
      sessionDetailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  async function loadDailyAssessment(row: PlanVsRealRow) {
    if (!row.daily_assessment_url || row.daily_review_id == null) {
      return;
    }
    try {
      setLoadingDailyAssessment(true);
      setError(null);
      const markdown = await fetchText(row.daily_assessment_url);
      setSelectedDailyAssessment({
        dailyReviewId: row.daily_review_id,
        sessionDate: row.session_date,
        plannedSession: getPlanVsRealPlannedText(row),
        markdown,
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoadingDailyAssessment(false);
    }
  }

  async function loadWeeklyAssessment() {
    if (!weeklyReview?.weekly_assessment_url) {
      return;
    }
    try {
      setLoadingWeeklyAssessment(true);
      setError(null);
      const markdown = await fetchText(weeklyReview.weekly_assessment_url);
      setSelectedWeeklyAssessmentMarkdown(markdown);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoadingWeeklyAssessment(false);
    }
  }

  async function loadBlockAssessment() {
    if (!blockReview?.block_assessment_url) {
      return;
    }
    try {
      setLoadingBlockAssessment(true);
      setError(null);
      const markdown = await fetchText(blockReview.block_assessment_url);
      setSelectedBlockAssessmentMarkdown(markdown);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoadingBlockAssessment(false);
    }
  }

  async function loadWeightReview(seasonId: number) {
    try {
      const review = await fetchJson<WeightReview>(`/api/seasons/${seasonId}/weight-review/latest`);
      setWeightReview(review);
    } catch (requestError) {
      if (isNotFoundError(requestError)) {
        setWeightReview(null);
        return;
      }
      throw requestError;
    }
  }

  async function loadWeightAssessment() {
    if (!weightReview?.weight_assessment_url) {
      return;
    }
    try {
      setLoadingWeightAssessment(true);
      setError(null);
      const markdown = await fetchText(weightReview.weight_assessment_url);
      setSelectedWeightAssessmentMarkdown(markdown);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoadingWeightAssessment(false);
    }
  }

  function handleImportInputChange(event: ChangeEvent<HTMLInputElement>) {
    const { name, value, type, checked } = event.target;
    setImportForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function previewGarminImport() {
    if (!selectedSeason) {
      setError("Selecciona una temporada antes de previsualizar una importacion Garmin.");
      return;
    }

    try {
      setPreviewingImport(true);
      setError(null);
      setSubmissionMessage(null);
      const response = await fetch("/api/imports/garmin-connect/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          season_id: selectedSeason.season_id,
          date_from: importForm.date_from,
          date_to: importForm.date_to,
          include_daily_metrics: importForm.include_daily_metrics,
        }),
      });
      if (!response.ok) {
        throw new Error(
          formatGarminRequestError(
            await getApiErrorMessage(response, `Error ${response.status} generando preview Garmin`),
          ),
        );
      }
      const result = (await response.json()) as GarminImportPreview;
      setImportPreview(result);
      setInfoMessage(`Preview Garmin listo: ${result.activities_detected} actividades y ${result.daily_metrics_detected} metricas diarias.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setPreviewingImport(false);
    }
  }

  async function runGarminImport() {
    if (!selectedSeason) {
      setError("Selecciona una temporada antes de lanzar una importacion Garmin.");
      return;
    }

    try {
      setImporting(true);
      setError(null);
      setInfoMessage(null);
      setSubmissionMessage(null);
      const response = await fetch("/api/imports/garmin-connect/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          season_id: selectedSeason.season_id,
          date_from: importForm.date_from,
          date_to: importForm.date_to,
          include_daily_metrics: importForm.include_daily_metrics,
        }),
      });
      if (!response.ok) {
        throw new Error(
          formatGarminRequestError(
            await getApiErrorMessage(response, `Error ${response.status} lanzando importacion Garmin`),
          ),
        );
      }
      const result = (await response.json()) as GarminImportRunResponse;
      setSubmissionMessage(
        `Importacion Garmin ${result.import_job.status}: job ${result.import_job.import_job_id}, ${result.import_job.rows_loaded} filas cargadas y ${result.counts.segment_efforts_loaded} esfuerzos de segmento normalizados. ${formatRetrySuitabilityLabel(result.import_job.retry_suitability)}.`,
      );
      const activities = await loadSeasonActivities(selectedSeason.season_id);
      setImportForm((current) => ({
        ...current,
        ...getSeasonImportDateRange(selectedSeason, activities),
      }));
      await loadImportJobs();
      await loadSegments(selectedSeason.season_id, selectedSegmentId);
      if (selectedDailyMetricDate) {
        await loadDailyMetric(selectedSeason.season_id, selectedDailyMetricDate);
      }
      if (selectedWeek) {
        await handleWeekSelect(selectedWeek);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setImporting(false);
    }
  }

  async function loadActivityDetail(activityId: number) {
    try {
      setLoadingActivity(true);
      setLoadingActivityQuality(true);
      setError(null);
      const [activity, quality, runningDynamicsHistory] = await Promise.all([
        fetchJson<ActivityDetail>(`/api/activities/${activityId}`),
        fetchJson<ActivityQualityDetail>(`/api/activities/${activityId}/quality`).catch((requestError) => {
          if (isNotFoundError(requestError)) {
            return null;
          }
          throw requestError;
        }),
        fetchJson<RunningDynamicsHistoryResponse>(`/api/activities/${activityId}/running-dynamics-history`).catch((requestError) => {
          if (isNotFoundError(requestError)) {
            return null;
          }
          throw requestError;
        }),
      ]);
      setSelectedActivity(activity);
      setSelectedActivityQuality(quality);
      setSelectedActivityRunningDynamicsHistory(runningDynamicsHistory);
      setSelectedDailyMetricDate(activity.activity_date);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {

        const dailyMetricDates = Array.from(new Set([...sessions.map((session) => session.session_date), ...planVsRealRows.map((row) => row.session_date)])).sort();
      setLoadingActivity(false);
      setLoadingActivityQuality(false);
    }
  }

  async function replaySelectedActivityQuality() {
    if (!selectedActivity) {
      return;
    }

    try {
      setReplayingActivityQuality(true);
      setError(null);
      setInfoMessage(null);
      const response = await fetch(`/api/activities/${selectedActivity.activity_id}/quality/replay`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_mode: "artifact" }),
      });
      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, `Error ${response.status} reevaluando calidad de actividad`));
      }
      const result = (await response.json()) as ActivityQualityReplayResponse;
      await loadActivityDetail(selectedActivity.activity_id);
      setSubmissionMessage(
        `Calidad reevaluada para la actividad ${result.activity_id}: ${formatQualityStatusLabel(result.quality_status)} (${result.result === "reused_existing_run" ? "run reutilizado" : "run nuevo"}).`,
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setReplayingActivityQuality(false);
    }
  }

  async function enrichSelectedActivityWeather(force = false) {
    if (!selectedActivity) {
      return;
    }

    try {
      setLoadingActivityWeather(true);
      setError(null);
      setInfoMessage(null);
      await postJson(`/api/activities/${selectedActivity.activity_id}/weather/enrich`, { force });
      await loadActivityDetail(selectedActivity.activity_id);
      setSubmissionMessage(
        force
          ? `Meteorologia recalculada para la actividad ${selectedActivity.activity_id}.`
          : `Meteorologia cargada para la actividad ${selectedActivity.activity_id}.`,
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoadingActivityWeather(false);
    }
  }

  const weeklySummary = {
    total: planVsRealRows.length,
    completed: planVsRealRows.filter((row) => row.compliance_status === "completed").length,
    partial: planVsRealRows.filter((row) => row.compliance_status === "partial").length,
    pending: planVsRealRows.filter((row) => row.compliance_status === "pending").length,
    other: planVsRealRows.filter((row) => !["completed", "partial", "pending"].includes(row.compliance_status)).length,
    actualMinutes: Math.round(planVsRealRows.reduce((total, row) => total + (row.actual_duration_min ?? 0), 0)),
  };
  const optionalDailyActivities = planVsRealRows.flatMap((row) => getOptionalDailyActivities(row));
  const supportDailyActivities = planVsRealRows.flatMap((row) => getSupportDailyActivities(row));
  const optionalStrengthCount = optionalDailyActivities.filter((activity) => activity.actual_discipline === "strength_training").length;
  const supportFlexibilityCount = supportDailyActivities.length;
  const optionalDailyMinutes = Math.round(optionalDailyActivities.reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
  const supportDailyMinutes = Math.round(supportDailyActivities.reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
  const otherDailyActivities = planVsRealRows.flatMap((row) => row.other_daily_activities ?? []);
  const otherDailyMinutes = Math.round(otherDailyActivities.reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
  const dailyMetricDates = Array.from(new Set([...sessions.map((session) => session.session_date), ...planVsRealRows.map((row) => row.session_date)])).sort();
  const totalLoadMinutes = weeklySummary.actualMinutes + optionalDailyMinutes + supportDailyMinutes + otherDailyMinutes;
  const skippedCount = planVsRealRows.filter((row) => row.compliance_status === "skipped").length;
  const replacedCount = planVsRealRows.filter((row) => row.compliance_status === "replaced").length;
  const trackedCount = weeklySummary.total - weeklySummary.pending;
  const plannedLowerMinutes = sessions.reduce((total, session) => total + (session.duration_min ?? 0), 0);
  const plannedUpperMinutes = sessions.reduce((total, session) => total + (session.duration_max ?? session.duration_min ?? 0), 0);
  const plannedReferenceMinutes = Math.round(
    sessions.reduce((total, session) => {
      const lowerBound = session.duration_min ?? session.duration_max ?? 0;
      const upperBound = session.duration_max ?? session.duration_min ?? 0;
      return total + (lowerBound + upperBound) / 2;
    }, 0),
  );
  const adherenceRate = weeklySummary.total === 0 ? 0 : ((weeklySummary.completed + weeklySummary.partial) / weeklySummary.total) * 100;
  const traceabilityRate = weeklySummary.total === 0 ? 0 : (trackedCount / weeklySummary.total) * 100;
  const volumeDeltaMinutes = weeklySummary.actualMinutes - plannedReferenceMinutes;
  const volumeStatus =
    weeklySummary.actualMinutes === 0
      ? "sin carga real"
      : weeklySummary.actualMinutes < plannedLowerMinutes
        ? "por debajo de la banda"
        : weeklySummary.actualMinutes > plannedUpperMinutes
          ? "por encima de la banda"
          : "dentro de la banda";
  const keySessionRows = planVsRealRows.filter((row) => row.is_key_session === 1);
  const keySessionsClosed = keySessionRows.filter((row) => ["completed", "partial", "replaced"].includes(row.compliance_status)).length;
  const riskLevel =
    weeklySummary.pending >= 2 || skippedCount >= 2 || volumeStatus === "por debajo de la banda"
      ? "Riesgo alto"
      : weeklySummary.pending === 1 || skippedCount === 1 || replacedCount > 0 || volumeStatus === "por encima de la banda"
        ? "Riesgo medio"
        : "Riesgo bajo";
  const weeklyRecommendation =
    weeklySummary.pending > 0
      ? "Cerrar primero los registros pendientes antes de interpretar la semana."
      : skippedCount > 0
        ? "Revisar si las sesiones omitidas exigen recorte o rediseno de la siguiente microsemana."
        : replacedCount > 0
          ? "Verificar que las sustituciones mantengan el objetivo funcional original de la semana."
          : volumeStatus === "por debajo de la banda"
            ? "Semana util pero corta; conviene confirmar si la reduccion fue deliberada o defensiva."
            : volumeStatus === "por encima de la banda"
              ? "Semana mas cargada de lo previsto; vigilar absorcion y fatiga antes de empujar mas."
              : "Mantener la estructura actual; la semana cierra dentro de rango y sin incidencias operativas.";
  const operationalStatus =
    weeklySummary.pending === 0 && skippedCount === 0 && replacedCount === 0
      ? "Semana cerrada"
      : trackedCount === 0
        ? "Semana abierta"
        : "Semana en revision";
  const operationalFocus =
    weeklySummary.pending > 0
      ? `Faltan ${weeklySummary.pending} registros para cerrar la semana.`
      : skippedCount > 0 || replacedCount > 0
        ? `Hay ${skippedCount + replacedCount} decisiones de ajuste que conviene revisar.`
        : "La semana tiene trazabilidad completa y puede considerarse cerrada.";
  const dashboardSignals = [
    `${selectedWeek?.week_role ?? "Semana activa"} con objetivo "${selectedWeek?.objective_primary ?? "sin objetivo definido"}".`,
    `Volumen real ${volumeStatus}: ${toHoursLabel(weeklySummary.actualMinutes)} frente a una referencia de ${toHoursLabel(plannedReferenceMinutes)}.`,
    `Carga total registrada: ${toHoursLabel(totalLoadMinutes)} (${toHoursLabel(weeklySummary.actualMinutes)} del plan + ${toHoursLabel(optionalDailyMinutes + otherDailyMinutes)} en actividades no planificadas + ${toHoursLabel(supportDailyMinutes)} de flexibilidad de soporte).`,
    optionalDailyActivities.length > 0
      ? `Extras diarios: ${optionalStrengthCount} sesiones de fuerza (${toHoursLabel(optionalDailyMinutes)}).`
      : "Sin extras diarios opcionales registrados en la semana.",
    supportDailyActivities.length > 0
      ? `Flexibilidad de soporte: ${supportFlexibilityCount} sesiones de yoga (${toHoursLabel(supportDailyMinutes)}).`
      : "Sin sesiones de flexibilidad de soporte registradas en la semana.",
    otherDailyActivities.length > 0
      ? `Otras actividades ejecutadas: ${otherDailyActivities.length} (${toHoursLabel(otherDailyMinutes)}).`
      : "Sin otras actividades no enlazadas en la semana.",
    keySessionRows.length > 0
      ? `Sesiones clave resueltas ${keySessionsClosed}/${keySessionRows.length}.`
      : "Esta semana no tiene sesiones clave marcadas.",
  ];
  const persistedRiskLevel = weeklyReview?.risk_level ?? riskLevel;
  const persistedRecommendation = weeklyReview?.recommendation_text ?? weeklyRecommendation;
  const persistedSummary = weeklyReview?.summary_text;
  const isWeeklyReviewClosed = weeklyReview?.review_status === "closed";

  async function closeWeeklyReview() {
    if (!selectedWeek) {
      return;
    }

    try {
      setSavingWeeklyReview(true);
      setError(null);
      setInfoMessage(null);
      setSelectedWeeklyAssessmentMarkdown(null);
      const review = await fetchJson<WeeklyReview>(`/api/weeks/${selectedWeek.week_id}/review`,);
      const response = await fetch(`/api/weeks/${selectedWeek.week_id}/review`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ summary_text: review.summary_text ?? undefined }),
      });
      if (!response.ok) {
        throw new Error(`Error ${response.status} cerrando revision semanal`);
      }
      const result = (await response.json()) as WeeklyReview;
      setWeeklyReview(result);
      setSubmissionMessage(`Revision semanal cerrada para ${result.week_code}.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setSavingWeeklyReview(false);
    }
  }

  async function reopenWeeklyReview() {
    if (!selectedWeek) {
      return;
    }

    try {
      setSavingWeeklyReview(true);
      setError(null);
      setInfoMessage(null);
      setSelectedWeeklyAssessmentMarkdown(null);
      const response = await fetch(`/api/weeks/${selectedWeek.week_id}/review`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`Error ${response.status} reabriendo revision semanal`);
      }
      const refreshed = await fetchJson<WeeklyReview>(`/api/weeks/${selectedWeek.week_id}/review`);
      setWeeklyReview(refreshed);
      setSubmissionMessage(`Revision semanal reabierta para ${selectedWeek.week_code}.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setSavingWeeklyReview(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">V0.2 GUI operativa</p>
          <h1>Planificacion y realidad</h1>
          <p className="subtitle">
            Navegacion sobre SQLite con comparativa semanal y operativa Garmin-only sobre el estado real.
          </p>
        </div>
        <div className="status-card">
          <span>Fuente</span>
          <strong>Sistema/training.sqlite</strong>
          <span>{loading ? "Cargando..." : "Lectura y escritura minima"}</span>
        </div>
      </header>

      {error ? <section className="error-banner">{error}</section> : null}
  {infoMessage ? <section className="info-banner">{infoMessage}</section> : null}
      {submissionMessage ? <section className="success-banner">{submissionMessage}</section> : null}

      <section className="breadcrumbs">
        <span>{selectedSeason?.season_name ?? "Sin temporada"}</span>
        <span>{selectedBlock?.block_name ?? "Sin bloque"}</span>
        <span>{selectedWeek?.week_code ?? "Sin semana"}</span>
      </section>

      {selectedDailyMetric?.load_model?.trend?.length ? renderLoadModelChart(selectedDailyMetric.load_model, "panel load-chart-card load-chart-panel-top") : null}
      {selectedDailyMetric?.weight_trend?.length ? renderWeightTrendChart(selectedDailyMetric.weight_trend, selectedDailyMetric.weight_measurements ?? [], "panel weight-chart-card load-chart-panel-top") : null}

      <section className="import-layout">
        <section className="panel import-panel">
          <div className="section-heading">
            <div>
              <h2>Garmin Connect</h2>
              <p className="section-subtitle">Preview y ejecucion directa sobre la temporada activa.</p>
            </div>
            {garminStatus ? (
              <span className={garminStatus.configured ? "status-pill status-pill-ready" : "status-pill status-pill-missing"}>
                {toGarminAuthModeLabel(garminStatus)}
              </span>
            ) : null}
          </div>

          {garminStatus ? (
            <div className="import-status-meta">
              <p className="import-status-note">{garminStatus.detail}</p>
              {garminStatus.configured && garminStatus.auth_mode === "tokenstore" && garminStatus.tokenstore_path ? (
                <p className="import-status-subnote">Tokenstore: {garminStatus.tokenstore_path}</p>
              ) : null}
            </div>
          ) : null}

          <div className="form-grid import-form-grid">
            <label>
              Desde
              <input name="date_from" type="date" value={importForm.date_from} onChange={handleImportInputChange} />
            </label>
            <label>
              Hasta
              <input name="date_to" type="date" value={importForm.date_to} onChange={handleImportInputChange} />
            </label>
          </div>

          <label className="checkbox-row">
            <input name="include_daily_metrics" type="checkbox" checked={importForm.include_daily_metrics} onChange={handleImportInputChange} />
            <span>Incluir metricas diarias</span>
          </label>

          <div className="review-actions">
            <button className="ghost-button" type="button" onClick={() => void previewGarminImport()} disabled={previewingImport || importing || !selectedSeason}>
              {previewingImport ? "Previsualizando..." : "Preview Garmin"}
            </button>
            <button className="secondary-button" type="button" onClick={() => void runGarminImport()} disabled={previewingImport || importing || !selectedSeason}>
              {importing ? "Importando..." : "Ejecutar importacion"}
            </button>
          </div>

          {importPreview ? (
            <div className="import-preview-card">
              <div className="summary-strip import-summary-strip">
                <article>
                  <strong>{importPreview.activities_detected}</strong>
                  <span>Actividades detectadas</span>
                </article>
                <article>
                  <strong>{importPreview.daily_metrics_detected}</strong>
                  <span>Metricas detectadas</span>
                </article>
              </div>
              <div className="import-notes-list">
                {importPreview.notes.map((note) => (
                  <p key={note}>{note}</p>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="panel import-panel">
          <div className="section-heading">
            <div>
              <h2>Historial de import jobs</h2>
              <p className="section-subtitle">Ultimas ejecuciones con detalle de insertadas y actualizadas.</p>
            </div>
          </div>

          <div className="panel-list import-jobs-list">
            {importJobs.map((job) => (
              (() => {
                const scope = getImportJobScope(job);
                return (
              <article key={job.import_job_id} className="import-job-card">
                <div className="item-head">
                  <strong>Job {job.import_job_id}</strong>
                  <span className={toBadgeClass(job.status)}>{job.status}</span>
                </div>
                <span>{job.source_path ?? "Sin rango"}</span>
                <small>{toDateTimeLabel(job.imported_at)}</small>
                {job.finished_at ? <small>Finalizado: {toDateTimeLabel(job.finished_at)}</small> : null}
                <div className="import-job-meta">
                  <span>Temporada: {scope.season_id}</span>
                  <span>Rango: {scope.date_from ?? "?"} a {scope.date_to ?? "?"}</span>
                  <span>Metricas diarias: {scope.include_daily_metrics ? "si" : "no"}</span>
                  <span>Retry: {formatRetrySuitabilityLabel(job.retry_suitability)}</span>
                  {job.failure_stage ? <span>Etapa: {formatFailureStageLabel(job.failure_stage)}</span> : null}
                  {job.failure_class ? <span>Clase: {formatFailureClassLabel(job.failure_class)}</span> : null}
                  {job.partial_completion ? <span>Resultado parcial</span> : null}
                </div>
                {job.operator_detail ? <p className="import-job-detail">{job.operator_detail}</p> : null}
                <div className="import-job-grid">
                  <span>Detectadas: {job.rows_detected}</span>
                  <span>Cargadas: {job.rows_loaded}</span>
                  {job.has_breakdown_details ? (
                    <>
                      <span>Act. det: {job.breakdown.activity_rows_detected}</span>
                      <span>Act. +: {job.breakdown.activity_rows_inserted}</span>
                      <span>Act. upd: {job.breakdown.activity_rows_updated}</span>
                      <span>Act. skip: {job.breakdown.activity_rows_skipped}</span>
                      <span>Met. det: {job.breakdown.daily_metric_rows_detected}</span>
                      <span>Met. +: {job.breakdown.daily_metric_rows_inserted}</span>
                      <span>Met. upd: {job.breakdown.daily_metric_rows_updated}</span>
                      <span>Met. skip: {job.breakdown.daily_metric_rows_skipped}</span>
                    </>
                  ) : (
                    <span className="import-job-grid-note">Breakdown inserted/updated no disponible</span>
                  )}
                </div>
                {job.notes.length > 0 ? (
                  <div className="import-notes-list">
                    {job.notes.map((note) => (
                      <p key={`${job.import_job_id}-${note}`}>{note}</p>
                    ))}
                  </div>
                ) : null}
              </article>
                );
              })()
            ))}
            {importJobs.length === 0 ? (
              <div className="empty-state-card">
                <strong>Sin import jobs</strong>
                <p>Aun no hay importaciones Garmin registradas en SQLite.</p>
              </div>
            ) : null}
          </div>
        </section>
      </section>

      <section className="panel segment-panel">
        <div className="section-heading">
          <div>
            <h2>Segmentos Garmin</h2>
            <p className="section-subtitle">Lectura minima de historial y evolucion por segmento sobre SQLite canonica.</p>
          </div>
        </div>

        <div className="segment-layout">
          <div className="segment-list">
            {loadingSegments ? (
              <div className="empty-state-card empty-state-card-wide">
                <strong>Cargando segmentos</strong>
                <p>Recuperando segmentos repetidos de la temporada activa.</p>
              </div>
            ) : segments.length === 0 ? (
              <div className="empty-state-card empty-state-card-wide">
                <strong>Sin segmentos</strong>
                <p>Aun no hay esfuerzos de segmento Garmin guardados para esta temporada.</p>
              </div>
            ) : (
              segments.map((segment) => (
                <button
                  key={segment.segment_id}
                  type="button"
                  className={`segment-list-item${selectedSegmentId === segment.segment_id ? " selected" : ""}`}
                  onClick={() => void loadSegmentHistory(segment.segment_id)}
                >
                  <div className="segment-list-head">
                    <strong>{segment.segment_name ?? `Segmento ${segment.segment_id}`}</strong>
                    <span className={segment.comparable_effort_count > 0 ? "status-pill status-pill-ready" : "status-pill"}>
                      {formatSegmentCoverageLabel(segment.effort_count, segment.comparable_effort_count)}
                    </span>
                  </div>
                  <div className="segment-list-meta">
                    <span>Mejor: {formatSecondsLabel(segment.best_elapsed_time_seconds)}</span>
                    <span>Ultimo: {formatSecondsLabel(segment.latest_elapsed_time_seconds)}</span>
                    <span>Primero: {segment.first_activity_date ?? "-"}</span>
                    <span>Ultimo dia: {segment.last_activity_date ?? "-"}</span>
                  </div>
                  <p className="segment-missing-copy">
                    {segment.comparable_effort_count === 0
                      ? "Garmin confirmo la presencia del segmento en estas actividades, pero no expuso tiempos por intento."
                      : `Huecos: potencia ${segment.missing_metric_counts.avg_power}, cadencia ${segment.missing_metric_counts.avg_cadence}, FC ${segment.missing_metric_counts.avg_heart_rate}`}
                  </p>
                </button>
              ))
            )}
          </div>

          <div className="segment-detail-card panel-subcard">
            {loadingSegmentHistory ? (
              <div className="empty-state-card empty-state-card-wide">
                <strong>Cargando detalle</strong>
                <p>Recuperando historial y resumen del segmento seleccionado.</p>
              </div>
            ) : selectedSegmentHistory ? (
              <>
                <div className="segment-detail-head">
                  <div>
                    <h3>{selectedSegmentHistory.segment.segment_name ?? `Segmento ${selectedSegmentHistory.segment.segment_id}`}</h3>
                    <p className="section-subtitle">
                      {selectedSegmentHistory.segment.distance_meters != null ? `${selectedSegmentHistory.segment.distance_meters.toFixed(0)} m` : "Distancia sin dato"}
                      {selectedSegmentHistory.segment.average_grade_percent != null ? ` · ${selectedSegmentHistory.segment.average_grade_percent.toFixed(1)}% media` : ""}
                    </p>
                  </div>
                  <div className="segment-detail-controls">
                    <label className="segment-history-limit-control">
                      <span>Ultimas ocurrencias</span>
                      <select value={segmentHistoryLimit} onChange={(event) => void handleSegmentHistoryLimitChange(event)}>
                        {SEGMENT_HISTORY_LIMIT_OPTIONS.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>
                    <span
                      className={
                        selectedSegmentHistory.summary.comparable_effort_count > 0 &&
                        selectedSegmentHistory.summary.trend_status === "improving"
                          ? "status-pill status-pill-ready"
                          : "status-pill status-pill-missing"
                      }
                    >
                      {selectedSegmentHistory.summary.comparable_effort_count === 0
                        ? "Solo presencia"
                        : formatTrendLabel(selectedSegmentHistory.summary.trend_status)}
                    </span>
                  </div>
                </div>

                <div className="summary-strip segment-summary-strip">
                  <article>
                    <strong>{selectedSegmentHistory.summary.effort_count}</strong>
                    <span>{selectedSegmentHistory.summary.comparable_effort_count === 0 ? "Presencias" : "Esfuerzos"}</span>
                  </article>
                  <article>
                    <strong>{selectedSegmentHistory.summary.best_effort_id ? formatSecondsLabel(selectedSegmentHistory.efforts.find((effort) => effort.segment_effort_id === selectedSegmentHistory.summary.best_effort_id)?.elapsed_time_seconds ?? null) : "Sin dato"}</strong>
                    <span>Mejor registro</span>
                  </article>
                  <article>
                    <strong>{selectedSegmentHistory.summary.latest_effort_id ? formatSecondsLabel(selectedSegmentHistory.efforts.find((effort) => effort.segment_effort_id === selectedSegmentHistory.summary.latest_effort_id)?.elapsed_time_seconds ?? null) : "Sin dato"}</strong>
                    <span>Ultimo intento</span>
                  </article>
                </div>

                <p className="segment-availability-copy">
                  {selectedSegmentHistory.summary.comparable_effort_count === 0
                    ? `Garmin solo expuso la pertenencia del segmento en ${selectedSegmentHistory.summary.membership_only_count} actividades. Todavia no hay tiempos comparables.`
                    : `Metricas comparables: ${selectedSegmentHistory.summary.available_metric_names.join(", ")}${selectedSegmentHistory.summary.missing_metric_names.length > 0 ? ` · faltan en algun intento: ${selectedSegmentHistory.summary.missing_metric_names.join(", ")}` : ""}`}
                </p>

                {selectedSegmentHistory.summary.comparable_effort_count > 0 ? renderSegmentEvolutionChart(selectedSegmentHistory) : null}

                <div className="segment-effort-list">
                  {selectedSegmentHistory.efforts.map((effort) => (
                    <article key={effort.segment_effort_id} className="segment-effort-item">
                      <div className="segment-list-head">
                        <strong>{effort.activity_date}</strong>
                        <div className="segment-effort-badges">
                          {effort.is_best_effort ? <span className="status-pill status-pill-ready">Mejor</span> : null}
                          {effort.is_latest_effort ? <span className="status-pill">Ultimo</span> : null}
                        </div>
                      </div>
                      <div className="segment-list-meta">
                        <span>Tiempo: {formatSecondsLabel(effort.elapsed_time_seconds)}</span>
                        <span>Vs mejor: {formatDeltaLabel(effort.delta_vs_best_seconds)}</span>
                        <span>Vs previo: {formatDeltaLabel(effort.delta_vs_previous_seconds)}</span>
                        <span>Potencia: {effort.avg_power != null ? `${effort.avg_power.toFixed(0)} W` : "Sin dato"}</span>
                        <span>Cadencia: {effort.avg_cadence != null ? `${effort.avg_cadence.toFixed(0)} rpm` : "Sin dato"}</span>
                        <span>FC: {effort.avg_heart_rate != null ? `${effort.avg_heart_rate.toFixed(0)} ppm` : "Sin dato"}</span>
                        <span>Resp: {effort.avg_respiration_rate != null ? `${effort.avg_respiration_rate.toFixed(1)} rpm resp` : "Sin dato"}</span>
                      </div>
                      {effort.missing_metrics.length > 0 ? (
                        <p className="segment-missing-copy">Faltan: {effort.missing_metrics.join(", ")}</p>
                      ) : null}
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state-card empty-state-card-wide">
                <strong>Selecciona un segmento</strong>
                <p>Cuando existan esfuerzos repetidos, aqui veras su historial cronologico y la tendencia reciente.</p>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="panel activity-feed-panel">
        <div className="section-heading">
          <div>
            <h2>Actividades reales</h2>
            <p className="section-subtitle">Ultimas actividades registradas de la temporada activa, con foco en lectura operativa y acceso rapido al detalle.</p>
          </div>
        </div>

        {selectedSeason ? (
          <div className="zone-governance-strip">
            <article className="zone-governance-card zone-governance-card-wide">
              <div className="item-head">
                <strong>Perfiles de zona activos</strong>
                <span className="dashboard-label">cycling</span>
              </div>
              {currentZoneProfiles && Object.keys(currentZoneProfiles.profiles).length > 0 ? (
                <div className="zone-profile-grid">
                  {(["heart_rate", "power"] as const).flatMap((metricBasis) => {
                    const profile = currentZoneProfiles.profiles[metricBasis];
                    if (!profile) {
                      return [];
                    }
                    return (
                      <article key={metricBasis} className="zone-profile-card">
                        <div className="item-head">
                          <strong>{formatZoneBasisLabel(metricBasis)}</strong>
                          <span className="zone-pill zone-pill-target">{profile.profile_label ?? "perfil activo"}</span>
                        </div>
                        <small>Desde {profile.effective_start_date}</small>
                        <div className="zone-boundary-list">
                          {profile.boundaries.map((boundary) => (
                            <span key={`${metricBasis}-${boundary.zone_index}`} className="zone-pill">
                              {formatZoneBoundaryLabel(boundary)}
                            </span>
                          ))}
                        </div>
                      </article>
                    );
                  })}
                </div>
              ) : (
                <p>No hay perfiles de zonas aceptados cargados para esta temporada. Cuando existan, aqui veras los rangos de FC y potencia.</p>
              )}
            </article>
            <article className="zone-governance-card zone-governance-card-wide zone-anchors-card">
              <div className="item-head">
                <strong>Anclas fisiologicas</strong>
                <span className="dashboard-label">nueva version</span>
              </div>
              <div className="zone-anchor-current-grid">
                <article className="zone-profile-card">
                  <div className="item-head">
                    <strong>Frecuencia cardiaca</strong>
                    <span className="zone-pill zone-pill-target">
                      {formatMetricProfileModelLabel(currentZoneProfiles?.profiles.heart_rate?.metric_profile?.model_key ?? currentZoneProfiles?.profiles.heart_rate?.calculation_model_key)}
                    </span>
                  </div>
                  <small>
                    {currentZoneProfiles?.profiles.heart_rate?.metric_profile?.effective_start_date
                      ? `Desde ${currentZoneProfiles.profiles.heart_rate.metric_profile.effective_start_date}`
                      : "Sin version activa"}
                  </small>
                  <div className="zone-chip-list">
                    <span className="zone-pill">HRmin {currentZoneProfiles?.profiles.heart_rate?.metric_profile?.parameters.resting_hr != null ? Math.round(currentZoneProfiles.profiles.heart_rate.metric_profile.parameters.resting_hr) : "-"} bpm</span>
                    <span className="zone-pill">HRmax {currentZoneProfiles?.profiles.heart_rate?.metric_profile?.parameters.max_hr != null ? Math.round(currentZoneProfiles.profiles.heart_rate.metric_profile.parameters.max_hr) : "-"} bpm</span>
                  </div>
                </article>
                <article className="zone-profile-card">
                  <div className="item-head">
                    <strong>Potencia</strong>
                    <span className="zone-pill zone-pill-target">
                      {formatMetricProfileModelLabel(currentZoneProfiles?.profiles.power?.metric_profile?.model_key ?? currentZoneProfiles?.profiles.power?.calculation_model_key)}
                    </span>
                  </div>
                  <small>
                    {currentZoneProfiles?.profiles.power?.metric_profile?.effective_start_date
                      ? `Desde ${currentZoneProfiles.profiles.power.metric_profile.effective_start_date}`
                      : "Sin version activa"}
                  </small>
                  <div className="zone-chip-list">
                    <span className="zone-pill">FTP {currentZoneProfiles?.profiles.power?.metric_profile?.parameters.ftp != null ? Math.round(currentZoneProfiles.profiles.power.metric_profile.parameters.ftp) : "-"} W</span>
                  </div>
                </article>
              </div>
              <form className="manual-form zone-anchor-form" onSubmit={(event) => {
                event.preventDefault();
                void savePhysiologicalAnchorsVersion();
              }}>
                <div className="form-grid metrics-grid zone-anchor-form-grid">
                  <label>
                    Fecha efectiva
                    <input name="effective_start_date" type="date" value={physiologicalAnchorsForm.effective_start_date} onChange={handlePhysiologicalAnchorsInputChange} />
                  </label>
                  <label>
                    HRmin
                    <input name="resting_hr" type="number" min="1" step="1" value={physiologicalAnchorsForm.resting_hr} onChange={handlePhysiologicalAnchorsInputChange} />
                  </label>
                  <label>
                    HRmax
                    <input name="max_hr" type="number" min="1" step="1" value={physiologicalAnchorsForm.max_hr} onChange={handlePhysiologicalAnchorsInputChange} />
                  </label>
                  <label>
                    FTP
                    <input name="ftp" type="number" min="1" step="1" value={physiologicalAnchorsForm.ftp} onChange={handlePhysiologicalAnchorsInputChange} />
                  </label>
                </div>
                <label>
                  Notas de la version
                  <textarea name="notes" rows={2} value={physiologicalAnchorsForm.notes} onChange={handlePhysiologicalAnchorsInputChange} placeholder="Ejemplo: ajuste tras test de campo o revision de metricas recientes." />
                </label>
                <div className="review-actions zone-anchor-actions">
                  <button className="secondary-button" type="submit" disabled={savingPhysiologicalAnchors}>
                    {savingPhysiologicalAnchors ? "Creando version..." : "Crear nueva version"}
                  </button>
                  <small>Se crearan perfiles nuevos para FC por reserva cardiaca y potencia por FTP con la fecha efectiva indicada.</small>
                </div>
              </form>
            </article>
            <article className="zone-governance-card">
              <span className="dashboard-label">Propuestas de refinamiento</span>
              <strong>{zoneProposals.length}</strong>
              <p>{zoneProposals.length > 0 ? "Propuestas activas para revisar antes de consolidar los perfiles." : "Sin propuestas pendientes en la temporada activa."}</p>
            </article>
            {zoneProposals.slice(0, 3).map((proposal) => (
              <article key={proposal.proposal_id} className="zone-governance-card zone-governance-card-detail">
                <div className="item-head">
                  <strong>{formatZoneBasisLabel(proposal.metric_basis)}</strong>
                  <span className={toBadgeClass(proposal.proposal_status)}>{proposal.proposal_status}</span>
                </div>
                <p>{proposal.proposal_summary}</p>
                <small>
                  {toConfidenceLabel(proposal.confidence_level)}
                  {proposal.proposed_effective_start_date ? ` · efectiva ${proposal.proposed_effective_start_date}` : ""}
                </small>
              </article>
            ))}
          </div>
        ) : null}

        {loadingSeasonActivities ? (
          <div className="empty-state-card empty-state-card-wide">
            <strong>Cargando actividades</strong>
            <p>Recuperando las actividades reales ya registradas en SQLite.</p>
          </div>
        ) : seasonActivities.length > 0 ? (
          <div className="activity-feed-list">
            {seasonActivities.map((activity) => (
              (() => {
                const zoneSummaryLabel = formatActivityZoneSummaryLabel(activity.zone_summary);
                return (
              <button
                key={activity.activity_id}
                type="button"
                className={activity.activity_id === selectedActivity?.activity_id ? "activity-feed-item selected" : "activity-feed-item"}
                onClick={() => void loadActivityDetail(activity.activity_id)}
              >
                <div className="activity-feed-head">
                  <div>
                    <strong>{toActivityTypeLabel(activity.activity_type, activity.source_system)}</strong>
                    <p>
                      {[
                        activity.started_at ? toDateTimeLabel(activity.started_at) : activity.activity_date,
                        toSourceLabel(activity.source_system),
                        activity.discipline ? toDisciplineLabel(activity.discipline) : null,
                      ].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <span className={toBadgeClass(activity.quality_status ?? "pending")}>{formatQualityStatusLabel(activity.quality_status)}</span>
                </div>

                <div className="activity-feed-meta">
                  {activity.duration_seconds != null ? <span>{toDurationLabel(activity.duration_seconds / 60, activity.duration_seconds / 60)}</span> : null}
                  {activity.distance_meters != null ? <span>{toMetricLabel(activity.distance_meters / 1000, " km")}</span> : null}
                  {activity.avg_hr != null ? <span>FC: {toMetricLabel(activity.avg_hr, " ppm")}</span> : null}
                  {activity.avg_power != null ? <span>Potencia: {toMetricLabel(activity.avg_power, " W")}</span> : null}
                  {activity.calculated_training_load != null ? <span>{toTrainingLoadHeading(activity)}: {toMetricLabel(activity.calculated_training_load)} · {toTrainingLoadSourceLabel(activity.calculated_training_load_source)}</span> : null}
                  <span>Actividad #{activity.activity_id}</span>
                </div>

                {zoneSummaryLabel ? <p className="activity-feed-zones">{zoneSummaryLabel}</p> : null}

                <p className="activity-feed-summary">{activity.actual_summary ?? activity.notes ?? "Sin resumen adicional."}</p>
              </button>
                );
              })()
            ))}
          </div>
        ) : (
          <div className="empty-state-card empty-state-card-wide">
            <strong>Sin actividades registradas</strong>
            <p>La temporada activa aun no tiene actividades reales guardadas en SQLite.</p>
          </div>
        )}
      </section>

      <main className="grid-layout">
        <aside className="panel panel-seasons">
          <h2>Temporadas</h2>
          <div className="panel-list">
            {seasons.map((season) => (
              <button
                key={season.season_id}
                className={season.season_id === selectedSeason?.season_id ? "item-card selected" : "item-card"}
                onClick={() => void handleSeasonSelect(season)}
              >
                <strong>{season.season_code}</strong>
                <span>{season.season_name}</span>
                <small>{season.start_date} - {season.end_date}</small>
              </button>
            ))}
          </div>
        </aside>

        <section className="panel panel-blocks">
          <h2>Bloques</h2>
          <div className="panel-list">
            {blocks.map((block) => (
              <button
                key={block.block_id}
                className={block.block_id === selectedBlock?.block_id ? "item-card selected" : "item-card"}
                onClick={() => void handleBlockSelect(block)}
              >
                <div className="item-head">
                  <strong>{block.block_code}</strong>
                  <span>{block.phase_name}</span>
                </div>
                <span>{block.block_name}</span>
                <small>{block.objective_primary}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="panel panel-weeks">
          <h2>Semanas</h2>
          <div className="panel-list">
            {weeks.map((week) => (
              <button
                key={week.week_id}
                className={week.week_id === selectedWeek?.week_id ? "item-card selected" : "item-card"}
                onClick={() => void handleWeekSelect(week)}
              >
                <div className="item-head">
                  <strong>{week.week_code}</strong>
                  <span>{week.week_role}</span>
                </div>
                <span>{week.start_date} - {week.end_date}</span>
                <small>
                  {week.target_volume_hours_min ?? "-"}h - {week.target_volume_hours_max ?? "-"}h
                </small>
              </button>
            ))}
            {weeks.length === 0 ? (
              <div className="empty-state-card">
                <strong>Sin semanas cargadas</strong>
                <p>{selectedBlock ? `El bloque ${selectedBlock.block_code} aun no tiene semanas en la base.` : "Selecciona un bloque para ver sus semanas."}</p>
              </div>
            ) : null}
          </div>
        </section>

        <section className="panel panel-sessions">
          <h2>Sesiones planificadas</h2>
          {selectedWeek ? (
            <>
              <div className="session-table-wrapper">
                <table className="session-table">
                  <thead>
                    <tr>
                      <th>Dia</th>
                      <th>Rol</th>
                      <th>Objetivo</th>
                      <th>Sesion principal</th>
                      <th>Zona</th>
                      <th>Complementario</th>
                      <th>Duracion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((session) => {
                      const isSelectedSession = session.planned_session_id === selectedPlannedSessionId;
                      return (
                        <tr
                          key={session.planned_session_id}
                          className={`${session.is_key_session ? 'key-session ' : ''}clickable-row${isSelectedSession ? ' selected-row' : ''}`.trim()}
                          onClick={() => setSelectedPlannedSessionId(session.planned_session_id)}
                        >
                          <td>
                            <strong>{session.day_name}</strong>
                            <small>{session.session_date}</small>
                          </td>
                          <td>{toPlannedRoleLabel(session.planned_role ?? session.planned_type)}</td>
                          <td>{session.objective}</td>
                          <td>{getSessionPrimaryText(session)}</td>
                          <td>
                            {session.planned_zone_target ? (
                              <span className="zone-pill zone-pill-target">{formatPlannedZoneTargetLabel(session.planned_zone_target)}</span>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td>
                            <div>
                              <div>{getSessionSupportText(session)}</div>
                              {session.planned_support_routine ? <small>Soporte opcional diario: {session.planned_support_routine}</small> : null}
                            </div>
                          </td>
                          <td>{toDurationLabel(session.duration_min, session.duration_max)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div ref={sessionDetailRef} className="session-detail-surface">
                <div className="section-heading">
                  <div>
                    <h3>Detalle estructurado de la sesion</h3>
                    <p className="section-subtitle">Selecciona una fila para consultar la prescripcion completa desde el endpoint dedicado.</p>
                  </div>
                  {loadingSelectedPlannedSessionPrescription ? <span className="status-pill">Actualizando detalle</span> : null}
                </div>

                {selectedPlannedSession ? (
                  <article className="panel-subcard prescription-detail-card">
                    <div className="session-detail-header">
                      <div>
                        <h3>{selectedPlannedSession.day_name} · {selectedPlannedSession.session_date}</h3>
                        <p>{selectedPlannedSession.objective}</p>
                      </div>
                      <div className="session-detail-meta">
                        <span className="zone-pill">{toPlannedRoleLabel(selectedPlannedSession.planned_role ?? selectedPlannedSession.planned_type)}</span>
                        <span className="zone-pill">{toStructuredLabel(selectedPlannedSessionPrescription?.prescription_type ?? selectedPlannedSession.prescription_type ?? selectedPlannedSession.planned_type)}</span>
                        {selectedPlannedSession.is_key_session ? <span className="zone-pill zone-pill-target">Sesion clave</span> : null}
                      </div>
                    </div>

                    <div className="summary-strip session-detail-summary">
                      <article>
                        <strong>{toDurationLabel(selectedPlannedSession.duration_min, selectedPlannedSession.duration_max)}</strong>
                        <span>Duracion planificada</span>
                      </article>
                      <article>
                        <strong>{selectedPlannedSession.planned_zone_target ? formatPlannedZoneTargetLabel(selectedPlannedSession.planned_zone_target) : "-"}</strong>
                        <span>Objetivo de zona</span>
                      </article>
                      <article>
                        <strong>{selectedPlannedSessionPrescription?.discipline_family ? toStructuredLabel(selectedPlannedSessionPrescription.discipline_family) : "-"}</strong>
                        <span>Familia principal</span>
                      </article>
                      <article>
                        <strong>{toStructuredLabel(selectedPlannedSessionPrescription?.source_kind ?? "generated")}</strong>
                        <span>Origen estructurado</span>
                      </article>
                    </div>

                    <div className="session-detail-copy">
                      <article>
                        <strong>Sesion principal resumida</strong>
                        <p>{getSessionPrimaryText(selectedPlannedSession)}</p>
                      </article>
                      <article>
                        <strong>Complementario y soporte</strong>
                        <p>{getSessionSupportText(selectedPlannedSession)}</p>
                        {selectedPlannedSession.planned_support_routine ? <small>Soporte opcional diario: {selectedPlannedSession.planned_support_routine}</small> : null}
                      </article>
                      {selectedPlannedSessionPrescription?.adaptation_notes || selectedPlannedSessionPrescription?.execution_notes ? (
                        <article>
                          <strong>Ajustes y notas</strong>
                          {selectedPlannedSessionPrescription.execution_notes ? <p>{selectedPlannedSessionPrescription.execution_notes}</p> : null}
                          {selectedPlannedSessionPrescription.adaptation_notes ? <small>{selectedPlannedSessionPrescription.adaptation_notes}</small> : null}
                        </article>
                      ) : null}
                    </div>

                    {selectedPlanVsRealRow ? (
                      <div className="session-linked-activity-card panel-subcard">
                        <div className="session-linked-activity-head">
                          <div>
                            <strong>Referencia real del dia</strong>
                            <p className="section-subtitle">Cruce operativo con la fila de plan vs realidad para esta sesion.</p>
                          </div>
                          <span className={selectedPlanVsRealRow.compliance_status ? toBadgeClass(selectedPlanVsRealRow.compliance_status) : "badge badge-pending"}>
                            {selectedPlanVsRealRow.compliance_status}
                          </span>
                        </div>

                        <div className="session-linked-activity-summary">
                          <span>Plan real: {getPlanVsRealPlannedText(selectedPlanVsRealRow)}</span>
                          <span>Carga real: {toHoursLabel(getDailyTotalLoadMinutes(selectedPlanVsRealRow))}</span>
                          {selectedPlanVsRealRow.general_feeling ? <span>Sensacion: {selectedPlanVsRealRow.general_feeling}</span> : null}
                          {selectedPlanVsRealRow.next_day_decision ? <span>Decision: {selectedPlanVsRealRow.next_day_decision}</span> : null}
                        </div>

                        {selectedLinkedActivity ? (
                          <div className="session-linked-activity-detail">
                            <div>
                              <strong>{toPlanVsRealActivityLabel(selectedLinkedActivity)}</strong>
                              <p>{toPlanVsRealMetaLabel(selectedLinkedActivity) ?? "Sin metadatos adicionales"}</p>
                              {toPlanVsRealResolutionLabel(selectedLinkedActivity) ? <small>{toPlanVsRealResolutionLabel(selectedLinkedActivity)}</small> : null}
                            </div>
                            <button className="ghost-button" type="button" onClick={() => void loadActivityDetail(selectedLinkedActivity.activity_id)}>
                              Abrir actividad real
                            </button>
                          </div>
                        ) : selectedPlannedSessionActivities.length > 1 ? (
                          <div className="activity-detail-notes">
                            <p><strong>Varias actividades enlazadas.</strong> Usa la tabla de plan vs realidad para abrir la actividad concreta que quieras revisar.</p>
                          </div>
                        ) : (
                          <div className="activity-detail-notes">
                            <p><strong>Sin actividad enlazada de forma unica.</strong> Todavia no hay una ejecucion principal unica para cruzar con esta sesion.</p>
                          </div>
                        )}
                      </div>
                    ) : null}

                    {selectedPlannedSessionPrescription ? (
                      <div className="session-detail-layout">
                        {renderPrescriptionRoleSection(selectedPlannedSessionPrescription, "primary")}
                        {renderPrescriptionRoleSection(selectedPlannedSessionPrescription, "support")}
                      </div>
                    ) : (
                      <div className="empty-state-card empty-state-card-wide">
                        <strong>Sin prescripcion estructurada disponible</strong>
                        <p>La sesion sigue mostrando el resumen semanal, pero este detalle aun no tiene bloques persistidos.</p>
                      </div>
                    )}
                  </article>
                ) : (
                  <div className="empty-state-card empty-state-card-wide">
                    <strong>Sin sesion seleccionada</strong>
                    <p>Selecciona una sesion de la tabla para abrir su detalle estructurado.</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state-card empty-state-card-wide">
              <strong>Sin semana seleccionada</strong>
              <p>Selecciona una semana disponible para ver sus sesiones planificadas.</p>
            </div>
          )}
        </section>
      </main>

      <section className="detail-layout">
        <section className="panel panel-plan-real">
          <div className="section-heading">
            <div>
              <h2>Plan vs realidad</h2>
              <p className="section-subtitle">Comparativa semanal operativa derivada de la base.</p>
            </div>
          </div>

          {selectedWeek ? (
            <section className="weekly-dashboard">
              <div className="dashboard-hero">
                <div>
                  <p className="dashboard-kicker">Dashboard semanal consolidado</p>
                  <h3>
                    {selectedWeek?.week_code ?? "Semana activa"} · {selectedWeek?.week_role ?? "Sin rol"}
                  </h3>
                  <p className="section-subtitle">Lectura operativa de cumplimiento, volumen, trazabilidad y decisiones de la semana.</p>
                </div>
                <div className={operationalStatus === "Semana cerrada" ? "dashboard-status is-ready" : "dashboard-status is-open"}>
                  <span>Estado semanal</span>
                  <strong>{isWeeklyReviewClosed ? "Revision cerrada" : operationalStatus}</strong>
                  <small>{isWeeklyReviewClosed ? `Cerrada el ${toDateTimeLabel(weeklyReview?.closed_at ?? null)}` : operationalFocus}</small>
                </div>
              </div>

              <div className="summary-strip dashboard-summary-strip">
                <article>
                  <strong>{toPercentLabel(adherenceRate)}</strong>
                  <span>Cumplimiento</span>
                  <small>
                    {weeklySummary.completed} completadas · {weeklySummary.partial} parciales
                  </small>
                </article>
                <article>
                  <strong>{toPercentLabel(traceabilityRate)}</strong>
                  <span>Trazabilidad</span>
                  <small>
                    {trackedCount} de {weeklySummary.total} sesiones con cierre
                  </small>
                </article>
                <article>
                  <strong>{toHoursLabel(weeklySummary.actualMinutes)}</strong>
                  <span>Carga real</span>
                  <small>{volumeStatus}</small>
                </article>
                <article>
                  <strong>{toHoursLabel(totalLoadMinutes)}</strong>
                  <span>Carga total</span>
                  <small>{toHoursLabel(optionalDailyMinutes + otherDailyMinutes)} fuera del plan · {toHoursLabel(supportDailyMinutes)} soporte movilidad</small>
                </article>
                <article>
                  <strong>
                    {keySessionsClosed}/{keySessionRows.length || 0}
                  </strong>
                  <span>Sesiones clave</span>
                  <small>{keySessionRows.length > 0 ? "cerradas o ajustadas" : "sin sesiones marcadas"}</small>
                </article>
                <article>
                  <strong>{optionalDailyActivities.length}</strong>
                  <span>Extras diarios</span>
                  <small>{optionalStrengthCount} fuerza</small>
                </article>
                <article>
                  <strong>{weeklyReview?.zone_comparison_summary?.items.length ?? 0}</strong>
                  <span>Vistas de zona</span>
                  <small>{weeklyReview?.zone_comparison_summary?.items.map((item) => formatZoneBasisLabel(item.metric_basis)).join(" · ") || "sin comparativa"}</small>
                </article>
              </div>

              {weeklyReview?.zone_comparison_summary && weeklyReview.zone_comparison_summary.items.length > 0 ? (
                <div className="zone-week-summary-grid">
                  {weeklyReview.zone_comparison_summary.items.map((item) => (
                    <article key={item.metric_basis} className="dashboard-card zone-week-summary-card">
                      <span className="dashboard-label">{formatZoneBasisLabel(item.metric_basis)}</span>
                      <strong>{item.aligned_count}/{item.planned_session_count}</strong>
                      <p>
                        {item.aligned_count} alineadas · {item.limited_count} limitadas · {item.misaligned_count} desalineadas
                      </p>
                    </article>
                  ))}
                </div>
              ) : null}

              <div className="dashboard-grid">
                <article className="dashboard-card">
                  <span className="dashboard-label">Banda objetivo</span>
                  <strong>
                    {selectedWeek?.target_volume_hours_min ?? "-"}h - {selectedWeek?.target_volume_hours_max ?? "-"}h
                  </strong>
                  <p>
                    Referencia calculada desde las sesiones planificadas: {toHoursLabel(plannedLowerMinutes)} - {toHoursLabel(plannedUpperMinutes)}.
                  </p>
                </article>

                <article className="dashboard-card">
                  <span className="dashboard-label">Desviacion de carga</span>
                  <strong>
                    {volumeDeltaMinutes === 0 ? "En linea" : `${volumeDeltaMinutes > 0 ? "+" : "-"}${toHoursLabel(Math.abs(volumeDeltaMinutes))}`}
                  </strong>
                  <p>{weeklySummary.actualMinutes === 0 ? "Sin ejecucion registrada aun." : `Contra una referencia media de ${toHoursLabel(plannedReferenceMinutes)}.`}</p>
                </article>

                <article className="dashboard-card">
                  <span className="dashboard-label">Desviaciones operativas</span>
                  <strong>
                    {weeklySummary.pending + skippedCount + replacedCount}
                  </strong>
                  <p>
                    {weeklySummary.pending} pendientes · {skippedCount} skipped · {replacedCount} replaced
                  </p>
                </article>

                <article className="dashboard-card dashboard-card-emphasis">
                  <span className="dashboard-label">Riesgo semanal</span>
                  <strong>{persistedRiskLevel}</strong>
                  <p>{persistedRecommendation}</p>
                </article>
              </div>

              <div className="dashboard-insights">
                {dashboardSignals.map((signal) => (
                  <article key={signal} className="dashboard-insight-card">
                    <p>{signal}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : (
            <div className="empty-state-card empty-state-card-wide">
              <strong>Dashboard pendiente</strong>
              <p>No hay una semana cargada para consolidar cumplimiento, volumen y decisiones.</p>
            </div>
          )}

          {selectedWeek ? (
            <div className="session-table-wrapper">
              <table className="session-table plan-real-table">
                <thead>
                  <tr>
                    <th>Dia</th>
                    <th>Plan</th>
                    <th>Real</th>
                    <th>Estado</th>
                    <th>Sensacion</th>
                    <th>Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {planVsRealRows.map((row) => {
                    const rowActivities = getPlanVsRealActivities(row);
                    const optionalDailyActivities = getOptionalDailyActivities(row);
                    const supportDailyActivities = getSupportDailyActivities(row);
                    const otherDailyActivities = getOtherDailyActivities(row);
                    const optionalDailyLoadMinutes = getOptionalDailyLoadMinutes(row);
                    const supportDailyLoadMinutes = getSupportDailyLoadMinutes(row);
                    const otherDailyLoadMinutes = getOtherDailyLoadMinutes(row);
                    const dailyTotalLoadMinutes = getDailyTotalLoadMinutes(row);
                    const isRowClickable = rowActivities.length === 1;
                    const hasSelectedActivity = rowActivities.some((activity) => activity.activity_id === selectedActivity?.activity_id);

                    return (
                      <tr
                        key={row.planned_session_id}
                        className={`${row.is_key_session ? 'key-session ' : ''}${isRowClickable ? 'clickable-row' : ''}${hasSelectedActivity ? ' selected-row' : ''}`.trim()}
                        onClick={isRowClickable ? () => void loadActivityDetail(rowActivities[0].activity_id) : undefined}
                      >
                        <td>
                          <strong>{row.day_name}</strong>
                          <small>{row.session_date}</small>
                        </td>
                        <td>
                          <strong>{toPlannedRoleLabel(row.planned_role ?? row.planned_type)}</strong>
                          <small>{getPlanVsRealPlannedText(row)}</small>
                          <button
                            className="table-link-button"
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              focusPlannedSessionDetail(row.planned_session_id);
                            }}
                          >
                            Ver sesion estructurada
                          </button>
                          {row.planned_support_routine ? <small>Soporte opcional diario: {row.planned_support_routine}</small> : null}
                        </td>
                        <td>
                          {rowActivities.length > 0 ? (
                            <div className="plan-real-activity-list">
                              {rowActivities.map((activity) => (
                                <div
                                  key={activity.activity_id}
                                  className={`plan-real-activity-item${selectedActivity?.activity_id === activity.activity_id ? ' selected' : ''}`}
                                >
                                  <strong>{toPlanVsRealActivityLabel(activity)}</strong>
                                  {toPlanVsRealMetaLabel(activity) ? <small>{toPlanVsRealMetaLabel(activity)}</small> : null}
                                  {toPlanVsRealResolutionLabel(activity) ? <small>{toPlanVsRealResolutionLabel(activity)}</small> : null}
                                  <button
                                    className="table-link-button"
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void loadActivityDetail(activity.activity_id);
                                    }}
                                  >
                                    Ver actividad #{activity.activity_id}
                                  </button>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <strong>Sin actividad</strong>
                          )}
                          {optionalDailyActivities.length > 0 ? (
                            <div className="plan-real-optional-list">
                              <small className="plan-real-optional-title">Opcionales del dia</small>
                              {optionalDailyActivities.map((activity) => (
                                <div key={activity.activity_id} className="plan-real-optional-item">
                                  <strong>{toOptionalDailyLabel(activity)}</strong>
                                  <small>{toPlanVsRealActivityLabel(activity)}</small>
                                  {toOptionalDailyMetaLabel(activity) ? <small>{toOptionalDailyMetaLabel(activity)}</small> : null}
                                  <button
                                    className="table-link-button"
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void loadActivityDetail(activity.activity_id);
                                    }}
                                  >
                                    Ver actividad #{activity.activity_id}
                                  </button>
                                </div>
                              ))}
                            </div>
                          ) : null}
                          {supportDailyActivities.length > 0 ? (
                            <div className="plan-real-optional-list">
                              <small className="plan-real-optional-title">Soporte de flexibilidad</small>
                              {supportDailyActivities.map((activity) => (
                                <div key={activity.activity_id} className="plan-real-optional-item">
                                  <strong>{toSupportDailyLabel(activity)}</strong>
                                  <small>{toPlanVsRealActivityLabel(activity)}</small>
                                  {toOptionalDailyMetaLabel(activity) ? <small>{toOptionalDailyMetaLabel(activity)}</small> : null}
                                  <button
                                    className="table-link-button"
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void loadActivityDetail(activity.activity_id);
                                    }}
                                  >
                                    Ver actividad #{activity.activity_id}
                                  </button>
                                </div>
                              ))}
                            </div>
                          ) : null}
                          {otherDailyActivities.length > 0 ? (
                            <div className="plan-real-optional-list">
                              <small className="plan-real-optional-title">Otras actividades del dia</small>
                              {otherDailyActivities.map((activity) => (
                                <div key={activity.activity_id} className="plan-real-optional-item">
                                  <strong>{toOtherDailyLabel(activity)}</strong>
                                  <small>{toPlanVsRealActivityLabel(activity)}</small>
                                  {toOtherDailyMetaLabel(activity) ? <small>{toOtherDailyMetaLabel(activity)}</small> : null}
                                  <button
                                    className="table-link-button"
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void loadActivityDetail(activity.activity_id);
                                    }}
                                  >
                                    Ver actividad #{activity.activity_id}
                                  </button>
                                </div>
                              ))}
                            </div>
                          ) : null}
                          <small>
                            Carga total del dia: {toHoursLabel(dailyTotalLoadMinutes)}
                            {optionalDailyLoadMinutes > 0 || supportDailyLoadMinutes > 0 || otherDailyLoadMinutes > 0
                              ? ` (${toHoursLabel(row.actual_duration_min ?? 0)} plan + ${toHoursLabel(optionalDailyLoadMinutes + otherDailyLoadMinutes)} fuera del plan + ${toHoursLabel(supportDailyLoadMinutes)} soporte movilidad)`
                              : ''}
                          </small>
                          <small>{row.actual_summary ?? 'Sin revision diaria'}</small>
                          {row.daily_assessment_available && row.daily_assessment_url ? (
                            <button
                              className="table-link-button"
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                void loadDailyAssessment(row);
                              }}
                            >
                              Ver assessment diario
                            </button>
                          ) : null}
                        </td>
                        <td>
                          <span className={toBadgeClass(row.compliance_status)}>{row.compliance_status}</span>
                        </td>
                        <td>
                          {row.general_feeling ?? '-'}
                          <small>{row.perceived_exertion ? `RPE ${row.perceived_exertion}` : 'Sin RPE'}</small>
                        </td>
                        <td>{row.next_day_decision ?? '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          {selectedWeek ? (
            <div className="week-review-card">
              <h3>Revision semanal minima</h3>
              <p>
                {persistedSummary ?? `${selectedWeek?.week_code ?? 'Esta semana'}: ${weeklySummary.completed} completadas, ${weeklySummary.partial} parciales, ${weeklySummary.pending} pendientes y ${weeklySummary.other} con otro estado. La semana acumula ${weeklySummary.actualMinutes} minutos reales.`}
              </p>
              <p>
                Carga total registrada: {toHoursLabel(totalLoadMinutes)}. De ese total, {toHoursLabel(weeklySummary.actualMinutes)} corresponden a sesiones del plan, {toHoursLabel(optionalDailyMinutes + otherDailyMinutes)} a actividades fuera del plan y {toHoursLabel(supportDailyMinutes)} a flexibilidad de soporte.
              </p>
              <p>
                Opcionales diarios: {optionalDailyActivities.length === 0 ? 'sin registro adicional.' : `${optionalStrengthCount} sesiones de fuerza, con ${optionalDailyMinutes} minutos acumulados.`}
              </p>
              <p>
                Soporte de flexibilidad: {supportDailyActivities.length === 0 ? 'sin registro adicional.' : `${supportFlexibilityCount} sesiones de yoga, con ${supportDailyMinutes} minutos acumulados.`}
              </p>
              <p>
                Otras actividades ejecutadas: {otherDailyActivities.length === 0 ? 'sin actividad extra registrada.' : `${otherDailyActivities.length} actividades no enlazadas, con ${otherDailyMinutes} minutos acumulados.`}
              </p>
              <p>
                Criterio operativo: {isWeeklyReviewClosed ? `Revision persistida en SQLite el ${toDateTimeLabel(weeklyReview?.closed_at ?? null)}.` : operationalFocus}
              </p>
              <p>
                Recomendacion: {persistedRecommendation}
              </p>
              <div className="review-actions">
                <button className="secondary-button" type="button" onClick={() => void closeWeeklyReview()} disabled={savingWeeklyReview || isWeeklyReviewClosed}>
                  {savingWeeklyReview && !isWeeklyReviewClosed ? "Cerrando..." : "Cerrar revision semanal"}
                </button>
                <button className="ghost-button" type="button" onClick={() => void reopenWeeklyReview()} disabled={savingWeeklyReview || !isWeeklyReviewClosed}>
                  {savingWeeklyReview && isWeeklyReviewClosed ? "Reabriendo..." : "Reabrir revision"}
                </button>
                {weeklyReview?.weekly_assessment_available && weeklyReview.weekly_assessment_url ? (
                  <button className="ghost-button" type="button" onClick={() => void loadWeeklyAssessment()} disabled={loadingWeeklyAssessment}>
                    {loadingWeeklyAssessment ? "Cargando assessment semanal..." : "Ver assessment semanal"}
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}

          {selectedBlock ? (
            <div className="week-review-card daily-assessment-card">
              <div className="daily-assessment-card-head">
                <div>
                  <h3>Assessment bloque</h3>
                  <p className="daily-assessment-subtitle">Cierre narrativo del bloque seleccionado, accesible sin salir de la GUI.</p>
                </div>
                {selectedBlockAssessmentMarkdown ? (
                  <button className="ghost-button" type="button" onClick={() => setSelectedBlockAssessmentMarkdown(null)}>
                    Cerrar assessment bloque
                  </button>
                ) : null}
              </div>

              {blockReview?.block_code ? (
                <p>
                  {blockReview.block_code} · {blockReview.block_name ?? selectedBlock.block_name} · {blockReview.risk_level ?? "Sin riesgo persistido"}
                </p>
              ) : null}

              {blockReview?.summary_text ? <p>{blockReview.summary_text}</p> : null}

              {blockReview?.block_assessment_available && blockReview.block_assessment_url ? (
                <div className="review-actions">
                  <button className="ghost-button" type="button" onClick={() => void loadBlockAssessment()} disabled={loadingBlockAssessment}>
                    {loadingBlockAssessment ? "Cargando assessment bloque..." : "Ver assessment bloque"}
                  </button>
                </div>
              ) : null}

              {loadingBlockAssessment ? (
                <p>Cargando assessment bloque...</p>
              ) : selectedBlockAssessmentMarkdown ? (
                <article className="daily-assessment-markdown" aria-label="assessment bloque renderizado">
                  <ReactMarkdown>{selectedBlockAssessmentMarkdown}</ReactMarkdown>
                </article>
              ) : (
                <div className="empty-state-card">
                  <strong>{blockReview?.block_assessment_available ? "Assessment bloque disponible sin abrir" : "Sin assessment bloque persistido"}</strong>
                  <p>
                    {blockReview?.block_assessment_available
                      ? 'Pulsa en "Ver assessment bloque" para abrir el cierre del bloque en esta misma vista.'
                      : "Cuando exista una valoracion de bloque persistida, podras abrirla aqui."}
                  </p>
                </div>
              )}
            </div>
          ) : null}

          {selectedSeason ? (
            <div className="week-review-card daily-assessment-card">
              <div className="daily-assessment-card-head">
                <div>
                  <h3>Assessment peso</h3>
                  <p className="daily-assessment-subtitle">Ultima valoracion de peso persistida para la temporada seleccionada.</p>
                </div>
                {selectedWeightAssessmentMarkdown ? (
                  <button className="ghost-button" type="button" onClick={() => setSelectedWeightAssessmentMarkdown(null)}>
                    Cerrar assessment peso
                  </button>
                ) : null}
              </div>

              {weightReview?.review_date ? (
                <p>
                  {weightReview.review_date} · {weightReview.classification ?? "Sin clasificacion"}
                </p>
              ) : null}

              {weightReview?.summary_text ? <p>{weightReview.summary_text}</p> : null}

              {weightReview?.weight_assessment_available && weightReview.weight_assessment_url ? (
                <div className="review-actions">
                  <button className="ghost-button" type="button" onClick={() => void loadWeightAssessment()} disabled={loadingWeightAssessment}>
                    {loadingWeightAssessment ? "Cargando assessment peso..." : "Ver assessment peso"}
                  </button>
                </div>
              ) : null}

              {loadingWeightAssessment ? (
                <p>Cargando assessment peso...</p>
              ) : selectedWeightAssessmentMarkdown ? (
                <article className="daily-assessment-markdown" aria-label="assessment peso renderizado">
                  <ReactMarkdown>{selectedWeightAssessmentMarkdown}</ReactMarkdown>
                </article>
              ) : (
                <div className="empty-state-card">
                  <strong>{weightReview?.review_date ? "Assessment peso disponible sin abrir" : "Sin assessment peso persistido"}</strong>
                  <p>
                    {weightReview?.review_date
                      ? "Pulsa en \"Ver assessment peso\" para abrir la ultima valoracion de peso en esta misma vista."
                      : "Cuando exista una valoracion de peso persistida para la temporada, podras abrirla aqui."}
                  </p>
                </div>
              )}
            </div>
          ) : null}

          {selectedWeek ? (
            <div className="week-review-card daily-assessment-card">
              <div className="daily-assessment-card-head">
                <div>
                  <h3>Assessment semanal</h3>
                  <p className="daily-assessment-subtitle">Logbook narrativo semanal, accesible sin salir de la GUI.</p>
                </div>
                {selectedWeeklyAssessmentMarkdown ? (
                  <button className="ghost-button" type="button" onClick={() => setSelectedWeeklyAssessmentMarkdown(null)}>
                    Cerrar assessment semanal
                  </button>
                ) : null}
              </div>

              {loadingWeeklyAssessment ? (
                <p>Cargando assessment semanal...</p>
              ) : selectedWeeklyAssessmentMarkdown ? (
                <article className="daily-assessment-markdown" aria-label="assessment semanal renderizado">
                  <ReactMarkdown>{selectedWeeklyAssessmentMarkdown}</ReactMarkdown>
                </article>
              ) : (
                <div className="empty-state-card">
                  <strong>Sin assessment semanal cargado</strong>
                  <p>Cuando exista una valoracion semanal persistida, podras abrirla aqui desde la revision semanal.</p>
                </div>
              )}
            </div>
          ) : null}

          {selectedWeek ? (
            <div className="week-review-card daily-assessment-card">
              <div className="daily-assessment-card-head">
                <div>
                  <h3>Assessment diario</h3>
                  <p className="daily-assessment-subtitle">Logbook narrativo del dia seleccionado, accesible sin salir de la GUI.</p>
                </div>
                {selectedDailyAssessment ? (
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => setSelectedDailyAssessment(null)}
                  >
                    Cerrar assessment
                  </button>
                ) : null}
              </div>

              {loadingDailyAssessment ? (
                <p>Cargando assessment diario...</p>
              ) : selectedDailyAssessment ? (
                <>
                  <p>
                    {selectedDailyAssessment.sessionDate} · {selectedDailyAssessment.plannedSession}
                  </p>
                  <article className="daily-assessment-markdown" aria-label="assessment diario renderizado">
                    <ReactMarkdown>{selectedDailyAssessment.markdown}</ReactMarkdown>
                  </article>
                </>
              ) : (
                <div className="empty-state-card">
                  <strong>Sin assessment diario cargado</strong>
                  <p>Pulsa en "Ver assessment diario" dentro de Plan vs realidad para abrir el logbook en esta misma vista.</p>
                </div>
              )}
            </div>
          ) : null}
        </section>

        <section className="panel panel-form">
          <div className="section-heading">
            <div>
              <h2>Metricas del dia</h2>
              <p className="section-subtitle">Lectura diaria independiente de las actividades, ligada al dia seleccionado dentro de la semana.</p>
            </div>
          </div>

          {selectedWeek ? (
            <>
              <div className="day-chip-row">
                {dailyMetricDates.map((metricDate) => (
                  <button
                    key={metricDate}
                    type="button"
                    className={metricDate === selectedDailyMetricDate ? "day-chip selected" : "day-chip"}
                    onClick={() => setSelectedDailyMetricDate(metricDate)}
                  >
                    {metricDate}
                  </button>
                ))}
              </div>

              {loadingDailyMetric ? (
                <div className="empty-state-card empty-state-card-wide">
                  <strong>Cargando metricas del dia</strong>
                  <p>Recuperando fisiologia y contexto diario para {selectedDailyMetricDate ?? "la fecha activa"}.</p>
                </div>
              ) : selectedDailyMetric ? (
                <div className="activity-quality-card panel-subcard">
                  <div className="activity-quality-head">
                    <div>
                      <strong>{selectedDailyMetric.metric_date}</strong>
                      <p className="activity-quality-copy">Senales diarias de recuperacion y contexto, separadas de la actividad realizada.</p>
                    </div>
                    <span className={toSourceChipClass(selectedDailyMetric.source_system)}>{toSourceLabel(selectedDailyMetric.source_system)}</span>
                  </div>

                  <div className="activity-detail-grid">
                    {selectedDailyMetric.load_model ? <article><span>Carga del dia</span><strong>{toMetricLabel(selectedDailyMetric.load_model.daily_training_load)}</strong></article> : null}
                    {selectedDailyMetric.load_model ? <article><span>ATL</span><strong>{toMetricLabel(selectedDailyMetric.load_model.atl)}</strong></article> : null}
                    {selectedDailyMetric.load_model ? <article><span>CTL</span><strong>{toMetricLabel(selectedDailyMetric.load_model.ctl)}</strong></article> : null}
                    {selectedDailyMetric.load_model ? <article><span>TSB</span><strong>{toMetricLabel(selectedDailyMetric.load_model.tsb)}</strong></article> : null}
                    {selectedDailyMetric.weight_kg != null ? <article><span>Peso</span><strong>{toMetricLabel(selectedDailyMetric.weight_kg, " kg")}</strong></article> : null}
                    {selectedDailyMetric.body_fat_pct != null ? <article><span>Grasa corporal</span><strong>{toMetricLabel(selectedDailyMetric.body_fat_pct, "%")}</strong></article> : null}
                    {selectedDailyMetric.body_water_pct != null ? <article><span>Agua corporal</span><strong>{toMetricLabel(selectedDailyMetric.body_water_pct, "%")}</strong></article> : null}
                    {selectedDailyMetric.muscle_mass_kg != null ? <article><span>Masa muscular</span><strong>{toMetricLabel(selectedDailyMetric.muscle_mass_kg, " kg")}</strong></article> : null}
                    {selectedDailyMetric.bone_mass_kg != null ? <article><span>Masa osea</span><strong>{toMetricLabel(selectedDailyMetric.bone_mass_kg, " kg")}</strong></article> : null}
                    {selectedDailyMetric.bmi != null ? <article><span>IMC Garmin</span><strong>{toMetricLabel(selectedDailyMetric.bmi)}</strong></article> : null}
                    {selectedDailyMetric.visceral_fat != null ? <article><span>Grasa visceral</span><strong>{toMetricLabel(selectedDailyMetric.visceral_fat)}</strong></article> : null}
                    {selectedDailyMetric.metabolic_age != null ? <article><span>Edad metabolica</span><strong>{toMetricLabel(selectedDailyMetric.metabolic_age)}</strong></article> : null}
                    {selectedDailyMetric.physique_rating != null ? <article><span>Physique rating</span><strong>{toMetricLabel(selectedDailyMetric.physique_rating)}</strong></article> : null}
                    {selectedDailyMetric.sleep_hours != null ? <article><span>Sueno</span><strong>{toMetricLabel(selectedDailyMetric.sleep_hours, " h")}</strong></article> : null}
                    {selectedDailyMetric.sleep_quality != null ? <article><span>Calidad sueno</span><strong>{selectedDailyMetric.sleep_quality}</strong></article> : null}
                    {selectedDailyMetric.resting_hr != null ? <article><span>FC reposo</span><strong>{toMetricLabel(selectedDailyMetric.resting_hr, " bpm")}</strong></article> : null}
                    {selectedDailyMetric.vo2max_cycling != null ? <article><span>VO2max ciclismo Garmin</span><strong>{toMetricLabel(selectedDailyMetric.vo2max_cycling, " ml/kg/min")}</strong></article> : null}
                    {selectedDailyMetric.vo2max_running != null ? <article><span>VO2max carrera Garmin</span><strong>{toMetricLabel(selectedDailyMetric.vo2max_running, " ml/kg/min")}</strong></article> : null}
                    {selectedDailyMetric.lactate_threshold_hr != null ? <article><span>FC umbral Garmin</span><strong>{toMetricLabel(selectedDailyMetric.lactate_threshold_hr, " bpm")}</strong></article> : null}
                    {selectedDailyMetric.hrv != null ? <article><span>HRV</span><strong>{toMetricLabel(selectedDailyMetric.hrv)}</strong></article> : null}
                    {selectedDailyMetric.body_battery != null ? <article><span>Body Battery</span><strong>{toMetricLabel(selectedDailyMetric.body_battery)}</strong></article> : null}
                    {selectedDailyMetric.total_steps != null ? <article><span>Pasos</span><strong>{toMetricLabel(selectedDailyMetric.total_steps)}</strong></article> : null}
                    {selectedDailyMetric.total_distance_m != null ? <article><span>Distancia pie</span><strong>{toMetricLabel(selectedDailyMetric.total_distance_m / 1000, " km")}</strong></article> : null}
                    {selectedDailyMetric.step_goal != null ? <article><span>Objetivo pasos</span><strong>{toMetricLabel(selectedDailyMetric.step_goal)}</strong></article> : null}
                    {selectedDailyMetric.stress_avg != null ? <article><span>Estres medio</span><strong>{toMetricLabel(selectedDailyMetric.stress_avg)}</strong></article> : null}
                    {selectedDailyMetric.stress_max != null ? <article><span>Estres pico</span><strong>{toMetricLabel(selectedDailyMetric.stress_max)}</strong></article> : null}
                    {selectedDailyMetric.spo2_sleep_avg != null ? <article><span>SpO2 sueno</span><strong>{toMetricLabel(selectedDailyMetric.spo2_sleep_avg, "%")}</strong></article> : null}
                    {selectedDailyMetric.spo2_avg != null ? <article><span>SpO2 media</span><strong>{toMetricLabel(selectedDailyMetric.spo2_avg, "%")}</strong></article> : null}
                    {selectedDailyMetric.spo2_7d_avg != null ? <article><span>SpO2 7 dias</span><strong>{toMetricLabel(selectedDailyMetric.spo2_7d_avg, "%")}</strong></article> : null}
                    {selectedDailyMetric.spo2_lowest != null ? <article><span>SpO2 minima</span><strong>{toMetricLabel(selectedDailyMetric.spo2_lowest, "%")}</strong></article> : null}
                    {selectedDailyMetric.subjective_energy != null ? <article><span>Energia subjetiva</span><strong>{toMetricLabel(selectedDailyMetric.subjective_energy)}</strong></article> : null}
                    {selectedDailyMetric.subjective_fatigue != null ? <article><span>Fatiga subjetiva</span><strong>{toMetricLabel(selectedDailyMetric.subjective_fatigue)}</strong></article> : null}
                    {selectedDailyMetric.soreness != null ? <article><span>Molestias</span><strong>{selectedDailyMetric.soreness}</strong></article> : null}
                  </div>

                  {hasBodyCompositionMetrics(selectedDailyMetric) ? (
                    <div className="activity-detail-notes">
                      <p><strong>Composicion corporal Garmin:</strong> estos campos vienen del pesaje/escala Garmin del dia y ayudan a distinguir si el cambio de peso parece venir de grasa, agua o tejido magro.</p>
                    </div>
                  ) : null}

                  {selectedDailyMetric.notes ? (
                    <div className="activity-detail-notes">
                      <p><strong>Notas:</strong> {selectedDailyMetric.notes}</p>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="empty-state-card empty-state-card-wide">
                  <strong>Sin metricas diarias</strong>
                  <p>No hay registro diario disponible para {selectedDailyMetricDate ?? "la fecha activa"}.</p>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state-card empty-state-card-wide">
              <strong>Sin semana seleccionada</strong>
              <p>Selecciona una semana para ver y cambiar las metricas del dia.</p>
            </div>
          )}

          <div className="section-heading">
            <div>
              <h2>Actividad seleccionada</h2>
              <p className="section-subtitle">Ficha minima con los campos reales disponibles en SQLite.</p>
            </div>
          </div>

          {loadingActivity ? (
            <div className="empty-state-card empty-state-card-wide">
              <strong>Cargando actividad</strong>
              <p>Recuperando detalle de la actividad seleccionada.</p>
            </div>
          ) : selectedActivity ? (
            <div className="activity-detail-card">
              <div className="activity-detail-header">
                <div>
                  <strong>{toActivityTypeLabel(selectedActivity.activity_type, selectedActivity.source_system)}</strong>
                  <div className="activity-origin-row">
                    <span className={toSourceChipClass(selectedActivity.source_system)}>{toSourceLabel(selectedActivity.source_system)}</span>
                    <p>{toDisciplineLabel(selectedActivity.discipline)}</p>
                  </div>
                </div>
                <span className={selectedActivity.compliance_status ? toBadgeClass(selectedActivity.compliance_status) : "badge badge-pending"}>
                  {selectedActivity.compliance_status ?? "sin enlace"}
                </span>
              </div>

              <div className="activity-detail-meta">
                <span>Actividad #{selectedActivity.activity_id}</span>
                <span>Origen: {toSourceLabel(selectedActivity.source_system)}</span>
                {selectedActivity.external_activity_id ? <span>Externa: {selectedActivity.external_activity_id}</span> : null}
                {selectedActivity.power_sensor_manufacturer ? <span>Sensor: {selectedActivity.power_sensor_manufacturer}</span> : null}
              </div>

              <div className="activity-detail-grid">
                <article><span>Fecha</span><strong>{selectedActivity.activity_date}</strong></article>
                <article><span>Inicio</span><strong>{toDateTimeLabel(selectedActivity.started_at)}</strong></article>
                <article><span>Duracion</span><strong>{selectedActivity.duration_seconds != null ? toHoursLabel(Math.round(selectedActivity.duration_seconds / 60)) : "-"}</strong></article>
                <article><span>Calorias</span><strong>{toMetricLabel(selectedActivity.calories)}</strong></article>
                {isDistanceRelevant(selectedActivity) ? <article><span>Distancia</span><strong>{toMetricLabel(selectedActivity.distance_meters != null ? selectedActivity.distance_meters / 1000 : null, " km")}</strong></article> : null}
                {isAscentRelevant(selectedActivity) ? <article><span>Desnivel</span><strong>{toMetricLabel(selectedActivity.ascent_meters, " m")}</strong></article> : null}
                {isHeartRateRelevant(selectedActivity) ? <article><span>FC media/max</span><strong>{`${toMetricLabel(selectedActivity.avg_hr, " bpm")} / ${toMetricLabel(selectedActivity.max_hr, " bpm")}`}</strong></article> : null}
                {selectedActivity.avg_respiration_rate != null || selectedActivity.max_respiration_rate != null ? <article><span>Resp media/max</span><strong>{`${toMetricLabel(selectedActivity.avg_respiration_rate, " rpm resp")} / ${toMetricLabel(selectedActivity.max_respiration_rate, " rpm resp")}`}</strong></article> : null}
                {isPowerRelevant(selectedActivity) ? <article><span>Potencia</span><strong>{toPowerSummary(selectedActivity)}</strong></article> : null}
                {selectedActivity.power_sensor_profile || selectedActivity.power_sensor_label ? <article><span>Sensor de potencia</span><strong>{selectedActivity.power_sensor_label ?? selectedActivity.power_sensor_manufacturer ?? "-"}</strong><small>{toPowerSensorProfileLabel(selectedActivity.power_sensor_profile)}</small></article> : null}
                {selectedActivity.calculated_training_load != null ? <article><span>{toTrainingLoadHeading(selectedActivity)}</span><strong>{toMetricLabel(selectedActivity.calculated_training_load)}</strong><small>{toTrainingLoadSourceLabel(selectedActivity.calculated_training_load_source)}</small></article> : null}
                {selectedActivity.avg_pace_seconds_per_km != null && isPaceDiscipline(selectedActivity.discipline) ? <article><span>Ritmo medio</span><strong>{toPaceLabel(selectedActivity.avg_pace_seconds_per_km)}</strong></article> : null}
                <article><span>RPE</span><strong>{toMetricLabel(selectedActivity.perceived_exertion)}</strong></article>
                <article><span>Sesion planificada</span><strong>{selectedActivity.planned_session_id ?? "-"}</strong></article>
              </div>

              <div className="activity-weather-card panel-subcard">
                <div className="activity-weather-head">
                  <div>
                    <strong>Meteorologia de la actividad</strong>
                    <p className="activity-dynamics-copy">Resumen meteorologico horario muestreado cada 15 min o 5 km sobre la ruta GPS persistida.</p>
                  </div>
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => void enrichSelectedActivityWeather(Boolean(selectedActivity.weather))}
                    disabled={loadingActivityWeather}
                  >
                    {loadingActivityWeather
                      ? (selectedActivity.weather ? "Recalculando..." : "Cargando...")
                      : (selectedActivity.weather ? "Recalcular meteo" : "Cargar meteo")}
                  </button>
                </div>

                {selectedActivity.weather?.summary ? (
                  <>
                    <div className="activity-weather-summary-grid">
                      <article>
                        <span>Condicion dominante</span>
                        <strong>{toWeatherCodeLabel(selectedActivity.weather.summary.dominant_weather_code)}</strong>
                        <small>{selectedActivity.weather.sample_count} muestras</small>
                      </article>
                      <article>
                        <span>Temperatura media</span>
                        <strong>{toMetricLabel(selectedActivity.weather.summary.temperature_mean, " °C")}</strong>
                        <small>Rango: {toTemperatureBandLabel(selectedActivity.weather.summary)}</small>
                      </article>
                      <article>
                        <span>Sensacion termica media</span>
                        <strong>{toMetricLabel(selectedActivity.weather.summary.apparent_temperature_mean, " °C")}</strong>
                        <small>Condicion percibida</small>
                      </article>
                      <article>
                        <span>Precipitacion estimada</span>
                        <strong>{toMetricLabel(selectedActivity.weather.summary.precipitation_sum_est, " mm")}</strong>
                        <small>Lluvia: {toMetricLabel(selectedActivity.weather.summary.rain_sum_est, " mm")}</small>
                      </article>
                      <article>
                        <span>Viento medio / max</span>
                        <strong>{`${toMetricLabel(selectedActivity.weather.summary.wind_speed_mean, " km/h")} / ${toMetricLabel(selectedActivity.weather.summary.wind_speed_max, " km/h")}`}</strong>
                        <small>Racha: {toMetricLabel(selectedActivity.weather.summary.wind_gusts_max, " km/h")}</small>
                      </article>
                      <article>
                        <span>Nubosidad media</span>
                        <strong>{toMetricLabel(selectedActivity.weather.summary.cloud_cover_mean, " %")}</strong>
                        <small>Radiacion: {toMetricLabel(selectedActivity.weather.summary.shortwave_radiation_mean, " W/m²")}</small>
                      </article>
                    </div>

                    <div className="activity-weather-timeline">
                      <div className="activity-weather-timeline-head">
                        <strong>Linea temporal de muestras</strong>
                        <small>{selectedActivity.weather.metadata.sampling_interval_seconds != null && selectedActivity.weather.metadata.sampling_distance_meters != null
                          ? `Paso objetivo: ${Math.round(selectedActivity.weather.metadata.sampling_interval_seconds / 60)} min o ${Math.round(selectedActivity.weather.metadata.sampling_distance_meters / 1000)} km`
                          : "Muestras sobre puntos representativos de la ruta"}</small>
                      </div>
                      <div className="activity-weather-sample-list">
                        {selectedActivity.weather.samples.map((sample) => (
                          <article className="activity-weather-sample-item" key={`${sample.route_point_index}-${sample.sampled_at}`}>
                            <div className="activity-weather-sample-head">
                              <strong>{toWeatherSampleDateTimeLabel(selectedActivity.started_at, sample.elapsed_seconds, sample.sampled_at)}</strong>
                              <span>{toWeatherCodeLabel(sample.weather_code)}</span>
                            </div>
                            <div className="activity-weather-sample-grid">
                              <span>Tramo {sample.route_point_index}</span>
                              <span>{toElapsedTimeLabel(sample.elapsed_seconds)}</span>
                              <span>{toMetricLabel(sample.distance_meters != null ? sample.distance_meters / 1000 : null, " km")}</span>
                              <span>{toMetricLabel(sample.temperature_2m, " °C")}</span>
                              <span>{toMetricLabel(sample.apparent_temperature, " °C aparente")}</span>
                              <span>{toMetricLabel(sample.precipitation, " mm")}</span>
                              <span>{toMetricLabel(sample.wind_speed_10m, " km/h")}</span>
                              <span>{toCardinalWindLabel(sample.wind_direction_10m)}</span>
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="activity-detail-notes">
                    <p><strong>Sin meteorologia persistida.</strong> Usa el boton superior para consultar Open-Meteo y guardar un resumen horario sobre la ruta GPS de esta actividad.</p>
                  </div>
                )}
              </div>

              {(() => {
                const performanceConditionSignal = selectedActivity.activity_metric_analysis?.performance_condition_signal;
                const performanceConditionEvolution = selectedActivity.activity_metric_analysis?.performance_condition_evolution;
                if (!performanceConditionEvolution) {
                  return null;
                }

                return (
                  <div className="activity-dynamics-card panel-subcard">
                    <div className="activity-dynamics-head">
                      <div>
                        <strong>Performance Condition</strong>
                        <p className="activity-dynamics-copy">Lectura narrativa de la evolucion del indicador de Garmin a lo largo de la actividad, usando la serie persistida en SQLite.</p>
                      </div>
                      {performanceConditionSignal?.status ? <span className="status-pill">{formatPerformanceConditionStatus(performanceConditionSignal.status)}</span> : null}
                    </div>

                    {performanceConditionSignal ? (
                      <div className="activity-quality-meta">
                        {performanceConditionSignal.average != null ? <span>Media: {toMetricLabel(performanceConditionSignal.average, " pts")}</span> : null}
                        {performanceConditionSignal.minimum != null ? <span>Min: {toMetricLabel(performanceConditionSignal.minimum, " pts")}</span> : null}
                        {performanceConditionSignal.maximum != null ? <span>Max: {toMetricLabel(performanceConditionSignal.maximum, " pts")}</span> : null}
                      </div>
                    ) : null}

                    <div className="activity-dynamics-insights">
                      <p>{performanceConditionEvolution}</p>
                      {performanceConditionSignal?.notes?.length ? <p>{performanceConditionSignal.notes.join(" ")}</p> : null}
                    </div>
                  </div>
                );
              })()}

              {(() => {
                const runningDynamicsMetrics = getRunningDynamicsMetrics(selectedActivityQuality);
                const runningDynamicsInsights = buildRunningDynamicsInsights(selectedActivity, selectedActivityQuality);
                const runningDynamicsHistoryInsights = buildRunningDynamicsHistoryInsights(selectedActivityQuality, selectedActivityRunningDynamicsHistory);
                return runningDynamicsMetrics.length > 0 ? (
                  <div className="activity-dynamics-card panel-subcard">
                    <div className="activity-dynamics-head">
                      <div>
                        <strong>Running dynamics</strong>
                        <p className="activity-dynamics-copy">Metricas tecnicas expuestas por Garmin para esta actividad, usando los valores limpios persistidos en SQLite.</p>
                      </div>
                      {selectedActivityRunningDynamicsHistory?.compared_activity_count ? <span className="status-pill status-pill-ready">Base {selectedActivityRunningDynamicsHistory.compared_activity_count} sesiones</span> : null}
                    </div>

                    <div className="activity-dynamics-grid">
                      {runningDynamicsMetrics.map((metric) => {
                        const baselineValue = getRunningDynamicsBaselineValue(selectedActivityRunningDynamicsHistory, metric.metric_name);
                        return (
                          <article key={`running-dynamics-${metric.metric_name}`}>
                            <span>{formatMetricNameLabel(metric.metric_name)}</span>
                            <strong>{formatQualityMetricValue(metric.metric_name, getQualitySummaryValue(metric))}</strong>
                            {baselineValue != null && selectedActivityRunningDynamicsHistory?.compared_activity_count ? (
                              <small className="activity-dynamics-baseline">Base reciente ({selectedActivityRunningDynamicsHistory.compared_activity_count}): {formatQualityMetricValue(metric.metric_name, baselineValue)}</small>
                            ) : null}
                          </article>
                        );
                      })}
                    </div>

                    {selectedActivityRunningDynamicsHistory?.compared_activity_count ? (
                      <p className="activity-dynamics-history-note">Comparativa construida con carreras previas comparables de la misma temporada.</p>
                    ) : null}

                    {runningDynamicsInsights.length > 0 ? (
                      <div className="activity-dynamics-insights">
                        {runningDynamicsInsights.map((insight, index) => (
                          <p key={`running-dynamics-insight-${index}`}>{insight}</p>
                        ))}
                      </div>
                    ) : null}

                    {runningDynamicsHistoryInsights.length > 0 ? (
                      <div className="activity-dynamics-insights">
                        {runningDynamicsHistoryInsights.map((insight, index) => (
                          <p key={`running-dynamics-history-insight-${index}`}>{insight}</p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null;
              })()}

              <div className="activity-quality-card panel-subcard">
                <div className="activity-quality-head">
                  <div>
                    <strong>Calidad de lecturas</strong>
                    <p className="activity-quality-copy">Resumen trazable del filtrado sobre las series importadas antes de consolidar FC media y maxima.</p>
                  </div>
                  <div className="activity-quality-actions">
                    <span className={toQualityBadgeClass(selectedActivity.quality_status)}>{formatQualityStatusLabel(selectedActivity.quality_status)}</span>
                    <button className="ghost-button" type="button" onClick={() => void replaySelectedActivityQuality()} disabled={replayingActivityQuality || loadingActivityQuality}>
                      {replayingActivityQuality ? "Reevaluando..." : "Reevaluar"}
                    </button>
                  </div>
                </div>

                <div className="activity-quality-meta">
                  <span>Revision: {selectedActivity.quality_checked_at ? toDateTimeLabel(selectedActivity.quality_checked_at) : "pendiente"}</span>
                  <span>Regla: {selectedActivity.quality_rule_version ?? "sin version"}</span>
                  <span>Decisiones: {selectedActivity.quality_decision_count ?? 0}</span>
                  <span>Metricas limitadas: {selectedActivity.quality_limited_metric_count ?? 0}</span>
                  {selectedActivityQuality?.activity.source_reading_fingerprint ? <span>Fingerprint: {selectedActivityQuality.activity.source_reading_fingerprint}</span> : null}
                </div>

                {loadingActivityQuality ? (
                  <p className="activity-quality-empty">Recuperando detalle de calidad...</p>
                ) : selectedActivityQuality && selectedActivityQuality.metrics.length > 0 ? (
                  <div className="activity-quality-metric-list">
                    {selectedActivityQuality.metrics.map((metric) => (
                      <article key={metric.metric_name} className="activity-quality-metric">
                        <div className="item-head">
                          <strong>{formatMetricNameLabel(metric.metric_name)}</strong>
                          <span className={toQualityBadgeClass(metric.metric_status)}>{formatQualityStatusLabel(metric.metric_status)}</span>
                        </div>
                        <p className="activity-quality-counts">
                          {metric.accepted_reading_count} aceptadas de {metric.evaluated_reading_count} lecturas · {metric.excluded_reading_count} excluidas
                        </p>
                        <div className="activity-quality-impact-list">
                          {metric.summary_impacts.map((impact) => (
                            <div key={`${metric.metric_name}-${impact.summary_kind}`} className="activity-quality-impact-item">
                              <strong>{formatQualitySummaryKindLabel(impact.summary_kind)}</strong>
                              <span>
                                {impact.changed_by_filter
                                  ? `${formatQualityMetricValue(metric.metric_name, impact.source_value)} -> ${formatQualityMetricValue(metric.metric_name, impact.trusted_value)}`
                                  : formatQualityMetricValue(metric.metric_name, impact.trusted_value)}
                              </span>
                            </div>
                          ))}
                        </div>
                        {metric.decisions.length > 0 ? (
                          <div className="activity-quality-decision-list">
                            {metric.decisions.map((decision) => (
                              <div key={decision.quality_decision_id} className="activity-quality-decision-item">
                                <strong>{formatQualityDecisionReason(decision.reason_code)}</strong>
                                <span>{formatQualitySampleRange(decision.start_sample_index, decision.end_sample_index)}</span>
                                {decision.threshold_high != null ? <span>Techo: {toMetricLabel(decision.threshold_high, metric.metric_name === "heart_rate" ? " bpm" : "")}</span> : null}
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="activity-quality-empty">No hay detalle persistido para esta actividad. Si es una importacion antigua, usa "Reevaluar" para reconstruirlo desde el artefacto guardado.</p>
                )}
              </div>

              <div className="activity-detail-notes">
                <p><strong>Captura:</strong> {selectedActivity.source_system === "garmin" ? "Importada desde Garmin Connect y normalizada en SQLite." : "Registrada manualmente y guardada en SQLite."}</p>
                <p><strong>Resumen:</strong> {selectedActivity.actual_summary ?? selectedActivity.notes ?? "Sin resumen adicional."}</p>
                <p><strong>Sensacion:</strong> {selectedActivity.general_feeling ?? selectedActivity.subjective_feeling ?? "-"}</p>
                <p><strong>Decision siguiente:</strong> {selectedActivity.next_day_decision ?? "-"}</p>
                <p><strong>Racional:</strong> {selectedActivity.rationale ?? "-"}</p>
              </div>
            </div>
          ) : (
            <div className="empty-state-card empty-state-card-wide">
              <strong>Sin actividad seleccionada</strong>
              <p>Pulsa en "Ver actividad" dentro de Plan vs realidad para abrir su ficha.</p>
            </div>
          )}
        </section>
      </section>
    </div>
  );
}
