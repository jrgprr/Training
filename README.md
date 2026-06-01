# Plan de entrenamiento

Este workspace organiza la planificacion de entrenamiento por temporadas.

Cada carpeta anual contiene la informacion especifica de una temporada concreta, mientras que este documento define la estructura comun aplicable a cualquier ano.

## 1. Organizacion general

- Cada temporada vive en su propia carpeta: `2026/`, `2027/`, etc.
- Cada carpeta anual contiene el contenido especifico de la temporada, mientras que la base relacional plurianual y la infraestructura general viven en raiz.
- La estructura de niveles es comun para todas las temporadas.

Arquitectura base por temporada:
- `Sistema/`: infraestructura general y base SQLite unica plurianual.
- `Bloques/`, `Macro.md`, `Ficha-usuario.md`: vistas humanas y documentos de trabajo.
- `Datos/`: importaciones, exportaciones y trazabilidad de fuentes externas.
- `Agentes/`: arquitectura y roles de agentes del sistema completo.
- `GUI/`: interfaz de usuario para operar, revisar y gobernar el sistema.
- `Roadmap/`: hoja de ruta con versiones intermedias y criterios de validacion.

Capas funcionales del sistema completo:
- datos estructurados,
- automatizacion mediante agentes,
- y GUI para la interaccion humana.

## 2. Niveles del modelo

### Macro ciclo
- Define la direccion de toda la temporada.
- Responde a: que se quiere conseguir ese ano, desde que punto se parte y bajo que restricciones.
- Vive de forma estructurada en la base de datos de la temporada y se expone de forma legible en `Macro.md`.

### Meso ciclos
- Dividen el macro en bloques con una funcion concreta.
- Responden a: que fase del proceso toca construir ahora, con que criterios de entrada, salida y progresion.
- Viven de forma estructurada en la base de datos de la temporada y se exponen en `Bloques/README.md` y en el `README.md` de cada bloque.

### Micro ciclos
- Traducen cada bloque a semanas operables.
- Responden a: que se hace esta semana, como se distribuye la carga y que ajustes pide el estado real del usuario.
- Viven de forma estructurada en la base de datos de la temporada y se exponen en los markdown semanales.

## 3. Regla de dependencia

- El macro fija el sentido general.
- El meso traduce ese sentido a bloques de trabajo.
- El micro concreta cada bloque en semanas y dias.
- Ningun micro deberia contradecir el objetivo del meso.
- Ningun meso deberia contradecir las prioridades del macro.

## 4. Estructura tipo de una temporada

```text
Plan/
  README.md
  Sistema/
    README.md
    schema.sql
    views.sql
    training.sqlite
    Seeds/
      2026.sql
  2026/
    README.md
    Ficha-usuario.md
    Macro.md
    Bloques/
      README.md
      Bx-Nombre-del-bloque/
        README.md
        Semanas/
          Semana-01/
            README.md
          Semana-02/
            README.md
  2027/
    README.md
    ...
```

## 5. Criterio practico de uso

- Cuando se define o revisa la estructura del sistema, se trabaja en este README raiz.
- Cuando faltan datos del contexto real del usuario, se revisa la ficha del ano correspondiente.
- Cuando cambian los objetivos globales o el contexto del usuario, se revisa el macro de esa temporada.
- Cuando cambia la fase de trabajo o el enfoque del bloque, se revisa el meso.
- Cuando cambia la carga real, la fatiga o la disponibilidad, se revisa el micro.
- Cuando se quiere consultar la fuente estructurada de verdad, se revisa `Sistema/`.
- Cuando se quiere contrastar la planificacion con lo que realmente ocurre o revisar trazabilidad externa, se revisa `Datos/`.

## 6. Fuente primaria y vistas humanas

El sistema no solo planifica; tambien necesita registrar lo que realmente ocurre y dejarlo disponible para analisis automatizado.

Por eso cada temporada debe incorporar una fuente primaria relacional con tres funciones:
- guardar estructura de planificacion,
- guardar ejecucion real y fisiologia,
- y enlazar ambas capas para poder revisar, analizar y ajustar.

Los markdown no desaparecen: pasan a ser vistas humanas del sistema, utiles para pensar, leer y revisar. La fuente principal de datos pasa a ser la base SQLite unica en `Sistema/`.

## 7. Papel de Garmin

Garmin pasa a ser una fuente externa principal de datos de ejecucion y fisiologia.

Esos datos pueden entrar en la carpeta `Datos/Importaciones/` y transformarse despues a las tablas relacionales del sistema, con opcion de exportar CSV si hace falta para intercambio o revision.

## 8. Estado actual de desarrollo

Situacion actual del workspace a mayo de 2026:

- La fuente canonica runtime sigue siendo `Sistema/training.sqlite`.
- La GUI local ya permite navegar temporadas, bloques, semanas, sesiones, actividades Garmin y comparativas `plan vs realidad`.
- El sistema funciona en modo Garmin-only: las nuevas actividades reales deben entrar por Garmin Connect y no por captura manual en la GUI.

Estado funcional por areas:

- `GUI/backend/`: FastAPI local con endpoints de lectura e importacion Garmin.
- `GUI/frontend/`: Vite + React para operar el sistema y revisar ejecucion real.
- `Sistema/`: esquema SQL, vistas y base SQLite plurianual como unica fuente de verdad.

## 9. Arranque local de la aplicacion

Arranque rapido del stack local con Garmin:

```bash
source /home/jparra/Training/.venv/bin/activate
bash /home/jparra/Training/GUI/dev-with-garmin.sh
```

Resultado esperado:

- backend FastAPI en `http://127.0.0.1:8000`
- frontend Vite en `http://127.0.0.1:5173`

Requisitos practicos:

- existe el entorno Python en `/home/jparra/Training/.venv`
- existen dependencias frontend instaladas en `GUI/frontend`
- Garmin Connect esta configurado mediante `GUI/.env.garmin.local`, `GARMIN_CONNECT_SESSION_PATH` o credenciales exportadas en shell

## 10. Documentos recomendados segun la tarea

- Para entender la estructura general del entrenamiento: `README.md`, `2026/Macro.md`, `2026/Bloques/README.md`.
- Para entender la fuente de verdad runtime: `Sistema/README.md`, `Sistema/schema.sql`, `Sistema/views.sql`.
- Para operar la GUI y el backend: `GUI/frontend/README.md` y `GUI/backend/README.md`.
- Para la arquitectura de agentes del sistema: `Agentes/README.md`.