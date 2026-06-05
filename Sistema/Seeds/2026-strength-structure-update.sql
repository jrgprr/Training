UPDATE plan_macro_cycles
SET priorities = '1) Normalizar semanas consistentes. 2) Consolidar tolerancia al volumen aerobico basico. 3) Reducir peso de forma gradual. 4) Mantener fuerza estructurada ligera y frecuente. 5) Introducir trabajo mas intencional solo cuando la semana normal ya sea estable. 6) Progresar por acumulacion aerobica y repetibilidad antes que por intensidad. 7) Usar flexibilidad de medios y horarios para sostener adherencia.',
    weight_rules = 'Bajar peso bien y no rapido, evitando comprometer energia disponible, recuperacion o fuerza estructurada ligera.',
    success_criteria = 'Semanas repetibles sin fatiga arrastrada, bicicleta como actividad central normal, indice aerobico estable o mejor, peso a la baja sin deterioro, fuerza estructurada ligera mantenida, rutina matinal y recuperacion sosteniendo el proceso.'
WHERE macro_id = 1 AND season_id = 2026;

UPDATE plan_meso_blocks
SET exit_criteria = 'Semanas sin deuda, salida larga controlada tolerada, fuerza estructurada ligera integrada y sensacion de semana tipo asumible.',
    micro_pattern = 'Semanas con bici como eje, 6 micro-sesiones ligeras de fuerza estructurada, paseo y movilidad como soporte, intensidad contenida.'
WHERE block_id = 1 AND season_id = 2026;

UPDATE plan_meso_blocks
SET objective_complementary = 'Sostener tendencia de peso y fuerza estructurada ligera sin interferencia.'
WHERE block_id = 2 AND season_id = 2026;

UPDATE plan_meso_blocks
SET objective_complementary = 'Mantener peso y fuerza estructurada ligera en una zona compatible con entrenar bien.'
WHERE block_id = 3 AND season_id = 2026;

UPDATE plan_meso_blocks
SET objective_complementary = 'Sostener fuerza estructurada ligera y tendencia de peso con buena recuperacion.'
WHERE block_id = 4 AND season_id = 2026;

UPDATE plan_meso_blocks
SET objective_secondary = 'Mantener fuerza estructurada ligera y valorar algun estimulo mas intencional solo si la recuperacion lo permite.',
    key_risks = 'Abrir intensidad demasiado pronto o descuidar la fuerza estructurada ligera.'
WHERE block_id = 5 AND season_id = 2026;

UPDATE plan_meso_blocks
SET objective_secondary = 'Conservar fuerza estructurada ligera y rutina suficiente para no perder normalidad.'
WHERE block_id = 6 AND season_id = 2026;

UPDATE plan_micro_weeks
SET objective_secondary = 'Introducir la semana tipo y sostener la fuerza estructurada ligera sin interferencia.',
    support_days = 'Rodajes suaves, fuerza estructurada ligera, paseo y movilidad.'
WHERE week_id = 101;

UPDATE plan_micro_weeks
SET objective_secondary = 'Consolidar la bicicleta como eje central y sostener la fuerza estructurada ligera.',
    support_days = 'Fuerza estructurada ligera, paseo y movilidad.'
WHERE week_id = 102;

UPDATE plan_micro_weeks
SET support_days = 'Fuerza estructurada ligera, paseo y un dia muy facil.'
WHERE week_id = 103;

UPDATE plan_micro_weeks
SET objective_secondary = 'Confirmar que la fuerza estructurada ligera y la bici siguen conviviendo bien.',
    support_days = 'Fuerza estructurada ligera muy controlada, paseo y movilidad.'
WHERE week_id = 104;

UPDATE plan_micro_weeks
SET key_days = '2 dias aerobicos, trabajo complementario fijo de lunes a sabado y 1 salida larga asentada.'
WHERE week_id = 105;

UPDATE plan_micro_weeks
SET key_days = '1 referencia aerobica y 1 salida larga controlada.',
    support_days = 'Paseo, un dia muy facil y 6 micro-sesiones complementarias ligeras de lunes a sabado.'
WHERE week_id = 106;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10101;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10102;

UPDATE plan_planned_sessions
SET planned_type = 'complementaria',
    objective = 'Introducir el trabajo de core sin interferencia.',
    primary_session = 'Paseo suave 20-45 minutos o descanso activo.',
    complementary_session = 'Core 30-35 minutos.',
    notes = 'Dia ligero de soporte; el core no debe comprometer el jueves.',
    intensity_class = 'muy suave',
    duration_min = 30,
    duration_max = 35,
    adjustment_rule = 'Reducir a solo core corto o descanso completo si aparece fatiga.'
WHERE planned_session_id = 10103;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10104;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10105;

UPDATE plan_planned_sessions
SET complementary_session = 'Core 30-35 minutos y nutricion ordenada durante la salida.'
WHERE planned_session_id = 10106;

UPDATE plan_planned_sessions
SET complementary_session = 'Revision rapida de sensaciones, peso y fatiga, sin fuerza.'
WHERE planned_session_id = 10107;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10201;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10202;

UPDATE plan_planned_sessions
SET planned_type = 'complementaria',
    objective = 'Sostener el patron semanal con un dia ligero de core.',
    primary_session = 'Paseo suave 20-45 minutos o descanso activo.',
    complementary_session = 'Core 30-35 minutos.',
    notes = 'Dia ligero; el core no debe condicionar jueves o sabado.',
    intensity_class = 'muy suave',
    duration_min = 30,
    duration_max = 35,
    adjustment_rule = 'Reducir a solo core corto o descanso si la semana llega cargada.'
WHERE planned_session_id = 10203;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10204;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10205;

UPDATE plan_planned_sessions
SET complementary_session = 'Core 30-35 minutos y nutricion e hidratacion desde el inicio.'
WHERE planned_session_id = 10206;

UPDATE plan_planned_sessions
SET complementary_session = 'Revision de sensaciones y peso, sin fuerza.'
WHERE planned_session_id = 10207;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10301;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos y registro de potencia media, frecuencia cardiaca media y sensacion.'
WHERE planned_session_id = 10302;

UPDATE plan_planned_sessions
SET planned_type = 'complementaria',
    objective = 'Mantener fuerza estructurada ligera y soporte general con foco en core.',
    primary_session = 'Paseo suave 20-45 minutos o descanso activo.',
    complementary_session = 'Core 30-35 minutos.',
    notes = 'Dia ligero de soporte general; el core no debe restar calidad al jueves.',
    intensity_class = 'muy suave',
    duration_min = 30,
    duration_max = 35,
    adjustment_rule = 'Reducir a un bloque corto de core si la semana llega cargada.'
WHERE planned_session_id = 10303;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10304;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10305;

UPDATE plan_planned_sessions
SET complementary_session = 'Core 30-35 minutos y alimentacion e hidratacion estables.'
WHERE planned_session_id = 10306;

UPDATE plan_planned_sessions
SET complementary_session = 'Revision de datos de la semana, sin fuerza.'
WHERE planned_session_id = 10307;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10401;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10402;

UPDATE plan_planned_sessions
SET planned_type = 'complementaria',
    objective = 'Mantener fuerza estructurada ligera con menos carga y foco en core.',
    primary_session = 'Paseo suave 20-40 minutos o descanso activo.',
    complementary_session = 'Core 30-35 minutos.',
    notes = 'Version muy controlada para absorber; no comprometer jueves.',
    intensity_class = 'muy suave',
    duration_min = 30,
    duration_max = 35,
    adjustment_rule = 'Si hay fatiga, dejar solo un bloque corto de core o descanso.'
WHERE planned_session_id = 10403;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10404;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10405;

UPDATE plan_planned_sessions
SET complementary_session = 'Core 30-35 minutos y nutricion e hidratacion normales.'
WHERE planned_session_id = 10406;

UPDATE plan_planned_sessions
SET complementary_session = 'Revision de sensaciones generales, sin fuerza.'
WHERE planned_session_id = 10407;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10501;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10502;

UPDATE plan_planned_sessions
SET planned_type = 'complementaria',
    objective = 'Mantener fuerza estructurada ligera con foco en core.',
    primary_session = 'Paseo suave 20-45 minutos o descanso activo.',
    complementary_session = 'Core 30-35 minutos.',
    notes = 'Dia ligero; no buscar progresos agresivos y proteger jueves y domingo.',
    intensity_class = 'muy suave',
    duration_min = 30,
    duration_max = 35,
    adjustment_rule = 'Reducir a solo core si la semana ya tiene carga alta.'
WHERE planned_session_id = 10503;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10504;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10505;

UPDATE plan_planned_sessions
SET complementary_session = 'Core 30-35 minutos y revision de peso, sensacion y carga.'
WHERE planned_session_id = 10506;

UPDATE plan_planned_sessions
SET complementary_session = 'Alimentacion, bebida y ritmo bien ordenados, sin fuerza.'
WHERE planned_session_id = 10507;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10601;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos y registrar potencia media, frecuencia cardiaca media y sensacion.'
WHERE planned_session_id = 10602;

UPDATE plan_planned_sessions
SET planned_type = 'complementaria',
    objective = 'Sostener el trabajo de core dentro del patron semanal sin generar fatiga residual.',
    primary_session = 'Paseo 20-45 minutos o descanso activo.',
    complementary_session = 'Core 30-35 minutos.',
    notes = 'Debe sentirse ligero y no comprometer jueves.',
    intensity_class = 'muy suave',
    duration_min = 30,
    duration_max = 35,
    adjustment_rule = 'Reducir a solo core corto o descanso activo si aparece fatiga.'
WHERE planned_session_id = 10603;

UPDATE plan_planned_sessions
SET complementary_session = 'Pecho, triceps y hombro 30-35 minutos.'
WHERE planned_session_id = 10604;

UPDATE plan_planned_sessions
SET complementary_session = 'Espalda y biceps 30-35 minutos.'
WHERE planned_session_id = 10605;

UPDATE plan_planned_sessions
SET complementary_session = 'Core 30-35 minutos y revision parcial de sensaciones antes del cierre del bloque.'
WHERE planned_session_id = 10606;

UPDATE plan_planned_sessions
SET complementary_session = 'Nutricion e hidratacion ordenadas y revision completa del bloque, sin fuerza.'
WHERE planned_session_id = 10607;

DELETE FROM plan_prescription_exercise_options
WHERE prescription_exercise_id IN (
    1010311, 1010312, 1010321, 1010322, 1010331, 1010332,
    1020311, 1020312, 1020321, 1020322, 1020331, 1020332,
    1030311, 1030312, 1030313, 1030321, 1030322, 1030331, 1030332,
    1040311, 1040312, 1040321, 1040322, 1040323, 1040331, 1040332,
    1050311, 1050312, 1050321, 1050322, 1050323, 1050331, 1050332,
    1060311, 1060312, 1060313, 1060321, 1060322, 1060331, 1060332
);

DELETE FROM plan_prescription_exercises
WHERE prescription_block_id IN (
    101031, 101032, 101033,
    102031, 102032, 102033,
    103031, 103032, 103033,
    104031, 104032, 104033,
    105031, 105032, 105033,
    106031, 106032, 106033
);

DELETE FROM plan_prescription_blocks
WHERE prescription_block_id IN (
    101031, 101032, 101033,
    102031, 102032, 102033,
    103031, 103032, 103033,
    104031, 104032, 104033,
    105031, 105032, 105033,
    106031, 106032, 106033
);

DELETE FROM plan_session_prescriptions
WHERE planned_session_id IN (10103, 10203, 10303, 10403, 10503, 10603);