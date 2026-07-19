# Actividad 8 — Monitorización, Mantenimiento y Gobernanza Operativa

> Construida sobre la Fase 2 ([`../README.md`](../README.md)): reutiliza el mismo
> modelo, dataset y API ya desplegada en
> **https://fase2-abandono-escolar.onrender.com**. Esta carpeta contiene únicamente
> lo nuevo de la Actividad 8 — monitoreo proactivo, alertas, detección de drift,
> runbooks y respuesta automatizada a incidentes.

## Mapa de entregables

| Entregable (rúbrica) | Dónde verificarlo |
|---|---|
| **Documento técnico** — indicadores, alertas, dashboards, runbooks, drift, respuesta automatizada | [`documento_tecnico.md`](documento_tecnico.md) |
| **Evidencia de implementación** — capturas de MLflow, métricas, alertas, dashboards | [`evidencia/capturas/`](evidencia/capturas/) + [`evidencia/alertas_log.jsonl`](evidencia/alertas_log.jsonl) + [`evidencia/reporte_drift.md`](evidencia/reporte_drift.md) |
| **Simulación de incidentes** — ≥2 incidentes, ejecución de runbooks, resultados | [`incidentes/registro_incidentes.md`](incidentes/registro_incidentes.md) |
| **Código / configuración** — scripts de monitoreo, automatización, config de alertas | [`scripts/`](scripts/) |

## Contenido de `scripts/`

| Archivo | Qué hace |
|---|---|
| `monitor.py` | Monitoreo proactivo contra un despliegue real: health checks, canary checks de calidad del modelo, latencia, logging a MLflow, evaluación de alertas |
| `alertas_config.yaml` | SLOs, error budgets y reglas de alerta priorizadas por severidad (P1-P3) |
| `generar_dataset_drift.py` | Genera un dataset sintético con drift deliberado (simula datos de producción) |
| `detectar_drift.py` | Calcula Population Stability Index (PSI) entre el dataset de entrenamiento y el de producción |
| `rollback.py` | Respuesta automatizada: rollback del modelo vía git, o reentrenamiento con validación de F1 mínimo |

## Uso rápido

```bash
# Desde la raíz del repo, con el venv de la Fase 2 activado
source .venv/bin/activate

# Monitorear la API en producción (5 ciclos, cada 10s)
python -m actividad8.scripts.monitor --ciclos 5 --intervalo-seg 10

# Generar dataset de "producción" y detectar drift
python -m actividad8.scripts.generar_dataset_drift
python -m actividad8.scripts.detectar_drift

# Ver el dashboard de métricas (MLflow UI)
mlflow ui --port 5000
# abrir http://localhost:5000 -> experimento "actividad8_monitoreo_produccion"

# Rollback de emergencia (requiere el hash de un commit bueno conocido)
python -m actividad8.scripts.rollback --modo rollback --commit-bueno <hash> --push
```

## Resumen de lo ejecutado (no solo documentado)

- **2 incidentes simulados de verdad** contra la API en producción (no un entorno de
  prueba paralelo): latencia degradada y modelo degradado. Ambos con alerta
  disparada, runbook ejecutado, y recuperación verificada. Detalle completo con
  timestamps y comandos reales en
  [`incidentes/registro_incidentes.md`](incidentes/registro_incidentes.md).
- **Detección de drift real** sobre un dataset sintético con desplazamiento
  deliberado: detectó correctamente las 4 variables modificadas (2 significativas, 2
  moderadas) sin falsos positivos en las 4 sin cambios.
- **Script de rollback automatizado probado en producción**: restauró el modelo
  degradado en un solo comando durante el incidente 2.
