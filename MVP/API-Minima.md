# API minima del MVP

## 1. Objetivo

Definir una API suficientemente pequena para cubrir:
- configuracion inicial,
- importacion de datos,
- entrada manual diaria,
- consulta del plan,
- cierre semanal,
- y visualizacion del estado.

La API no debe intentar resolver toda la logica futura. Debe exponer bien el flujo diario y semanal del MVP.

---

## 2. Principios de diseno

- API REST JSON.
- Versionado desde el principio: `/api/v1`.
- Recursos centrados en usuario, plan, registros, sesiones y metricas.
- Endpoints pequenos y predecibles.
- La analitica compleja debe vivir en servicios internos, no en el front-end.

---

## 3. Recursos principales

### Perfil y configuracion
- `GET /api/v1/profile`
- `PATCH /api/v1/profile`
- `GET /api/v1/goals`
- `POST /api/v1/goals`
- `PATCH /api/v1/goals/{goalId}`
- `GET /api/v1/devices`
- `POST /api/v1/devices`
- `PATCH /api/v1/devices/{deviceId}`
- `GET /api/v1/settings`
- `PATCH /api/v1/settings`

### Planificacion
- `GET /api/v1/plans/years/{year}`
- `GET /api/v1/blocks/{blockId}`
- `GET /api/v1/weeks/{weekId}`
- `PATCH /api/v1/weeks/{weekId}`
- `GET /api/v1/weeks/{weekId}/days`
- `PATCH /api/v1/days/{dayId}`
- `POST /api/v1/days/{dayId}/sessions`
- `PATCH /api/v1/planned-sessions/{plannedSessionId}`

### Registro diario manual
- `GET /api/v1/checkins/{date}`
- `PUT /api/v1/checkins/{date}`
- `GET /api/v1/body-measurements/{date}`
- `PUT /api/v1/body-measurements/{date}`
- `GET /api/v1/sleep-records/{date}`
- `PUT /api/v1/sleep-records/{date}`
- `GET /api/v1/habits/{date}`
- `PUT /api/v1/habits/{date}`
- `GET /api/v1/nutrition/{date}`
- `PUT /api/v1/nutrition/{date}`

### Sesiones realizadas
- `GET /api/v1/training-sessions/{sessionId}`
- `POST /api/v1/training-sessions`
- `PATCH /api/v1/training-sessions/{sessionId}`
- `GET /api/v1/training-sessions?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `POST /api/v1/training-sessions/{sessionId}/devices`
- `PUT /api/v1/days/{dayId}/execution-review`

### Ingesta
- `POST /api/v1/imports`
- `GET /api/v1/imports/{importId}`
- `GET /api/v1/imports/{importId}/files`
- `POST /api/v1/imports/files`
- `POST /api/v1/imports/garmin`

### Analitica y seguimiento
- `GET /api/v1/metrics/daily?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /api/v1/metrics/weekly?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `POST /api/v1/weeks/{weekId}/recalculate`
- `GET /api/v1/weeks/{weekId}/review`
- `PUT /api/v1/weeks/{weekId}/review`
- `GET /api/v1/dashboard/today`
- `GET /api/v1/dashboard/week/{weekId}`
- `GET /api/v1/dashboard/trends`

---

## 4. Endpoints minimos imprescindibles para la primera version

Si hay que recortar al MVP real, estos son los imprescindibles:
- `GET /api/v1/profile`
- `GET /api/v1/weeks/{weekId}`
- `GET /api/v1/weeks/{weekId}/days`
- `PUT /api/v1/checkins/{date}`
- `PUT /api/v1/habits/{date}`
- `PUT /api/v1/nutrition/{date}`
- `POST /api/v1/imports/files`
- `POST /api/v1/training-sessions`
- `PATCH /api/v1/training-sessions/{sessionId}`
- `GET /api/v1/weeks/{weekId}/review`
- `PUT /api/v1/weeks/{weekId}/review`
- `GET /api/v1/dashboard/today`
- `GET /api/v1/dashboard/week/{weekId}`

---

## 5. Contratos funcionales principales

### 5.1 Panel diario

`GET /api/v1/dashboard/today`

Debe devolver en una sola respuesta:
- fecha,
- dia planificado,
- sesiones previstas,
- checkin del dia,
- medicion corporal del dia,
- habitos del dia,
- sesiones realizadas del dia,
- campos pendientes de completar,
- y estado general del dia.

Ejemplo de respuesta:
```json
{
  "date": "2026-05-12",
  "plannedDay": {
    "id": 101,
    "objective": "Primer estimulo aerobico util",
    "primarySessionType": "bike",
    "indoorAlternativeType": "spinning"
  },
  "checkin": {
    "wakeFeelingScore": 4,
    "sleepQualityScore": 3,
    "dayDecision": "normal"
  },
  "bodyMeasurement": {
    "weightKg": 91.4
  },
  "sessions": [],
  "pendingFields": ["nutrition", "habit_record"],
  "dayStatus": "ready"
}
```

### 5.2 Registro manual diario

`PUT /api/v1/checkins/{date}`

Payload ejemplo:
```json
{
  "wakeFeelingScore": 4,
  "sleepQualityScore": 3,
  "fatigueScore": 2,
  "sorenessScore": 2,
  "motivationScore": 4,
  "painNotes": "Sin molestias relevantes",
  "dayDecision": "normal",
  "freeNotes": "Piernas normales"
}
```

### 5.3 Creacion o ajuste de sesion realizada

`POST /api/v1/training-sessions`

Payload ejemplo:
```json
{
  "sessionDate": "2026-05-12",
  "plannedDayId": 101,
  "plannedSessionId": 201,
  "sessionType": "bike",
  "sportType": "cycling",
  "executionMode": "indoor",
  "indoor": true,
  "weatherImpact": true,
  "substitutionReason": "rain",
  "sourceDeviceId": 3,
  "durationMin": 72,
  "distanceKm": 31.2,
  "avgHeartRate": 132,
  "avgPowerW": 168,
  "normalizedPowerW": 175,
  "avgCadenceRpm": 87,
  "rpeScore": 4,
  "sessionComment": "Spinning equivalente por lluvia",
  "completedAsPlanned": true
}
```

### 5.4 Importacion de archivos

`POST /api/v1/imports/files`

Debe permitir:
- subir uno o varios archivos,
- asociarlos a un tipo de importacion,
- lanzar normalizacion,
- y devolver un `importId` para seguimiento.

Respuesta ejemplo:
```json
{
  "importId": 55,
  "status": "processing",
  "filesAccepted": 2
}
```

### 5.5 Revision semanal

`GET /api/v1/weeks/{weekId}/review`

Debe devolver:
- resumen plan vs realizado,
- metricas semanales,
- tendencia de peso,
- indice aerobico,
- estado sugerido,
- y comentario operativo.

Respuesta ejemplo:
```json
{
  "weekId": 12,
  "completionRatePct": 86.0,
  "indoorSubstitutionsCount": 1,
  "aerobicIndex": 98.4,
  "weightTrendLabel": "down_slow_stable",
  "suggestedNextDecision": "maintain",
  "reviewComment": "Semana repetible con progresion asumible"
}
```

---

## 6. Reglas de escritura y lectura

- `PUT` para recursos diarios identificados por fecha.
- `POST` para crear sesiones, importaciones o nuevos recursos sin clave natural.
- `PATCH` para ajustes parciales.
- `GET` para consultas y paneles.

Regla practica:
- el front-end debe consumir paneles agregados cuando necesite vistas operativas,
- y recursos atomicos cuando este editando datos concretos.

---

## 7. Errores esperables

Formato de error recomendado:
```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid session payload",
    "details": [
      {
        "field": "durationMin",
        "message": "Must be greater than 0"
      }
    ]
  }
}
```

Errores frecuentes:
- `validation_error`
- `not_found`
- `duplicate_import`
- `conflict_with_existing_session`
- `unsupported_file_type`
- `analysis_failed`

---

## 8. Orden de implementacion recomendado

1. Perfil, dispositivos y settings.
2. Plan semanal y panel diario.
3. Registro manual diario.
4. Sesiones realizadas.
5. Importacion de archivos.
6. Revision y metricas semanales.
7. Tendencias e historico.
