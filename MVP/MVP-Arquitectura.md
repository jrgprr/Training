# Arquitectura operativa del MVP

## 1. Objetivo

Definir una operativa de trabajo clara para que el sistema de entrenamiento funcione en el dia a dia con el menor trabajo manual posible.

El MVP debe cubrir cuatro necesidades:
- ejecutar el plan diario,
- registrar automaticamente los datos disponibles,
- permitir anadir el contexto subjetivo que los dispositivos no capturan,
- y revisar cada semana los resultados para ajustar el plan siguiente.

Documentos relacionados:
- [Esquema SQL PostgreSQL](./schema-postgresql.sql)
- [API minima](./API-Minima.md)
- [Stack tecnico](./Stack-Tecnico.md)

---

## 2. Flujo operativo real

### Flujo diario

1. La semana ya tiene un plan diario definido.
2. Cada dia se ejecuta la sesion prevista o su sustitucion indoor si la meteorologia lo exige.
3. Los dispositivos registran automaticamente los datos fisiologicos y de entrenamiento.
4. El usuario anade a mano los datos subjetivos minimos.
5. El sistema consolida todo en un registro diario unico.

### Flujo semanal

1. Al cierre de la semana se agregan todos los registros diarios.
2. El sistema calcula indicadores semanales.
3. Se compara lo planificado frente a lo realizado.
4. Se evalua la adecuacion al bloque y al estado real.
5. Se decide la siguiente semana: progresar, mantener o reducir.

### Flujo historico

1. Las semanas alimentan la base historica.
2. La base historica permite calcular medias cortas y largas.
3. El MVP usa esa historia para mostrar tendencia aerobica, tendencia de peso y consistencia.

---

## 3. Modelo funcional del sistema

El sistema se divide en cinco capas:

### Capa 1 - Planificacion

Contiene:
- macro,
- meso,
- micro semanal,
- plan diario.

Funcion:
- definir lo que deberia hacerse.

### Capa 2 - Ingesta automatica

Contiene conectores o procesos de importacion para:
- Garmin S2,
- Garmin Fenix 5X Plus,
- Garmin Edge 530,
- Garmin Vector 3,
- bicicleta de spinning,
- cinta de correr,
- y en el futuro Garmin pod running dynamics si se usa carrera.

Funcion:
- traer al sistema los datos objetivos sin necesidad de introducirlos a mano.

### Capa 3 - Registro manual ligero

Contiene la entrada manual de:
- sensacion general,
- calidad de sueno percibida,
- molestias,
- hambre y apetito,
- adherencia alimentaria,
- comentario de la sesion,
- decision del dia,
- y valoracion final del dia.

Funcion:
- completar el contexto que no capturan los dispositivos.

### Capa 4 - Analisis

Contiene:
- calculo del indice aerobico,
- calculo del indicador de tendencia de peso,
- agregacion diaria y semanal,
- comparacion plan vs realizado,
- deteccion de consistencia,
- y reglas de ajuste.

Funcion:
- transformar datos en informacion util para decidir.

### Capa 5 - Visualizacion y operacion

Contiene:
- front-end diario,
- resumen semanal,
- graficos de tendencia,
- panel de adherencia,
- y panel de estado.

Funcion:
- simplificar entrada, revision y toma de decisiones.

---

## 4. Base de datos propuesta

El sistema ya justifica una base de datos relacional. Aunque el MVP empiece pequeno, necesitas historico, trazabilidad, agregaciones por semana, comparacion plan vs realizado y soporte para datos automaticos y manuales.

La propuesta correcta para este caso es:
- una base relacional central,
- un modelo con tablas operativas para el dia a dia,
- tablas de importacion para conservar trazabilidad,
- y tablas de resumen para acelerar analisis y visualizacion.

### 4.1 Criterios de modelado

La base debe cumplir estos criterios:
- separar claramente plan, realizado y analisis,
- soportar datos automaticos y manuales sin mezclar origenes,
- permitir sustituir una sesion outdoor por una indoor sin perder la intencion planificada,
- guardar historico suficiente para recalcular indicadores,
- y permitir crecer sin rehacer el modelo al anadir nuevas metricas.

Decisiones recomendadas:
- claves primarias tipo UUID o enteros largos,
- timestamps de creacion y actualizacion en tablas principales,
- campos `source_type` y `source_id` cuando la trazabilidad del origen importe,
- y fechas separadas de timestamps cuando el dato sea diario y no intradiario.

### 4.2 Modulos de datos

El modelo se puede organizar en siete modulos:
- perfil y configuracion,
- dispositivos e ingesta,
- planificacion,
- registro diario,
- sesiones de entrenamiento,
- resultados y analitica,
- catalogos y reglas.

### 4.3 Tablas de perfil y configuracion

#### user_profile

Guarda el perfil principal del usuario.

Campos recomendados:
- id
- display_name
- birth_date
- sex opcional
- height_cm
- primary_sport
- preferred_units
- timezone
- created_at
- updated_at

Notas:
- En este caso soporta un unico usuario, pero conviene dejarlo bien modelado desde el principio.

#### user_goal

Guarda objetivos que cambian con el tiempo.

Campos recomendados:
- id
- user_id
- goal_type
- start_date
- end_date opcional
- target_weight_kg opcional
- target_description
- priority_order
- active
- notes

Ejemplos:
- reconstruccion aerobica,
- acercarse a 80 kg,
- mantener fuerza minima eficaz.

#### user_threshold

Guarda zonas y referencias fisiologicas o de trabajo.

Campos recomendados:
- id
- user_id
- threshold_type
- valid_from
- valid_to opcional
- value
- unit
- notes

Ejemplos:
- ftp,
- frecuencia cardiaca umbral,
- zonas de pulso,
- zonas de potencia.

#### user_setting

Guarda configuracion funcional del MVP.

Campos recomendados:
- id
- user_id
- setting_key
- setting_value_json
- updated_at

Ejemplos:
- duracion de media corta,
- duracion de media larga,
- reglas de equivalencia indoor,
- escala de sensaciones.

### 4.4 Tablas de dispositivos e ingesta

#### device

Inventario de dispositivos y equipamiento.

Campos recomendados:
- id
- user_id
- device_type
- brand
- model
- display_name
- serial_number opcional
- data_origin_type
- active
- notes

Ejemplos de `device_type`:
- smartwatch,
- bike_computer,
- power_meter,
- scale,
- spinning_bike,
- treadmill.

#### data_source_account

Representa una cuenta o integracion externa.

Campos recomendados:
- id
- user_id
- provider_name
- account_identifier
- status
- last_sync_at
- metadata_json

Ejemplos:
- Garmin Connect,
- importacion manual por archivos.

#### import_batch

Traza cada proceso de importacion.

Campos recomendados:
- id
- user_id
- source_account_id opcional
- import_type
- started_at
- finished_at opcional
- status
- files_count
- records_count
- error_count
- notes

#### import_file

Traza cada fichero importado.

Campos recomendados:
- id
- import_batch_id
- original_filename
- file_type
- file_hash
- imported_at
- status
- raw_metadata_json

#### import_record

Tabla de trazabilidad de registros crudos o semiprocesados.

Campos recomendados:
- id
- import_file_id
- record_type
- external_id
- record_timestamp
- payload_json
- normalized
- normalized_entity_type opcional
- normalized_entity_id opcional

Funcion:
- permitir reimportar, depurar errores y evitar duplicados.

### 4.5 Tablas de planificacion

#### annual_plan

Representa el marco anual.

Campos recomendados:
- id
- user_id
- year
- title
- macro_objective
- start_date
- end_date
- status
- notes

#### meso_block

Representa cada bloque del ano.

Campos recomendados:
- id
- annual_plan_id
- code
- name
- sequence_order
- start_date
- end_date
- objective
- characteristics_text
- success_signals_text
- caution_signals_text
- target_weight_phase_text opcional
- notes

#### planned_week

Representa la unidad semanal planificada.

Campos recomendados:
- id
- meso_block_id
- week_number_in_block
- calendar_week_label opcional
- start_date
- end_date
- entry_state
- weekly_objective
- secondary_priority
- risk_to_watch
- expected_decision_mode
- target_weight_note
- status
- notes

#### planned_day

Representa el plan operativo del dia.

Campos recomendados:
- id
- planned_week_id
- day_date
- weekday
- primary_objective
- primary_session_type
- primary_session_subtype opcional
- target_duration_min
- target_duration_max_min
- target_intensity_text
- target_zone_text opcional
- indoor_alternative_type opcional
- complementary_work_text
- comments

#### planned_session

Permite mas de una pieza planificada por dia sin romper la regla de una carga principal.

Campos recomendados:
- id
- planned_day_id
- role_type
- session_type
- subtype
- duration_min
- duration_max_min opcional
- intensity_text
- is_key_session
- is_indoor_allowed
- indoor_alternative_text
- notes

Ejemplos de `role_type`:
- primary,
- complementary,
- recovery,
- habit.

### 4.6 Tablas de registro diario

#### daily_checkin

Tabla central del estado subjetivo del dia.

Campos recomendados:
- id
- user_id
- checkin_date
- wake_feeling_score
- sleep_quality_score
- fatigue_score opcional
- soreness_score opcional
- motivation_score opcional
- pain_notes
- day_decision
- free_notes
- created_at
- updated_at

#### body_measurement

Guarda mediciones corporales objetivas.

Campos recomendados:
- id
- user_id
- measurement_date
- measurement_time opcional
- source_device_id opcional
- weight_kg
- body_fat_pct opcional
- bmi opcional
- hydration_pct opcional
- muscle_mass_kg opcional
- payload_json opcional

Notas:
- aqui deberia entrar lo que proporcione Garmin S2.

#### sleep_record

Separa el sueno objetivo del sueno percibido.

Campos recomendados:
- id
- user_id
- sleep_date
- source_device_id opcional
- total_sleep_min opcional
- deep_sleep_min opcional
- rem_sleep_min opcional
- awakenings_count opcional
- device_sleep_score opcional
- perceived_sleep_score opcional
- notes

#### daily_habit_record

Guarda habitos y rutinas del dia.

Campos recomendados:
- id
- user_id
- habit_date
- morning_routine_done
- morning_routine_min opcional
- extra_mobility_done
- extra_mobility_min opcional
- night_walk_done
- night_walk_min opcional
- hydration_quality opcional
- notes

#### nutrition_check

MVP simple de contexto nutricional sin hacer nutricion detallada.

Campos recomendados:
- id
- user_id
- nutrition_date
- appetite_level
- adherence_level
- fueling_quality_training_day opcional
- overeating_episode boolean opcional
- notes

### 4.7 Tablas de sesiones realizadas

#### training_session

Tabla central del entrenamiento realmente realizado.

Campos recomendados:
- id
- user_id
- session_date
- planned_day_id opcional
- planned_session_id opcional
- session_type
- session_subtype
- sport_type
- execution_mode
- indoor boolean
- weather_impact boolean
- substitution_reason opcional
- source_device_id opcional
- start_time opcional
- end_time opcional
- duration_min
- distance_km opcional
- elevation_gain_m opcional
- avg_heart_rate opcional
- max_heart_rate opcional
- avg_power_w opcional
- normalized_power_w opcional
- max_power_w opcional
- avg_cadence_rpm opcional
- avg_speed_kmh opcional
- calories_kcal opcional
- rpe_score opcional
- session_comment
- completed_as_planned boolean
- created_at
- updated_at

Valores importantes:
- `execution_mode`: outdoor, indoor, mixed.
- `substitution_reason`: lluvia, frio, viento, seguridad, tiempo limitado.

#### session_interval_summary

Opcional pero muy util si luego quieres analisis mas fino.

Campos recomendados:
- id
- training_session_id
- interval_order
- interval_type
- duration_sec
- avg_power_w opcional
- avg_heart_rate opcional
- avg_cadence_rpm opcional
- notes

#### session_zone_summary

Guarda tiempo por zonas para analitica rapida.

Campos recomendados:
- id
- training_session_id
- zone_type
- zone_label
- duration_sec
- percent_of_session

Ejemplos de `zone_type`:
- power,
- heart_rate,
- pace.

#### session_device_link

Relaciona varios dispositivos a una misma sesion.

Campos recomendados:
- id
- training_session_id
- device_id
- role_type

Ejemplos:
- Edge 530 como dispositivo principal,
- Vector 3 como sensor asociado,
- Fenix como secundario.

### 4.8 Tablas de comparacion plan vs realizado

#### day_execution_review

Resume como salio el dia frente al plan.

Campos recomendados:
- id
- planned_day_id
- user_id
- was_executed
- was_substituted
- substitution_quality
- perceived_match_to_plan
- daily_load_comment
- reviewer_note opcional

#### week_review

Tabla central del cierre semanal operativo.

Campos recomendados:
- id
- planned_week_id
- user_id
- total_sessions_completed
- total_bike_sessions_completed
- total_activity_min
- total_bike_min
- long_session_completed
- strength_completed
- indoor_substitutions_count
- perceived_consistency_score
- fatigue_end_week_score opcional
- weight_trend_label
- aerobic_index_value opcional
- suggested_next_decision
- final_decision
- review_comment
- reviewed_at

### 4.9 Tablas de resultados y analitica

#### daily_metric

Tabla de metricas derivadas por dia.

Campos recomendados:
- id
- user_id
- metric_date
- aerobic_load_value opcional
- wellness_score opcional
- weight_trend_short_value opcional
- weight_trend_long_value opcional
- readiness_flag opcional
- calculation_version

#### weekly_metric

Tabla de metricas derivadas por semana.

Campos recomendados:
- id
- planned_week_id opcional
- user_id
- week_start_date
- week_end_date
- short_aerobic_load
- long_aerobic_load
- aerobic_index
- short_weight_avg
- long_weight_avg
- weight_trend_delta
- total_bike_hours
- total_activity_hours
- completion_rate_pct
- consistency_label
- calculation_version

#### analysis_snapshot

Permite congelar resultados de analisis cuando cambien las reglas.

Campos recomendados:
- id
- snapshot_type
- reference_entity_type
- reference_entity_id
- snapshot_date
- payload_json
- calculation_version

Funcion:
- comparar resultados si cambian formulas o reglas del MVP.

### 4.10 Catalogos utiles

Para evitar textos libres excesivos, conviene tener catalogos sencillos:
- sport_type
- session_type
- habit_type
- device_type
- goal_type
- decision_type
- adherence_level
- appetite_level
- weather_condition opcional
- substitution_reason

No hace falta sobredisenar estos catalogos en la primera version, pero si conviene dejar el modelo listo para no llenar la base de strings inconsistentes.

### 4.11 Relaciones principales

Relaciones clave del modelo:
- `user_profile` 1:N `user_goal`
- `user_profile` 1:N `device`
- `annual_plan` 1:N `meso_block`
- `meso_block` 1:N `planned_week`
- `planned_week` 1:N `planned_day`
- `planned_day` 1:N `planned_session`
- `planned_day` 1:N `training_session`
- `training_session` 1:N `session_zone_summary`
- `training_session` 1:N `session_device_link`
- `planned_week` 1:1 o 1:N `week_review`
- `planned_week` 1:1 o 1:N `weekly_metric`

La relacion mas importante de negocio es esta:
- una semana planificada genera dias planificados,
- los dias planificados se comparan con sesiones reales,
- y de esa comparacion salen las metricas y decisiones semanales.

### 4.12 Indices recomendados

Indices minimos para que el sistema responda bien:
- por fecha en `body_measurement`, `daily_checkin`, `sleep_record`, `training_session`
- por `planned_week_id` en tablas de review y metricas
- por `planned_day_id` en `training_session`
- por `external_id` y `file_hash` en tablas de importacion
- por `user_id + date` en tablas diarias

### 4.13 Tablas estrictamente necesarias para la primera version

Si quieres construir solo el MVP util, empezaria con estas:
- `user_profile`
- `user_goal`
- `device`
- `annual_plan`
- `meso_block`
- `planned_week`
- `planned_day`
- `daily_checkin`
- `body_measurement`
- `daily_habit_record`
- `nutrition_check`
- `training_session`
- `week_review`
- `weekly_metric`
- `import_batch`
- `import_file`

Con eso ya puedes:
- planificar,
- importar,
- registrar contexto,
- analizar semanas,
- y mostrar un front-end funcional.

### 4.14 Eleccion practica de base de datos

Para esta necesidad:
- SQLite sirve para una primera version local y personal,
- PostgreSQL es mejor si quieres escalar servicios, tareas programadas y front-end web serio.

Recomendacion practica:
- si el objetivo inmediato es validar el MVP rapido, empezar con PostgreSQL simplifica menos el arranque pero evita migraciones tempranas si el sistema crece enseguida.

---

## 5. Servicios necesarios

### 5.1 Servicio de ingesta

Responsabilidad:
- importar datos desde ficheros o exportaciones de Garmin,
- mapear los campos de origen al modelo interno,
- evitar duplicados,
- asociar cada dato a una fecha y una fuente.

Entradas posibles:
- ficheros exportados de Garmin,
- sincronizaciones periodicas,
- cargas manuales de archivos,
- datos de spinning y cinta si generan archivo compatible.

Salidas:
- registros fisiologicos diarios,
- sesiones realizadas,
- metadatos de origen.

### 5.2 Servicio de normalizacion

Responsabilidad:
- limpiar datos incompletos,
- unificar formatos de fecha y unidades,
- decidir equivalencias indoor/outdoor,
- consolidar multiples fuentes del mismo dia.

### 5.3 Servicio de registro manual

Responsabilidad:
- guardar las entradas subjetivas del usuario,
- validar campos simples,
- completar los dias que ya tienen datos automaticos.

### 5.4 Servicio de analisis

Responsabilidad:
- calcular carga diaria y semanal,
- calcular indice aerobico,
- calcular indicador de tendencia de peso,
- comparar plan vs realizado,
- detectar cumplimiento, deuda o exceso.

### 5.5 Servicio de recomendacion operativa

Responsabilidad:
- no prescribir entrenamientos automaticamente,
- pero si proponer un estado semanal:
- progresar,
- mantener,
- reducir,
- o revisar.

### 5.6 Servicio de visualizacion

Responsabilidad:
- exponer datos al front-end,
- servir paneles, graficos y filtros,
- mostrar historico diario, semanal y por bloques.

---

## 6. Operativa de registro automatizado

### Automatizable desde dispositivos

Debe entrar automatico siempre que sea posible:
- peso desde Garmin S2,
- actividad diaria y paseos desde Fenix,
- sesiones de bici desde Edge 530,
- potencia y cadencia desde Vector 3,
- datos de spinning si se exportan,
- datos de cinta si se exportan o se registran con Fenix.

### Manual minimo necesario

Debe quedar manual:
- calidad de sueno percibida si no quieres depender solo del dispositivo,
- sensacion general,
- molestias,
- hambre,
- adherencia alimentaria,
- valoracion de la sesion,
- motivo de una sustitucion o recorte,
- y decision del dia siguiente.

### Regla practica

El sistema debe seguir esta prioridad:
- automatico si el dato existe y es fiable,
- manual solo cuando aporte contexto,
- nunca duplicar trabajo si el dispositivo ya lo hace bien.

---

## 7. Analisis semanal

Cada semana el sistema debe producir un cierre con estas preguntas:
- se hizo lo planificado,
- se hizo algo equivalente,
- se hizo menos o mas de lo previsto,
- la semana fue repetible,
- el largo dejo deuda o fue tolerable,
- el peso evoluciono bien,
- la tendencia aerobica acompana,
- y la siguiente semana debe progresar, mantenerse o recortarse.

### Salidas minimas del analisis semanal

- porcentaje de cumplimiento del plan,
- numero de sustituciones indoor,
- tiempo total de bici,
- tiempo total de actividad,
- peso medio semanal,
- tendencia de peso,
- indice aerobico,
- comentario de consistencia,
- y decision semanal.

---

## 8. Front-end necesario

El front-end no es accesorio. Es necesario para reducir friccion y hacer util el sistema.

### Pantallas minimas

#### Panel diario

Debe mostrar:
- plan del dia,
- datos ya importados,
- campos manuales pendientes,
- estado del dia,
- y si la sesion fue indoor u outdoor.

#### Registro de sesion

Debe permitir:
- revisar la sesion importada,
- corregir si hizo falta una sustitucion indoor,
- anadir comentario breve,
- y validar el cierre diario.

#### Resumen semanal

Debe mostrar:
- plan vs realizado,
- tendencia de peso,
- indice aerobico,
- sesiones completadas,
- fuerza,
- paseos,
- y decision sugerida.

#### Vista historica

Debe mostrar:
- peso,
- carga,
- tiempo de bici,
- consistencia,
- bloques,
- y semanas.

### Principios del front-end

- muy rapido para completar,
- orientado a flujo diario y semanal,
- mas panel de control que hoja de calculo,
- y con visualizaciones simples antes que sofisticadas.

---

## 9. Arquitectura tecnica minima recomendada

Para un MVP razonable, la arquitectura minima deberia ser:

### Base de datos
- PostgreSQL o SQLite para la primera version.

### Backend
- API y servicios de ingesta, normalizacion y analisis.
- Tareas programadas para importacion y recalculo semanal.

### Front-end
- aplicacion web simple para escritorio y movil.
- formularios cortos para entrada manual.
- graficos de tendencia y resumentes semanales.

### Procesos programados
- importacion diaria de datos,
- recalculo de indicadores,
- cierre semanal de resumen.

---

## 10. Orden de construccion recomendado

### Fase 1 - MVP funcional
- base de datos,
- importacion simple desde Garmin,
- registro manual diario,
- calculo de indice aerobico,
- calculo de tendencia de peso,
- resumen semanal,
- pantalla diaria y semanal.

### Fase 2 - Mejora operativa
- mejores visualizaciones,
- deteccion de datos faltantes,
- mejor gestion de sesiones indoor,
- y automatizacion de cierres semanales.

### Fase 3 - Monitorizacion y calidad
- alertas,
- comprobacion de inconsistencias,
- historico mas rico,
- y reglas mas refinadas para decisiones semanales.

---

## 11. Criterio final

La arquitectura correcta no es la mas grande, sino la que permite:
- registrar bien sin esfuerzo excesivo,
- revisar cada semana con claridad,
- tomar decisiones mejores,
- y construir un historico fiable para interpretar el proceso real.
