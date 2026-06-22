UPDATE plan_planned_sessions
SET
    planned_role = 'resistencia-aerobica-principal',
    planned_type = 'referencia-aerobica',
    objective = 'Absorber hoy la referencia aerobica util de la semana sin convertir el lunes en un dia agresivo.',
    primary_session = 'Bicicleta Z2 100-120 minutos.',
    complementary_session = 'Core 20-25 minutos o movilidad, sin fuerza de empuje si resta calidad a la bici.',
    notes = 'La bici prevista para el martes se absorbe el lunes con un techo algo mas corto para respetar el arranque de semana y llegar con margen al jueves.',
    is_key_session = 1,
    intensity_class = 'suave',
    duration_min = 100,
    duration_max = 120,
    adjustment_rule = 'Usar el lunes para salvar la referencia aerobica sin apurar el techo original del martes; si la sensacion no es buena, quedarse en el suelo del rango.'
WHERE planned_session_id = 20201;

UPDATE plan_planned_sessions
SET
    planned_role = 'resistencia-aerobica-suave',
    planned_type = 'complementaria',
    objective = 'Mantener continuidad sin bici y dejar el dia deliberadamente barato para no comprimir la semana.',
    primary_session = 'Paseo 45-75 minutos o descanso activo si el dia queda muy cerrado.',
    complementary_session = 'Espalda y biceps 20-25 minutos muy controlados, solo si encajan sin prisa.',
    notes = 'El martes deja de ser dia aerobico principal por indisponibilidad de bici. La prioridad es no generar residuo ni obligar a recolocar el jueves.',
    is_key_session = 0,
    intensity_class = 'muy suave',
    duration_min = 45,
    duration_max = 75,
    adjustment_rule = 'Si no hay hueco real, convertir el dia en descanso activo y proteger la normalidad del jueves.'
WHERE planned_session_id = 20202;

UPDATE plan_planned_sessions
SET
    planned_role = 'resistencia-aerobica-principal',
    planned_type = 'bicicleta-z2',
    objective = 'Adelantar al miercoles el segundo dia aerobico util para aprovechar la disponibilidad de bici sin comprimir mas la semana.',
    primary_session = 'Bicicleta Z2 120-130 minutos.',
    complementary_session = 'Pecho, triceps y hombro 25-30 minutos.',
    notes = 'El miercoles absorbe la bici prevista originalmente para el jueves. Debe seguir sintiendose como dia de consolidacion aerobica, no como competicion con el lunes.',
    is_key_session = 1,
    intensity_class = 'suave',
    duration_min = 120,
    duration_max = 130,
    adjustment_rule = 'Mantener una ejecucion estable y globalmente aerobica aunque el dia se adelante; si las piernas no estan normales, recortar antes que endurecer.'
WHERE planned_session_id = 20203;

UPDATE plan_planned_sessions
SET
    planned_role = 'recuperacion',
    planned_type = 'recuperacion',
    objective = 'Usar el jueves como dia de descarga activa para absorber la bici del miercoles y seguir protegiendo el sabado.',
    primary_session = 'Bicicleta Z1 75-105 minutos o descanso activo si las piernas no estan normales.',
    complementary_session = 'Core 25-30 minutos.',
    notes = 'El jueves deja de ser segundo dia aerobico principal y pasa a ser dia de recuperacion activa despues de adelantar la bici al miercoles.',
    is_key_session = 0,
    intensity_class = 'suave',
    duration_min = 75,
    duration_max = 105,
    adjustment_rule = 'Hacer la bici solo en Z1 y cortar sin problema si aparece fatiga residual; la prioridad es absorber bien el miercoles y llegar con margen al sabado.'
WHERE planned_session_id = 20204;