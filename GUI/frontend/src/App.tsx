import { useEffect, useState, type ChangeEvent } from "react";

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
  planned_type: string;
  objective: string;
  primary_session: string;
  complementary_session: string | null;
  intensity_class: string | null;
  duration_min: number | null;
  duration_max: number | null;
  is_key_session: number;
  has_structured_prescription: number;
};

type SessionPrescriptionOption = {
  exercise_option_id: number;
  sequence_order: number;
  option_name: string;
  equipment: string | null;
  condition_notes: string | null;
};

type SessionPrescriptionExercise = {
  prescription_exercise_id: number;
  prescription_block_id: number;
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
  options: SessionPrescriptionOption[];
};

type SessionPrescriptionBlock = {
  prescription_block_id: number;
  sequence_order: number;
  block_type: string;
  block_name: string | null;
  objective: string | null;
  rounds: number | null;
  rest_seconds: number | null;
  notes: string | null;
  exercises: SessionPrescriptionExercise[];
};

type SessionPrescription = {
  planned_session_id: number;
  session_date: string;
  day_name: string;
  planned_type: string;
  objective: string | null;
  primary_session: string | null;
  complementary_session: string | null;
  prescription_id: number;
  prescription_type: string;
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
  source_markdown_path: string | null;
  blocks: SessionPrescriptionBlock[];
};

type PlanVsRealRow = {
  planned_session_id: number;
  session_date: string;
  day_name: string;
  planned_type: string;
  planned_objective: string;
  planned_session: string;
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
  compliance_status: string;
  actual_summary: string | null;
  general_feeling: string | null;
  next_day_decision: string | null;
  activities?: PlanVsRealActivity[];
  optional_daily_activities?: OptionalDailyActivity[];
  other_daily_activities?: DailyUnlinkedActivity[];
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
  avg_power: number | null;
  normalized_power: number | null;
  training_load: number | null;
  avg_pace_seconds_per_km: number | null;
  perceived_exertion: number | null;
  subjective_feeling: string | null;
  source_file: string | null;
  raw_payload_path: string | null;
  notes: string | null;
  planned_session_id: number | null;
  compliance_status: string | null;
  rationale: string | null;
  actual_summary: string | null;
  general_feeling: string | null;
  next_day_decision: string | null;
};

function getTodayIsoDate() {
  return new Date().toISOString().slice(0, 10);
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
  avg_pace_seconds_per_km: number | null;
  perceived_exertion: number | null;
  subjective_feeling: string | null;
  raw_payload_path: string | null;
  notes: string | null;
  planned_session_id: number | null;
  compliance_status: string | null;
  rationale: string | null;
  actual_summary: string | null;
  general_feeling: string | null;
  next_day_decision: string | null;
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
  rows_detected: number;
  rows_loaded: number;
  status: string;
  notes: string[];
  breakdown: {
    activity_rows_inserted: number;
    activity_rows_updated: number;
    daily_metric_rows_inserted: number;
    daily_metric_rows_updated: number;
  };
  has_breakdown_details: boolean;
};

type GarminImportRunResponse = {
  status: string;
  counts: {
    activities_detected: number;
    daily_metrics_detected: number;
  };
  metadata: {
    notes: string[];
  };
  import_job: {
    import_job_id: number;
    status: string;
    rows_detected: number;
    rows_loaded: number;
    notes: string[];
    breakdown: ImportJob["breakdown"];
    has_breakdown_details: boolean;
  };
};

const emptyGarminImportForm = (): GarminImportFormState => ({
  date_from: "2026-05-04",
  date_to: "2026-05-10",
  include_daily_metrics: true,
});

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Error ${response.status} cargando ${path}`);
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

function toDurationLabel(min: number | null, max: number | null) {
  if (min == null) {
    return "-";
  }
  if (max != null && max !== min) {
    return `${min} - ${max} min`;
  }
  return `${min} min`;
}

function toBadgeClass(status: string) {
  return `badge badge-${status}`;
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

function toPrescriptionDoseLabel(exercise: SessionPrescriptionExercise) {
  const parts: string[] = [];
  if (exercise.sets_count != null) {
    if (exercise.reps_min != null) {
      parts.push(`${exercise.sets_count} x ${exercise.reps_min}${exercise.reps_max != null && exercise.reps_max !== exercise.reps_min ? `-${exercise.reps_max}` : ""}`);
    } else if (exercise.hold_seconds_min != null) {
      parts.push(`${exercise.sets_count} x ${exercise.hold_seconds_min}${exercise.hold_seconds_max != null && exercise.hold_seconds_max !== exercise.hold_seconds_min ? `-${exercise.hold_seconds_max}` : ""} s`);
    } else if (exercise.distance_meters != null) {
      parts.push(`${exercise.sets_count} x ${toMetricLabel(exercise.distance_meters, " m")}`);
    }
  }
  if (parts.length === 0) {
    return "Sin dosificacion detallada";
  }
  return parts.join(" · ");
}

function toPrescriptionIntensityLabel(exercise: SessionPrescriptionExercise) {
  const parts: string[] = [];
  if (exercise.target_rpe_min != null) {
    parts.push(`RPE ${exercise.target_rpe_min}${exercise.target_rpe_max != null && exercise.target_rpe_max !== exercise.target_rpe_min ? `-${exercise.target_rpe_max}` : ""}`);
  }
  if (exercise.target_rir_min != null) {
    parts.push(`RIR ${exercise.target_rir_min}${exercise.target_rir_max != null && exercise.target_rir_max !== exercise.target_rir_min ? `-${exercise.target_rir_max}` : ""}`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function getOptionalDailyLoadMinutes(row: PlanVsRealRow) {
  return Math.round((row.optional_daily_activities ?? []).reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
}

function getOtherDailyLoadMinutes(row: PlanVsRealRow) {
  return Math.round((row.other_daily_activities ?? []).reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
}

function getDailyTotalLoadMinutes(row: PlanVsRealRow) {
  return Math.round((row.actual_duration_min ?? 0) + getOptionalDailyLoadMinutes(row) + getOtherDailyLoadMinutes(row));
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

function getOptionalDailyActivities(row: PlanVsRealRow): OptionalDailyActivity[] {
  return row.optional_daily_activities ?? [];
}

function getOtherDailyActivities(row: PlanVsRealRow): DailyUnlinkedActivity[] {
  return row.other_daily_activities ?? [];
}

function toOptionalDailyLabel(activity: OptionalDailyActivity) {
  if (activity.actual_discipline === "strength_training") {
    return "Activacion opcional";
  }
  if (activity.actual_discipline === "yoga") {
    return "Flexibilidad opcional";
  }
  return "Opcional del dia";
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

function toTrainingLoadHeading(activity: ActivityDetail) {
  return activity.source_system === "garmin" ? "Carga Garmin" : "Carga";
}

function isPaceDiscipline(discipline: string | null) {
  return discipline != null && ["running", "trail_running", "walking", "hiking"].includes(discipline);
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

export default function App() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [weeks, setWeeks] = useState<Week[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [planVsRealRows, setPlanVsRealRows] = useState<PlanVsRealRow[]>([]);

  const [selectedSeason, setSelectedSeason] = useState<Season | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<Block | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<Week | null>(null);
  const [weeklyReview, setWeeklyReview] = useState<WeeklyReview | null>(null);
  const [selectedActivity, setSelectedActivity] = useState<ActivityDetail | null>(null);
  const [selectedSessionPrescription, setSelectedSessionPrescription] = useState<SessionPrescription | null>(null);
  const [seasonActivities, setSeasonActivities] = useState<ActivityListItem[]>([]);
  const [submissionMessage, setSubmissionMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importJobs, setImportJobs] = useState<ImportJob[]>([]);
  const [garminStatus, setGarminStatus] = useState<GarminConnectStatus | null>(null);
  const [importForm, setImportForm] = useState<GarminImportFormState>(emptyGarminImportForm);
  const [importPreview, setImportPreview] = useState<GarminImportPreview | null>(null);
  const [importing, setImporting] = useState(false);
  const [previewingImport, setPreviewingImport] = useState(false);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [loadingSessionPrescription, setLoadingSessionPrescription] = useState(false);
  const [loadingSeasonActivities, setLoadingSeasonActivities] = useState(false);
  const [loading, setLoading] = useState(false);
  const [savingWeeklyReview, setSavingWeeklyReview] = useState(false);

  useEffect(() => {
    void loadSeasons();
    void loadImportJobs();
    void loadGarminStatus();
  }, []);

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

  async function loadSeasonActivities(seasonId: number) {
    try {
      setLoadingSeasonActivities(true);
      const data = await fetchJson<ActivityListItem[]>(`/api/seasons/${seasonId}/activities`);
      setSeasonActivities(data);
    } catch (requestError) {
      if (isNotFoundError(requestError)) {
        setSeasonActivities([]);
        return;
      }
      throw requestError;
    } finally {
      setLoadingSeasonActivities(false);
    }
  }

  async function handleSeasonSelect(season: Season) {
    try {
      setLoading(true);
      setError(null);
      setInfoMessage(null);
      setSubmissionMessage(null);
      setSelectedSeason(season);
      setImportForm((current) => ({
        ...current,
        date_from: season.start_date,
        date_to: season.end_date,
      }));
      setSelectedBlock(null);
      setSelectedWeek(null);
      setWeeklyReview(null);
      setSelectedActivity(null);
      setSelectedSessionPrescription(null);
      setSeasonActivities([]);
      setWeeks([]);
      setSessions([]);
      setPlanVsRealRows([]);
      const [data] = await Promise.all([
        fetchJson<Block[]>(`/api/seasons/${season.season_id}/blocks`),
        loadSeasonActivities(season.season_id),
      ]);
      setBlocks(data);
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

  async function handleBlockSelect(block: Block) {
    try {
      setLoading(true);
      setError(null);
      setInfoMessage(null);
      setSubmissionMessage(null);
      setSelectedBlock(block);
      setSelectedWeek(null);
      setWeeklyReview(null);
      setSelectedActivity(null);
      setSelectedSessionPrescription(null);
      setWeeks([]);
      setSessions([]);
      setPlanVsRealRows([]);
      const data = await fetchJson<Week[]>(`/api/blocks/${block.block_id}/weeks`);
      setWeeks(data);
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
      setSelectedActivity(null);
      setSelectedSessionPrescription(null);
      const [sessionData, comparisonData, reviewData] = await Promise.all([
        fetchJson<Session[]>(`/api/weeks/${week.week_id}/sessions`),
        fetchJson<PlanVsRealRow[]>(`/api/weeks/${week.week_id}/plan-vs-real`),
        fetchJson<WeeklyReview>(`/api/weeks/${week.week_id}/review`),
      ]);
      setSessions(sessionData);
      setPlanVsRealRows(comparisonData);
      setWeeklyReview(reviewData);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoading(false);
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
      setSubmissionMessage(`Importacion Garmin completada: job ${result.import_job.import_job_id}, ${result.import_job.rows_loaded} filas cargadas.`);
      await loadImportJobs();
      await loadSeasonActivities(selectedSeason.season_id);
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
      setError(null);
      const activity = await fetchJson<ActivityDetail>(`/api/activities/${activityId}`);
      setSelectedActivity(activity);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoadingActivity(false);
    }
  }

  async function loadSessionPrescription(plannedSessionId: number) {
    try {
      setLoadingSessionPrescription(true);
      setError(null);
      const prescription = await fetchJson<SessionPrescription>(`/api/planned-sessions/${plannedSessionId}/prescription`);
      setSelectedSessionPrescription(prescription);
    } catch (requestError) {
      setSelectedSessionPrescription(null);
      setError(requestError instanceof Error ? requestError.message : "Error desconocido");
    } finally {
      setLoadingSessionPrescription(false);
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
  const optionalDailyActivities = planVsRealRows.flatMap((row) => row.optional_daily_activities ?? []);
  const optionalActivationCount = optionalDailyActivities.filter((activity) => activity.actual_discipline === "strength_training").length;
  const optionalFlexibilityCount = optionalDailyActivities.filter((activity) => activity.actual_discipline === "yoga").length;
  const optionalDailyMinutes = Math.round(optionalDailyActivities.reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
  const otherDailyActivities = planVsRealRows.flatMap((row) => row.other_daily_activities ?? []);
  const otherDailyMinutes = Math.round(otherDailyActivities.reduce((total, activity) => total + (activity.actual_duration_min ?? 0), 0));
  const totalLoadMinutes = weeklySummary.actualMinutes + optionalDailyMinutes + otherDailyMinutes;
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
    `Carga total registrada: ${toHoursLabel(totalLoadMinutes)} (${toHoursLabel(weeklySummary.actualMinutes)} del plan + ${toHoursLabel(optionalDailyMinutes + otherDailyMinutes)} en actividades no planificadas).`,
    optionalDailyActivities.length > 0
      ? `Extras diarios: ${optionalActivationCount} activaciones y ${optionalFlexibilityCount} sesiones de flexibilidad (${toHoursLabel(optionalDailyMinutes)}).`
      : "Sin extras diarios opcionales registrados en la semana.",
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
              <article key={job.import_job_id} className="import-job-card">
                <div className="item-head">
                  <strong>Job {job.import_job_id}</strong>
                  <span className={toBadgeClass(job.status)}>{job.status}</span>
                </div>
                <span>{job.source_path ?? "Sin rango"}</span>
                <small>{toDateTimeLabel(job.imported_at)}</small>
                <div className="import-job-grid">
                  <span>Detectadas: {job.rows_detected}</span>
                  <span>Cargadas: {job.rows_loaded}</span>
                  {job.has_breakdown_details ? (
                    <>
                      <span>Act. +: {job.breakdown.activity_rows_inserted}</span>
                      <span>Act. upd: {job.breakdown.activity_rows_updated}</span>
                      <span>Met. +: {job.breakdown.daily_metric_rows_inserted}</span>
                      <span>Met. upd: {job.breakdown.daily_metric_rows_updated}</span>
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

      <section className="panel activity-feed-panel">
        <div className="section-heading">
          <div>
            <h2>Actividades reales</h2>
            <p className="section-subtitle">Ultimas actividades registradas de la temporada activa, con foco en lectura operativa y acceso rapido al detalle.</p>
          </div>
        </div>

        {loadingSeasonActivities ? (
          <div className="empty-state-card empty-state-card-wide">
            <strong>Cargando actividades</strong>
            <p>Recuperando las actividades reales ya registradas en SQLite.</p>
          </div>
        ) : seasonActivities.length > 0 ? (
          <div className="activity-feed-list">
            {seasonActivities.map((activity) => (
              <button
                key={activity.activity_id}
                type="button"
                className={`activity-feed-card${selectedActivity?.activity_id === activity.activity_id ? ' selected' : ''}`}
                onClick={() => void loadActivityDetail(activity.activity_id)}
              >
                <div className="activity-feed-head">
                  <div>
                    <strong>{toActivityTypeLabel(activity.activity_type, activity.source_system)}</strong>
                    <div className="activity-origin-row">
                      <span className={toSourceChipClass(activity.source_system)}>{toSourceLabel(activity.source_system)}</span>
                      <p>{toDisciplineLabel(activity.discipline)}</p>
                    </div>
                  </div>
                  <span className={activity.compliance_status ? toBadgeClass(activity.compliance_status) : "badge badge-pending"}>
                    {activity.compliance_status ?? "sin enlace"}
                  </span>
                </div>

                <div className="activity-feed-meta">
                  <span>{activity.activity_date}</span>
                  <span>{toDateTimeLabel(activity.started_at)}</span>
                  {activity.planned_session_id != null ? <span>Sesion {activity.planned_session_id}</span> : null}
                  {activity.external_activity_id ? <span>Ext. {activity.external_activity_id}</span> : null}
                </div>

                <div className="activity-feed-grid">
                  <span>Duracion: {activity.duration_seconds != null ? toHoursLabel(Math.round(activity.duration_seconds / 60)) : "-"}</span>
                  {isDistanceRelevantInList(activity) ? <span>Distancia: {toMetricLabel(activity.distance_meters != null ? activity.distance_meters / 1000 : null, " km")}</span> : null}
                  {isHeartRateRelevantInList(activity) ? <span>FC: {`${toMetricLabel(activity.avg_hr, " bpm")} / ${toMetricLabel(activity.max_hr, " bpm")}`}</span> : null}
                  {isPowerRelevantInList(activity) ? <span>Potencia: {activity.avg_power != null ? `${toMetricLabel(activity.avg_power, " W")} media` : `${toMetricLabel(activity.normalized_power, " W")} NP`}</span> : null}
                  {activity.training_load != null ? <span>{toTrainingLoadHeading(activity as ActivityDetail)}: {toMetricLabel(activity.training_load)}</span> : null}
                  <span>Actividad #{activity.activity_id}</span>
                </div>

                <p className="activity-feed-summary">{activity.actual_summary ?? activity.notes ?? "Sin resumen adicional."}</p>
              </button>
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
            <div className="session-table-wrapper">
              <table className="session-table">
                <thead>
                  <tr>
                    <th>Dia</th>
                    <th>Tipo</th>
                    <th>Objetivo</th>
                    <th>Sesion principal</th>
                    <th>Complementario</th>
                    <th>Duracion</th>
                    <th>Detalle</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((session) => (
                    <tr key={session.planned_session_id} className={session.is_key_session ? 'key-session' : ''}>
                      <td>
                        <strong>{session.day_name}</strong>
                        <small>{session.session_date}</small>
                      </td>
                      <td>{session.planned_type}</td>
                      <td>{session.objective}</td>
                      <td>{session.primary_session}</td>
                      <td>{session.complementary_session ?? '-'}</td>
                      <td>{toDurationLabel(session.duration_min, session.duration_max)}</td>
                      <td>
                        {session.has_structured_prescription === 1 ? (
                          <button className="table-link-button" type="button" onClick={() => void loadSessionPrescription(session.planned_session_id)}>
                            Ver fuerza
                          </button>
                        ) : (
                          '-'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
                  <small>{toHoursLabel(optionalDailyMinutes + otherDailyMinutes)} fuera del plan</small>
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
                  <small>{optionalActivationCount} activacion · {optionalFlexibilityCount} flexibilidad</small>
                </article>
              </div>

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
                    {volumeDeltaMinutes === 0 ? "En linea" : `${volumeDeltaMinutes > 0 ? "+" : "-"}${Math.abs(volumeDeltaMinutes)} min`}
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
                    const otherDailyActivities = getOtherDailyActivities(row);
                    const optionalDailyLoadMinutes = getOptionalDailyLoadMinutes(row);
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
                          <strong>{row.planned_type}</strong>
                          <small>{row.planned_session}</small>
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
                            {optionalDailyLoadMinutes > 0 || otherDailyLoadMinutes > 0
                              ? ` (${toHoursLabel(row.actual_duration_min ?? 0)} plan + ${toHoursLabel(optionalDailyLoadMinutes + otherDailyLoadMinutes)} fuera del plan)`
                              : ''}
                          </small>
                          <small>{row.actual_summary ?? 'Sin revision diaria'}</small>
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
                Carga total registrada: {toHoursLabel(totalLoadMinutes)}. De ese total, {toHoursLabel(weeklySummary.actualMinutes)} corresponden a sesiones del plan y {toHoursLabel(optionalDailyMinutes + otherDailyMinutes)} a actividades fuera del plan.
              </p>
              <p>
                Opcionales diarios: {optionalDailyActivities.length === 0 ? 'sin registro adicional.' : `${optionalActivationCount} activaciones y ${optionalFlexibilityCount} sesiones de flexibilidad, con ${optionalDailyMinutes} minutos acumulados.`}
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
              </div>
            </div>
          ) : null}
        </section>

        <section className="panel panel-form">
          <div className="section-heading">
            <div>
              <h2>Sesion planificada</h2>
              <p className="section-subtitle">Detalle estructurado de la prescripcion cuando existe en SQLite.</p>
            </div>
          </div>

          {loadingSessionPrescription ? (
            <div className="empty-state-card empty-state-card-wide">
              <strong>Cargando sesion planificada</strong>
              <p>Recuperando la prescripcion estructurada de la sesion seleccionada.</p>
            </div>
          ) : selectedSessionPrescription ? (
            <div className="prescription-detail-card">
              <div className="activity-detail-header">
                <div>
                  <strong>{selectedSessionPrescription.title ?? selectedSessionPrescription.primary_session ?? 'Prescripcion estructurada'}</strong>
                  <p>
                    {selectedSessionPrescription.day_name} · {selectedSessionPrescription.session_date} · {selectedSessionPrescription.planned_type}
                  </p>
                </div>
                <span className="badge badge-completed">{selectedSessionPrescription.prescription_type}</span>
              </div>

              <div className="activity-detail-grid">
                <article><span>Duracion objetivo</span><strong>{toDurationLabel(selectedSessionPrescription.estimated_duration_min, selectedSessionPrescription.estimated_duration_max)}</strong></article>
                <article><span>RPE objetivo</span><strong>{selectedSessionPrescription.target_rpe_min != null ? `RPE ${selectedSessionPrescription.target_rpe_min}${selectedSessionPrescription.target_rpe_max != null && selectedSessionPrescription.target_rpe_max !== selectedSessionPrescription.target_rpe_min ? `-${selectedSessionPrescription.target_rpe_max}` : ''}` : '-'}</strong></article>
                <article><span>Foco principal</span><strong>{selectedSessionPrescription.focus_primary ?? '-'}</strong></article>
                <article><span>Foco secundario</span><strong>{selectedSessionPrescription.focus_secondary ?? '-'}</strong></article>
              </div>

              <div className="activity-detail-notes">
                <p><strong>Objetivo:</strong> {selectedSessionPrescription.objective ?? '-'}</p>
                <p><strong>Calentamiento:</strong> {selectedSessionPrescription.warmup_notes ?? '-'}</p>
                <p><strong>Ejecucion:</strong> {selectedSessionPrescription.execution_notes ?? '-'}</p>
                <p><strong>Ajustes:</strong> {selectedSessionPrescription.adaptation_notes ?? '-'}</p>
                <p><strong>Cierre:</strong> {selectedSessionPrescription.cooldown_notes ?? '-'}</p>
              </div>

              <div className="prescription-block-list">
                {selectedSessionPrescription.blocks.map((block) => (
                  <article key={block.prescription_block_id} className="prescription-block-card">
                    <div className="item-head">
                      <strong>{block.block_name ?? block.block_type}</strong>
                      <span>{block.block_type}</span>
                    </div>
                    {block.objective ? <p>{block.objective}</p> : null}
                    {block.notes ? <small>{block.notes}</small> : null}
                    <div className="prescription-exercise-list">
                      {block.exercises.map((exercise) => (
                        <div key={exercise.prescription_exercise_id} className="prescription-exercise-item">
                          <strong>{exercise.exercise_name}</strong>
                          <small>{toPrescriptionDoseLabel(exercise)}</small>
                          {toPrescriptionIntensityLabel(exercise) ? <small>{toPrescriptionIntensityLabel(exercise)}</small> : null}
                          {exercise.equipment ? <small>{exercise.equipment}</small> : null}
                          {exercise.load_guidance ? <small>{exercise.load_guidance}</small> : null}
                          {exercise.notes ? <small>{exercise.notes}</small> : null}
                          {exercise.options.length > 0 ? (
                            <div className="prescription-option-list">
                              {exercise.options.map((option) => (
                                <small key={option.exercise_option_id}>Alternativa: {option.option_name}{option.condition_notes ? ` · ${option.condition_notes}` : ''}</small>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state-card empty-state-card-wide">
              <strong>Sin sesion estructurada seleccionada</strong>
              <p>Usa "Ver fuerza" en una sesion planificada para abrir su prescripcion estructurada.</p>
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
              </div>

              <div className="activity-detail-grid">
                <article><span>Fecha</span><strong>{selectedActivity.activity_date}</strong></article>
                <article><span>Inicio</span><strong>{toDateTimeLabel(selectedActivity.started_at)}</strong></article>
                <article><span>Duracion</span><strong>{selectedActivity.duration_seconds != null ? toHoursLabel(Math.round(selectedActivity.duration_seconds / 60)) : "-"}</strong></article>
                <article><span>Calorias</span><strong>{toMetricLabel(selectedActivity.calories)}</strong></article>
                {isDistanceRelevant(selectedActivity) ? <article><span>Distancia</span><strong>{toMetricLabel(selectedActivity.distance_meters != null ? selectedActivity.distance_meters / 1000 : null, " km")}</strong></article> : null}
                {isAscentRelevant(selectedActivity) ? <article><span>Desnivel</span><strong>{toMetricLabel(selectedActivity.ascent_meters, " m")}</strong></article> : null}
                {isHeartRateRelevant(selectedActivity) ? <article><span>FC media/max</span><strong>{`${toMetricLabel(selectedActivity.avg_hr, " bpm")} / ${toMetricLabel(selectedActivity.max_hr, " bpm")}`}</strong></article> : null}
                {isPowerRelevant(selectedActivity) ? <article><span>Potencia</span><strong>{toPowerSummary(selectedActivity)}</strong></article> : null}
                {selectedActivity.training_load != null ? <article><span>{toTrainingLoadHeading(selectedActivity)}</span><strong>{toMetricLabel(selectedActivity.training_load)}</strong></article> : null}
                {selectedActivity.avg_pace_seconds_per_km != null && isPaceDiscipline(selectedActivity.discipline) ? <article><span>Ritmo medio</span><strong>{toPaceLabel(selectedActivity.avg_pace_seconds_per_km)}</strong></article> : null}
                <article><span>RPE</span><strong>{toMetricLabel(selectedActivity.perceived_exertion)}</strong></article>
                <article><span>Sesion planificada</span><strong>{selectedActivity.planned_session_id ?? "-"}</strong></article>
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

          <div className="section-heading manual-section-heading">
            <div>
              <h2>Registro manual</h2>
              <p className="section-subtitle">Deshabilitado en este entorno para mantener el dataset Garmin-only.</p>
            </div>
          </div>

          <div className="empty-state-card empty-state-card-wide">
            <strong>Registro manual deshabilitado</strong>
            <p>La escritura manual de actividades, metricas y revisiones esta bloqueada en esta instancia para no mezclar fuentes con Garmin Connect.</p>
          </div>
        </section>
      </section>
    </div>
  );
}
