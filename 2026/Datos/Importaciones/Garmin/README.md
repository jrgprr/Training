# Importaciones Garmin

Esta carpeta sirve para guardar exportaciones originales o intermedias desde Garmin antes de incorporarlas al sistema.

Estructura actual:
- `Actividades/<fecha>/<garmin_activity_id>.tcx` para artefactos crudos descargados por la importacion directa.

Uso recomendado:
- guardar aqui los ficheros exportados desde Garmin Connect o desde otras herramientas,
- no editar los originales,
- y transformar despues esos datos a la base SQLite de la temporada.

Destino principal de carga:
- `../../../Sistema/training.sqlite`

Destinos opcionales intermedios:
- exportaciones CSV generadas ad hoc fuera del flujo normal,
- o cualquier otra capa temporal que se use para depuracion o intercambio.

Formatos posibles:
- CSV exportado,
- JSON,
- FIT o TCX,
- o cualquier otro formato intermedio que se use en la automatizacion.