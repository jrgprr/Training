INSERT INTO plan_micro_weeks (
    week_id, block_id, week_code, sequence_in_block, start_date, end_date,
    week_role, entry_state, objective_primary, objective_secondary, key_risk,
    weight_goal, target_volume_hours_min, target_volume_hours_max,
    key_days, support_days, closure_rule, markdown_path
) VALUES
(
    202, 2, 'Semana-02', 2, '2026-06-22', '2026-06-28',
    'Construccion extensiva normal',
    'Descanso absorbente completado y frescura previsiblemente mas normalizada.',
    'Reabrir el bloque con crecimiento normal del volumen aerobico respecto a la semana 01.',
    'Consolidar la bicicleta como soporte principal sin que la fuerza invada la carga.',
    'Pasar demasiado rapido de semana descargada a semana demasiado densa.',
    'Sostener regularidad alimentaria y usar medias moviles, no valores aislados.',
    11.0, 13.0,
    '2 dias aerobicos entre semana y 1 salida larga ya plenamente normal dentro del bloque.',
    'Un paseo ligero, un dia muy facil y un viernes de recuperacion antes del fin de semana.',
    'Crecer un poco mas solo si esta semana ya se comporta como una semana tipo util y no como una semana salvada por el descanso previo.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-02/README.md'
),
(
    203, 2, 'Semana-03', 3, '2026-06-29', '2026-07-05',
    'Consolidacion constructiva',
    'Primera semana normal de B2 tolerada y semana tipo extensiva empezando a asentarse.',
    'Sostener el volumen util alcanzado con mejor normalidad interna.',
    'Hacer que los dias de soporte vuelvan a sentirse claramente subordinados.',
    'Intentar progresar por todas las esquinas en lugar de consolidar la forma de la semana.',
    'Evitar que la ligera mejora corporal se compre con peor sensacion de vaciado.',
    11.0, 13.0,
    '2 dias aerobicos entre semana y 1 salida larga ya normal del bloque.',
    'Un dia muy facil, un dia ligero de paseo y un cierre complementario controlado.',
    'Solo abrir un segundo empuje si la semana ya se lee como estructura normal y no como esfuerzo especial.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-03/README.md'
),
(
    204, 2, 'Semana-04', 4, '2026-07-06', '2026-07-12',
    'Construccion principal',
    'Semana tipo extensiva consolidada y margen para un segundo empuje controlado.',
    'Ampliar de forma visible el tiempo aerobico util del bloque.',
    'Sostener frecuencia y salida larga con buena calidad tecnica.',
    'Repetir el error de B1 y dejar que la magnitud de la semana crezca por demasiados frentes a la vez.',
    'Proteger disponibilidad energetica y no leer la bajada corporal como permiso para apretar mas.',
    11.0, 13.5,
    '2 dias aerobicos entre semana, 1 salida larga principal y 1 cierre complementario muy controlado.',
    'Paseo ligero, un dia claramente facil y fuerza ligera sin ambicion extra.',
    'Usar la semana 05 para validar y ordenar, no para seguir creciendo a cualquier precio.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-04/README.md'
),
(
    205, 2, 'Semana-05', 5, '2026-07-13', '2026-07-19',
    'Validacion y cierre',
    'Segundo empuje completado y necesidad de validar control antes de pasar a B3.',
    'Repetir una semana fuerte sin hacer crecer toda la semana a la vez, usando la salida larga como validacion final y no como nuevo empuje sistemico.',
    'Confirmar que la referencia aerobica y la salida larga siguen encajando con buena sensacion.',
    'Llegar a B3 con cansancio innecesario por cerrar B2 demasiado arriba.',
    'Estabilizar y evitar que la lectura corporal se deteriore al final del bloque.',
    10.5, 13.0,
    '1 referencia aerobica comparable, 1 segundo dia util comodo y 1 salida larga controlada.',
    'Paseo, activacion y un cierre complementario que no compita con la salida larga.',
    'Pasar a B3 si el cierre es de control y margen; si no, usar el arranque de B3 para absorber mas claramente desde el primer dia.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-05/README.md'
)
ON CONFLICT(week_id) DO UPDATE SET
    block_id = excluded.block_id,
    week_code = excluded.week_code,
    sequence_in_block = excluded.sequence_in_block,
    start_date = excluded.start_date,
    end_date = excluded.end_date,
    week_role = excluded.week_role,
    entry_state = excluded.entry_state,
    objective_primary = excluded.objective_primary,
    objective_secondary = excluded.objective_secondary,
    key_risk = excluded.key_risk,
    weight_goal = excluded.weight_goal,
    target_volume_hours_min = excluded.target_volume_hours_min,
    target_volume_hours_max = excluded.target_volume_hours_max,
    key_days = excluded.key_days,
    support_days = excluded.support_days,
    closure_rule = excluded.closure_rule,
    markdown_path = excluded.markdown_path;

INSERT INTO plan_planned_sessions (
    planned_session_id, week_id, session_date, day_name, sequence_in_week,
    planned_type, objective, primary_session, complementary_session, notes,
    is_key_session, intensity_class, duration_min, duration_max, adjustment_rule, markdown_path
) VALUES
(
    20201, 202, '2026-06-22', 'Lunes', 1, 'recuperacion',
    'Reabrir la semana con soltura y preparar bien la vuelta a una carga normal.',
    'Paseo 60-120 minutos o bicicleta Z1 60-120 minutos.', 'Pecho, triceps y hombro 25-30 minutos.',
    'El dia facil sigue siendo obligatorio para que el crecimiento empiece el martes y no el lunes; incluso en el extremo alto debe seguir siendo claramente regenerativa.',
    0, 'muy suave', 60, 120, 'Mantener el lunes deliberadamente facil; incluso en el extremo alto la sesion debe seguir siendo claramente regenerativa.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-02/README.md'
),
(
    20202, 202, '2026-06-23', 'Martes', 2, 'referencia-aerobica',
    'Retomar un dia extensivo normal entre semana.',
    'Bicicleta Z2 120-135 minutos.', 'Espalda y biceps 25-30 minutos.',
    'Subir tiempo, no intensidad; debe sentirse como trabajo normal del bloque, no como test de reentrada.',
    1, 'suave', 120, 135, 'Priorizar control del pulso y de la sensacion global.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-02/README.md'
),
(
    20203, 202, '2026-06-24', 'Miercoles', 3, 'complementaria',
    'Sostener la estructura sin dejar residuo.',
    'Paseo suave 20-45 minutos o descanso activo.', 'Core 25-30 minutos.',
    'Si el martes se ha sentido caro, dejar solo paseo muy corto o movilidad.',
    0, 'muy suave', 20, 45, 'Reducir a movilidad si el martes deja coste alto.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-02/README.md'
),
(
    20204, 202, '2026-06-25', 'Jueves', 4, 'bicicleta-z2',
    'Repetir un segundo dia aerobico util ya dentro de una semana plenamente funcional.',
    'Bicicleta Z2 120-130 minutos.', 'Pecho, triceps y hombro 25-30 minutos.',
    'Dia para consolidar, no para competir con el martes.',
    1, 'suave', 120, 130, 'Mantener una ejecucion estable y globalmente aerobica.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-02/README.md'
),
(
    20205, 202, '2026-06-26', 'Viernes', 5, 'recuperacion',
    'Proteger la salida larga y llegar con ganas.',
    'Paseo 60-120 minutos o bicicleta Z1 60-120 minutos.', 'Espalda y biceps 25-30 minutos.',
    'Dia de recuperacion real; sesion principal y fuerza opcionales segun el estado de recuperacion. Incluso en el extremo alto debe seguir siendo claramente regenerativa y la fuerza debe omitirse si resta soltura para el sabado.',
    0, 'muy suave', 60, 120, 'La prioridad es llegar fresco al sabado; incluso en el extremo alto la sesion debe seguir siendo claramente regenerativa y omitir la fuerza si deja residuo.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-02/README.md'
),
(
    20206, 202, '2026-06-27', 'Sabado', 6, 'salida-larga',
    'Consolidar una salida larga ya plenamente integrada en el bloque.',
    'Bicicleta 3h-3h15 en Z2.', 'Core 25-30 minutos y revision parcial de carga, hambre y piernas.',
    'Usar nutricion ordenada y no cerrar con sensacion de vaciado.',
    1, 'suave', 180, 195, 'Recortar si el coste sube por encima del papel de la semana.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-02/README.md'
),
(
    20207, 202, '2026-06-28', 'Domingo', 7, 'complementaria',
    'Sumar continuidad sin borrar el valor del sabado.',
    'Monte suave, paseo largo o bicicleta facil 2h-2h30.', 'Revision semanal y movilidad, sin fuerza.',
    'Si el sabado ya deja coste alto, reducir a 90-120 minutos o a paseo llano.',
    0, 'muy suave', 120, 150, 'Mantener el domingo subordinado al sabado.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-02/README.md'
),
(
    20301, 203, '2026-06-29', 'Lunes', 1, 'recuperacion',
    'Mantener el patron de apertura con margen.',
    'Paseo 60-120 minutos, bicicleta Z1 60-120 minutos o descanso activo.', 'Pecho, triceps y hombro 25-30 minutos.',
    'Si el fin de semana fue caro, hacer del lunes un dia claramente mas vacio; incluso en el extremo alto debe sentirse claramente recuperadora.',
    0, 'muy suave', 60, 120, 'No contaminar el arranque de la semana; incluso en el extremo alto la sesion debe seguir siendo claramente recuperadora.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-03/README.md'
),
(
    20302, 203, '2026-06-30', 'Martes', 2, 'referencia-aerobica',
    'Consolidar una referencia aerobica ya algo mas larga.',
    'Bicicleta Z2 120-135 minutos.', 'Espalda y biceps 25-30 minutos.',
    'Registrar potencia media, frecuencia cardiaca media y sensacion para comparar estabilidad.',
    1, 'suave', 120, 135, 'Priorizar estabilidad y comparabilidad.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-03/README.md'
),
(
    20303, 203, '2026-07-01', 'Miercoles', 3, 'complementaria',
    'Sostener el bloque desde la ligereza, no desde el relleno.',
    'Paseo 25-45 minutos o descanso activo.', 'Core 25-30 minutos.',
    'Dia de absorcion real; si se alarga, pierde su funcion.',
    0, 'muy suave', 25, 45, 'Mantener el dia claramente ligero.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-03/README.md'
),
(
    20304, 203, '2026-07-02', 'Jueves', 4, 'bicicleta-z2',
    'Repetir un segundo dia aerobico util sin deriva de ambicion.',
    'Bicicleta Z2 120-130 minutos.', 'Pecho, triceps y hombro 25-30 minutos.',
    'La prioridad es estabilidad de ejecucion, no mas vatios ni mas terreno.',
    1, 'suave', 120, 130, 'Mantener la bici gobernable y estable.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-03/README.md'
),
(
    20305, 203, '2026-07-03', 'Viernes', 5, 'recuperacion',
    'Llegar suelto al fin de semana largo.',
    'Paseo 60-120 minutos o bicicleta Z1 60-120 minutos.', 'Espalda y biceps 25-30 minutos.',
    'Viernes de recuperacion; sesion principal y fuerza opcionales segun el estado de recuperacion. Si hace falta elegir, proteger primero la frescura del sabado y mantener la bici claramente regenerativa incluso en el extremo alto.',
    0, 'muy suave', 60, 120, 'No comprometer el sabado; incluso en el extremo alto la sesion debe seguir siendo claramente recuperadora y omitir la fuerza si deja residuo.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-03/README.md'
),
(
    20306, 203, '2026-07-04', 'Sabado', 6, 'salida-larga',
    'Hacer de la salida larga un elemento ya normal de la semana.',
    'Bicicleta 3h-3h30 en Z2 estable.', 'Core 25-30 minutos y revision de tolerancia global del bloque.',
    'La sesion debe sentirse larga pero gobernable; no perseguir dureza por terreno.',
    1, 'suave', 180, 210, 'Mantener la salida larga dentro de una sesion globalmente aerobica.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-03/README.md'
),
(
    20307, 203, '2026-07-05', 'Domingo', 7, 'complementaria',
    'Mantener continuidad con un segundo dia aerobico claramente secundario.',
    'Paseo largo, monte suave o bicicleta facil 2h-2h30.', 'Movilidad y revision semanal, sin fuerza.',
    'Si el sabado deja arrastre, convertir en 90-120 minutos muy suaves o descanso activo.',
    0, 'muy suave', 120, 150, 'Domingo claramente subordinado.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-03/README.md'
),
(
    20401, 204, '2026-07-06', 'Lunes', 1, 'recuperacion',
    'Abrir con orden y no contaminar el empuje principal.',
    'Paseo 60-120 minutos o bicicleta Z1 60-120 minutos.', 'Pecho, triceps y hombro 25-30 minutos.',
    'El lunes no debe usarse para compensar nada del fin de semana anterior; incluso en el extremo alto mantenerla muy llana y claramente recuperadora.',
    0, 'muy suave', 60, 120, 'No anadir coste extra al lunes; incluso en el extremo alto la sesion debe seguir siendo claramente regenerativa.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-04/README.md'
),
(
    20402, 204, '2026-07-07', 'Martes', 2, 'referencia-aerobica',
    'Hacer un dia aerobico entre semana ya claramente productivo.',
    'Bicicleta Z2 120-140 minutos.', 'Espalda y biceps 25-30 minutos.',
    'Subir tiempo, no dureza; evitar terreno que obligue a cambios de ritmo innecesarios.',
    1, 'suave', 120, 140, 'Subir tiempo sin convertirlo en sesion dura.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-04/README.md'
),
(
    20403, 204, '2026-07-08', 'Miercoles', 3, 'complementaria',
    'Absorber el martes sin perder estructura.',
    'Paseo 25-45 minutos o descanso activo.', 'Core 25-30 minutos.',
    'Si el martes deja mas huella de la prevista, simplificar el dia todo lo posible.',
    0, 'muy suave', 25, 45, 'Mantener el miercoles como dia de absorcion.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-04/README.md'
),
(
    20404, 204, '2026-07-09', 'Jueves', 4, 'bicicleta-z2',
    'Consolidar un segundo dia aerobico util dentro de la misma semana.',
    'Bicicleta Z2 120-135 minutos.', 'Pecho, triceps y hombro 25-30 minutos.',
    'El jueves debe sentirse como continuidad controlada, no como segundo pico.',
    1, 'suave', 120, 135, 'Mantener continuidad controlada.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-04/README.md'
),
(
    20405, 204, '2026-07-10', 'Viernes', 5, 'recuperacion',
    'Llegar al sabado largo con piernas dispuestas.',
    'Paseo 60-120 minutos o bicicleta Z1 60-120 minutos.', 'Espalda y biceps 25-30 minutos.',
    'Mantenerlo simple; viernes de recuperacion, con sesion principal y fuerza opcionales segun el estado de recuperacion. La bici debe seguir siendo claramente facil y la fuerza debe omitirse si compromete la soltura del sabado, incluso en el extremo alto.',
    0, 'muy suave', 60, 120, 'La prioridad es frescura; incluso en el extremo alto la sesion debe seguir siendo claramente regenerativa y omitir la fuerza si deja residuo.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-04/README.md'
),
(
    20406, 204, '2026-07-11', 'Sabado', 6, 'salida-larga',
    'Ejecutar la salida larga mas importante del bloque.',
    'Bicicleta 3h-3h45 en Z2 estable.', 'Core 25-30 minutos y revision de nutricion, sensacion y deriva cardiaca.',
    'Si la sesion se desordena o pide demasiada voluntad, cortar antes del techo.',
    1, 'suave', 180, 225, 'Mantener la salida larga como sesion globalmente aerobica.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-04/README.md'
),
(
    20407, 204, '2026-07-12', 'Domingo', 7, 'complementaria',
    'Cerrar con continuidad util pero subordinada.',
    'Monte suave, paseo largo o bicicleta facil 2h-2h30.', 'Movilidad y revision semanal, sin fuerza.',
    'Este dia no debe convertirse en segunda carga larga; si el sabado fue caro, bajar a 90-120 minutos como minimo efectivo.',
    0, 'muy suave', 120, 150, 'No competir con el sabado.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-04/README.md'
),
(
    20501, 205, '2026-07-13', 'Lunes', 1, 'recuperacion',
    'Abrir la validacion con soltura.',
    'Paseo 60-120 minutos, bicicleta Z1 60-120 minutos o descanso activo.', 'Pecho, triceps y hombro 25-30 minutos.',
    'Si la semana 04 salio cara, recortar sin problema y priorizar frescura; incluso en el extremo alto la sesion debe seguir siendo muy facil.',
    0, 'muy suave', 60, 120, 'Priorizar frescura de inicio; incluso en el extremo alto la sesion debe seguir siendo claramente recuperadora.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-05/README.md'
),
(
    20502, 205, '2026-07-14', 'Martes', 2, 'referencia-aerobica',
    'Repetir una referencia aerobica comparable del bloque.',
    'Bicicleta Z2 120-130 minutos.', 'Espalda y biceps 25-30 minutos.',
    'Importar mas la normalidad de la sesion que su tamano exacto.',
    1, 'suave', 120, 130, 'Buscar comparabilidad antes que ambicion.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-05/README.md'
),
(
    20503, 205, '2026-07-15', 'Miercoles', 3, 'complementaria',
    'Dejar respirar la semana sin perder estructura.',
    'Paseo 20-40 minutos o descanso activo.', 'Core 25-30 minutos.',
    'El dia debe sentirse ligero y recuperar confianza para el jueves.',
    0, 'muy suave', 20, 40, 'Mantener ligereza real.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-05/README.md'
),
(
    20504, 205, '2026-07-16', 'Jueves', 4, 'bicicleta-z2',
    'Sumar un segundo dia aerobico util y comodo.',
    'Bicicleta Z2 120-125 minutos.', 'Pecho, triceps y hombro 25-30 minutos.',
    'No buscar crecimiento; si aparece pesadez, quedarse en el minimo efectivo.',
    1, 'suave', 120, 125, 'Mantener dia util y comodo.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-05/README.md'
),
(
    20505, 205, '2026-07-17', 'Viernes', 5, 'recuperacion',
    'Proteger la salida larga final del bloque.',
    'Paseo 60-120 minutos o bicicleta Z1 60-120 minutos.', 'Espalda y biceps 25-30 minutos.',
    'Cualquier duda se resuelve bajando carga, no manteniendola; viernes de recuperacion con sesion principal y fuerza opcionales segun el estado de recuperacion. La bici debe seguir siendo muy facil y la fuerza debe omitirse si quita frescura para el sabado, incluso en el extremo alto.',
    0, 'muy suave', 60, 120, 'Llegar fresco al sabado; incluso en el extremo alto la sesion debe seguir siendo claramente recuperadora y omitir la fuerza si deja residuo.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-05/README.md'
),
(
    20506, 205, '2026-07-18', 'Sabado', 6, 'salida-larga',
    'Cerrar B2 con salida larga controlada y bien gobernada.',
    'Bicicleta 3h-4h en Z2.', 'Core 25-30 minutos y revision completa del bloque.',
    'Si el jueves o el viernes dejan carga inesperada, recortar al extremo bajo sin dudar.',
    1, 'suave', 180, 240, 'Usar la salida larga como validacion final, no como nuevo empuje sistemico.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-05/README.md'
),
(
    20507, 205, '2026-07-19', 'Domingo', 7, 'complementaria',
    'Dejar el bloque listo para entrar en absorcion.',
    'Paseo largo, monte muy suave o bicicleta facil 2h-2h30.', 'Movilidad, hidratacion y cierre del bloque, sin fuerza.',
    'El domingo debe seguir siendo ligero a nivel de coste; si el sabado deja deuda, recortar a 90-120 minutos.',
    0, 'muy suave', 120, 150, 'Cerrar el bloque con margen.',
    '2026/Bloques/B2-Construccion-aerobica-extensiva-I/Semanas/Semana-05/README.md'
)
ON CONFLICT(planned_session_id) DO UPDATE SET
    week_id = excluded.week_id,
    session_date = excluded.session_date,
    day_name = excluded.day_name,
    sequence_in_week = excluded.sequence_in_week,
    planned_type = excluded.planned_type,
    objective = excluded.objective,
    primary_session = excluded.primary_session,
    complementary_session = excluded.complementary_session,
    notes = excluded.notes,
    is_key_session = excluded.is_key_session,
    intensity_class = excluded.intensity_class,
    duration_min = excluded.duration_min,
    duration_max = excluded.duration_max,
    adjustment_rule = excluded.adjustment_rule,
    markdown_path = excluded.markdown_path;

INSERT INTO plan_session_zone_targets (
    planned_zone_target_id, planned_session_id, target_basis, target_kind, source_kind, source_text, comparison_eligibility
) VALUES
(22, 20202, 'heart_rate', 'single_zone', 'derived', 'Bicicleta Z2 120-135 minutos.', 'eligible'),
(23, 20204, 'heart_rate', 'single_zone', 'derived', 'Bicicleta Z2 120-130 minutos.', 'eligible'),
(24, 20206, 'heart_rate', 'single_zone', 'derived', 'Bicicleta 3h-3h15 en Z2.', 'eligible'),
(25, 20302, 'heart_rate', 'single_zone', 'derived', 'Bicicleta Z2 120-135 minutos.', 'eligible'),
(26, 20304, 'heart_rate', 'single_zone', 'derived', 'Bicicleta Z2 120-130 minutos.', 'eligible'),
(27, 20306, 'heart_rate', 'single_zone', 'derived', 'Bicicleta 3h-3h30 en Z2 estable.', 'eligible'),
(28, 20402, 'heart_rate', 'single_zone', 'derived', 'Bicicleta Z2 120-140 minutos.', 'eligible'),
(29, 20404, 'heart_rate', 'single_zone', 'derived', 'Bicicleta Z2 120-135 minutos.', 'eligible'),
(30, 20406, 'heart_rate', 'single_zone', 'derived', 'Bicicleta 3h-3h45 en Z2 estable.', 'eligible'),
(31, 20502, 'heart_rate', 'single_zone', 'derived', 'Bicicleta Z2 120-130 minutos.', 'eligible'),
(32, 20504, 'heart_rate', 'single_zone', 'derived', 'Bicicleta Z2 120-125 minutos.', 'eligible'),
(33, 20506, 'heart_rate', 'single_zone', 'derived', 'Bicicleta 3h-4h en Z2.', 'eligible')
ON CONFLICT(planned_session_id) DO UPDATE SET
    target_basis = excluded.target_basis,
    target_kind = excluded.target_kind,
    source_kind = excluded.source_kind,
    source_text = excluded.source_text,
    comparison_eligibility = excluded.comparison_eligibility;

INSERT INTO plan_session_zone_segments (
    planned_zone_target_id, sequence_order, segment_label, target_zone_min_code, target_zone_max_code,
    target_duration_seconds_min, target_duration_seconds_max, notes
) VALUES
(22, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(23, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(24, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(25, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(26, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(27, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(28, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(29, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(30, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(31, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(32, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.'),
(33, 1, 'Derived target', 'Z2', 'Z2', NULL, NULL, 'Sesion globalmente aerobica con Z2 como techo funcional.')
ON CONFLICT(planned_zone_target_id, sequence_order) DO UPDATE SET
    segment_label = excluded.segment_label,
    target_zone_min_code = excluded.target_zone_min_code,
    target_zone_max_code = excluded.target_zone_max_code,
    target_duration_seconds_min = excluded.target_duration_seconds_min,
    target_duration_seconds_max = excluded.target_duration_seconds_max,
    notes = excluded.notes;