# Stack recomendado para la GUI

Este documento fija la recomendacion de stack tecnico para la GUI inicial del sistema.

## 1. Decision

Para la GUI minima de `V0.2` y la evolucion posterior del sistema, la opcion recomendada es:

- Frontend: React + TypeScript + Vite
- Backend local: FastAPI en Python
- Base de datos: SQLite existente en `Sistema/training.sqlite`

## 2. Motivo principal

Este stack separa bien responsabilidades y encaja con lo que ya existe:
- SQLite como fuente primaria,
- Python como capa natural para agentes, importacion y analisis,
- y frontend web local para validacion visual y crecimiento futuro.

## 3. Por que no otra cosa en V0.2

### Solo frontend leyendo SQLite directamente
No recomendado.

Problemas:
- expone demasiado la estructura interna,
- obliga a meter logica de datos en la GUI,
- y complica evolucionar hacia agentes y acciones controladas.

### App de escritorio primero
Posible, pero no es la mejor primera inversion.

Problemas:
- mas acoplamiento con el cliente,
- menos natural para crecer hacia servicios, MCP y agentes.

### GUI dentro de VS Code
Util para prototipos, pero insuficiente como direccion principal de producto.

## 4. Arquitectura minima en V0.2

### Frontend web local
Responsabilidad:
- mostrar temporadas, bloques, semanas y sesiones.

### Backend FastAPI
Responsabilidad:
- abrir SQLite,
- ejecutar consultas de lectura,
- devolver JSON estable a la GUI.

### SQLite
Responsabilidad:
- seguir siendo la fuente de verdad.

## 5. Ventajas practicas

- El backend Python podra reutilizar codigo futuro de agentes.
- La GUI podra crecer sin reescribir la capa de datos.
- La API local sera la frontera natural entre lectura, escritura y acciones.
- El salto de `V0.2` a `V0.6` sera incremental, no un reinicio.

## 6. Coste asumido

Este stack introduce una pequena complejidad inicial porque separa frontend y backend.

Pero compensa porque evita un problema mayor mas adelante: una GUI que nace simple pero queda acoplada a SQLite de forma dificil de gobernar.

## 7. Recomendacion operativa

Para `V0.2`:
- implementar solo endpoints de lectura,
- sin autenticacion,
- sin acciones de escritura,
- y con cuatro rutas minimas para temporadas, bloques, semanas y sesiones.

## 8. Endpoints minimos sugeridos

- `GET /api/seasons`
- `GET /api/seasons/{seasonId}/blocks`
- `GET /api/blocks/{blockId}/weeks`
- `GET /api/weeks/{weekId}/sessions`

## 9. Criterio de eleccion cerrado

Salvo que aparezca una restriccion nueva fuerte, este es el stack recomendado para avanzar.

La decision deberia darse por cerrada para evitar reabrir el debate tecnologico antes de implementar `V0.2`.