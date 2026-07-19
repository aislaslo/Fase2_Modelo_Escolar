# Reporte de Data Drift

Comparacion: `data/dataset_abandono.csv` (entrenamiento) vs `actividad8/evidencia/dataset_produccion_con_drift.csv` (produccion simulada).

| Variable | PSI | Clasificacion | Media referencia | Media producción |
|---|---|---|---|---|
| asistencia | 0.2640 | SIGNIFICATIVO | 0.841 | 0.779 |
| promedio_academico | 0.2558 | SIGNIFICATIVO | 7.157 | 6.555 |
| horas_trabajo_semanales | 0.1960 | MODERADO | 10.405 | 16.593 |
| modalidad | 0.1602 | MODERADO | 0.237 | 0.423 |
| semestre_actual | 0.0486 | SIN DRIFT | 4.928 | 4.863 |
| distancia_campus | 0.0346 | SIN DRIFT | 14.658 | 15.427 |
| materias_reprobadas | 0.0273 | SIN DRIFT | 1.249 | 1.403 |
| condicion_beca | 0.0019 | SIN DRIFT | 0.313 | 0.333 |

**Resumen:** 2 variable(s) con drift significativo, 2 con drift moderado.

**Alerta ALERT-DRIFT-01 disparada.** Ver `actividad8/docs/runbook_drift.md` para el procedimiento de respuesta.