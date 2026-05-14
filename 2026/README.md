# Temporada 2026

Este directorio contiene la informacion especifica de la temporada 2026.

La estructura general del sistema se define en el README raiz del workspace. Aqui solo se mantiene el contenido propio de esta temporada.

## 1. Documentos base de 2026

- `Ficha-usuario.md`: contexto base y datos del usuario para 2026.
- `Macro.md`: direccion anual y criterios generales de la temporada.
- `Bloques/`: bloques meso y semanas micro de 2026.
- `Datos/`: importaciones, exportaciones y trazabilidad de datos externos de 2026.

## 2. Alcance de esta carpeta

Esta temporada recoge:
- el punto de partida del usuario en 2026,
- los objetivos y restricciones del ano,
- la secuencia de bloques definida para este ciclo,
- la microplanificacion semanal que se vaya concretando,
- y los datos reales con los que se compara la planificacion.

La fuente primaria relacional del sistema vive en `../Sistema/` y esta temporada se representa en esa base mediante `season_id = 2026`.

## 3. Criterio practico de uso para 2026

- Cuando faltan datos del contexto real del usuario en 2026, se revisa `Ficha-usuario.md`.
- Cuando cambian los objetivos globales o el contexto de la temporada, se revisa `Macro.md`.
- Cuando cambia la fase de trabajo o el enfoque de un bloque, se revisa `Bloques/README.md` o el `README.md` del bloque correspondiente.
- Cuando cambia la carga real, la fatiga o la disponibilidad, se revisa la semana afectada.
- Cuando se quiere consultar la fuente estructurada principal, se revisa `../Sistema/` filtrando por la temporada 2026.
- Cuando se quiere revisar importaciones Garmin, exportaciones o trazabilidad externa, se revisa `Datos/`.