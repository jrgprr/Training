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