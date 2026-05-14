INSERT OR IGNORE INTO exec_daily_metrics (
    daily_metric_id, season_id, metric_date, source_system, weight_kg, sleep_hours,
    sleep_quality, resting_hr, hrv, body_battery, subjective_energy,
    subjective_fatigue, soreness, notes
) VALUES
(910101, 2026, '2026-05-04', 'manual_v0_2', 91.8, 7.5, 'buena', 56, 41, 72, 7, 3, 'ligera rigidez general', 'Inicio de semana con sensacion estable y ganas de moverse.'),
(910102, 2026, '2026-05-05', 'manual_v0_2', 91.6, 7.2, 'buena', 55, 43, 75, 7, 3, 'sin molestias relevantes', 'Buena disponibilidad para la primera sesion aerobica.'),
(910103, 2026, '2026-05-06', 'manual_v0_2', 91.5, 6.9, 'correcta', 57, 39, 68, 6, 4, 'piernas algo pesadas', 'La bici del martes se absorbe bien pero deja algo de carga.'),
(910104, 2026, '2026-05-07', 'manual_v0_2', 91.4, 7.4, 'buena', 55, 42, 73, 7, 3, 'sin molestias relevantes', 'Dia apropiado para repetir bici suave.'),
(910105, 2026, '2026-05-08', 'manual_v0_2', 91.3, 7.8, 'muy buena', 54, 45, 78, 8, 2, 'muy poca rigidez', 'Se llega al viernes con buena frescura.'),
(910106, 2026, '2026-05-09', 'manual_v0_2', 91.2, 7.0, 'correcta', 56, 40, 70, 7, 4, 'fatiga normal post salida larga', 'Salida larga controlada, sin deuda excesiva.'),
(910107, 2026, '2026-05-10', 'manual_v0_2', 91.2, 8.1, 'muy buena', 53, 46, 80, 8, 2, 'ligera fatiga residual', 'El domingo aparece mejor de lo esperado.' );

INSERT OR IGNORE INTO exec_activities (
    activity_id, season_id, source_system, external_activity_id, activity_date,
    started_at, discipline, activity_type, duration_seconds, distance_meters,
    ascent_meters, calories, avg_hr, max_hr, avg_power, normalized_power,
    training_load, avg_pace_seconds_per_km, perceived_exertion, subjective_feeling,
    source_file, raw_payload_path, notes
) VALUES
(900101, 2026, 'manual_v0_2', NULL, '2026-05-04', NULL, 'paseo', 'paseo-recuperacion', 3000, NULL, NULL, 210, 88, 104, NULL, NULL, 18, NULL, 2, 'muy facil', NULL, NULL, 'Paseo de 50 minutos y movilidad ligera.'),
(900102, 2026, 'manual_v0_2', NULL, '2026-05-05', NULL, 'bicicleta', 'bicicleta-z2', 4920, 28700, 260, 690, 124, 138, 158, 164, 48, NULL, 4, 'estable y comoda', NULL, NULL, 'Rodaje aerobico continuo de 82 minutos.'),
(900103, 2026, 'manual_v0_2', NULL, '2026-05-06', NULL, 'fuerza', 'fuerza-base', 2100, NULL, NULL, 230, 96, 118, NULL, NULL, 30, NULL, 5, 'controlada', NULL, NULL, 'Circuito basico de fuerza de 35 minutos.'),
(900104, 2026, 'manual_v0_2', NULL, '2026-05-07', NULL, 'bicicleta', 'bicicleta-z2', 3300, 19100, 170, 470, 121, 136, 152, 158, 34, NULL, 4, 'piernas algo pesadas pero dentro de control', NULL, NULL, 'Sesion recortada a 55 minutos para no dejar deuda.'),
(900105, 2026, 'manual_v0_2', NULL, '2026-05-08', NULL, 'paseo', 'paseo-recuperacion', 2700, NULL, NULL, 180, 85, 100, NULL, NULL, 14, NULL, 2, 'muy facil', NULL, NULL, 'Se mantiene paseo suave en lugar de bici.'),
(900106, 2026, 'manual_v0_2', NULL, '2026-05-09', NULL, 'bicicleta', 'salida-larga-z2', 8400, 52300, 540, 1320, 128, 144, 162, 169, 86, NULL, 5, 'larga pero sostenible', NULL, NULL, 'Salida larga de 2h20 bien controlada.'),
(900107, 2026, 'manual_v0_2', NULL, '2026-05-10', NULL, 'senderismo', 'monte-suave', 3000, 4200, 110, 240, 94, 112, NULL, NULL, 19, NULL, 3, 'recuperadora', NULL, NULL, 'Actividad mas corta de lo previsto para soltar piernas.');

INSERT OR IGNORE INTO link_plan_execution (
    link_id, planned_session_id, activity_id, link_type, compliance_status, rationale
) VALUES
(920101, 10101, 900101, 'direct', 'completed', 'El paseo cumple el objetivo de activacion suave.'),
(920102, 10102, 900102, 'direct', 'completed', 'Sesion aerobica realizada dentro del rango previsto.'),
(920103, 10103, 900103, 'direct', 'completed', 'Trabajo de fuerza base completado sin interferencia relevante.'),
(920104, 10104, 900104, 'direct', 'partial', 'Se recorta duracion por sensacion de piernas pesadas, manteniendo el objetivo.'),
(920105, 10105, 900105, 'direct', 'completed', 'El paseo suave cumple la funcion de recuperacion del viernes.'),
(920106, 10106, 900106, 'direct', 'completed', 'Salida larga completada dentro del espiritu del plan.'),
(920107, 10107, 900107, 'direct', 'partial', 'Se opta por una actividad complementaria mas corta para priorizar absorcion.');

INSERT OR IGNORE INTO review_daily_reviews (
    daily_review_id, season_id, review_date, block_id, week_id, planned_session_id,
    planned_summary, actual_summary, compliance_status, general_feeling,
    perceived_recovery, motivation, observations, next_day_decision
) VALUES
(930101, 2026, '2026-05-04', 1, 101, 10101, 'Paseo 45-60 min o descanso activo.', 'Paseo 50 min con movilidad ligera.', 'completed', 'ligero', 'buena', 'alta', 'Dia muy facil y util para arrancar la semana con orden.', 'Mantener la bici del martes en Z2 real.'),
(930102, 2026, '2026-05-05', 1, 101, 10102, 'Bicicleta Z2 75-90 min.', 'Bicicleta Z2 82 min estable.', 'completed', 'positivo', 'buena', 'alta', 'Buenas sensaciones y control del pulso.', 'Sostener la fuerza del miercoles sin buscar mas carga.'),
(930103, 2026, '2026-05-06', 1, 101, 10103, 'Fuerza base 30-40 min.', 'Rutina de fuerza base 35 min.', 'completed', 'correcto', 'normal', 'media', 'Sesion suficiente; deja algo de carga normal en piernas.', 'Si el jueves pesa, recortar sin problema.'),
(930104, 2026, '2026-05-07', 1, 101, 10104, 'Bicicleta Z2 60-75 min.', 'Bicicleta Z2 55 min, recortada por piernas pesadas.', 'partial', 'aceptable', 'normal', 'media', 'Buen criterio al recortar; no interesa convertirlo en deuda.', 'Mantener el viernes deliberadamente facil.'),
(930105, 2026, '2026-05-08', 1, 101, 10105, 'Descanso activo o paseo 45 min.', 'Paseo suave 45 min.', 'completed', 'muy bueno', 'buena', 'alta', 'Se llega al fin de semana con sensacion de margen.', 'Mantener la salida larga del sabado en control, no en ambicion.'),
(930106, 2026, '2026-05-09', 1, 101, 10106, 'Bicicleta 2h15-2h30 Z2.', 'Bicicleta 2h20 Z2 controlada.', 'completed', 'bueno', 'aceptable', 'alta', 'Salida larga sostenible y bien tolerada.', 'Reducir el domingo si aparece pesadez.'),
(930107, 2026, '2026-05-10', 1, 101, 10107, 'Actividad complementaria 45-75 min.', 'Monte suave 50 min.', 'partial', 'positivo', 'buena', 'alta', 'Cierre con mejor sensacion de lo esperado tras la salida larga.', 'Semana 02 puede repetirse con progresion ligera.');