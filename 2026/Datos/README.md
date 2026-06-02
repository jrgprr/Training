# Datos 2026

Esta carpeta contiene la capa de intercambio y trazabilidad de datos de la temporada 2026.

Su objetivo no es ser la fuente primaria del sistema, sino:
- recibir importaciones externas,
- conservar trazabilidad de origen,
- y permitir exportaciones o ficheros intermedios cuando hagan falta.

## 1. Principios de esta capa

- La fuente primaria del sistema vive en `../../Sistema/training.sqlite`.
- `Datos/` no sustituye a la base relacional: la alimenta o la exporta.
- Garmin es la fuente externa principal, pero el sistema admite otras entradas manuales o automáticas.

## 2. Componentes de esta carpeta

### `Importaciones/`
- Guarda ficheros originales o intermedios de sistemas externos.
- No deben editarse los originales.

## 3. Estructura propuesta

```text
Plan/
  Sistema/
    training.sqlite
  2026/
  Datos/
    README.md
    Importaciones/
      Garmin/
        README.md
```

## 4. Regla de uso

- Los CSV ya no son la fuente primaria.
- Si se necesitan, deben generarse de forma explicita como staging o exportacion puntual.
- La verdad estructurada debe terminar en SQLite.
- No hace falta esperar a tener automatizacion completa con Garmin para empezar: se puede importar primero de forma manual o semimanual.
- Los ficheros crudos de Garmin que conserven detalle util para analisis posteriores, como los `.tcx`, pueden versionarse en `Importaciones/` cuando SQLite no preserve toda esa informacion.
- Esos ficheros deben tratarse como artefactos de trazabilidad y analisis: no se editan manualmente y se conservan con su identificador original.

## 5. Correspondencia minima con la base relacional

Si se usan CSV intermedios, deben mapearse como minimo a estos grupos de tablas en SQLite:

- `actividades.csv` -> `exec_activities`
- `fisiologia-diaria.csv` -> `exec_daily_metrics`
- `seguimiento-diario.csv` -> `review_daily_reviews` y enlaces plan-real

Actualmente esos CSV no forman parte del estado normal del workspace: se eliminan cuando no se usan y, si hacen falta, se regeneran desde SQLite o desde un proceso de importacion.

## 6. Siguiente evolucion natural

Cuando la capa relacional ya tenga continuidad, se pueden anadir:
- importadores automáticos desde Garmin,
- vistas SQL de resumen semanal,
- reglas de sincronizacion Markdown <-> SQLite,
- y agentes que analicen cumplimiento, tendencia y ajuste.